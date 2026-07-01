# Voice-to-Form Live — Note de synthèse projet

*Document de présentation à destination de la direction — juin 2026*

---

## 1. En une phrase

**Voice-to-Form Live** est un service qui permet à un médecin de **remplir un dossier
médical en parlant naturellement**, par un dialogue vocal en temps réel : il dicte, un
assistant vocal lui pose les questions manquantes, et le formulaire se remplit tout seul.

## 2. Le problème adressé

La saisie de dossiers médicaux est chronophage et détourne le soignant du patient.
Notre service supprime la saisie manuelle : le praticien parle, le formulaire se
structure automatiquement, avec un dialogue qui réclame les informations obligatoires
manquantes. Gain de temps, moins d'erreurs, meilleure expérience pour le soignant.

## 3. Le modèle économique (B2B)

Nous ne fournissons pas d'application au médecin final : nous fournissons une **brique
technique (API)** que les éditeurs de logiciels médicaux **intègrent dans leur propre
application**. Chaque client (application) dispose d'un compte, de clés d'accès, et de
ses propres formulaires. L'intégration est conçue pour être réalisable **en moins de
30 minutes** côté client.

## 4. Ce qui a changé (évolution majeure)

La première version fonctionnait « par tours » (le médecin envoyait un enregistrement,
le système répondait). Nous avons **pivoté vers un mode « live » conversationnel** beaucoup
plus naturel, propulsé par un modèle d'IA vocale de pointe (**NVIDIA PersonaPlex**) :
l'assistant **écoute et parle en même temps**, gère les interruptions, avec un temps de
réaction d'environ **0,17 seconde** — proche d'une conversation humaine.

## 5. Ce qui a été livré

L'intégralité du périmètre prévu (12 lots de travail) est **développée et testée** :

| Domaine | Livré |
|--------|-------|
| **Portail d'administration** (web) | Gestion des comptes clients, des clés d'accès, **constructeur de formulaires** sur-mesure, choix de la **langue (français / anglais) par compte**, configuration de la voix et du ton de l'assistant |
| **Dialogue vocal temps réel** | Conversation full-duplex, remplissage du formulaire en direct, clôture automatique quand les champs obligatoires sont complets |
| **Intégration client** | API sécurisée + kit d'intégration (SDK) + documentation |
| **Sécurité** | Mots de passe chiffrés, accès par jetons, limitation de débit, cloisonnement par client |
| **Conformité données de santé** | **Aucun enregistrement audio ni transcription n'est conservé** ; seules des métadonnées (comptes, usage) sont stockées ; le formulaire final est purgé après un court délai |
| **Supervision** | Journaux et métriques (latence, volumétrie) sans donnée clinique |
| **Déploiement** | Infrastructure conteneurisée (Docker), prête pour la production |

**Qualité** : 83 tests automatisés au vert sur le cœur du service, interface web qui
compile sans erreur, et **l'ensemble de la chaîne a été démontré de bout en bout** sur un
environnement de test (création d'un compte → formulaire → session vocale → remplissage).

## 6. Comment ça marche (vue simplifiée)

```
Le médecin parle
      │
      ▼
Assistant vocal IA (PersonaPlex)  ──►  mène la conversation, pose les questions
      │
      ▼
Moteur d'extraction (IA texte)    ──►  remplit le formulaire en direct, champ par champ
      │
      ▼
Formulaire structuré renvoyé à l'application cliente
```

L'application du client ouvre une connexion temps réel sécurisée ; **la clé d'accès reste
toujours sur son serveur** (jamais exposée), via un système de jeton à usage unique.

## 7. Choix technologiques (et pourquoi)

- **Architecture « propre » et modulaire** : chaque brique (modèle vocal, extraction,
  base de données) est interchangeable. Concrètement, **nous avons pu développer et
  tester sans matériel GPU coûteux**, en remplaçant le modèle réel par un simulateur ;
  le passage en production se fait par un simple changement de configuration.
- **Modèle d'extraction auto-hébergeable (Ollama)** : les données de santé ne sont pas
  envoyées à un tiers — argument fort de confidentialité.
- **Français et anglais** pris en charge dès le départ (clients anglophones visés).

## 8. Ce qu'il reste avant la mise en production

Le service est complet côté logiciel. Les éléments restants relèvent de
**l'infrastructure et de l'intégration matérielle** :

1. **Serveur d'inférence GPU** : le modèle PersonaPlex nécessite une carte graphique
   professionnelle (NVIDIA A100/H100). À provisionner (location cloud ou serveur dédié).
2. **Branchement du modèle vocal réel** : finaliser la connexion au serveur PersonaPlex
   officiel (le format d'échange exact reste à confirmer auprès du fournisseur).
3. **Recette visuelle** de l'interface d'administration par un utilisateur.

> En environnement de développement (sans GPU), tout fonctionne avec un simulateur ; la
> reconnaissance vocale « réelle » et la voix de synthèse n'apparaissent qu'avec le GPU.

## 9. Implications & prochaines étapes proposées

- **Court terme** : valider le budget/fournisseur GPU et obtenir l'accès au serveur
  d'inférence PersonaPlex.
- **Moyen terme** : déploiement d'un environnement de pré-production avec GPU, puis
  recette avec un client pilote.
- **À noter** : le principal poste de coût récurrent sera l'**infrastructure GPU** (le
  reste — base de données, API, hébergement web — est léger).

---

*Synthèse rédigée pour la direction. Documentation technique détaillée disponible :
architecture, runbook d'exploitation, guide d'intégration client.*
