from __future__ import annotations

from dataclasses import dataclass
from typing import Any
from urllib import error as urllib_error
from urllib import parse as urllib_parse
from urllib import request as urllib_request
import json
import time

from .config import AppConfig
from .models import EntitySpan, ProcessingProfile, TranscriptSegment, TranscriptWord, make_id
from .pii import digits_only, email_like_normalize, normalize_compact_text, normalize_token


class LMStudioError(RuntimeError):
    pass


class LMStudioTransportError(LMStudioError):
    def __init__(self, message: str, *, status_code: int | None = None, response_body: str | None = None) -> None:
        super().__init__(message)
        self.status_code = status_code
        self.response_body = response_body


class LMStudioSchemaError(LMStudioError):
    pass


def _join_url(base_url: str, path: str) -> str:
    if path.startswith("http://") or path.startswith("https://"):
        return path
    return urllib_parse.urljoin(base_url.rstrip("/") + "/", path.lstrip("/"))


def _extract_message_text(payload: dict[str, Any]) -> str:
    direct_content = payload.get("content")
    if isinstance(direct_content, str) and direct_content.strip():
        return direct_content.strip()
    choice = ((payload.get("choices") or [{}])[0]).get("message") or {}
    content = choice.get("content")
    if isinstance(content, list):
        text_parts = [item.get("text", "") for item in content if isinstance(item, dict) and item.get("type") == "text"]
        if any(text_parts):
            return "\n".join(part for part in text_parts if part).strip()
    if isinstance(content, str) and content.strip():
        return content.strip()
    reasoning = choice.get("reasoning_content")
    if isinstance(reasoning, str) and reasoning.strip():
        return reasoning.strip()
    output = payload.get("output")
    if isinstance(output, list):
        text_parts = []
        for item in output:
            if not isinstance(item, dict):
                continue
            for content_item in item.get("content", []):
                if isinstance(content_item, dict) and content_item.get("type") == "output_text":
                    text_parts.append(content_item.get("text", ""))
        if any(text_parts):
            return "\n".join(part for part in text_parts if part).strip()
    raise LMStudioSchemaError("LM Studio response did not contain assistant text content")


def _decode_json_payload(payload_bytes: bytes) -> dict[str, Any]:
    text = payload_bytes.decode("utf-8-sig", errors="replace")
    stripped = text.strip()
    if not stripped:
        raise json.JSONDecodeError("Empty response body", text, 0)
    try:
        return json.loads(stripped)
    except json.JSONDecodeError as initial_exc:
        # Some proxies prepend non-JSON framing. Try to recover by extracting data lines.
        if "data:" in stripped:
            data_lines: list[str] = []
            for raw_line in stripped.splitlines():
                line = raw_line.strip()
                if not line.startswith("data:"):
                    continue
                chunk = line[5:].strip()
                if not chunk or chunk == "[DONE]":
                    continue
                data_lines.append(chunk)
            for chunk in reversed(data_lines):
                try:
                    return json.loads(chunk)
                except json.JSONDecodeError:
                    continue
        # Last resort for prefixed/suffixed garbage around a valid JSON object.
        first_brace = stripped.find("{")
        last_brace = stripped.rfind("}")
        if 0 <= first_brace < last_brace:
            candidate = stripped[first_brace : last_brace + 1]
            try:
                return json.loads(candidate)
            except json.JSONDecodeError:
                pass
        raise initial_exc


def _tokenize_text(text: str) -> list[str]:
    return [token for token in text.replace("\n", " ").split(" ") if token]


def _distribute_words(
    *,
    text: str,
    speaker_id: str,
    channel_id: int | None,
    start_ms: int,
    end_ms: int,
) -> list[TranscriptWord]:
    tokens = _tokenize_text(text)
    if not tokens:
        return []
    duration = max(end_ms - start_ms, len(tokens))
    word_duration = max(duration // len(tokens), 1)
    words: list[TranscriptWord] = []
    for index, token in enumerate(tokens):
        word_start = start_ms + index * word_duration
        word_end = end_ms if index == len(tokens) - 1 else min(end_ms, word_start + word_duration)
        words.append(
            TranscriptWord(
                text=token,
                start_ms=word_start,
                end_ms=word_end,
                confidence=0.9,
                speaker_id=speaker_id,
                channel_id=channel_id,
            )
        )
    return words


def _remap_words_preserving_timing(
    *,
    cleaned_text: str,
    original_words: list[TranscriptWord],
    speaker_id: str,
    channel_id: int | None,
    start_ms: int,
    end_ms: int,
) -> list[TranscriptWord]:
    cleaned_tokens = _tokenize_text(cleaned_text)
    if not cleaned_tokens:
        return []
    if not original_words:
        return _distribute_words(
            text=cleaned_text,
            speaker_id=speaker_id,
            channel_id=channel_id,
            start_ms=start_ms,
            end_ms=end_ms,
        )
    if len(cleaned_tokens) == len(original_words):
        return [
            TranscriptWord(
                text=token,
                start_ms=original.start_ms,
                end_ms=original.end_ms,
                confidence=original.confidence,
                speaker_id=speaker_id,
                channel_id=channel_id,
            )
            for token, original in zip(cleaned_tokens, original_words, strict=False)
        ]

    words: list[TranscriptWord] = []
    original_count = len(original_words)
    for index, token in enumerate(cleaned_tokens):
        start_index = min(int(index * original_count / len(cleaned_tokens)), original_count - 1)
        end_index = min(int(((index + 1) * original_count / len(cleaned_tokens)) - 1), original_count - 1)
        if end_index < start_index:
            end_index = start_index
        source_words = original_words[start_index : end_index + 1]
        words.append(
            TranscriptWord(
                text=token,
                start_ms=source_words[0].start_ms,
                end_ms=source_words[-1].end_ms,
                confidence=sum(word.confidence for word in source_words) / len(source_words),
                speaker_id=speaker_id,
                channel_id=channel_id,
            )
        )
    return words


def _coerce_float(value: Any, default: float) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


@dataclass(slots=True)
class RequestTrace:
    endpoint: str
    latency_ms: int
    retry_count: int
    response_preview: dict[str, Any]


@dataclass(slots=True)
class TranscriptCleanupResult:
    segments: list[TranscriptSegment]
    language: str
    prompt_version: str
    trace: RequestTrace
    edits_applied: list[dict[str, Any]]
    speaker_changes: list[dict[str, Any]]
    validation_report: dict[str, Any]
    raw_response: dict[str, Any]


@dataclass(slots=True)
class LlmNerResult:
    entities: list[EntitySpan]
    prompt_version: str
    trace: RequestTrace
    raw_response: dict[str, Any]
    report: dict[str, Any]


@dataclass(slots=True)
class SummaryResult:
    title: str
    summary: str
    bullets: list[str]
    confidence: float
    prompt_version: str
    trace: RequestTrace
    raw_response: dict[str, Any]


class LMStudioClient:
    def __init__(self, config: AppConfig) -> None:
        self.config = config

    def list_models(self) -> dict[str, Any]:
        payload, _ = self._request_json("GET", self.config.lmstudio_models_path)
        return payload

    def chat_json(
        self,
        *,
        model: str,
        system_prompt: str,
        user_payload: dict[str, Any],
        schema: dict[str, Any],
        prompt_version: str,
        overrides: dict[str, Any] | None = None,
    ) -> tuple[dict[str, Any], RequestTrace]:
        overrides = overrides or {}
        transport_mode = str(overrides.get("llm_transport_mode") or overrides.get("transport_mode") or self.config.lmstudio_transport_mode)
        payload = self._build_chat_payload(
            model=model,
            system_prompt=system_prompt,
            user_payload=user_payload,
            schema=schema,
            prompt_version=prompt_version,
            overrides=overrides,
            transport_mode=transport_mode,
        )
        raw_payload, trace = self._request_json(
            "POST",
            self._chat_path_for_mode(overrides, transport_mode),
            body=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
            headers={"Content-Type": "application/json"},
        )
        text = _extract_message_text(raw_payload)
        try:
            parsed = json.loads(text)
        except json.JSONDecodeError:
            repair_payload = {
                "invalid_response": text,
                "original_request": user_payload,
                "instruction": "Repair the invalid JSON so it matches the required schema exactly. Return JSON only.",
            }
            repair_raw, repair_trace = self._request_json(
                "POST",
                self._chat_path_for_mode(overrides, transport_mode),
                body=json.dumps(
                    self._build_chat_payload(
                        model=model,
                        system_prompt="Return valid JSON only.",
                        user_payload=repair_payload,
                        schema=schema,
                        prompt_version=f"{prompt_version}_repair",
                        overrides={"temperature": 0, **overrides},
                        transport_mode=transport_mode,
                    ),
                    ensure_ascii=False,
                ).encode("utf-8"),
                headers={"Content-Type": "application/json"},
            )
            trace = RequestTrace(
                endpoint=trace.endpoint,
                latency_ms=trace.latency_ms + repair_trace.latency_ms,
                retry_count=trace.retry_count + repair_trace.retry_count + 1,
                response_preview=repair_trace.response_preview,
            )
            raw_payload = repair_raw
            text = _extract_message_text(repair_raw)
            try:
                parsed = json.loads(text)
            except json.JSONDecodeError as exc:
                raise LMStudioSchemaError(f"LM Studio returned invalid JSON for {prompt_version}") from exc
        return parsed, trace

    def _chat_path_for_mode(self, overrides: dict[str, Any], transport_mode: str) -> str:
        if transport_mode == "lmstudio_native":
            return str(overrides.get("native_chat_path") or overrides.get("chat_path") or self.config.lmstudio_native_chat_path)
        return str(overrides.get("chat_path") or self.config.lmstudio_chat_path)

    def _build_chat_payload(
        self,
        *,
        model: str,
        system_prompt: str,
        user_payload: dict[str, Any],
        schema: dict[str, Any],
        prompt_version: str,
        overrides: dict[str, Any],
        transport_mode: str,
    ) -> dict[str, Any]:
        if transport_mode == "lmstudio_native":
            instruction = (
                f"{system_prompt}\n"
                f"Schema name: {prompt_version}.\n"
                "Return valid JSON only. The response must strictly match the provided schema.\n"
                f"JSON schema: {json.dumps(schema, ensure_ascii=False)}"
            )
            payload = {
                "model": overrides.get("model", model),
                "system_prompt": instruction,
                "input": json.dumps(user_payload, ensure_ascii=False),
                "temperature": overrides.get("temperature", 0),
            }
            if "reasoning" in overrides:
                payload["reasoning"] = overrides["reasoning"]
            return payload
        payload = {
            "model": overrides.get("model", model),
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": json.dumps(user_payload, ensure_ascii=False)},
            ],
            "temperature": overrides.get("temperature", 0),
            "stream": False,
            "response_format": {
                "type": "json_schema",
                "json_schema": {
                    "name": prompt_version,
                    "strict": True,
                    "schema": schema,
                },
            },
        }
        if "reasoning" in overrides:
            payload["reasoning"] = overrides["reasoning"]
        return payload

    def _request_json(
        self,
        method: str,
        path: str,
        *,
        body: bytes | None = None,
        headers: dict[str, str] | None = None,
    ) -> tuple[dict[str, Any], RequestTrace]:
        url = _join_url(self.config.lmstudio_base_url, path)
        request_headers = dict(headers or {})
        request_headers.setdefault("Accept", "application/json")
        if self.config.lmstudio_api_key:
            request_headers["Authorization"] = f"Bearer {self.config.lmstudio_api_key}"
        if self.config.lmstudio_cookie:
            request_headers["Cookie"] = self.config.lmstudio_cookie
        timeout = self.config.lmstudio_timeout_seconds
        last_error: Exception | None = None
        for attempt in range(self.config.lmstudio_max_retries + 1):
            started_at = time.monotonic()
            request = urllib_request.Request(url, data=body, method=method, headers=request_headers)
            try:
                with urllib_request.urlopen(request, timeout=timeout) as response:
                    payload_bytes = response.read()
                    try:
                        payload = _decode_json_payload(payload_bytes)
                    except json.JSONDecodeError as exc:
                        response_text = payload_bytes.decode("utf-8", errors="replace")
                        snippet = response_text.strip().replace("\n", "\\n")[:500]
                        if "<html" in response_text.lower():
                            raise LMStudioTransportError(
                                f"LM Studio returned HTML instead of JSON (likely auth/session issue) from {url}: {snippet}",
                                response_body=response_text,
                            ) from exc
                        raise LMStudioTransportError(
                            f"LM Studio returned non-JSON body from {url}: {snippet}",
                            response_body=response_text,
                        ) from exc
                    latency_ms = int((time.monotonic() - started_at) * 1000)
                    return payload, RequestTrace(
                        endpoint=url,
                        latency_ms=latency_ms,
                        retry_count=attempt,
                        response_preview=self._response_preview(payload),
                    )
            except urllib_error.HTTPError as exc:
                response_body = exc.read().decode("utf-8", errors="replace")
                last_error = LMStudioTransportError(
                    self._http_error_message(url, exc.code, response_body),
                    status_code=exc.code,
                    response_body=response_body,
                )
                if exc.code >= 500 and attempt < self.config.lmstudio_max_retries:
                    time.sleep(0.2 * (attempt + 1))
                    continue
                raise last_error
            except (urllib_error.URLError, TimeoutError) as exc:
                last_error = exc
                if attempt < self.config.lmstudio_max_retries:
                    time.sleep(0.2 * (attempt + 1))
                    continue
                raise LMStudioTransportError(f"LM Studio request to {url} failed: {exc}") from exc
        raise LMStudioTransportError(f"LM Studio request to {url} failed: {last_error}")

    def _http_error_message(self, url: str, status_code: int, response_body: str) -> str:
        if status_code == 404:
            return f"LM Studio endpoint was not found: {url}"
        return f"LM Studio request failed with HTTP {status_code}: {response_body[:500]}"

    def _response_preview(self, payload: dict[str, Any]) -> dict[str, Any]:
        preview = dict(payload)
        if "choices" in preview:
            preview["choices"] = preview["choices"][:1]
        return preview


class TranscriptRefiner:
    PROMPT_VERSION = "transcript_cleanup_pii_guard_v3"

    def __init__(self, client: LMStudioClient, config: AppConfig) -> None:
        self.client = client
        self.config = config

    def refine(self, segments: list[TranscriptSegment], profile: ProcessingProfile) -> TranscriptCleanupResult:
        allowed_speaker_ids = sorted({segment.speaker_id for segment in segments})
        schema = {
            "type": "object",
            "properties": {
                "language": {"type": "string"},
                "segments": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "segment_id": {"type": "string"},
                            "text": {"type": "string"},
                            "normalized_text": {"type": "string"},
                            "confidence": {"type": "number"},
                            "edits": {"type": "array", "items": {"type": "string"}},
                            "speaker_id": {"type": "string"},
                            "speaker_change_reason": {"type": "string"},
                        },
                        "required": ["segment_id", "text", "normalized_text", "confidence", "edits", "speaker_id", "speaker_change_reason"],
                        "additionalProperties": False,
                    },
                },
            },
            "required": ["language", "segments"],
            "additionalProperties": False,
        }
        payload = {
            "task": (
                "Clean up ASR transcript text while preserving timing, wording, and segment structure. "
                "Fix only probable ASR slips, punctuation, casing, domain wording, and spoken Russian numerals when confidence is high and when it improves downstream PII detection. "
                "Treat PII candidates as fragile tokens: never shorten, paraphrase, or partially rewrite them. "
                "Do not merge or split segments. "
                "Keep complete boundaries for PERSON_NAME, ADDRESS, PLACE_OF_BIRTH, RU_PASSPORT_ISSUER, DATE_OF_BIRTH, PHONE, EMAIL, RU_PASSPORT, RU_PASSPORT_UNIT_CODE, RU_INN, RU_SNILS, CARD_NUMBER, BANK_ACCOUNT. "
                "Never invent missing digits or letters. If uncertain, keep the original text. "
                "You may reassign a segment speaker only to one of the allowed speaker ids when the current attribution is clearly inconsistent with adjacent segments."
            ),
            "entity_hints": {
                "PERSON_NAME": "2-3 contiguous Russian name words, often surname+name+patronymic.",
                "DATE_OF_BIRTH": "DD.MM.YYYY, DD-MM-YYYY, DD/MM/YYYY, or textual dates like 12 марта 1987.",
                "PLACE_OF_BIRTH": "After triggers место рождения, родился в, родилась в, родом из, уроженец, уроженка.",
                "RU_PASSPORT": "10 digits total, often near паспорт, серия, номер.",
                "RU_PASSPORT_ISSUER": "Long phrase after выдан or кем выдан until code/date/series/number.",
                "RU_PASSPORT_UNIT_CODE": "NNN-NNN or NNN NNN near код подразделения.",
                "RU_INN": "10 or 12 digits near ИНН.",
                "RU_SNILS": "XXX-XXX-XXX YY or 11 digits near СНИЛС.",
                "PHONE": "+7/8/7 and 10-11 digits, maybe spoken in Russian words.",
                "EMAIL": "Local part + @ + domain, maybe spoken as собака / точка / тире / подчерк.",
                "ADDRESS": "Multi-token address chain with city/street/house/building/apartment.",
                "CARD_NUMBER": "16-19 digits, often in 4-digit blocks, maybe near CVV/CVC.",
                "BANK_ACCOUNT": "20 digits near счет/расчетный/лицевой/банк.",
            },
            "allowed_speaker_ids": allowed_speaker_ids,
            "segments": [
                {
                    "segment_id": segment.segment_id,
                    "speaker_id": segment.speaker_id,
                    "start_ms": segment.start_ms,
                    "end_ms": segment.end_ms,
                    "text": segment.text,
                }
                for segment in segments
            ],
        }
        response, trace = self.client.chat_json(
            model=profile.lmstudio_request_overrides.get("llm_model", self.config.lmstudio_llm_model),
            system_prompt=(
                "Return valid JSON only. Never change segment ids, segment order, or timing. "
                "Only use speaker ids from allowed_speaker_ids. "
                "Do not crop sensitive spans. Preserve complete names, dates, places, addresses, document issuers, emails, phones, passports, SNILS, INN, card and bank account numbers."
            ),
            user_payload=payload,
            schema=schema,
            prompt_version=self.PROMPT_VERSION,
            overrides={**profile.lmstudio_request_overrides, "llm_transport_mode": profile.llm_transport_mode},
        )
        cleaned_segments = response.get("segments")
        if not isinstance(cleaned_segments, list):
            raise LMStudioSchemaError("Transcript cleanup response is missing segments array")
        source_by_id = {segment.segment_id: segment for segment in segments}
        output_segments: list[TranscriptSegment] = []
        edits_applied: list[dict[str, Any]] = []
        speaker_changes: list[dict[str, Any]] = []
        for item in cleaned_segments:
            if not isinstance(item, dict):
                raise LMStudioSchemaError("Transcript cleanup returned a non-object segment")
            segment_id = str(item.get("segment_id") or "")
            if segment_id not in source_by_id:
                raise LMStudioSchemaError(f"Transcript cleanup returned unknown segment_id: {segment_id}")
            original = source_by_id[segment_id]
            cleaned_text = str(item.get("normalized_text") or item.get("text") or "").strip()
            if not cleaned_text:
                raise LMStudioSchemaError(f"Transcript cleanup returned empty text for segment {segment_id}")
            cleaned_speaker_id = str(item.get("speaker_id") or original.speaker_id).strip()
            if cleaned_speaker_id not in allowed_speaker_ids:
                raise LMStudioSchemaError(f"Transcript cleanup returned unknown speaker_id for segment {segment_id}: {cleaned_speaker_id}")
            words = _remap_words_preserving_timing(
                cleaned_text=cleaned_text,
                original_words=original.words,
                speaker_id=cleaned_speaker_id,
                channel_id=original.channel_id,
                start_ms=original.start_ms,
                end_ms=original.end_ms,
            )
            confidence = _coerce_float(item.get("confidence"), original.avg_confidence or 0.9)
            output_segments.append(
                TranscriptSegment(
                    segment_id=original.segment_id,
                    speaker_id=cleaned_speaker_id,
                    start_ms=original.start_ms,
                    end_ms=original.end_ms,
                    text=cleaned_text,
                    words=words,
                    avg_confidence=confidence,
                    overlap=original.overlap,
                    channel_id=original.channel_id,
                )
            )
            edits_applied.append(
                {
                    "segment_id": original.segment_id,
                    "original_text": original.text,
                    "cleaned_text": cleaned_text,
                    "edits": item.get("edits") or [],
                }
            )
            if cleaned_speaker_id != original.speaker_id:
                speaker_changes.append(
                    {
                        "segment_id": original.segment_id,
                        "from_speaker_id": original.speaker_id,
                        "to_speaker_id": cleaned_speaker_id,
                        "reason": str(item.get("speaker_change_reason") or "").strip(),
                    }
                )
        if set(source_by_id) != {segment.segment_id for segment in output_segments}:
            raise LMStudioSchemaError("Transcript cleanup response did not cover all input segments")
        output_segments.sort(key=lambda segment: segment.start_ms)
        return TranscriptCleanupResult(
            segments=output_segments,
            language=str(response.get("language") or "ru"),
            prompt_version=self.PROMPT_VERSION,
            trace=trace,
            edits_applied=edits_applied,
            speaker_changes=speaker_changes,
            validation_report={
                "input_segments": len(segments),
                "output_segments": len(output_segments),
                "allowed_speaker_ids": allowed_speaker_ids,
                "speaker_changes": len(speaker_changes),
            },
            raw_response=response,
        )


class LlmNerRecognizer:
    PROMPT_VERSION = "pii_ner_ru_span_v2"
    ALLOWED_TYPES = [
        "PERSON_NAME",
        "DATE_OF_BIRTH",
        "PLACE_OF_BIRTH",
        "RU_PASSPORT",
        "RU_PASSPORT_ISSUER",
        "RU_PASSPORT_UNIT_CODE",
        "RU_INN",
        "RU_SNILS",
        "PHONE",
        "EMAIL",
        "ADDRESS",
        "CARD_NUMBER",
        "BANK_ACCOUNT",
    ]

    def __init__(self, client: LMStudioClient, config: AppConfig) -> None:
        self.client = client
        self.config = config

    def detect(self, segments: list[TranscriptSegment], profile: ProcessingProfile) -> LlmNerResult:
        schema = {
            "type": "object",
            "properties": {
                "entities": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "segment_id": {"type": "string"},
                            "type": {"type": "string", "enum": self.ALLOWED_TYPES},
                            "text": {"type": "string"},
                            "normalized_value": {"type": "string"},
                            "reasoning_short": {"type": "string"},
                            "confidence": {"type": "number"},
                        },
                        "required": ["segment_id", "type", "text", "normalized_value", "reasoning_short", "confidence"],
                        "additionalProperties": False,
                    },
                }
            },
            "required": ["entities"],
            "additionalProperties": False,
        }
        payload = {
            "task": (
                "Find only these entity types in the cleaned Russian transcript: "
                + ", ".join(self.ALLOWED_TYPES)
                + ". Return only spans explicitly present in the segment text. "
                "Choose the shortest complete span that fully covers the entity. "
                "Do not return inner fragments if the entity clearly continues. "
                "Do not guess, restore, or invent missing symbols."
            ),
            "entity_hints": {
                "PERSON_NAME": "2-3 contiguous person-name words, often surname+name+patronymic.",
                "DATE_OF_BIRTH": "Numeric or textual birth dates after date-of-birth triggers.",
                "PLACE_OF_BIRTH": "Location phrase after birth-place triggers; can include city/region/republic.",
                "RU_PASSPORT": "Series+number, usually 10 digits total.",
                "RU_PASSPORT_ISSUER": "Issuer phrase after выдан/кем выдан up to stop trigger.",
                "RU_PASSPORT_UNIT_CODE": "NNN-NNN or NNN NNN near код подразделения.",
                "RU_INN": "10 or 12 digits near ИНН.",
                "RU_SNILS": "11 digits or XXX-XXX-XXX YY.",
                "PHONE": "Phone number in digits or Russian spoken numerals.",
                "EMAIL": "Literal email or spoken email tokens like собака/точка.",
                "ADDRESS": "Continuous address phrase with city/street/house/apartment markers.",
                "CARD_NUMBER": "16-19 digits, often bank card.",
                "BANK_ACCOUNT": "20 digits, bank account context.",
            },
            "few_shots": [
                {"segment": "ФИО Иванов Петр Сергеевич дата рождения 12 марта 1987", "entities": [{"type": "PERSON_NAME", "text": "Иванов Петр Сергеевич"}, {"type": "DATE_OF_BIRTH", "text": "12 марта 1987"}]},
                {"segment": "место рождения город Нижний Новгород Нижегородская область", "entities": [{"type": "PLACE_OF_BIRTH", "text": "город Нижний Новгород Нижегородская область"}]},
                {"segment": "паспорт выдан отделом уфмс россии по городу москве код подразделения 770 001", "entities": [{"type": "RU_PASSPORT_ISSUER", "text": "отделом уфмс россии по городу москве"}, {"type": "RU_PASSPORT_UNIT_CODE", "text": "770 001"}]},
                {"segment": "телефон восемь девять два шесть пять пять пять один два три четыре", "entities": [{"type": "PHONE", "text": "восемь девять два шесть пять пять пять один два три четыре"}]},
                {"segment": "почта иванов точка ии собака майл точка ру", "entities": [{"type": "EMAIL", "text": "иванов точка ии собака майл точка ру"}]},
                {"segment": "адрес город тула улица ленина дом 5 квартира 7", "entities": [{"type": "ADDRESS", "text": "город тула улица ленина дом 5 квартира 7"}]},
                {"segment": "расчетный счет 40817810099910004312 карта 4276 3800 1234 5678", "entities": [{"type": "BANK_ACCOUNT", "text": "40817810099910004312"}, {"type": "CARD_NUMBER", "text": "4276 3800 1234 5678"}]},
            ],
            "segments": [
                {
                    "segment_id": segment.segment_id,
                    "speaker_id": segment.speaker_id,
                    "text": segment.text,
                }
                for segment in segments
            ],
        }
        response, trace = self.client.chat_json(
            model=profile.lmstudio_request_overrides.get("llm_model", self.config.lmstudio_llm_model),
            system_prompt=(
                "Return valid JSON only. Use only the allowed entity types. "
                "Extract literal spans from the segment text. Prefer complete spans over partial ones. "
                "reasoning_short must be concise and use trigger+shape style such as 'выдан+long_org_phrase' or 'spoken_email+delimiter_words'."
            ),
            user_payload=payload,
            schema=schema,
            prompt_version=self.PROMPT_VERSION,
            overrides={**profile.lmstudio_request_overrides, "llm_transport_mode": profile.llm_transport_mode},
        )
        segment_map = {segment.segment_id: segment for segment in segments}
        entities: list[EntitySpan] = []
        dropped = 0
        mapping_failures: list[dict[str, Any]] = []
        for item in response.get("entities") or []:
            if not isinstance(item, dict):
                raise LMStudioSchemaError("LLM NER returned a non-object entity")
            segment_id = str(item.get("segment_id") or "")
            segment = segment_map.get(segment_id)
            if not segment:
                raise LMStudioSchemaError(f"LLM NER returned unknown segment_id: {segment_id}")
            mapped = self._map_entity_to_span(segment, item)
            if mapped is None:
                dropped += 1
                mapping_failures.append(
                    {
                        "segment_id": segment_id,
                        "type": str(item.get("type") or ""),
                        "text": str(item.get("text") or ""),
                        "normalized_value": str(item.get("normalized_value") or ""),
                    }
                )
                continue
            entities.append(mapped)
        report = {
            "llm_hits": len(entities),
            "dropped_unmapped": dropped,
            "threshold": profile.llm_ner_threshold,
            "mapping_failures": mapping_failures,
        }
        return LlmNerResult(
            entities=entities,
            prompt_version=self.PROMPT_VERSION,
            trace=trace,
            raw_response=response,
            report=report,
        )

    def _map_entity_to_span(self, segment: TranscriptSegment, item: dict[str, Any]) -> EntitySpan | None:
        entity_text = str(item.get("text") or "").strip()
        normalized_value = str(item.get("normalized_value") or entity_text).strip()
        if not entity_text:
            return None
        search_candidates = [entity_text, normalized_value]
        normalized_words = [normalize_token(word.text) for word in segment.words]
        for candidate in search_candidates:
            candidate_tokens = [normalize_token(token) for token in _tokenize_text(candidate)]
            if not candidate_tokens:
                continue
            match = self._find_subsequence(normalized_words, candidate_tokens)
            if match is not None:
                start_index, end_index = match
                return self._build_entity_from_match(segment, item, entity_text, normalized_value, start_index, end_index)
        compact_candidate = normalize_compact_text(entity_text) or normalize_compact_text(normalized_value)
        if compact_candidate:
            compact_words = [normalize_compact_text(word.text) for word in segment.words]
            match = self._find_compact_subsequence(compact_words, compact_candidate)
            if match is not None:
                return self._build_entity_from_match(segment, item, entity_text, normalized_value, match[0], match[1])
        numeric_candidate = digits_only(normalized_value) or digits_only(entity_text)
        if numeric_candidate:
            match = self._find_digits_subsequence(segment, numeric_candidate)
            if match is not None:
                return self._build_entity_from_match(segment, item, entity_text, normalized_value, match[0], match[1])
        if str(item.get("type")) == "EMAIL":
            email_candidate = email_like_normalize(normalized_value or entity_text)
            match = self._find_email_subsequence(segment, email_candidate)
            if match is not None:
                return self._build_entity_from_match(segment, item, entity_text, normalized_value, match[0], match[1])
        if str(item.get("type")) in {"ADDRESS", "RU_PASSPORT_ISSUER", "PLACE_OF_BIRTH", "PERSON_NAME"}:
            match = self._find_fuzzy_contiguous_match(segment, entity_text or normalized_value)
            if match is not None:
                return self._build_entity_from_match(segment, item, entity_text, normalized_value, match[0], match[1])
        return None

    def _find_subsequence(self, haystack: list[str], needle: list[str]) -> tuple[int, int] | None:
        if not needle:
            return None
        for index in range(0, len(haystack) - len(needle) + 1):
            if haystack[index : index + len(needle)] == needle:
                return index, index + len(needle) - 1
        return None

    def _build_entity_from_match(
        self,
        segment: TranscriptSegment,
        item: dict[str, Any],
        entity_text: str,
        normalized_value: str,
        start_index: int,
        end_index: int,
    ) -> EntitySpan:
        return EntitySpan(
            entity_id=make_id("ent"),
            type=str(item["type"]),
            text=entity_text,
            normalized_value=normalized_value,
            speaker_id=segment.speaker_id,
            segment_id=segment.segment_id,
            start_word_index=start_index,
            end_word_index=end_index,
            confidence=_coerce_float(item.get("confidence"), 0.75),
            sources=["qwen_llm_ner", f"reason:{str(item.get('reasoning_short') or '')[:120]}"],
            action="beep_and_mask",
        )

    def _find_compact_subsequence(self, compact_words: list[str], compact_candidate: str) -> tuple[int, int] | None:
        best: tuple[int, int] | None = None
        for start in range(len(compact_words)):
            joined = ""
            for end in range(start, min(len(compact_words), start + 12)):
                joined += compact_words[end]
                if joined == compact_candidate:
                    if best is None or (end - start) > (best[1] - best[0]):
                        best = (start, end)
                    break
                if len(joined) > len(compact_candidate):
                    break
        return best

    def _find_digits_subsequence(self, segment: TranscriptSegment, digits_candidate: str) -> tuple[int, int] | None:
        best: tuple[int, int] | None = None
        for start in range(len(segment.words)):
            joined = ""
            for end in range(start, min(len(segment.words), start + 12)):
                joined += digits_only(segment.words[end].text)
                if joined == digits_candidate:
                    if best is None or (end - start) > (best[1] - best[0]):
                        best = (start, end)
                    break
                if len(joined) > len(digits_candidate):
                    break
        return best

    def _find_email_subsequence(self, segment: TranscriptSegment, email_candidate: str) -> tuple[int, int] | None:
        best: tuple[int, int] | None = None
        for start in range(len(segment.words)):
            for end in range(start, min(len(segment.words), start + 12)):
                if email_like_normalize(" ".join(word.text for word in segment.words[start : end + 1])) == email_candidate:
                    if best is None or (end - start) > (best[1] - best[0]):
                        best = (start, end)
        return best

    def _find_fuzzy_contiguous_match(self, segment: TranscriptSegment, candidate: str) -> tuple[int, int] | None:
        candidate_tokens = [normalize_token(token) for token in _tokenize_text(candidate)]
        if not candidate_tokens:
            return None
        normalized_words = [normalize_token(word.text) for word in segment.words]
        best: tuple[int, int, int, int] | None = None
        for start in range(len(normalized_words)):
            for end in range(start, min(len(normalized_words), start + len(candidate_tokens) + 2)):
                window = normalized_words[start : end + 1]
                overlap = sum(1 for left, right in zip(window, candidate_tokens, strict=False) if left == right)
                mismatches = max(len(window), len(candidate_tokens)) - overlap
                if overlap >= max(2, len(candidate_tokens) - 1) and mismatches <= 2:
                    score = (overlap, end - start)
                    if best is None or score > (best[2], best[3]):
                        best = (start, end, overlap, end - start)
        if best is None:
            return None
        return best[0], best[1]


class PiiMerger:
    HARD_RULE_TYPES = {"PHONE", "RU_INN", "RU_SNILS", "RU_PASSPORT"}
    TOKEN_NER_PRIORITY_TYPES = {"PERSON_NAME", "DATE_OF_BIRTH", "PLACE_OF_BIRTH", "RU_PASSPORT_ISSUER", "RU_PASSPORT_UNIT_CODE", "ADDRESS"}
    EXPANDABLE_TYPES = {"ADDRESS", "RU_PASSPORT_ISSUER", "PLACE_OF_BIRTH", "PERSON_NAME"}

    def merge(
        self,
        *,
        rule_entities: list[EntitySpan],
        token_ner_entities: list[EntitySpan],
        llm_entities: list[EntitySpan],
        llm_threshold: float,
        action_mode: str,
    ) -> tuple[list[EntitySpan], dict[str, Any], list[dict[str, Any]]]:
        merged = list(rule_entities)
        conflicts: list[dict[str, Any]] = []
        decisions: list[dict[str, Any]] = [{"entity_id": entity.entity_id, "decision": "accepted", "reason": "rule_base"} for entity in rule_entities]
        accepted_token_ner = 0
        rejected_token_ner = 0
        accepted_llm = 0
        rejected_llm = 0

        for entity in token_ner_entities:
            entity.action = "mute_and_mask" if action_mode == "mute" else "beep_and_mask"
            conflict = next(
                (
                    existing
                    for existing in merged
                    if existing.segment_id == entity.segment_id
                    and not (entity.end_word_index < existing.start_word_index or entity.start_word_index > existing.end_word_index)
                ),
                None,
            )
            if conflict is None:
                merged.append(entity)
                accepted_token_ner += 1
                decisions.append({"entity_id": entity.entity_id, "decision": "accepted", "reason": "token_ner_no_conflict"})
                continue
            if conflict.type in self.HARD_RULE_TYPES:
                conflicts.append({"winner": conflict.entity_id, "dropped": entity.entity_id, "reason": "hard_rule_priority_over_token_ner"})
                decisions.append({"entity_id": entity.entity_id, "decision": "rejected", "reason": "hard_rule_priority"})
                rejected_token_ner += 1
                continue
            if entity.type == conflict.type and entity.type in self.EXPANDABLE_TYPES:
                conflict.start_word_index = min(conflict.start_word_index, entity.start_word_index)
                conflict.end_word_index = max(conflict.end_word_index, entity.end_word_index)
                conflict.confidence = max(conflict.confidence, entity.confidence)
                conflict.sources.extend(source for source in entity.sources if source not in conflict.sources)
                if len(entity.text) > len(conflict.text):
                    conflict.text = entity.text
                    conflict.normalized_value = entity.normalized_value
                accepted_token_ner += 1
                decisions.append({"entity_id": entity.entity_id, "decision": "accepted", "reason": "token_ner_expanded_existing"})
                continue
            if entity.type == conflict.type and entity.confidence >= conflict.confidence:
                conflict.start_word_index = min(conflict.start_word_index, entity.start_word_index)
                conflict.end_word_index = max(conflict.end_word_index, entity.end_word_index)
                conflict.confidence = max(conflict.confidence, entity.confidence)
                conflict.sources.extend(source for source in entity.sources if source not in conflict.sources)
                if len(entity.normalized_value) > len(conflict.normalized_value):
                    conflict.normalized_value = entity.normalized_value
                    conflict.text = entity.text
                accepted_token_ner += 1
                decisions.append({"entity_id": entity.entity_id, "decision": "accepted", "reason": "token_ner_enriched_existing"})
                continue
            if entity.type in self.TOKEN_NER_PRIORITY_TYPES and conflict.type not in self.HARD_RULE_TYPES and entity.confidence > conflict.confidence:
                conflicts.append({"winner": entity.entity_id, "dropped": conflict.entity_id, "reason": "token_ner_priority"})
                merged.remove(conflict)
                merged.append(entity)
                accepted_token_ner += 1
                decisions.append({"entity_id": entity.entity_id, "decision": "accepted", "reason": "token_ner_priority"})
                decisions.append({"entity_id": conflict.entity_id, "decision": "rejected", "reason": "replaced_by_token_ner"})
            else:
                conflicts.append({"winner": conflict.entity_id, "dropped": entity.entity_id, "reason": "existing_span_kept_over_token_ner"})
                decisions.append({"entity_id": entity.entity_id, "decision": "rejected", "reason": "existing_span_kept"})
                rejected_token_ner += 1

        for entity in llm_entities:
            if entity.confidence < llm_threshold:
                rejected_llm += 1
                decisions.append({"entity_id": entity.entity_id, "decision": "rejected", "reason": "below_llm_threshold"})
                continue
            entity.action = "mute_and_mask" if action_mode == "mute" else "beep_and_mask"
            conflict = next(
                (
                    existing
                    for existing in merged
                    if existing.segment_id == entity.segment_id
                    and not (entity.end_word_index < existing.start_word_index or entity.start_word_index > existing.end_word_index)
                ),
                None,
            )
            if conflict is None:
                merged.append(entity)
                accepted_llm += 1
                decisions.append({"entity_id": entity.entity_id, "decision": "accepted", "reason": "llm_no_conflict"})
                continue
            if conflict.type in self.HARD_RULE_TYPES and conflict.type == entity.type:
                conflict.start_word_index = min(conflict.start_word_index, entity.start_word_index)
                conflict.end_word_index = max(conflict.end_word_index, entity.end_word_index)
                conflict.confidence = max(conflict.confidence, entity.confidence)
                conflict.sources.extend(source for source in entity.sources if source not in conflict.sources)
                if len(entity.normalized_value) > len(conflict.normalized_value):
                    conflict.normalized_value = entity.normalized_value
                    conflict.text = entity.text
                conflicts.append(
                    {
                        "winner": conflict.entity_id,
                        "dropped": entity.entity_id,
                        "reason": "hard_rule_enriched_by_llm",
                    }
                )
                accepted_llm += 1
                decisions.append({"entity_id": entity.entity_id, "decision": "accepted", "reason": "llm_enriched_hard_rule"})
                continue
            if entity.type == conflict.type and entity.type in self.EXPANDABLE_TYPES and entity.confidence >= max(llm_threshold, conflict.confidence - 0.05):
                conflict.start_word_index = min(conflict.start_word_index, entity.start_word_index)
                conflict.end_word_index = max(conflict.end_word_index, entity.end_word_index)
                conflict.confidence = max(conflict.confidence, entity.confidence)
                conflict.sources.extend(source for source in entity.sources if source not in conflict.sources)
                if len(entity.text) > len(conflict.text):
                    conflict.text = entity.text
                    conflict.normalized_value = entity.normalized_value
                conflicts.append({"winner": conflict.entity_id, "dropped": entity.entity_id, "reason": "llm_expanded_existing"})
                accepted_llm += 1
                decisions.append({"entity_id": entity.entity_id, "decision": "accepted", "reason": "llm_expanded_existing"})
                continue
            if conflict.type in self.HARD_RULE_TYPES:
                conflict.sources.append("llm_conflict_seen")
                conflicts.append(
                    {
                        "winner": conflict.entity_id,
                        "dropped": entity.entity_id,
                        "reason": "hard_rule_priority",
                    }
                )
                rejected_llm += 1
                decisions.append({"entity_id": entity.entity_id, "decision": "rejected", "reason": "hard_rule_priority"})
                continue
            if entity.type == conflict.type and entity.confidence > conflict.confidence:
                conflict.sources.extend(source for source in entity.sources if source not in conflict.sources)
                conflict.confidence = entity.confidence
                conflict.normalized_value = entity.normalized_value
                conflict.text = entity.text
                accepted_llm += 1
                decisions.append({"entity_id": entity.entity_id, "decision": "accepted", "reason": "llm_enriched_existing"})
                continue
            if entity.confidence > conflict.confidence and conflict.type not in self.HARD_RULE_TYPES:
                conflicts.append({"winner": entity.entity_id, "dropped": conflict.entity_id, "reason": "higher_confidence"})
                merged.remove(conflict)
                merged.append(entity)
                accepted_llm += 1
                decisions.append({"entity_id": entity.entity_id, "decision": "accepted", "reason": "llm_higher_confidence"})
                decisions.append({"entity_id": conflict.entity_id, "decision": "rejected", "reason": "replaced_by_llm"})
            else:
                conflicts.append({"winner": conflict.entity_id, "dropped": entity.entity_id, "reason": "existing_span_kept"})
                rejected_llm += 1
                decisions.append({"entity_id": entity.entity_id, "decision": "rejected", "reason": "existing_span_kept"})

        merged.sort(key=lambda item: (item.segment_id, item.start_word_index, item.end_word_index))
        return merged, {
            "rule_hits": len(rule_entities),
            "token_ner_hits": len(token_ner_entities),
            "llm_hits": len(llm_entities),
            "merged_hits": len(merged),
            "accepted_token_ner_hits": accepted_token_ner,
            "rejected_token_ner_hits": rejected_token_ner,
            "accepted_llm_hits": accepted_llm,
            "rejected_llm_hits": rejected_llm,
            "conflicts": conflicts,
        }, decisions


class SummaryGenerator:
    PROMPT_VERSION = "redacted_summary_v1"

    def __init__(self, client: LMStudioClient, config: AppConfig) -> None:
        self.client = client
        self.config = config

    def generate(self, segments: list[TranscriptSegment], profile: ProcessingProfile) -> SummaryResult:
        schema = {
            "type": "object",
            "properties": {
                "title": {"type": "string"},
                "summary": {"type": "string"},
                "bullets": {"type": "array", "items": {"type": "string"}},
                "confidence": {"type": "number"},
            },
            "required": ["title", "summary", "bullets", "confidence"],
            "additionalProperties": False,
        }
        payload = {
            "task": (
                "Generate a concise internal summary in Russian from the already redacted transcript. "
                "Do not infer or restore redacted values. All fields in the response must be in Russian."
            ),
            "segments": [
                {
                    "segment_id": segment.segment_id,
                    "speaker_id": segment.speaker_id,
                    "text": segment.text,
                }
                for segment in segments
            ],
        }
        response, trace = self.client.chat_json(
            model=profile.lmstudio_request_overrides.get("llm_model", self.config.lmstudio_llm_model),
            system_prompt=(
                "Return valid JSON only. Summarize only the redacted content that is present. "
                "Write the title, summary, and bullets in Russian."
            ),
            user_payload=payload,
            schema=schema,
            prompt_version=self.PROMPT_VERSION,
            overrides=profile.lmstudio_request_overrides,
        )
        title = str(response.get("title") or "").strip()
        summary = str(response.get("summary") or "").strip()
        bullets = [str(item).strip() for item in (response.get("bullets") or []) if str(item).strip()]
        if not title or not summary:
            raise LMStudioSchemaError("Summary response is missing title or summary")
        return SummaryResult(
            title=title,
            summary=summary,
            bullets=bullets,
            confidence=_coerce_float(response.get("confidence"), 0.8),
            prompt_version=self.PROMPT_VERSION,
            trace=trace,
            raw_response=response,
        )
