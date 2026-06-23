from __future__ import annotations

import argparse
import asyncio

from eset_incident_ai.infrastructure.eset.auth_client import EsetAuthClient
from eset_incident_ai.infrastructure.eset.incident_client import EsetIncidentClient
from eset_incident_ai.settings.config import Settings


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Check ESET incident list access safely.")
    parser.add_argument(
        "--updated-after",
        default=None,
        help="Optional ISO timestamp used for ESET updateTime filtering.",
    )
    parser.add_argument("--limit", type=int, default=5, help="Maximum incidents to fetch.")
    return parser.parse_args()


async def run(updated_after: str, limit: int) -> None:
    settings = Settings()
    auth_client = EsetAuthClient(
        auth_url=settings.eset_auth_url,
        username=settings.eset_username,
        password=settings.eset_password,
        client_id=settings.eset_client_id,
        client_secret=settings.eset_client_secret,
        access_token=settings.eset_access_token,
        access_token_expires_in=settings.eset_access_token_expires_in,
    )
    incident_client = EsetIncidentClient(
        base_url=settings.eset_base_url,
        auth_client=auth_client,
    )

    count = 0
    observed_keys: set[str] = set()
    async for incident in incident_client.iter_incidents(
        updated_after=updated_after,
        page_size=min(settings.eset_page_size, max(limit, 1)),
    ):
        count += 1
        observed_keys.update(str(key) for key in incident.keys())
        if count >= limit:
            break

    print(f"eset_incident_list_ok=true count={count}")
    if observed_keys:
        print("observed_keys=" + ",".join(sorted(observed_keys)))


def main() -> None:
    args = parse_args()
    asyncio.run(run(updated_after=args.updated_after, limit=args.limit))


if __name__ == "__main__":
    main()
