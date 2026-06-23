from __future__ import annotations

from eset_incident_ai.api.dependencies import _get_llm_gateway
from eset_incident_ai.infrastructure.llm.anthropic_gateway import AnthropicGateway
from eset_incident_ai.infrastructure.llm.local_gateway import LocalAnalysisGateway
from eset_incident_ai.settings.config import Settings


def _settings(**overrides: object) -> Settings:
    defaults: dict[str, object] = {
        "sanitizer_hmac_secret": "test-secret",
        "database_url": "postgresql+psycopg://user:pass@localhost:5432/db",
    }
    defaults.update(overrides)
    return Settings(**defaults)  # type: ignore[arg-type]


def test_anthropic_selected_when_provider_key_and_model_present() -> None:
    settings = _settings(
        llm_provider="anthropic", anthropic_api_key="sk-test", anthropic_model="claude-test"
    )

    assert isinstance(_get_llm_gateway(settings), AnthropicGateway)


def test_local_selected_when_api_key_missing() -> None:
    settings = _settings(
        llm_provider="anthropic", anthropic_api_key="", anthropic_model="claude-test"
    )

    assert isinstance(_get_llm_gateway(settings), LocalAnalysisGateway)


def test_local_selected_when_model_missing() -> None:
    settings = _settings(llm_provider="anthropic", anthropic_api_key="sk-test", anthropic_model="")

    assert isinstance(_get_llm_gateway(settings), LocalAnalysisGateway)


def test_local_selected_when_provider_is_not_anthropic() -> None:
    settings = _settings(
        llm_provider="openai", anthropic_api_key="sk-test", anthropic_model="claude-test"
    )

    assert isinstance(_get_llm_gateway(settings), LocalAnalysisGateway)
