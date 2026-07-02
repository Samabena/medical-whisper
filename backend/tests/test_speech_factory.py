"""MODEL-6.1/6.3 — la factory choisit l'implémentation selon la config (DIP)."""

from __future__ import annotations

from app.infrastructure.config import Settings
from app.infrastructure.speech.factory import build_speech_agent
from app.infrastructure.speech.llm_agent import LlmSpeechAgent
from app.infrastructure.speech.sandwich import SandwichSpeechAgent
from app.infrastructure.speech.stub_agent import StubSpeechAgent
from app.infrastructure.stt.stub import StubSttStream
from app.infrastructure.tts.stub import StubTts


def test_defaut_stub():
    s = Settings(_env_file=None, jwt_secret="x" * 32, admin_password="y")
    assert isinstance(build_speech_agent(s), StubSpeechAgent)


def test_sandwich_si_configure():
    s = Settings(_env_file=None, jwt_secret="x" * 32, admin_password="y", speech_agent="sandwich")
    agent = build_speech_agent(s)
    assert isinstance(agent, SandwichSpeechAgent)
    # Backends dev par défaut : STT stub + TTS stub.
    assert isinstance(agent.stt_stream, StubSttStream)
    assert isinstance(agent.tts, StubTts)


def test_sandwich_bascule_whisperlive_et_piper():
    s = Settings(
        _env_file=None, jwt_secret="x" * 32, admin_password="y",
        speech_agent="sandwich", stt_backend="whisperlive", tts_backend="piper",
        tts_voice_path="/voices/fr.onnx",
    )
    agent = build_speech_agent(s)
    assert isinstance(agent, SandwichSpeechAgent)
    assert type(agent.stt_stream).__name__ == "WhisperLiveStream"
    assert type(agent.tts).__name__ == "PiperTts"


def test_llm_si_configure():
    s = Settings(
        _env_file=None, jwt_secret="x" * 32, admin_password="y",
        speech_agent="llm", ollama_model="gpt-oss:120b-cloud",
    )
    agent = build_speech_agent(s)
    assert isinstance(agent, LlmSpeechAgent)
    assert agent.model == "gpt-oss:120b-cloud"
