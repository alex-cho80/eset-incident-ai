from eset_incident_ai.agents.router import (
    route_after_approval,
    route_after_critique,
    route_after_security_review,
)


def test_critique_retries_unsupported_claims() -> None:
    route = route_after_critique(
        {"critique": {"unsupported_claim_count": 1}, "retry_count": 0, "confidence": 0.9}
    )

    assert route == "retry_investigation"


def test_critique_rejects_after_retry_limit() -> None:
    route = route_after_critique(
        {"critique": {"unsupported_claim_count": 1}, "retry_count": 2, "confidence": 0.9}
    )

    assert route == "reject"


def test_critique_rejects_low_confidence() -> None:
    route = route_after_critique(
        {"critique": {"unsupported_claim_count": 0}, "retry_count": 0, "confidence": 0.1}
    )

    assert route == "reject"


def test_critique_routes_to_security_review() -> None:
    route = route_after_critique(
        {"critique": {"unsupported_claim_count": 0}, "retry_count": 0, "confidence": 0.9}
    )

    assert route == "security_review"


def test_security_review_routes_to_approval_for_high_risk() -> None:
    route = route_after_security_review(
        {"security_review": {"pass": True}, "requires_human_approval": True}
    )

    assert route == "approval"


def test_security_review_rejects_failed_review() -> None:
    route = route_after_security_review({"security_review": {"pass": False}})

    assert route == "reject"


def test_security_review_routes_to_compose() -> None:
    route = route_after_security_review(
        {"security_review": {"pass": True}, "requires_human_approval": False}
    )

    assert route == "compose"


def test_approval_routes_by_status() -> None:
    assert route_after_approval({"approval_status": "approved"}) == "approved"
    assert route_after_approval({"approval_status": "rejected"}) == "rejected"
    assert route_after_approval({"approval_status": "pending"}) == "pending"
