from __future__ import annotations

from eset_incident_ai.api.dependencies import _get_llm_gateway
from eset_incident_ai.infrastructure.llm.local_gateway import LocalAnalysisGateway
from eset_incident_ai.infrastructure.llm.ollama_gateway import OllamaGateway
from eset_incident_ai.settings.config import Settings


def _settings(**overrides: object) -> Settings:
    defaults: dict[str, object] = {
        "sanitizer_hmac_secret": "test-secret",
        "database_url": "postgresql+psycopg://user:pass@localhost:5432/db",
    }
    defaults.update(overrides)
    defaults["_env_file"] = None
    return Settings(**defaults)  # type: ignore[arg-type]


def test_ollama_selected_when_provider_and_model_present() -> None:
    settings = _settings(llm_provider="ollama", ollama_model="qwen-test")

    assert isinstance(_get_llm_gateway(settings), OllamaGateway)


def test_local_selected_when_ollama_model_missing() -> None:
    settings = _settings(llm_provider="ollama", ollama_model="")

    assert isinstance(_get_llm_gateway(settings), LocalAnalysisGateway)


def test_local_selected_when_provider_is_not_ollama() -> None:
    settings = _settings(llm_provider="openai", ollama_model="qwen-test")

    assert isinstance(_get_llm_gateway(settings), LocalAnalysisGateway)
