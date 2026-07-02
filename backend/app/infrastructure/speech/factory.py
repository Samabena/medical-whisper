"""Sélection de l'agent vocal selon la configuration.

C'est le point unique où l'on choisit l'implémentation : tout le reste de l'app ne
manipule que le port `SpeechAgentPort`. Architecture cible v3 = **sandwich**
(`SPEECH_AGENT=sandwich`, composant STT + agent LLM + TTS).
"""

from __future__ import annotations

from app.application.ports.speech_agent import SpeechAgentPort
from app.domain.value_objects import Language
from app.infrastructure.config import Settings


def _build_sandwich(settings: Settings) -> SpeechAgentPort:
    """Compose le sandwich v3 : STT (stt_backend) + agent (agent_backend) + TTS (tts_backend)."""
    from app.infrastructure.speech.reply import OllamaStreamingReply, ReplyProvider, ScriptedReply
    from app.infrastructure.speech.sandwich import SandwichSpeechAgent
    from app.infrastructure.stt.factory import build_stt_stream
    from app.infrastructure.tts.factory import build_tts

    def reply_factory(persona: str, language: Language) -> ReplyProvider:
        if settings.agent_backend == "ollama":
            return OllamaStreamingReply(
                host=settings.ollama_host,
                model=settings.llm_agent_model or settings.ollama_model,
                persona=persona,
                language=language,
                api_key=settings.ollama_api_key or None,
                max_tokens=settings.agent_max_tokens,
            )
        return ScriptedReply()

    return SandwichSpeechAgent(
        stt_stream=build_stt_stream(settings),
        tts=build_tts(settings),
        reply_factory=reply_factory,
    )


def build_speech_agent(settings: Settings) -> SpeechAgentPort:
    if settings.speech_agent == "sandwich":
        return _build_sandwich(settings)

    if settings.speech_agent == "llm":
        from app.infrastructure.speech.llm_agent import LlmSpeechAgent

        return LlmSpeechAgent(
            host=settings.ollama_host,
            model=settings.ollama_model,
            api_key=settings.ollama_api_key or None,
        )

    from app.infrastructure.speech.stub_agent import StubSpeechAgent

    return StubSpeechAgent()
