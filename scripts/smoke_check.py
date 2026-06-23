from __future__ import annotations

import argparse
import json
import os
import sys
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import urljoin, urlsplit
from urllib.request import Request, urlopen


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run API smoke checks without printing secrets.")
    parser.add_argument(
        "--base-url",
        default=os.getenv("API_BASE_URL", "http://localhost:8000"),
        help="Base URL for the running API.",
    )
    parser.add_argument("--timeout", type=float, default=5.0, help="HTTP timeout in seconds.")
    return parser.parse_args()


def get_json(base_url: str, path: str, *, timeout: float) -> Any:
    scheme = urlsplit(base_url).scheme
    if scheme not in {"http", "https"}:
        raise RuntimeError("base URL must use http or https")
    url = urljoin(base_url.rstrip("/") + "/", path.lstrip("/"))
    request = Request(url, headers={"Accept": "application/json"})  # noqa: S310
    with urlopen(request, timeout=timeout) as response:  # noqa: S310
        return json.loads(response.read().decode("utf-8"))


def check_health(base_url: str, *, timeout: float) -> None:
    payload = get_json(base_url, "/health", timeout=timeout)
    if payload != {"status": "ok"}:
        raise RuntimeError("/health did not return ok")
    print("health=ok")


def check_ready(base_url: str, *, timeout: float) -> None:
    payload = get_json(base_url, "/ready", timeout=timeout)
    if payload.get("status") != "ready":
        raise RuntimeError("/ready did not return ready")
    checks = payload.get("checks", {})
    print(
        "ready=ok "
        f"database={checks.get('database', 'unknown')} "
        f"redis={checks.get('redis', 'unknown')}"
    )


def check_collection_runs(base_url: str, *, timeout: float) -> None:
    payload = get_json(base_url, "/api/v1/incidents/collection-runs/latest", timeout=timeout)
    if payload is None:
        print("latest_collection_run=none")
        return
    if not isinstance(payload, dict):
        raise RuntimeError("latest collection run response is not an object")
    print(
        "latest_collection_run=ok "
        f"status={payload.get('status', 'unknown')} "
        f"run_id={payload.get('run_id', 'unknown')}"
    )


def check_pending_approvals(base_url: str, *, timeout: float) -> None:
    payload = get_json(base_url, "/api/v1/approvals/pending", timeout=timeout)
    if not isinstance(payload, list):
        raise RuntimeError("pending approvals response is not a list")
    print(f"pending_approvals=ok count={len(payload)}")


def main() -> int:
    args = parse_args()
    try:
        check_health(args.base_url, timeout=args.timeout)
        check_ready(args.base_url, timeout=args.timeout)
        check_collection_runs(args.base_url, timeout=args.timeout)
        check_pending_approvals(args.base_url, timeout=args.timeout)
    except HTTPError as exc:
        print(f"smoke_check=failed http_status={exc.code}", file=sys.stderr)
        return 1
    except (OSError, URLError, RuntimeError, json.JSONDecodeError) as exc:
        print(f"smoke_check=failed reason={type(exc).__name__}", file=sys.stderr)
        return 1
    print("smoke_check=ok")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
