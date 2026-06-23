# ESET Incident AI

ESET Connect API에서 보안 인시던트를 수집하고, 정규화 및 비식별화 후 RAG 근거와 함께 Agentic AI 분석 결과를 생성하는 시스템입니다.

초기 목표는 자동 대응이 아니라 조사와 권고입니다. High/Critical 인시던트와 파괴적 조치는 반드시 사람 승인 뒤에만 외부 알림 또는 실행 대상으로 넘깁니다.

## Architecture

이 프로젝트는 Hexagonal Architecture를 따릅니다.

```text
API / Infrastructure -> Application -> Domain
```

- Domain: 순수 비즈니스 규칙, 외부 SDK 의존 금지
- Application: 유스케이스와 포트
- Infrastructure: ESET, PostgreSQL, LLM, Discord, Queue 어댑터
- API: FastAPI 라우트와 예외 처리

## Local Setup

```bash
uv sync
cp .env.example .env
docker compose -f docker-compose.dev.yml up --build
```

If Docker requires sudo on the host, use `sudo docker compose ...` directly or pass
`DOCKER="sudo docker"` to Makefile targets.

## Daily Incident Notification

The designed operating path is:

```text
Celery Beat at 10:00 Asia/Seoul
  -> collect_and_notify_incidents task
  -> ESET password/client credential token request
  -> ESET /v2/incidents collection
  -> sanitizer and severity policy
  -> Discord notification for low/medium incidents
  -> high/critical incidents counted as pending approval
```

For this mode, keep `ESET_ACCESS_TOKEN` empty and configure credentials through environment variables:

```env
ESET_USERNAME=
ESET_PASSWORD=
ESET_CLIENT_ID=
ESET_CLIENT_SECRET=
ESET_ACCESS_TOKEN=
INCIDENT_NOTIFY_LIMIT=10
INCIDENT_NOTIFY_CRON_HOUR=10
INCIDENT_NOTIFY_CRON_MINUTE=0
INCIDENT_NOTIFY_TIMEZONE=Asia/Seoul
DISCORD_ENABLED=true
```

Run the scheduled stack:

```bash
docker compose up -d --build --force-recreate api worker scheduler redis postgres
```

Run the operating flow manually:

```bash
docker compose exec worker uv run celery \
  -A eset_incident_ai.infrastructure.queue.celery_app \
  eset_incident_ai.collect_and_notify_incidents --args='[10]'
```

Operational smoke check:

```bash
uv run python scripts/smoke_check.py
make smoke
```

When Docker requires sudo:

```bash
make DOCKER="sudo docker" compose-up
make DOCKER="sudo docker" compose-ps
make DOCKER="sudo docker" compose-logs-worker
make DOCKER="sudo docker" collect-now
```

## Operations

Readiness and liveness:

```bash
curl http://localhost:8000/health
curl http://localhost:8000/ready
```

Collection run status:

```bash
curl http://localhost:8000/api/v1/incidents/collection-runs/latest
curl 'http://localhost:8000/api/v1/incidents/collection-runs?limit=5'
```

Approval queue:

```bash
curl http://localhost:8000/api/v1/approvals/pending
curl -X POST http://localhost:8000/api/v1/approvals/{approval_id}/approve
curl -X POST http://localhost:8000/api/v1/approvals/{approval_id}/reject
```

Expected normal state after duplicate-safe collection:

```json
{
  "status": "succeeded",
  "error_message": null
}
```

If collection fails, the latest collection run has `status: "failed"` and a short
`error_message` that does not include configured secrets.

## Verification

```bash
uv run ruff format --check .
uv run ruff check .
uv run mypy src
uv run pytest --cov=src --cov-fail-under=85
uv run bandit -r src
uv run pip-audit
```

## Safety

- ESET 원본 데이터는 LLM 또는 Discord로 직접 보내지 않습니다.
- 사용자, 이메일, 호스트명, 내부 IP, 토큰, 파일 경로는 정책 승인 전 마스킹합니다.
- LLM 출력은 권고이며 엔드포인트 조치를 직접 실행하지 않습니다.
- Discord는 초기값 `DISCORD_ENABLED=false`입니다.
