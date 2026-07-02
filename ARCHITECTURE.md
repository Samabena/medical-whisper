# ARCHITECTURE — Voice-to-Form (Live Sandwich)

> Document de référence technique. **À lire avant tout ticket.**
> Il fige les principes, les schémas, les contrats (ports, protocole WebSocket) et les cibles
> de latence. En cas de doute pendant un ticket, ce document fait foi ; le `BACKLOG_v3.md`
> décrit *quoi* faire, celui-ci décrit *comment ça tient ensemble*.

---

## 1. Vue d'ensemble

Service **B2B autonome** qui remplit des **formulaires médicaux** à partir d'une **conversation
vocale en français, en temps réel**. Les plateformes clientes l'appellent ; elles n'ont pas à
gérer la voix. Le service écoute, dialogue (pose des questions de clarification), et renvoie un
**formulaire structuré validé**.

**Architecture retenue : « sandwich » live** (STT → agent + extracteur → TTS).
**Écartée : speech-to-speech** (PersonaPlex), car anglais-only — incompatible avec le besoin FR.

Le sandwich a un coût (latence plus élevée, cf. §5) mais garantit le **français de bout en bout**
et une **séparation nette conversation / extraction**.

---

## 2. Schéma des composants

```
┌────────────────────────────────────────────────────────────────────────────┐
│                         PLATEFORME CLIENTE (tierce)                          │
│  Backend client ──(1) POST /v1/integration/sessions (X-API-Key)─────────────▶│
│                 ◀─(2) { session_id, ws_url, token éphémère, form_schema }     │
│  Frontend client ─(3) WSS /v1/live/{session_id}?token=… (audio FR) ──────────▶│
│                 ◀─(4) transcript / form_state / audio agent ─────────────────│
│  Backend client ──(5) GET /v1/integration/sessions/{id}/result ─────────────▶│
└────────────────────────────────────────────────────────────────────────────┘
                                     │
                                     ▼
┌────────────────────────────────────────────────────────────────────────────┐
│                        SERVICE VOICE-TO-FORM (nous)                          │
│                                                                              │
│  interface/                                                                  │
│    api/         REST admin + intégration (jetons, résultats)                 │
│    ws/          endpoint live WebSocket (auth jeton éphémère)                │
│                                                                              │
│  application/   cas d'usage : RunLiveDialogue, StartSession, GetResult…      │
│    ports/       SttStreamPort · TtsPort · LlmPort · FormExtractorPort ·      │
│                 *Repo · EphemeralTokenPort                                    │
│                                                                              │
│  infrastructure/                                                             │
│    stt/         WhisperLiveAdapter ──WS──▶ [srv-team-ia:9300 : WhisperLive]  │
│                 StubSttAdapter (dev)                                          │
│    tts/         PiperAdapter (local, voix FR)                                 │
│    llm/         AgentLlm (rapide) · ExtractorLlm (précis, structuré)         │
│    db/          Postgres (comptes, clés, formulaires, usage)                 │
│    cache/       Redis (sessions live, TTL, rate-limit)                        │
│    security/    argon2, JWT, hachage clés API                                │
│                                                                              │
│  domain/        entités & règles métier, AUCUNE dépendance externe           │
└────────────────────────────────────────────────────────────────────────────┘
```

---

## 3. Le pipeline live (cœur du produit)

Inspiré du pattern async de la doc LangChain voice-agent (producteur-consommateur, événements).

```
  audio client (frames PCM/Opus 16 kHz)
        │
        ▼
  ┌─────────────────────┐   partiels + finaux (+ confiance/mot)
  │  SttStreamPort       │──────────────┬───────────────────────────┐
  │  (WhisperLive)       │              │                           │
  └─────────────────────┘              ▼                           ▼
                            ┌────────────────────┐      ┌────────────────────────┐
            transcript      │  AGENT (LlmPort)    │      │ EXTRACTEUR             │
            FINAL ──────────▶│  rapide             │      │ (FormExtractorPort)    │
                            │  décide la relance, │      │ debounced sur le        │
                            │  confirme, clôt     │      │ transcript courant      │
                            └─────────┬──────────┘      └───────────┬────────────┘
                                      │ texte réponse               │ FormState
                                      ▼                             ▼ {valeur, confiance}
                            ┌────────────────────┐         message "form_state" → client
                            │  TtsPort (Piper)    │
                            │  synthèse par phrase │
                            └─────────┬──────────┘
                                      ▼
                            audio agent (WAV) → client

  Coordination : l'extracteur signale les champs requis encore "manquant" ;
  l'agent relance dessus, un champ à la fois. Quand tous les requis sont
  "confiant" → signal de clôture → message "final".
```

**Chemin bas-latence (LIVE-7.4, cf. §5) greffé sur ce pipeline :**
- **Spéculatif :** sur la **fin de parole** (VAD endpoint), l'agent et l'extracteur démarrent sur le
  meilleur **partiel stable**, sans attendre le final ; le final ré-extrait (fusion idempotente).
- **Backchannel :** un court accusé (« d'accord… ») part **immédiatement** à l'endpoint pour masquer
  la latence de réflexion.
- **TTS pipeliné :** la réponse de l'agent (streamée) passe par un **segmenteur de phrases** qui
  alimente la file TTS phrase par phrase → 1er son plus tôt.
- **Barge-in :** toute reprise de parole pendant que l'agent parle **annule** l'agent + la file TTS.

**Règles de séparation (DRY) :** l'agent et l'extracteur sont dérivés d'une **seule
`FormDefinition`** via `prompt_builder`, qui produit aussi la liste de **hotwords** envoyée au STT.
Modifier un champ du formulaire met à jour les trois sorties sans double saisie.

---

## 4. Protocole WebSocket (contrat client ↔ service)

Endpoint : `WSS /v1/live/{session_id}?token={jwt_éphémère}`.

### 4.1 Authentification
- Le `token` est le **JWT éphémère** émis par `POST /v1/integration/sessions` (TTL ~60 s, usage unique, `aud=session_id`).
- À l'ouverture : vérifier signature, expiration, `aud`, et l'en-tête `Origin` (CORS par compte).
- Échec → fermeture WebSocket code **4401** (non autorisé), sans détail.

### 4.2 Messages **client → serveur**
| Type | Forme | Sens |
|------|-------|------|
| audio | **binaire** (frames PCM s16le 16 kHz mono, ou Opus) | flux micro continu |
| `control` | `{"type":"control","action":"start"\|"stop"}` | bornes de prise de parole (optionnel) |

> **Barge-in :** toute trame audio reçue **pendant que l'agent parle** vaut interruption — le serveur
> annule la sortie agent + la file TTS en cours et renvoie un message `interrupted` (cf. §4.3).
> Réglé par `barge_in`. La fin de parole peut aussi être signalée explicitement (`end_turn`).

### 4.3 Messages **serveur → client**
Tous en **JSON texte**, sauf l'audio agent en **binaire**.
| Type | Charge utile | Quand |
|------|--------------|-------|
| `transcript` | `{type, kind:"partial"\|"final", text, stable?:bool, words?:[{w,conf}]}` | au fil de l'eau ; `stable` = partiel fiable (déclenchement spéculatif) |
| `form_state` | `{type, fields:{name:{valeur,confiance}}, champs_manquants:[…], pret:bool}` | après extraction (debounced) |
| `backchannel` | `{type, text}` (+ audio binaire optionnel) | **immédiatement** à la fin du tour (masque la latence) |
| `agent_text` | `{type, text}` | quand l'agent répond — **streamé** (un message par phrase/chunk) |
| audio agent | **binaire** WAV | synthèse Piper, **par phrase** (1er son plus tôt) |
| `interrupted` | `{type}` | l'agent a été coupé par une reprise de parole (barge-in) |
| `final` | `{type, form_state, raison:"complete"\|"timeout"\|"abandon"}` | fin de session |
| `error` | `{type, erreur, detail}` | toute erreur récupérable |

> Le client n'a jamais besoin de la clé API : seul le jeton éphémère circule côté navigateur.
> Le `form_state` est **idempotent** (état complet à chaque envoi), pas un diff — simplifie le client.

---

## 5. Cibles de latence (honnêtes)

Le sandwich FR n'est **pas** du sub-700ms. On distingue la latence **réelle** (calcul) de la latence
**perçue** (ce que ressent l'utilisateur, qu'on attaque par le backchannel et le chevauchement).
Cibles réalistes, en prod GPU, **avec les leviers ci-dessous activés** :

| Étape | Cible | Note |
|-------|-------|------|
| STT partiel (1er aperçu) | ~1 s | WhisperLive, aperçu non validé |
| STT final (validé) | ~2–3 s | LocalAgreement-2 — **plus sur le chemin critique** (cf. spéculatif) |
| **Accusé perçu (backchannel)** | **~0,2–0,4 s** | court « d'accord… » joué dès la fin de parole |
| Agent (réponse) | ~0,3–1 s | modèle rapide, `max_tokens` borné, prompt caché |
| TTS 1er son (Piper) | ~0,3–0,8 s | **pipeliné par phrase** (1er son sans attendre toute la réponse) |
| **1er audio agent utile** | **~1–1,5 s** | déclenchement spéculatif + TTS pipeliné (était ~3–5 s) |
| `form_state` après énoncé | **< 1,5 s** | extraction debounced, hors chemin critique |
| **Tour complet ressenti** | **~1,5–2,5 s** | énoncé → réponse vocale de l'agent (était ~3–5 s) |

### Stratégies de réduction de latence (LIVE-7.4)

| Levier | Effet | Réglage |
|--------|-------|---------|
| **Déclenchement spéculatif** | L'agent démarre sur la **fin de parole** détectée (VAD endpointing) + le meilleur **partiel stable**, sans attendre le final validé (~2–3 s). Le final **ré-extrait** (fusion idempotente, sans écraser le confiant). | `speculative_trigger`, `vad_silence_ms`, `partial_confidence_min` |
| **TTS pipeliné par phrase** | Tokens agent (streaming) → **segmenteur de phrases** → file TTS : on synthétise/joue la 1ʳᵉ phrase pendant que l'agent génère la suite. Réduit le time-to-first-audio. | `tts_sentence_chunking` |
| **Backchannel / filler** | Court accusé joué **immédiatement** à la fin du tour pour masquer la latence de réflexion (gain de latence **perçue**). | `backchannel`, `backchannel_text` |
| **Barge-in** | La reprise de parole **annule** l'agent + la file TTS en cours → réactivité immédiate. | `barge_in` |
| **Prompt caching + warm + persistant** | Préfixe stable (système + schéma form) caché côté LLM ; modèles préchauffés au `lifespan` ; connexions WhisperLive/Piper établies une fois. | `prompt_cache` |
| **Agent concis** | Réponses courtes, une question à la fois (`max_tokens` borné). | `agent_max_tokens` |

> **STT volontairement conservé en `large-v3`** (pas de `turbo`/`distil`) : la **précision sur le jargon
> médical** prime ; le spéculatif sort le STT du chemin critique sans dégrader la reconnaissance.

**Conséquence de conception :** privilégier le **chevauchement** (l'extraction et le STT final tournent
pendant que l'agent parle), la **synthèse par phrase**, le **backchannel** et un **agent concis**.
Ne jamais promettre une fluidité S2S.

En **dev** (CPU ou stub STT), les cibles ne s'appliquent pas : le stub est déterministe et instantané,
WhisperLive CPU en `small` est plus lent — c'est attendu, le dev valide la logique, pas la latence.

---

## 6. Règle de dépendance (Clean Architecture)

```
interface ──▶ application ──▶ domain
     │             │
     └──▶ infrastructure ──▶ (implémente les ports de application)
```

- **domain** : entités, value objects, règles métier. **N'importe rien** d'externe (ni FastAPI, ni SQLAlchemy, ni WhisperLive). Un test (`test_dependency_rule`) vérifie cette pureté par introspection des imports.
- **application** : cas d'usage + **ports** (Protocols). Ne connaît que `domain` et ses propres ports.
- **infrastructure** : adapters concrets (WhisperLive, Piper, LLM, Postgres, Redis) qui **implémentent** les ports.
- **interface** : FastAPI (REST + WS). Assemble tout via le **composition root** (`deps.py`).
- **Inversion de dépendance** : un cas d'usage reçoit un `SttStreamPort`, jamais `WhisperLiveAdapter` directement. En test, on injecte le stub/un fake.

---

## 7. Contrats des ports (signatures de référence)

> Signatures indicatives — l'implémentation exacte est dans les tickets EPIC 6 / 8.

```python
class SttStreamPort(Protocol):
    async def open(self, language: str, hotwords: list[str]) -> None: ...
    async def send_audio(self, frame: bytes) -> None: ...
    def receive(self) -> AsyncIterator[SttEvent]: ...   # partial(+stable)|final|endpoint + words[conf]
    async def close(self) -> None: ...
    # SttEvent inclut un `endpoint` (fin de parole VAD) et un drapeau `stable` sur les
    # partiels, exploités par le déclenchement spéculatif (cf. §5).

class TtsPort(Protocol):
    async def synthetiser(self, texte: str, voix: str) -> bytes: ...  # WAV, appelé PAR PHRASE

class LlmPort(Protocol):
    def repondre(self, messages: list[Message]) -> AsyncIterator[str]: ...  # agent, STREAMING
    async def extraire(self, prompt: str, schema: type[BaseModel]) -> BaseModel: ...  # extracteur

class FormExtractorPort(Protocol):
    async def update(self, transcript: str, form_def: FormDefinition,
                     partiel: FormState | None) -> FormState: ...

class EphemeralTokenPort(Protocol):
    def mint(self, session_id: str, ttl_s: int) -> str: ...
    def verify(self, token: str, session_id: str) -> bool: ...  # usage unique
```

> **Transition v2 → v3 :** le code part d'un port unique S2S `SpeechAgentPort` (héritage PersonaPlex).
> La migration vers le sandwich sépare `SttStreamPort` + `TtsPort` (tickets EPIC 6). Les **primitives
> bas-latence** déjà livrées sont indépendantes du transport : segmenteur de phrases
> (`application/live/segmenter.py`), contrôleur de tour/barge-in (`application/live/turn_control.py`),
> et les leviers câblés dans l'orchestrateur (`application/live/orchestrator.py`).

---

## 8. Modèle de données (métadonnées uniquement)

```
Account(id, nom, email, langue{en,fr}, persona_prompt, voix_piper, actif, créé_le)
ApiKey(id, account_id, prefixe, hash, actif, créé_le, révoqué_le)
FormDefinition(id, account_id, slug, version, langue?, titre, statut{draft,published})
FormField(id, form_id, name, label, type, required, enum_values[], description)
LiveSession(id, account_id, form_id, statut, créé_le, expire_le)   # éphémère, en Redis
FormState(session_id, fields{name:{valeur,confiance}}, champs_manquants[], pret)  # éphémère
UsageRecord(id, account_id, session_id, nb_tours, durée_audio_s, créé_le)         # agrégé, sans contenu
```

> **Aucune donnée clinique persistée** : ni audio, ni transcript. `FormState` vit en session
> (Redis, TTL court) puis est remis au backend client via `GET …/result`, puis purgé.

---

## 9. Sécurité & conformité (synthèse)

- **Clés API** hachées (préfixe indexé + hash), affichées en clair 1× ; rotation/révocation.
- **Jeton éphémère** pour le WS : TTL court, usage unique, lié au `session_id` — la clé API ne touche jamais le navigateur.
- **Auth admin** : argon2 + JWT (access court + refresh).
- **Edge** : rate-limit (Redis), CORS par compte, en-têtes (HSTS, CSP), validation `Origin` du WS au proxy.
- **TLS/WSS** terminé par Caddy en prod.
- **Données de santé** : non-persistance par défaut ; logs **sans** transcript (⚠️ baisser le log level de WhisperLive, qui peut écrire le texte) ; option de rétention chiffrée TTL court **opt-in** seulement.

---

## 10. Profils de déploiement

| | **dev** | **prod** |
|---|---------|----------|
| STT | stub **ou** WhisperLive en ligne | WhisperLive en ligne (`srv-team-ia:9300`) |
| GPU | non requis (STT distant) | non requis côté app (STT distant) |
| TTS | Piper (local) | Piper (local) |
| LLM | Ollama Cloud (ou mocké en test) | Ollama Cloud / fournisseur |
| TLS | non (http local) | oui (Caddy, WSS) |
| Lancement | `docker compose --profile dev up` | `docker compose --profile prod up` |

Bascule prod = `STT_BACKEND=whisperlive` + `WHISPERLIVE_URL` du serveur en ligne. Le reste du code est identique
(grâce aux ports), ce qui rend la démo dev fidèle au comportement prod, à la latence près.

---

## 11. Ce qui peut évoluer (et ne doit pas être figé en dur)

- **Fournisseur LLM** : derrière `LlmPort` — changeable sans toucher au pipeline.
- **STT** : derrière `SttStreamPort` — on pourrait passer à un autre moteur FR si besoin.
- **TTS** : derrière `TtsPort` — Piper aujourd'hui, **synthétisé par phrase** (pipeliné, cf. §5) ; un TTS à streaming token-audio FR plus tard pourrait encore réduire le 1er son.
- **Store de sessions** : Redis ; l'interface permet d'autres backends.
- **Transport** : WebSocket aujourd'hui ; le pipeline async pourrait alimenter de la téléphonie (SIP/RTP) plus tard.

> Tout choix externe passe par un port. Aucun cas d'usage `application/` ne doit importer
> directement une lib d'infrastructure.