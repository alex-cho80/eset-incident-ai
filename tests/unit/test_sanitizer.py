from eset_incident_ai.security.sanitizer import Sanitizer


def test_sanitizer_masks_email_and_user_home_but_preserves_ip() -> None:
    sanitizer = Sanitizer("test-secret")

    result = sanitizer.sanitize_text(
        "user alice@example.com ran C:\\Users\\alice\\Downloads\\a.exe from 10.1.1.25"
    )

    assert "alice@example.com" not in result.text
    assert "10.1.1.25" in result.text
    assert "C:\\Users\\alice\\" not in result.text
    assert "EMAIL_" in result.text
    assert "<USER_HOME>" in result.text


def test_sanitizer_preserves_private_and_public_ips() -> None:
    sanitizer = Sanitizer("test-secret")

    result = sanitizer.sanitize_text("internal host 10.1.1.25 talked to 8.8.8.8")

    assert "10.1.1.25" in result.text
    assert "8.8.8.8" in result.text
    assert "PRIVATE_IP_" not in result.text
    assert "PUBLIC_IP_" not in result.text


def test_sanitizer_masks_secret_values() -> None:
    sanitizer = Sanitizer("test-secret")

    result = sanitizer.sanitize_text("token=abc123 password='secret-value'")

    assert "abc123" not in result.text
    assert "secret-value" not in result.text
    assert result.text.count("<SECRET_REDACTED>") == 2


def test_sanitizer_masks_domain_accounts_consistently() -> None:
    sanitizer = Sanitizer("test-secret")

    first = sanitizer.sanitize_text("account nt authority\\local service triggered")
    second = sanitizer.sanitize_text("account nt authority\\local service triggered")
    corp = sanitizer.sanitize_text("account CORP\\jdoe triggered")

    assert first.text == second.text
    assert "nt authority\\local service" not in first.text
    assert "CORP\\jdoe" not in corp.text
    assert "ACCOUNT_" in first.text
    assert "ACCOUNT_" in corp.text


def test_sanitizer_preserves_multi_segment_program_paths() -> None:
    sanitizer = Sanitizer("test-secret")
    tomcat_path = "apache software foundation\\tomcat 9.0\\bin\\tomcat9.exe"
    program_files_path = "C:\\Program Files\\Vendor\\App\\app.exe"

    assert sanitizer.sanitize_text(tomcat_path).text == tomcat_path
    assert sanitizer.sanitize_text(program_files_path).text == program_files_path


def test_sanitizer_masks_legacy_windows_and_unix_home_paths() -> None:
    sanitizer = Sanitizer("test-secret")

    result = sanitizer.sanitize_text(
        "legacy C:\\Documents and Settings\\alice\\Desktop\\a.exe "
        "unix /home/bob/downloads/a.exe "
        "modern C:\\Users\\carol\\Downloads\\a.exe"
    )

    assert "C:\\Documents and Settings\\alice\\" not in result.text
    assert "/home/bob/" not in result.text
    assert "C:\\Users\\carol\\" not in result.text
    assert "<USER_HOME>\\Desktop\\a.exe" in result.text
    assert "<USER_HOME>/downloads/a.exe" in result.text
    assert "<USER_HOME>\\Downloads\\a.exe" in result.text


def test_sanitizer_requires_secret() -> None:
    try:
        Sanitizer("")
    except ValueError as exc:
        assert "hmac_secret is required" in str(exc)
    else:
        raise AssertionError("expected ValueError")
