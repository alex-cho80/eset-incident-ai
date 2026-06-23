from eset_incident_ai.security.sanitizer import Sanitizer


def test_sanitizer_redacts_private_identifiers() -> None:
    sanitizer = Sanitizer("test-secret")

    result = sanitizer.sanitize_text(
        "user alice@example.com ran C:\\Users\\alice\\Downloads\\a.exe from 10.1.1.25"
    )

    assert "alice@example.com" not in result.text
    assert "10.1.1.25" not in result.text
    assert "C:\\Users\\alice\\" not in result.text
    assert "EMAIL_" in result.text
    assert "PRIVATE_IP_" in result.text
    assert "<USER_HOME>" in result.text


def test_sanitizer_requires_secret() -> None:
    try:
        Sanitizer("")
    except ValueError as exc:
        assert "hmac_secret is required" in str(exc)
    else:
        raise AssertionError("expected ValueError")
