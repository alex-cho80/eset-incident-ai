from __future__ import annotations

from functools import lru_cache

from eset_incident_ai.application.ports.notifier import Notifier
from eset_incident_ai.application.use_cases.analyze_incident import AnalyzeIncident
from eset_incident_ai.application.use_cases.check_readiness import CheckReadiness
from eset_incident_ai.application.use_cases.collect_and_notify_incidents import (
    CollectAndNotifyIncidents,
)
from eset_incident_ai.application.use_cases.list_collection_runs import ListCollectionRuns
from eset_incident_ai.application.use_cases.list_pending_approvals import ListPendingApprovals
from eset_incident_ai.application.use_cases.review_pending_approval import ReviewPendingApproval
from eset_incident_ai.application.use_cases.search_knowledge import SearchKnowledge
from eset_incident_ai.infrastructure.discord.incident_notification_builder import (
    SanitizedIncidentNotificationBuilder,
)
from eset_incident_ai.infrastructure.discord.webhook_client import DiscordWebhookClient
from eset_incident_ai.infrastructure.eset.auth_client import EsetAuthClient
from eset_incident_ai.infrastructure.eset.incident_client import EsetIncidentClient
from eset_incident_ai.infrastructure.llm.local_gateway import LocalAnalysisGateway
from eset_incident_ai.infrastructure.observability.readiness import ServiceReadinessProbe
from eset_incident_ai.infrastructure.persistence.approval_repository import (
    PostgresApprovalRepository,
)
from eset_incident_ai.infrastructure.persistence.collection_run_repository import (
    PostgresCollectionRunRepository,
)
from eset_incident_ai.infrastructure.persistence.notification_repository import (
    PostgresNotificationRepository,
)
from eset_incident_ai.infrastructure.persistence.vector_repository import PgVectorRepository
from eset_incident_ai.security.sanitizer import Sanitizer
from eset_incident_ai.settings.config import Settings


@lru_cache
def get_settings() -> Settings:
    return Settings()


class DisabledNotifier:
    async def send(self, payload: dict[str, object]) -> None:
        _ = payload


def get_check_readiness() -> CheckReadiness:
    settings = get_settings()
    return CheckReadiness(
        ServiceReadinessProbe(
            database_url=settings.database_url,
            redis_url=settings.redis_url,
        )
    )


def get_analyze_incident() -> AnalyzeIncident:
    settings = get_settings()
    return AnalyzeIncident(
        vector_repository=PgVectorRepository(settings.database_url),
        llm_gateway=LocalAnalysisGateway(),
    )


def get_collect_and_notify_incidents() -> CollectAndNotifyIncidents:
    settings = get_settings()
    sanitizer = Sanitizer(settings.sanitizer_hmac_secret)
    auth_client = EsetAuthClient(
        auth_url=settings.eset_auth_url,
        username=settings.eset_username,
        password=settings.eset_password,
        client_id=settings.eset_client_id,
        client_secret=settings.eset_client_secret,
        access_token=settings.eset_access_token,
        access_token_expires_in=settings.eset_access_token_expires_in,
    )
    notifier: Notifier
    if settings.discord_enabled:
        notifier = DiscordWebhookClient(webhook_url=settings.discord_webhook_url)
    else:
        notifier = DisabledNotifier()

    return CollectAndNotifyIncidents(
        incident_source=EsetIncidentClient(
            base_url=settings.eset_base_url,
            auth_client=auth_client,
        ),
        approval_repository=PostgresApprovalRepository(
            database_url=settings.database_url,
            sanitizer=sanitizer,
        ),
        collection_run_repository=PostgresCollectionRunRepository(settings.database_url),
        notification_builder=SanitizedIncidentNotificationBuilder(sanitizer),
        notification_repository=PostgresNotificationRepository(settings.database_url),
        notifier=notifier,
        analyzer=AnalyzeIncident(
            vector_repository=PgVectorRepository(settings.database_url),
            llm_gateway=LocalAnalysisGateway(),
        ),
    )


def get_list_pending_approvals() -> ListPendingApprovals:
    settings = get_settings()
    return ListPendingApprovals(
        PostgresApprovalRepository(
            database_url=settings.database_url,
            sanitizer=Sanitizer(settings.sanitizer_hmac_secret),
        )
    )


def get_review_pending_approval() -> ReviewPendingApproval:
    settings = get_settings()
    sanitizer = Sanitizer(settings.sanitizer_hmac_secret)
    notifier: Notifier
    if settings.discord_enabled:
        notifier = DiscordWebhookClient(webhook_url=settings.discord_webhook_url)
    else:
        notifier = DisabledNotifier()

    return ReviewPendingApproval(
        approval_repository=PostgresApprovalRepository(
            database_url=settings.database_url,
            sanitizer=sanitizer,
        ),
        notification_builder=SanitizedIncidentNotificationBuilder(sanitizer),
        notification_repository=PostgresNotificationRepository(settings.database_url),
        notifier=notifier,
    )


def get_list_collection_runs() -> ListCollectionRuns:
    settings = get_settings()
    return ListCollectionRuns(PostgresCollectionRunRepository(settings.database_url))


def get_search_knowledge() -> SearchKnowledge:
    settings = get_settings()
    return SearchKnowledge(PgVectorRepository(settings.database_url))
