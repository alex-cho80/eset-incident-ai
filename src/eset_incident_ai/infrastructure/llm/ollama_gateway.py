from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Protocol

import httpx
from jinja2 import Environment, FileSystemLoader, select_autoescape
from tenacity import AsyncRetrying, retry_if_exception_type, stop_after_attempt, wait_exponential

from eset_incident_ai.domain.entities.analysis import IncidentAnalysisResult
from eset_incident_ai.domain.entities.evidence import RetrievedEvidence
from eset_incident_ai.domain.entities.incident import Incident
from eset_incident_ai.infrastructure.llm.structured_output import (
    StructuredOutputError,
    parse_incident_analysis,
)
from eset_incident_ai.security.prompt_injection_filter import PromptInjectionFilter
from eset_incident_ai.security.sanitizer import Sanitizer

logger = logging.getLogger(__name__)

_PROMPT_DIR = Path(__file__).resolve().parents[4] / "config" / "prompts"
_PROMPT_TEMPLATE_NAME = "incident_analysis.jinja2"
_NO_EVIDENCE_ID = "no-supporting-evidence"
_INJECTION_NOTICE = (
    "Automated prompt-injection check flagged suspicious instructions embedded in the "
    "incident text; those instructions were not followed."
)
_RETRYABLE_OLLAMA_ERRORS = (
    httpx.ConnectError,
    httpx.ConnectTimeout,
    httpx.ReadTimeout,
)


class _AsyncHttpClient(Protocol):
    async def post(self, url: str, *, json: dict[str, object]) -> httpx.Response: ...


class OllamaGateway:
    def __init__(
        self,
        *,
        base_url: str,
        model: str,
        keep_alive: str,
        sanitizer: Sanitizer,
        timeout_seconds: float = 240.0,
        max_retries: int = 2,
        injection_filter: PromptInjectionFilter | None = None,
        client: _AsyncHttpClient | None = None,
    ) -> None:
        if not base_url:
            raise ValueError("base_url is required")
        if not model:
            raise ValueError("model is required")
        self._base_url = base_url.rstrip("/")
        self._model = model
        self._keep_alive = keep_alive
        self._sanitizer = sanitizer
        self._injection_filter = injection_filter or PromptInjectionFilter()
        self._max_retries = max_retries
        self._client = client or httpx.AsyncClient(timeout=timeout_seconds)
        self._template = Environment(
            loader=FileSystemLoader(str(_PROMPT_DIR)),
            # select_autoescape()'s default extension list (html/htm/xml) does not include
            # .jinja2, so this renders plain text for the LLM prompt instead of HTML-escaping
            # incident data (which would corrupt it with &amp;/&lt; entities).
            autoescape=select_autoescape(),
            trim_blocks=True,
            lstrip_blocks=True,
        ).get_template(_PROMPT_TEMPLATE_NAME)

    async def analyze(
        self, *, incident: Incident, evidence: list[RetrievedEvidence]
    ) -> IncidentAnalysisResult:
        title = self._sanitizer.sanitize_text(incident.title).text
        summary = self._sanitizer.sanitize_text(incident.summary or "").text
        injection_flagged = self._injection_filter.contains_suspicious_instruction(
            incident.title
        ) or self._injection_filter.contains_suspicious_instruction(incident.summary or "")

        # The sentinel is always a valid citation, not only when evidence is empty: a
        # claim may honestly have no support even when other, unrelated evidence was
        # retrieved for the incident.
        valid_evidence_ids = {item.evidence_id for item in evidence} | {_NO_EVIDENCE_ID}
        prompt = self._render_prompt(
            title=title, summary=summary, severity=incident.severity.value, evidence=evidence
        )

        raw_text = await self._call_with_retry(prompt)
        try:
            result = self._parse_and_validate(raw_text, valid_evidence_ids)
        except StructuredOutputError as exc:
            logger.warning(
                "OllamaGateway validation failed, retrying once: %s | raw_text=%r",
                exc,
                raw_text[:2000],
            )
            retry_prompt = self._retry_prompt(prompt, exc)
            raw_text = await self._call_with_retry(retry_prompt)
            try:
                result = self._parse_and_validate(raw_text, valid_evidence_ids)
            except StructuredOutputError as exc2:
                logger.warning(
                    "OllamaGateway validation failed again after retry: %s | raw_text=%r",
                    exc2,
                    raw_text[:2000],
                )
                raise

        if injection_flagged:
            result = result.model_copy(
                update={"limitations": [*result.limitations, _INJECTION_NOTICE]}
            )
        return result

    def _render_prompt(
        self, *, title: str, summary: str, severity: str, evidence: list[RetrievedEvidence]
    ) -> str:
        incident_json = json.dumps(
            {"title": title, "severity": severity, "summary": summary}, ensure_ascii=False
        )
        return self._template.render(incident_json=incident_json, evidence_list=evidence)

    def _retry_prompt(self, prompt: str, exc: Exception) -> str:
        return (
            f"{prompt}\n\nYour previous response failed validation: {exc}\n"
            "Return only corrected JSON matching the schema exactly, with no extra text."
        )

    def _parse_and_validate(
        self, raw_text: str, valid_evidence_ids: set[str]
    ) -> IncidentAnalysisResult:
        result = parse_incident_analysis(raw_text)
        claims = [*result.root_cause.direct_cause, *result.root_cause.root_causes]
        for claim in claims:
            if not set(claim.evidence_ids) <= valid_evidence_ids:
                raise StructuredOutputError(
                    "LLM referenced evidence_ids not present in supplied evidence"
                )
        return result

    async def _call_with_retry(self, prompt: str) -> str:
        async for attempt in AsyncRetrying(
            stop=stop_after_attempt(self._max_retries + 1),
            wait=wait_exponential(multiplier=1, max=10),
            retry=retry_if_exception_type(_RETRYABLE_OLLAMA_ERRORS),
            reraise=True,
        ):
            with attempt:
                response = await self._client.post(
                    f"{self._base_url}/api/generate",
                    json={
                        "model": self._model,
                        "prompt": prompt,
                        "stream": False,
                        "format": "json",
                        "keep_alive": self._keep_alive,
                    },
                )
                response.raise_for_status()
                payload = response.json()
                generated_text = payload.get("response")
                if not isinstance(generated_text, str):
                    raise StructuredOutputError("Ollama response did not include response text")
                return generated_text
        raise AssertionError("unreachable: AsyncRetrying always returns or raises")
