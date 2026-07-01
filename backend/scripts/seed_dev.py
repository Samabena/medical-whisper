"""Seed de DÉVELOPPEMENT : crée la base, un compte, un formulaire publié et une clé API.

But : pouvoir tester la console live immédiatement (coller la clé API, charger le
formulaire, dialoguer). À lancer depuis `backend/` :

    .venv\\Scripts\\python.exe scripts\\seed_dev.py

Idempotent pour le compte et le formulaire ; émet une NOUVELLE clé API à chaque appel
(les clés ne sont stockées que hachées, on ne peut pas réafficher les anciennes).
"""

from __future__ import annotations

import asyncio
import sys

# Console Windows en cp1252 par défaut : forcer UTF-8 pour les accents et le → final.
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

from app.application.admin.api_keys import CreateApiKey
from app.application.admin.forms import CreateForm, PublishForm, UpdateForm
from app.domain.entities import Account, FormField
from app.domain.errors import ConflictError
from app.domain.value_objects import FieldType, Language
from app.infrastructure.db.engine import get_engine, get_sessionmaker
from app.infrastructure.db.models import Base
from app.infrastructure.db.repositories import (
    SqlAccountRepo,
    SqlApiKeyRepo,
    SqlFormRepo,
)
from app.infrastructure.security.hashing import Sha256KeyHasher

EMAIL = "demo@local"
FORM_ID = "consultation"

# Formulaire de démo (FR) — quelques champs représentatifs pour juger le rendu.
CHAMPS = [
    FormField(name="patient_nom", label="Nom du patient", type=FieldType.STRING, required=True),
    FormField(name="patient_age", label="Âge du patient", type=FieldType.INT, required=True),
    FormField(
        name="motif", label="Motif de consultation", type=FieldType.TEXT, required=True,
        description="Raison principale de la visite",
    ),
    FormField(name="date_consultation", label="Date de consultation", type=FieldType.DATE),
    FormField(
        name="urgence", label="Niveau d'urgence", type=FieldType.ENUM,
        enum_values=["faible", "moyen", "élevé"],
    ),
]

# Formulaire de consultation complet (consultation_v1). Le groupe « constantes » du
# cahier des charges est APLATI en champs racine (le modèle de formulaire est plat) ;
# temperature/poids utilisent le type NUMBER (flottant).
FORM_ID_V1 = "consultation_v1"
CHAMPS_V1 = [
    FormField(name="date_consultation", label="Date de consultation", type=FieldType.DATE, required=True),
    FormField(
        name="motif", label="Motif de consultation", type=FieldType.TEXT, required=True,
        description="Raison principale de la visite",
    ),
    FormField(name="antecedents", label="Antécédents", type=FieldType.TEXT,
              description="Antécédents médicaux du patient"),
    FormField(name="examen_clinique", label="Examen clinique", type=FieldType.TEXT),
    # --- Constantes (groupe aplati) ---
    FormField(name="tension_arterielle", label="Tension artérielle", type=FieldType.STRING,
              description="Tension artérielle (ex. 12/8)"),
    FormField(name="frequence_cardiaque", label="Fréquence cardiaque", type=FieldType.INT,
              description="Fréquence cardiaque en battements par minute"),
    FormField(name="temperature", label="Température", type=FieldType.NUMBER,
              description="Température corporelle en °C (ex. 38.5)"),
    FormField(name="poids", label="Poids", type=FieldType.NUMBER,
              description="Poids du patient en kg (ex. 72.4)"),
    # --- Conclusion ---
    FormField(name="diagnostic", label="Diagnostic", type=FieldType.TEXT, required=True),
    FormField(name="traitement_prescrit", label="Traitement prescrit", type=FieldType.TEXT),
    FormField(name="conduite_a_tenir", label="Conduite à tenir", type=FieldType.TEXT),
    FormField(name="prochain_rdv", label="Prochain rendez-vous", type=FieldType.DATE),
]


async def _seed_form(forms, account_id: int, form_id: str, titre: str, champs) -> None:
    """Crée le formulaire s'il est absent, sinon met à jour ses champs ; puis publie.

    Idempotent : ré-exécuter le seed applique toute modification des champs.
    """
    current = await forms.get(account_id, form_id)
    if current is None:
        try:
            await CreateForm(forms).execute(
                account_id=account_id, form_id=form_id,
                titre=titre, fields=champs, langue=Language.FR,
            )
        except ConflictError:
            pass
        await PublishForm(forms).execute(account_id, form_id)
        print(f"[seed] formulaire publié : {form_id}")
    elif current.fields == champs and current.titre == titre:
        # Déjà à jour : on s'assure seulement qu'il est publié (pas de bump de version).
        await PublishForm(forms).execute(account_id, form_id)
        print(f"[seed] formulaire déjà à jour : {form_id} (v{current.version})")
    else:
        await UpdateForm(forms).execute(
            account_id=account_id, form_id=form_id, titre=titre, fields=champs,
        )
        await PublishForm(forms).execute(account_id, form_id)
        print(f"[seed] formulaire mis à jour + publié : {form_id}")


async def main() -> None:
    engine = get_engine()
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    maker = get_sessionmaker()
    async with maker() as session:
        accounts = SqlAccountRepo(session)
        forms = SqlFormRepo(session)
        keys = SqlApiKeyRepo(session)

        account = await accounts.get_by_email(EMAIL)
        if account is None:
            account = await accounts.add(
                Account(nom="Compte démo", email_contact=EMAIL, langue=Language.FR)
            )
            print(f"[seed] compte créé (id={account.id})")
        else:
            print(f"[seed] compte existant (id={account.id})")

        await _seed_form(forms, account.id, FORM_ID, "Consultation médicale", CHAMPS)
        await _seed_form(
            forms, account.id, FORM_ID_V1, "Consultation médicale (complète)", CHAMPS_V1
        )

        nouvelle = await CreateApiKey(accounts, keys, Sha256KeyHasher()).execute(
            account.id, label="Clé dev"
        )

    print("\n==================== PRÊT À TESTER ====================")
    print(f"  Clé API   : {nouvelle.cle_claire}")
    print(f"  Formulaires: {FORM_ID} (Consultation médicale)")
    print(f"             : {FORM_ID_V1} (Consultation médicale complète)")
    print("  Console   : http://localhost:5173 → Console de test live")
    print("  Admin     : admin@local / admin1234")
    print("=======================================================\n")


if __name__ == "__main__":
    asyncio.run(main())
