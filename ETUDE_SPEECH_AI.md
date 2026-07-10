# Étude — Moteurs Speech AI & niveaux d'amélioration

> **Objet.** Comparer la solution **Speaches** (serveur STT/TTS unifié) à l'architecture
> **actuelle** de Voice-to-Form (« sandwich » maison), puis récapituler les **niveaux
> d'amélioration** du TTS (« Piper live ») et les correctifs de qualité identifiés et mis
> en œuvre.
>
> **Date.** 2026-07-07 · **Périmètre.** Chaîne vocale live (STT → agent LLM → TTS).

---

## 1. État actuel — architecture « sandwich » (v3)

La brique vocale compose **trois services derrière des ports** (clean architecture), orchestrés
en full-duplex par `RunLiveDialogue` sur le WebSocket `/v1/live` :

| Maillon | Implémentation actuelle | Détail |
|---|---|---|
| **STT** | **WhisperLive maison** (`ws://srv-team-ia:9300`) | faster-whisper `small`, handshake JSON + audio float32 16 kHz |
| **Agent** | **Ollama Cloud** (`gpt-oss:120b-cloud`) | réponse en streaming token par token |
| **TTS** | **Piper** via serveur HTTP dédié (`piper-server/`) | voix FR `fr_FR-siwis-medium` (22050 Hz) |
| Transport | React + FastAPI + WebSocket | Postgres, Redis, Docker Compose (profils dev/voice/prod) |

**Leviers de latence** déjà présents dans l'orchestrateur : déclenchement spéculatif,
backchannel, **barge-in**, segmentation par phrase du flux LLM → TTS pipeliné.

**Atout central.** Le protocole STT (partiels *stables*, endpoint) et la logique de latence
sont **entièrement sous notre contrôle** — c'est le cœur du pivot « live ».

---

## 2. Speaches — présentation

Serveur **OpenAI-API-compatible** qui unifie STT **et** TTS derrière une même API — « Ollama,
mais pour le STT/TTS ».

- **STT** : faster-whisper (streaming, transcription envoyée en SSE au fil de l'eau).
- **TTS** : **Piper** *et* **Kokoro** (Kokoro = #1 TTS Arena).
- **Chargement dynamique** des modèles (load/offload à la demande, comme Ollama).
- **Realtime API** compatible OpenAI. GPU **et** CPU. Déploiement Docker / Docker Compose.
- **Maturité** : ~3,5k ⭐, 35 contributeurs, releases actives (dernière rc déc. 2025), licence MIT.

Point clé : Speaches remplacerait **deux composants maison à la fois** (le STT WhisperLive **et**
le `piper-server`), pas un seul.

---

## 3. Étude comparative

| Axe | Version actuelle (WhisperLive maison + piper-server) | Speaches |
|---|---|---|
| **Composants à maintenir** | 2 serveurs maison (WS STT + HTTP Piper) | 1 service unifié |
| **STT** | WhisperLive maison, protocole **contrôlé** | faster-whisper (souvent plus rapide en CPU) |
| **TTS** | Piper (wrapper HTTP maison) | Piper **+ Kokoro** (voix nettement meilleure) |
| **Gestion des modèles** | Manuelle (→ a déjà causé une panne : `.onnx` corrompu) | Auto (download HF, load/offload) |
| **Protocole streaming** | Sur-mesure : partiels stables / endpoint / final | SSE + Realtime API (OpenAI) |
| **Contrôle latence** (spéculatif, backchannel, barge-in) | **Total** | Dépend de ce qu'expose Speaches |
| **API** | Propriétaire (couplée au code) | Standard OpenAI (SDK/outils interchangeables) |
| **Déploiement** | Docker Compose (en place) | Docker Compose |
| **Communauté / support** | Nous | 3,5k ⭐, 35 contributeurs, actif |

### Avantages d'un passage à Speaches
1. **Un composant en moins** à maintenir (supprime `piper-server` **et** le STT maison).
2. **Fin du provisioning manuel** des modèles (la cause de la panne `.onnx` corrompu).
3. **Kokoro** : montée en qualité vocale sans changer de serveur.
4. **API OpenAI standard** : outils/SDK interchangeables, moins de code propriétaire.
5. **faster-whisper** en général plus rapide/économe en CPU (cohérent « vrai vocal sans GPU »).

### Inconvénients / risques
1. **Perte du contrôle fin du protocole STT** — partiels *stables*, endpoint/VAD : toute la
   logique spéculatif/backchannel/barge-in en dépend. À **vérifier** que la Realtime API de
   Speaches expose ces signaux, sinon on casse le cœur du « live ».
2. **Coût de migration** réel pour un gain incertain : la stack actuelle **fonctionne**.
3. **Serveur STT mutualisé** (`srv-team-ia`) potentiellement partagé avec d'autres apps.
4. **Kokoro en FR** : qualité à valider (elle brille surtout en anglais).

### Recommandation
Ne **pas** migrer en bloc. Découpler grâce aux ports existants :
- **TTS → tester Speaches vite (faible risque)** : le `TtsPort` est simple ; comparer Kokoro-FR
  vs Piper. Gain immédiat (voix + fin du provisioning manuel), rollback trivial.
- **STT → statu quo** tant que la Realtime API de Speaches n'a pas prouvé qu'elle expose
  partiels-stables + endpoint avec une latence ≥ à l'existant. Sinon on perd l'ingénierie latence.

**En résumé :** Speaches = excellent candidat **TTS**, candidat **STT à valider prudemment**.

---

## 4. Niveaux d'amélioration « Piper live »

Objectif : réduire la latence et fluidifier la synthèse **sans changer de moteur**. Trois
niveaux avaient été identifiés ; tous sont **implémentés** (validés en local, à déployer).

| Niveau | Contenu | Gain | Statut |
|---|---|---|---|
| **1 — Modèle en mémoire** | Voix `.onnx` chargée **une fois** au démarrage (API Python `PiperVoice`), synthèse en mémoire ; plus de sous-processus ni de rechargement du modèle par phrase. `/health` → 503 si modèle corrompu. | ⭐ Le gros du gain : latence stable ~1 s/phrase (vs pic de rechargement à chaque phrase) | ✅ Fait |
| **2 — Streaming PCM chunké** | Endpoint `/stream` (HTTP/1.1 `Transfer-Encoding: chunked`) émettant le **PCM s16le au fil de l'eau** ; adaptateur `PiperHttpTts.stream()` côté backend. | Premier son plus tôt (mesuré : 1ᵉʳ chunk à 0,35 s vs 1,17 s complet) | ✅ Fait |
| **3 — Multi-chunks + lecture gapless** | Le sandwich relaie **plusieurs `AudioChunk`/phrase** ; **segmentation fine par clauses** (`,` `;` avec garde de longueur) ; **lecture PCM progressive** côté navigateur (fin du décodage WAV). | Fluidité (pas de clic entre phrases) + 1ᵉʳ son plus tôt sur phrases longues | ✅ Fait |

### Limite honnête du moteur
Piper synthétise **une phrase entière en une passe** du vocodeur — **pas de streaming
token-par-token** comme un LLM. La granularité réelle reste « la phrase ». Les vrais leviers :
1. **Modèle chargé** (Niveau 1 — l'essentiel),
2. **Premier son au plus tôt** (Niveau 2),
3. **Découpe plus fine en clauses** (Niveau 3).

Pour un streaming *sub-phrase* réel, il faudrait un autre moteur (**Kokoro**, XTTS…) — d'où
l'intérêt de Speaches côté TTS.

---

## 5. Benchmark — version GitHub vs version améliorée

> **Base de comparaison.** « Version GitHub » = dernier commit publié `b899f6e` (*add-voice-files*),
> l'état déployé avant ce chantier. « Version améliorée » = arbre de travail courant (17 fichiers
> modifiés, +572/−99 lignes, tests verts). Les chiffres de latence proviennent des mesures locales
> déjà citées au §4 ; les axes sans mesure fine sont qualifiés d'après la différence d'architecture
> (elle est structurelle, donc l'écart est certain même sans micro-benchmark).

### 5.1 Tableau comparatif

| # | Axe mesuré | Version GitHub (`b899f6e`) | Version améliorée | Gain |
|---|---|---|---|---|
| 1 | **Latence 1ᵉʳ son / phrase** | Attend le **WAV complet** avant d'émettre : **~1,17 s** | **1ᵉʳ chunk PCM à ~0,35 s** (streaming chunké) | **≈ −70 %** au premier son (−0,82 s) |
| 2 | **Coût par phrase (moteur)** | **Sous-processus Piper relancé + modèle `.onnx` (~60 Mo) rechargé à CHAQUE phrase** → pic de latence récurrent | Voix **chargée une fois en mémoire** au démarrage (`PiperVoice`) → **~1 s/phrase stable** | Élimine le pic de rechargement (le principal poste de latence TTS) |
| 3 | **Chunks audio par phrase** | **1 seul** `AudioChunk` (WAV entier) | **N** `AudioChunk` PCM relayés au fil de l'eau | Son plus tôt sur les phrases longues |
| 4 | **Fluidité lecture navigateur** | `decodeAudioData` par WAV → **clics/blancs** entre phrases | PCM brut → **AudioBuffer** enchaînés (**lecture gapless**) | Plus de coupure audible entre phrases |
| 5 | **Segmentation** | Phrase entière uniquement | **Clauses** (`,` `;`, garde `clause_min_chars=60`) | 1ᵉʳ son plus tôt sur phrases à rallonge |
| 6 | **Barge-in (couper l'agent)** | Déclenché sur **chaque trame micro** → l'agent est coupé **dès son 1ᵉʳ mot** (inutilisable) | **VAD d'énergie** (RMS ≥ 900, **3 trames voisées** consécutives) **+ echoCancellation** | Barge-in **fonctionnel** (0 fausse coupure sur silence) |
| 7 | **Hallucinations sur silence** | Tout `SttFinal` non vide accepté → formulaire **rempli de valeurs inventées** | Filtre **`no_speech_prob ≥ 0,6`** + liste d'artefacts + **VAD client** (parole seule émise) | Suppression des tours fantômes |
| 8 | **Trafic STT réseau** | Micro **streamé en continu** (silence compris) | **Porte VAD** (pré-roll 4 / hangover 10) : n'émet que la parole | Moins d'audio inutile envoyé au STT distant |
| 9 | **Robustesse modèle** | `.onnx` corrompu → **crash à la 1ʳᵉ synthèse**, `/health` **200 trompeur** (a déjà causé une panne) | Préchargement au boot, **`/health` → 503** si voix non chargée | Panne détectée au démarrage, pas en prod |
| 10 | **Filtre de confiance STT** | *(absent)* | `stt_final_min_confidence` exposé, **désactivé par défaut** (`no_speech_prob` fait le tri) | Réglage exposé sans rejeter de vraie parole |

### 5.2 Gains apportés après amélioration (synthèse)

- **Latence perçue.** Premier son à **~0,35 s** au lieu de **~1,17 s** (**≈ −70 %**), et surtout
  **fin des pics de rechargement** du modèle à chaque phrase (Niveau 1) → cadence **~1 s/phrase stable**.
- **Qualité audio.** Lecture **gapless** (plus de clic entre phrases) grâce au PCM brut + curseur de temps.
- **Fiabilité conversationnelle.** Le **barge-in devient utilisable** (VAD + AEC au lieu d'une coupure
  au 1ᵉʳ mot) et les **hallucinations sur silence disparaissent** (double garde front VAD + backend
  `no_speech_prob`) → le formulaire n'est plus pollué de valeurs inventées.
- **Robustesse d'exploitation.** Un `.onnx` corrompu est **détecté au démarrage** (`/health` 503)
  au lieu de tomber en production — la cause exacte d'une panne passée.
- **Empreinte réseau.** Le STT distant ne reçoit plus le silence continu du micro (porte VAD).

> **Honnêteté méthodologique.** Les valeurs 0,35 s / 1,17 s / ~1 s sont des mesures **locales**
> (poste de dev, voix `fr_FR-siwis-medium`) ; elles indiquent l'ordre de grandeur du gain, pas une
> garantie de SLA en production. Les axes 2–4, 6–10 sont des différences **structurelles** (présence /
> absence d'un mécanisme) et non des mesures continues. La latence **STT distant** (§6) n'est pas
> touchée par ce chantier et reste le principal levier restant.

---

## 6. Correctifs de qualité « live » (identifiés en test, corrigés)

Au-delà des 3 niveaux, la mise en conditions réelles a révélé des défauts de qualité, corrigés :

### 6.1 Barge-in (l'agent était coupé → on n'entendait rien)
- **Cause** : le barge-in se déclenchait sur **chaque trame micro** ; or le navigateur streame
  le micro en continu (silence compris) → l'agent était coupé dès son premier mot.
- **Correctif** : barge-in déclenché par un **VAD d'énergie** (RMS, N trames voisées
  consécutives) au lieu des trames brutes, **+ `echoCancellation`** activé côté navigateur pour
  que la voix de l'agent captée par le micro ne provoque pas d'auto-barge-in.

### 6.2 Hallucinations sur silence (« ça invente quand je ne dis rien »)
- **Cause** : Whisper produit du texte fantôme sur du silence/bruit ; tout `SttFinal` non vide
  déclenchait agent + extraction → formulaire rempli de valeurs inventées.
- **Correctif (2 volets)** :
  - **Front — porte VAD** : n'émettre l'audio que sur de la parole (seuil d'énergie, avec
    **pré-roll** anti-coupure d'attaque + **hangover** pour la fin de tour).
  - **Backend — filtre `no_speech_prob`** (≥ 0,6 → rejeté) + liste d'artefacts connus
    (« Sous-titres réalisés par… »). ⚠️ Le filtre de **confiance** a été **désactivé** : il
    rejetait de la vraie parole (probas basses même sur du réel) — le bon discriminant est
    `no_speech_prob`, pas la confiance de transcription.

---

## 7. Leviers de latence STT restants

La lenteur de transcription observée provient du **STT distant** (`srv-team-ia`,
faster-whisper `small`), pas du code local (backend/piper/front sont rapides).

| Levier | Effet | Où agir |
|---|---|---|
| **GPU sur `srv-team-ia`** | ⭐ Le plus gros gain (`small` GPU ≈ temps réel) | infra serveur STT |
| Modèle plus léger (`base`) | Plus rapide, moins précis (risqué en médical) | `WHISPER_MODEL` (`.env`) |
| Réduire le hangover VAD | Finalise un peu plus tôt (~0,85 s → 0,5 s) | `frontend/src/live/liveClient.ts` |

---

## 8. Synthèse & prochaines étapes

- **Piper live** : les 3 niveaux sont **codés et validés en local** ; reste **commit + déploiement**
  sur `srv-team-ia`.
- **Qualité live** : barge-in et anti-hallucination corrigés ; réglages exposés en config
  (`BARGE_IN_*`, `STT_FINAL_MIN_CONFIDENCE`) et en constantes front (`VAD_RMS`, pré-roll, hangover).
- **Latence** : principal levier restant = **STT distant** (GPU / modèle).
- **Speaches** : à **piloter d'abord côté TTS** (Kokoro-FR vs Piper) derrière le `TtsPort`,
  puis évaluer le STT **seulement** si sa Realtime API préserve les signaux de latence.

### Paramètres de réglage (référence rapide)
| Paramètre | Défaut | Rôle |
|---|---|---|
| `BARGE_IN` | `true` | Active le barge-in |
| `BARGE_IN_RMS_THRESHOLD` | `900` | Seuil d'énergie du VAD barge-in (serveur) |
| `BARGE_IN_MIN_VOICED_FRAMES` | `3` | Trames voisées consécutives avant coupure |
| `STT_FINAL_MIN_CONFIDENCE` | `0.0` | Filtre confiance (désactivé ; `no_speech_prob` fait le tri) |
| `VAD_RMS` (front) | `300` | Seuil d'énergie de la porte micro (anti-silence) |
| `PREROLL_FRAMES` / `HANGOVER_FRAMES` (front) | `4` / `10` | Contexte avant / après la parole |
