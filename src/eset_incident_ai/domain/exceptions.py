from __future__ import annotations


class DomainError(RuntimeError):
    """Base class for domain-level failures."""


class UnsafeNotificationError(DomainError):
    """Raised when an analysis payload is not safe to notify."""


class ApprovalRequiredError(DomainError):
    """Raised when an action requires human approval."""
