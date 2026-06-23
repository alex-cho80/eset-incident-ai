from __future__ import annotations

import argparse
import asyncio

from eset_incident_ai.api.dependencies import get_collect_and_notify_incidents
from eset_incident_ai.settings.config import Settings


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Notify sanitized ESET incidents to Discord.")
    parser.add_argument("--limit", type=int, default=1, help="Maximum incidents to notify.")
    return parser.parse_args()


async def run(limit: int) -> None:
    settings = Settings()
    if not settings.discord_enabled:
        raise SystemExit("DISCORD_ENABLED is not true")
    if not settings.discord_webhook_url:
        raise SystemExit("DISCORD_WEBHOOK_URL is empty")
    if not (settings.eset_access_token or (settings.eset_username and settings.eset_password)):
        raise SystemExit("ESET credentials are empty")
    if not settings.sanitizer_hmac_secret:
        raise SystemExit("SANITIZER_HMAC_SECRET is empty")

    result = await get_collect_and_notify_incidents().execute(limit=limit)

    print(result.model_dump_json())


def main() -> None:
    args = parse_args()
    asyncio.run(run(limit=args.limit))


if __name__ == "__main__":
    main()
