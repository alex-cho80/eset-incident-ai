from eset_incident_ai.api.dependencies import (
    get_analyze_incident,
    get_check_readiness,
    get_collect_and_notify_detections,
    get_collect_and_notify_incidents,
    get_list_collection_runs,
    get_list_pending_approvals,
    get_review_pending_approval,
    get_settings,
)
from eset_incident_ai.application.use_cases.analyze_incident import AnalyzeIncident
from eset_incident_ai.application.use_cases.check_readiness import CheckReadiness
from eset_incident_ai.application.use_cases.collect_and_notify_detections import (
    CollectAndNotifyDetections,
)
from eset_incident_ai.application.use_cases.collect_and_notify_incidents import (
    CollectAndNotifyIncidents,
)
from eset_incident_ai.application.use_cases.list_collection_runs import ListCollectionRuns
from eset_incident_ai.application.use_cases.list_pending_approvals import ListPendingApprovals
from eset_incident_ai.application.use_cases.review_pending_approval import ReviewPendingApproval
from eset_incident_ai.infrastructure.llm.local_gateway import LocalAnalysisGateway


def test_get_collect_and_notify_incidents_uses_settings(monkeypatch) -> None:
    get_settings.cache_clear()
    monkeypatch.setenv("SANITIZER_HMAC_SECRET", "test-secret")
    monkeypatch.setenv("DISCORD_WEBHOOK_URL", "https://example.invalid/webhook")
    monkeypatch.setenv("ESET_ACCESS_TOKEN", "token-value")
    monkeypatch.setenv("DATABASE_URL", "postgresql+psycopg://user:pass@localhost:5432/db")

    use_case = get_collect_and_notify_incidents()

    assert isinstance(use_case, CollectAndNotifyIncidents)
    get_settings.cache_clear()


def test_get_collect_and_notify_detections_sends_without_analysis(monkeypatch) -> None:
    get_settings.cache_clear()
    monkeypatch.setenv("SANITIZER_HMAC_SECRET", "test-secret")
    monkeypatch.setenv("DISCORD_WEBHOOK_URL", "https://example.invalid/webhook")
    monkeypatch.setenv("ESET_ACCESS_TOKEN", "token-value")
    monkeypatch.setenv("DATABASE_URL", "postgresql+psycopg://user:pass@localhost:5432/db")

    use_case = get_collect_and_notify_detections()

    assert isinstance(use_case, CollectAndNotifyDetections)
    assert use_case._analyzer is None  # noqa: SLF001
    get_settings.cache_clear()


def test_get_check_readiness_uses_settings(monkeypatch) -> None:
    get_settings.cache_clear()
    monkeypatch.setenv("DATABASE_URL", "postgresql+psycopg://user:pass@localhost:5432/db")
    monkeypatch.setenv("REDIS_URL", "redis://localhost:6379/0")

    use_case = get_check_readiness()

    assert isinstance(use_case, CheckReadiness)
    get_settings.cache_clear()


def test_get_analyze_incident_uses_settings(monkeypatch) -> None:
    get_settings.cache_clear()
    monkeypatch.setenv("DATABASE_URL", "postgresql+psycopg://user:pass@localhost:5432/db")

    use_case = get_analyze_incident()

    assert isinstance(use_case, AnalyzeIncident)
    get_settings.cache_clear()


def test_public_factories_send_without_llm_analysis(monkeypatch) -> None:
    get_settings.cache_clear()
    monkeypatch.setenv("SANITIZER_HMAC_SECRET", "test-secret")
    monkeypatch.setenv("DISCORD_WEBHOOK_URL", "https://example.invalid/webhook")
    monkeypatch.setenv("ESET_ACCESS_TOKEN", "token-value")
    monkeypatch.setenv("DATABASE_URL", "postgresql+psycopg://user:pass@localhost:5432/db")

    analyze = get_analyze_incident()
    incident_collection = get_collect_and_notify_incidents()
    detection_collection = get_collect_and_notify_detections()

    assert isinstance(analyze._llm_gateway, LocalAnalysisGateway)  # noqa: SLF001
    assert incident_collection._analyzer is None  # noqa: SLF001
    assert detection_collection._analyzer is None  # noqa: SLF001
    get_settings.cache_clear()


def test_get_list_pending_approvals_uses_settings(monkeypatch) -> None:
    get_settings.cache_clear()
    monkeypatch.setenv("SANITIZER_HMAC_SECRET", "test-secret")
    monkeypatch.setenv("DATABASE_URL", "postgresql+psycopg://user:pass@localhost:5432/db")

    use_case = get_list_pending_approvals()

    assert isinstance(use_case, ListPendingApprovals)
    get_settings.cache_clear()


def test_get_review_pending_approval_uses_settings(monkeypatch) -> None:
    get_settings.cache_clear()
    monkeypatch.setenv("SANITIZER_HMAC_SECRET", "test-secret")
    monkeypatch.setenv("DISCORD_WEBHOOK_URL", "https://example.invalid/webhook")
    monkeypatch.setenv("DATABASE_URL", "postgresql+psycopg://user:pass@localhost:5432/db")

    use_case = get_review_pending_approval()

    assert isinstance(use_case, ReviewPendingApproval)
    get_settings.cache_clear()


def test_get_list_collection_runs_uses_settings(monkeypatch) -> None:
    get_settings.cache_clear()
    monkeypatch.setenv("DATABASE_URL", "postgresql+psycopg://user:pass@localhost:5432/db")

    use_case = get_list_collection_runs()

    assert isinstance(use_case, ListCollectionRuns)
    get_settings.cache_clear()
