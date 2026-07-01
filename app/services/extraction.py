"""Service d'extraction des données du formulaire via LLM (structured output).

Stratégie robuste : on demande au LLM d'extraire des **valeurs plates** (une valeur
par champ, ou null si l'information est absente) — ce que les modèles produisent de
façon fiable — puis on **dérive en code** la structure ``{valeur, confiance}`` exigée
par les schémas de formulaire :
- valeur présente  → ``confiance = "confiant"`` ;
- valeur absente   → on conserve le défaut du formulaire (souvent ``manquant``).

Ceci évite l'échec observé où le modèle renvoyait des valeurs plates
(``"diagnostic": "migraine"``) là où le schéma attendait un objet ``Champ`` imbriqué,
ce qui faisait planter le parsing structuré.
"""

from __future__ import annotations

import logging
import typing
from typing import Optional, Type, TypeVar

from pydantic import BaseModel, Field, create_model

from app.schemas.forms import Champ
from app.services.llm import get_llm  # noqa: F401 — importé pour être mockable

logger = logging.getLogger(__name__)

M = TypeVar("M", bound=BaseModel)

# Descriptions FR par champ : exposées au LLM dans le schéma structuré pour qu'il
# relie correctement le texte au bon champ (sans description, gpt-oss ne mappe pas
# « le nom de famille est Dupont » au champ littéral `nom_patient`).
_DESCRIPTIONS: dict[str, str] = {
    "nom_patient": "Nom de famille du patient",
    "prenom_patient": "Prénom du patient",
    "date_naissance": "Date de naissance du patient",
    "date_consultation": "Date de la consultation",
    "motif": "Motif de la consultation",
    "antecedents": "Antécédents médicaux du patient",
    "allergies": "Allergies connues du patient",
    "traitement_en_cours": "Traitement médical en cours",
    "traitements_en_cours": "Traitements médicaux en cours",
    "diagnostic": "Diagnostic posé",
    "ordonnance": "Ordonnance / prescription",
    "date_intervention": "Date de l'intervention chirurgicale",
    "type_intervention": "Type d'intervention chirurgicale réalisée",
    "chirurgien": "Nom du chirurgien",
    "type_anesthesie": "Type d'anesthésie utilisé",
    "duree_minutes": "Durée de l'intervention en minutes",
    "saignement": "Niveau de saignement",
    "complications": "Complications survenues",
    "notes_postoperatoires": "Notes post-opératoires",
    "sexe": "Sexe du patient",
    "adresse": "Adresse du patient",
    "telephone": "Numéro de téléphone du patient",
    "medecin_traitant": "Nom du médecin traitant",
    "groupe_sanguin": "Groupe sanguin du patient",
}


def _description(nom: str) -> str:
    return _DESCRIPTIONS.get(nom, nom.replace("_", " "))


class ExtractionError(ValueError):
    """Échec d'extraction (LLM injoignable, parsing impossible, etc.).

    Sous-classe de ``ValueError`` (rétro-compatibilité) ; le routeur la traduit en
    HTTP 503 ``service_indisponible`` plutôt que de laisser remonter un 500.
    """


_PROMPT = (
    "Tu es un outil de transcription documentaire médicale, utilisé par un soignant "
    "autorisé pour remplir un dossier patient à partir de sa propre dictée. Ton rôle "
    "est de RECOPIER fidèlement dans le formulaire chaque information énoncée — y "
    "compris l'identité du patient (nom, prénom) qui est une donnée administrative "
    "normale et attendue dans ce contexte. N'omets jamais un nom ou un prénom "
    "explicitement dicté.\n\n"
    "Pour chaque champ du schéma, reporte la valeur exactement telle qu'énoncée. "
    "Si — et seulement si — une information n'est pas mentionnée dans le texte, "
    "laisse ce champ à null (n'invente rien).\n\n"
    "Texte dicté : {texte}"
)

# Cache des modèles « plats » dérivés (un par modèle de formulaire).
_flat_models: dict[type, type[BaseModel]] = {}


def _modele_plat(form_model: Type[BaseModel]) -> type[BaseModel]:
    """Construit (et met en cache) un modèle où chaque champ est ``Optional[type_interne]``.

    Le type interne est extrait de l'annotation ``Champ[X]`` (ex. ``str``, ``int``,
    un Enum) afin que le schéma structuré expose au LLM le bon typage / les valeurs
    autorisées, sans le sous-objet ``confiance`` (dérivé côté code).
    """
    if form_model in _flat_models:
        return _flat_models[form_model]
    champs: dict[str, tuple] = {}
    for nom, info in form_model.model_fields.items():
        args = typing.get_args(info.annotation)  # Champ[X] -> (X,)
        interne = args[0] if args else str
        champs[nom] = (Optional[interne], Field(default=None, description=_description(nom)))
    plat = create_model(f"{form_model.__name__}Plat", **champs)
    _flat_models[form_model] = plat
    return plat


def _valeur_brute(brut: object, nom: str):
    """Lit un champ de l'objet d'extraction, qu'il soit un modèle ou un dict."""
    if isinstance(brut, dict):
        return brut.get(nom)
    return getattr(brut, nom, None)


def _vers_formulaire(form_model: Type[M], brut: object) -> M:
    """Reconstruit une instance du formulaire à partir de l'extraction brute.

    Gère deux formes d'entrée :
    - **plate** (réelle) : valeurs scalaires → ``{valeur, confiance:"confiant"}`` ;
    - **imbriquée** (``Champ``/dict avec ``confiance``) : reprise telle quelle
      (rétro-compatibilité avec d'éventuelles sorties imbriquées et les tests).
    Les champs non extraits conservent le défaut du formulaire.
    """
    donnees = form_model().model_dump()
    for nom in form_model.model_fields:
        v = _valeur_brute(brut, nom)
        if v is None:
            continue  # garde le défaut du formulaire
        if isinstance(v, Champ):
            donnees[nom] = v.model_dump()
            continue
        if isinstance(v, dict) and "confiance" in v:
            donnees[nom] = v
            continue
        if isinstance(v, str) and not v.strip():
            continue  # chaîne vide = absent
        donnees[nom] = {"valeur": v, "confiance": "confiant"}
    return form_model.model_validate(donnees)


def _fusionner(partiel: M, nouveau: M) -> M:
    """Fusionne deux instances : les champs 'confiant' du partiel sont conservés."""
    donnees_partiel = partiel.model_dump()
    donnees_nouveau = nouveau.model_dump()
    resultat = {}

    for champ, valeur_partiel in donnees_partiel.items():
        valeur_nouveau = donnees_nouveau.get(champ, valeur_partiel)
        if isinstance(valeur_partiel, dict) and valeur_partiel.get("confiance") == "confiant":
            resultat[champ] = valeur_partiel
        else:
            resultat[champ] = valeur_nouveau

    return type(partiel).model_validate(resultat)


def extraire(texte: str, form_id: str, formulaire_partiel: BaseModel | None = None) -> BaseModel:
    """Extrait les informations du texte et retourne une instance du formulaire.

    Lève ``ExtractionError`` (sous-classe de ``ValueError``) si l'extraction échoue
    après 2 tentatives — à traiter en 503 côté routeur.
    """
    from app.catalog.forms_catalog import get_form_model
    form_model = get_form_model(form_id)

    llm = get_llm(temperature=0.0)
    chain = llm.with_structured_output(_modele_plat(form_model))
    prompt = _PROMPT.format(texte=texte)

    derniere_erreur: Exception | None = None
    for tentative in range(2):
        try:
            brut = chain.invoke(prompt)
            nouveau = _vers_formulaire(form_model, brut)
            if formulaire_partiel is not None:
                return _fusionner(formulaire_partiel, nouveau)
            return nouveau
        except Exception as exc:
            derniere_erreur = exc
            logger.warning("Extraction tentative %d échouée : %s", tentative + 1, exc)

    raise ExtractionError(f"Extraction échouée après 2 tentatives : {derniere_erreur}")
