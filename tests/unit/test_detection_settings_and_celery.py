from __future__ import annotations

from eset_incident_ai.infrastructure.queue.celery_app import celery_app
from eset_incident_ai.settings.config import Settings


def test_detection_settings_defaults_match_spec() -> None:
    settings = Settings(sanitizer_hmac_secret="test-secret", _env_file=None)  # noqa: S106

    assert settings.detection_notify_limit == 500
    assert settings.detection_max_pages_per_run == 1000
    assert settings.detection_backfill_window_days == 30
    assert settings.detection_notify_cron_interval_minutes == 60
    assert settings.eset_detection_page_size == 1000


def test_detection_celery_schedule_uses_configured_cron_interval() -> None:
    assert celery_app is not None
    schedule = celery_app.conf.beat_schedule["periodic-eset-detection-notification"]

    assert schedule["task"] == "eset_incident_ai.collect_and_notify_detections"
    assert str(schedule["schedule"]._orig_minute) == "*/60"  # noqa: SLF001
