import pytest

from eset_incident_ai.infrastructure.eset.auth_client import EsetAuthClient


@pytest.mark.asyncio
async def test_auth_client_uses_local_access_token_override() -> None:
    token_value = "-".join(["local", "token"])
    client = EsetAuthClient(
        auth_url="https://example.invalid/oauth/token",
        username="",
        password="",
        access_token=token_value,
        access_token_expires_in=3600,
    )

    assert await client.get_access_token() == token_value
