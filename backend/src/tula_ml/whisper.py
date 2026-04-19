from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any
from urllib import error as urllib_error
from urllib import parse as urllib_parse
from urllib import request as urllib_request
import json
import mimetypes
import time
import uuid

from .config import AppConfig
from .models import AsrResult, ProcessingProfile, TranscriptSegment, TranscriptWord, make_id

DEFAULT_RU_PII_HOTWORDS = (
    "ФИО",
    "дата рождения",
    "место рождения",
    "паспорт",
    "код подразделения",
    "ИНН",
    "СНИЛС",
    "электронная почта",
    "адрес",
    "расчетный счет",
)


class WhisperError(RuntimeError):
    pass


class WhisperTransportError(WhisperError):
    def __init__(self, message: str, *, status_code: int | None = None, response_body: str | None = None) -> None:
        super().__init__(message)
        self.status_code = status_code
        self.response_body = response_body


class WhisperSchemaError(WhisperError):
    pass


def _join_url(base_url: str, path: str) -> str:
    if path.startswith("http://") or path.startswith("https://"):
        return path
    return urllib_parse.urljoin(base_url.rstrip("/") + "/", path.lstrip("/"))


def _build_multipart_form(fields: dict[str, str], file_field: str, file_path: Path) -> tuple[bytes, str]:
    boundary = f"----whisper-{uuid.uuid4().hex}"
    chunks: list[bytes] = []
    for name, value in fields.items():
        chunks.extend(
            [
                f"--{boundary}\r\n".encode("utf-8"),
                f'Content-Disposition: form-data; name="{name}"\r\n\r\n'.encode("utf-8"),
                value.encode("utf-8"),
                b"\r\n",
            ]
        )
    mime_type = mimetypes.guess_type(file_path.name)[0] or "application/octet-stream"
    chunks.extend(
        [
            f"--{boundary}\r\n".encode("utf-8"),
            f'Content-Disposition: form-data; name="{file_field}"; filename="{file_path.name}"\r\n'.encode("utf-8"),
            f"Content-Type: {mime_type}\r\n\r\n".encode("utf-8"),
            file_path.read_bytes(),
            b"\r\n",
            f"--{boundary}--\r\n".encode("utf-8"),
        ]
    )
    return b"".join(chunks), f"multipart/form-data; boundary={boundary}"


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


class WhisperClient:
    def __init__(self, config: AppConfig) -> None:
        self.config = config

    def healthcheck(self) -> tuple[dict[str, Any], RequestTrace]:
        url = _join_url(self.config.whisper_base_url, self.config.whisper_health_path)
        started_at = time.monotonic()
        try:
            with urllib_request.urlopen(url, timeout=self.config.whisper_timeout_seconds) as response:
                payload_bytes = response.read()
        except urllib_error.HTTPError as exc:
            latency_ms = int((time.monotonic() - started_at) * 1000)
            return (
                {
                    "reachable": True,
                    "status_code": exc.code,
                    "body_preview": exc.read().decode("utf-8", errors="replace")[:300],
                },
                RequestTrace(endpoint=url, latency_ms=latency_ms, retry_count=0, response_preview={"status_code": exc.code}),
            )
        except (urllib_error.URLError, TimeoutError) as exc:
            raise WhisperTransportError(f"Whisper server healthcheck failed for {url}: {exc}") from exc

        latency_ms = int((time.monotonic() - started_at) * 1000)
        body_preview = payload_bytes.decode("utf-8", errors="replace")[:300]
        return (
            {"reachable": True, "status_code": 200, "body_preview": body_preview},
            RequestTrace(endpoint=url, latency_ms=latency_ms, retry_count=0, response_preview={"body_preview": body_preview}),
        )

    def transcribe_audio(
        self,
        *,
        audio_path: Path,
        language: str,
        overrides: dict[str, Any] | None = None,
    ) -> tuple[dict[str, Any], RequestTrace]:
        overrides = overrides or {}
        fields = {
            "response_format": str(overrides.get("response_format", self.config.whisper_response_format)),
        }
        effective_language = str(overrides.get("language", language or self.config.whisper_language))
        if effective_language and effective_language != "auto":
            fields["language"] = effective_language
        prompt = str(overrides.get("prompt") or "").strip()
        if prompt:
            fields["prompt"] = prompt
        hotwords = overrides.get("hotwords")
        if isinstance(hotwords, str) and hotwords.strip():
            fields["prompt"] = f"{fields.get('prompt', '')} {hotwords}".strip()
        temperature = overrides.get("temperature")
        if temperature is not None:
            fields["temperature"] = str(temperature)
        body, content_type = _build_multipart_form(fields, "file", audio_path)
        return self._request_json(
            "POST",
            overrides.get("transcript_path") or self.config.whisper_transcript_path,
            body=body,
            headers={"Content-Type": content_type},
        )

    def _request_json(
        self,
        method: str,
        path: str,
        *,
        body: bytes | None = None,
        headers: dict[str, str] | None = None,
    ) -> tuple[dict[str, Any], RequestTrace]:
        url = _join_url(self.config.whisper_base_url, path)
        timeout = self.config.whisper_timeout_seconds
        last_error: Exception | None = None
        for attempt in range(self.config.whisper_max_retries + 1):
            started_at = time.monotonic()
            request = urllib_request.Request(url, data=body, method=method, headers=dict(headers or {}))
            try:
                with urllib_request.urlopen(request, timeout=timeout) as response:
                    payload_bytes = response.read()
                    payload = json.loads(payload_bytes.decode("utf-8"))
                    latency_ms = int((time.monotonic() - started_at) * 1000)
                    return payload, RequestTrace(
                        endpoint=url,
                        latency_ms=latency_ms,
                        retry_count=attempt,
                        response_preview=self._response_preview(payload),
                    )
            except urllib_error.HTTPError as exc:
                response_body = exc.read().decode("utf-8", errors="replace")
                last_error = WhisperTransportError(
                    self._http_error_message(url, exc.code, response_body),
                    status_code=exc.code,
                    response_body=response_body,
                )
                if exc.code >= 500 and attempt < self.config.whisper_max_retries:
                    time.sleep(0.2 * (attempt + 1))
                    continue
                raise last_error
            except (urllib_error.URLError, TimeoutError, json.JSONDecodeError) as exc:
                last_error = exc
                if attempt < self.config.whisper_max_retries:
                    time.sleep(0.2 * (attempt + 1))
                    continue
                raise WhisperTransportError(f"Whisper request to {url} failed: {exc}") from exc
        raise WhisperTransportError(f"Whisper request to {url} failed: {last_error}")

    def _http_error_message(self, url: str, status_code: int, response_body: str) -> str:
        if status_code == 404:
            return f"Whisper endpoint was not found: {url}"
        return f"Whisper request failed with HTTP {status_code}: {response_body[:500]}"

    def _response_preview(self, payload: dict[str, Any]) -> dict[str, Any]:
        preview = dict(payload)
        if "segments" in preview and isinstance(preview["segments"], list):
            preview["segments"] = preview["segments"][:2]
        if "result" in preview and isinstance(preview["result"], list):
            preview["result"] = preview["result"][:2]
        return preview


class WhisperRuntimeValidator:
    def __init__(self, client: WhisperClient, config: AppConfig) -> None:
        self.client = client
        self.config = config

    def validate(self) -> dict[str, Any]:
        report, trace = self.client.healthcheck()
        result = {
            "whisper_base_url": self.config.whisper_base_url,
            "whisper_transcript_path": self.config.whisper_transcript_path,
            "whisper_model_name": self.config.whisper_model_name,
            "healthcheck": report,
            "trace": {
                "endpoint": trace.endpoint,
                "latency_ms": trace.latency_ms,
                "retry_count": trace.retry_count,
            },
        }
        if self.config.whisper_model_path:
            model_path = Path(self.config.whisper_model_path)
            if not model_path.exists():
                raise WhisperTransportError(f"Configured Whisper model file is missing: {model_path}")
            result["model_path"] = str(model_path)
        return result


class AsrTranscriber:
    def __init__(self, client: WhisperClient, config: AppConfig) -> None:
        self.client = client
        self.config = config

    def transcribe(
        self,
        *,
        audio_path: Path,
        duration_ms: int,
        speaker_id: str,
        channel_id: int | None,
        profile: ProcessingProfile,
        trace_id: str,
    ) -> tuple[AsrResult, RequestTrace]:
        overrides = dict(profile.whisper_request_overrides)
        effective_hotwords = list(profile.asr_hotwords or [])
        for hotword in DEFAULT_RU_PII_HOTWORDS:
            if hotword not in effective_hotwords:
                effective_hotwords.append(hotword)
        if effective_hotwords and "hotwords" not in overrides:
            overrides["hotwords"] = " ".join(effective_hotwords)
        if "prompt" not in overrides:
            overrides["prompt"] = "Точная русская транскрибация персональных данных, имен, адресов, документов, телефонов, email и банковских реквизитов."
        response, request_trace = self.client.transcribe_audio(
            audio_path=audio_path,
            language=profile.language if profile.language != "auto" else self.config.whisper_language,
            overrides=overrides,
        )
        text = str(response.get("text") or response.get("transcript") or "").strip()
        language = str(response.get("language") or (profile.language if profile.language != "auto" else self.config.whisper_language))
        raw_segments = response.get("segments") or response.get("result")
        raw_words = response.get("words")
        model_name = f"whisper.cpp/{self.config.whisper_model_name}"
        model_version = Path(self.config.whisper_model_path).name if self.config.whisper_model_path else "whisper-server"
        timing_mode = "word_timestamps_native"

        if isinstance(raw_segments, list) and raw_segments:
            segments: list[TranscriptSegment] = []
            all_words: list[TranscriptWord] = []
            for index, item in enumerate(raw_segments):
                if not isinstance(item, dict):
                    continue
                segment_text = str(item.get("text") or "").strip()
                start_ms = self._segment_timestamp_ms(item, ("start", "from", "t0"), index, duration_ms)
                end_ms = self._segment_timestamp_ms(item, ("end", "to", "t1"), start_ms + 500, duration_ms)
                segment_words = self._extract_words(
                    raw_words=item.get("words"),
                    fallback_text=segment_text,
                    speaker_id=speaker_id,
                    channel_id=channel_id,
                    start_ms=start_ms,
                    end_ms=end_ms,
                )
                if not item.get("words"):
                    timing_mode = "segment_distributed_timestamps"
                segments.append(
                    TranscriptSegment(
                        segment_id=make_id("seg"),
                        speaker_id=speaker_id,
                        start_ms=start_ms,
                        end_ms=end_ms,
                        text=segment_text,
                        words=segment_words,
                        avg_confidence=sum(word.confidence for word in segment_words) / len(segment_words) if segment_words else 0.0,
                        overlap=False,
                        channel_id=channel_id,
                    )
                )
                all_words.extend(segment_words)
            if segments:
                return (
                    AsrResult(
                        segments=segments,
                        words=all_words,
                        language_detected=language,
                        model_name=model_name,
                        model_version=model_version,
                        timing_mode=timing_mode,
                        raw_response=response,
                    ),
                    request_trace,
                )

        if isinstance(raw_words, list) and raw_words:
            words = self._extract_words(
                raw_words=raw_words,
                fallback_text=text,
                speaker_id=speaker_id,
                channel_id=channel_id,
                start_ms=0,
                end_ms=duration_ms,
            )
            segment_text = " ".join(word.text for word in words) if words else text
            segment = TranscriptSegment(
                segment_id=make_id("seg"),
                speaker_id=speaker_id,
                start_ms=0,
                end_ms=duration_ms,
                text=segment_text,
                words=words,
                avg_confidence=sum(word.confidence for word in words) / len(words) if words else 0.0,
                overlap=False,
                channel_id=channel_id,
            )
            return (
                AsrResult(
                    segments=[segment],
                    words=words,
                    language_detected=language,
                    model_name=model_name,
                    model_version=model_version,
                    timing_mode="word_timestamps_native",
                    raw_response=response,
                ),
                request_trace,
            )

        if not text:
            raise WhisperSchemaError("Whisper response did not include transcript text")
        words = _distribute_words(
            text=text,
            speaker_id=speaker_id,
            channel_id=channel_id,
            start_ms=0,
            end_ms=duration_ms,
        )
        segment = TranscriptSegment(
            segment_id=make_id("seg"),
            speaker_id=speaker_id,
            start_ms=0,
            end_ms=duration_ms,
            text=text,
            words=words,
            avg_confidence=0.9 if words else 0.0,
            overlap=False,
            channel_id=channel_id,
        )
        return (
            AsrResult(
                segments=[segment],
                words=words,
                language_detected=language,
                model_name=model_name,
                model_version=model_version,
                timing_mode="segment_distributed_timestamps",
                raw_response=response,
            ),
            request_trace,
        )

    def _segment_timestamp_ms(
        self,
        item: dict[str, Any],
        keys: tuple[str, ...],
        default_ms: int,
        duration_ms: int,
    ) -> int:
        for key in keys:
            if key not in item:
                continue
            value = item[key]
            if key in {"t0", "t1"}:
                return int(value) * 10
            numeric = _coerce_float(value, float(default_ms))
            if numeric <= duration_ms / 1000 + 1:
                return int(round(numeric * 1000))
            return int(round(numeric))
        return int(default_ms)

    def _extract_words(
        self,
        *,
        raw_words: Any,
        fallback_text: str,
        speaker_id: str,
        channel_id: int | None,
        start_ms: int,
        end_ms: int,
    ) -> list[TranscriptWord]:
        if not isinstance(raw_words, list) or not raw_words:
            return _distribute_words(
                text=fallback_text,
                speaker_id=speaker_id,
                channel_id=channel_id,
                start_ms=start_ms,
                end_ms=end_ms,
            )
        words: list[TranscriptWord] = []
        for word in raw_words:
            if not isinstance(word, dict):
                continue
            text = str(word.get("word") or word.get("text") or "").strip()
            if not text:
                continue
            start_value = word.get("start", word.get("from"))
            end_value = word.get("end", word.get("to"))
            word_start_ms = int(round(_coerce_float(start_value, start_ms / 1000) * 1000)) if start_value is not None else start_ms
            word_end_ms = int(round(_coerce_float(end_value, end_ms / 1000) * 1000)) if end_value is not None else end_ms
            words.append(
                TranscriptWord(
                    text=text,
                    start_ms=word_start_ms,
                    end_ms=word_end_ms,
                    confidence=_coerce_float(word.get("confidence"), 0.9),
                    speaker_id=speaker_id,
                    channel_id=channel_id,
                )
            )
        if not words:
            return _distribute_words(
                text=fallback_text,
                speaker_id=speaker_id,
                channel_id=channel_id,
                start_ms=start_ms,
                end_ms=end_ms,
            )
        return words
