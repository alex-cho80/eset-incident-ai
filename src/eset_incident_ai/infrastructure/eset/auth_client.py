from __future__ import annotations

import asyncio
import time
from dataclasses import dataclass

import httpx


class EsetAuthenticationError(RuntimeError):
    pass


@dataclass(frozen=True, slots=True)
class AccessToken:
    value: str
    expires_at: float

    def is_valid(self, skew_seconds: int = 60) -> bool:
        return time.time() < self.expires_at - skew_seconds


class EsetAuthClient:
    def __init__(
        self,
        *,
        auth_url: str,
        username: str,
        password: str,
        client_id: str = "",
        client_secret: str = "",
        access_token: str = "",
        access_token_expires_in: int = 3600,
        timeout_seconds: float = 15.0,
    ) -> None:
        self._auth_url = auth_url
        self._username = username
        self._password = password
        self._client_id = client_id
        self._client_secret = client_secret
        self._timeout = httpx.Timeout(timeout_seconds)
        self._token: AccessToken | None = (
            AccessToken(value=access_token, expires_at=time.time() + access_token_expires_in)
            if access_token
            else None
        )
        self._lock = asyncio.Lock()

    async def get_access_token(self) -> str:
        if self._token and self._token.is_valid():
            return self._token.value

        async with self._lock:
            if self._token and self._token.is_valid():
                return self._token.value

            async with httpx.AsyncClient(timeout=self._timeout) as client:
                response = await client.post(
                    self._auth_url,
                    data=self._build_token_request(),
                    headers={"Content-Type": "application/x-www-form-urlencoded"},
                )

            if response.status_code != 200:
                raise EsetAuthenticationError(
                    f"ESET authentication failed: status={response.status_code}"
                )

            payload = response.json()
            token = payload.get("access_token")
            expires_in = int(payload.get("expires_in", 3600))
            if not isinstance(token, str) or not token:
                raise EsetAuthenticationError("ESET response did not contain access_token")

            self._token = AccessToken(value=token, expires_at=time.time() + expires_in)
            return self._token.value

    def _build_token_request(self) -> dict[str, str]:
        if self._client_id and self._client_secret:
            return {
                "grant_type": "client_credentials",
                "client_id": self._client_id,
                "client_secret": self._client_secret,
            }
        return {
            "grant_type": "password",
            "username": self._username,
            "password": self._password,
        }
