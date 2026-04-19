from __future__ import annotations

from array import array
from dataclasses import dataclass
from pathlib import Path
from statistics import median
from typing import Any
from urllib import error as urllib_error
from urllib import parse as urllib_parse
from urllib import request as urllib_request
import json
import math
import mimetypes
import time
import uuid
import wave

from .config import AppConfig


class DiarizationError(RuntimeError):
    pass


@dataclass(slots=True)
class DiarizationResult:
    speaker_segments: list[dict[str, Any]]
    detected_speaker_count: int
    overlap_regions: list[dict[str, int]]
    strategy: str
    degraded: bool
    quality_report: dict[str, Any]
    model_name: str = "heuristic-mono-diarizer"
    model_version: str = "energy-zcr-v1"


@dataclass(slots=True)
class DiarizationTrace:
    endpoint: str
    latency_ms: int
    retry_count: int
    response_preview: dict[str, Any]


@dataclass(slots=True)
class _WindowFeatures:
    start_ms: int
    end_ms: int
    rms: float
    dominant_hz: float
    voiced: bool


def _join_url(base_url: str, path: str) -> str:
    if path.startswith("http://") or path.startswith("https://"):
        return path
    return urllib_parse.urljoin(base_url.rstrip("/") + "/", path.lstrip("/"))


def _build_multipart_form(file_path: Path) -> tuple[bytes, str]:
    boundary = f"----diarization-{uuid.uuid4().hex}"
    mime_type = mimetypes.guess_type(file_path.name)[0] or "application/octet-stream"
    body = (
        f"--{boundary}\r\n"
        f'Content-Disposition: form-data; name="file"; filename="{file_path.name}"\r\n'
        f"Content-Type: {mime_type}\r\n\r\n"
    ).encode("utf-8") + file_path.read_bytes() + f"\r\n--{boundary}--\r\n".encode("utf-8")
    return body, f"multipart/form-data; boundary={boundary}"


class RemoteDiarizationClient:
    def __init__(self, config: AppConfig) -> None:
        self.config = config

    def healthcheck(self) -> dict[str, Any]:
        if not self.config.diarization_base_url:
            raise DiarizationError("DIARIZATION_BASE_URL is not configured")
        url = _join_url(self.config.diarization_base_url, self.config.diarization_health_path)
        started_at = time.monotonic()
        request = urllib_request.Request(url, method="GET")
        try:
            with urllib_request.urlopen(request, timeout=self.config.diarization_timeout_seconds) as response:
                payload = json.loads(response.read().decode("utf-8"))
                return {
                    "ready": True,
                    "endpoint": url,
                    "status_code": getattr(response, "status", 200),
                    "latency_ms": int((time.monotonic() - started_at) * 1000),
                    "payload": payload,
                }
        except urllib_error.HTTPError as exc:
            raise DiarizationError(f"Diarization healthcheck failed with HTTP {exc.code}") from exc
        except (urllib_error.URLError, TimeoutError, json.JSONDecodeError) as exc:
            raise DiarizationError(f"Diarization healthcheck failed: {exc}") from exc

    def diarize(self, audio_path: Path) -> tuple[DiarizationResult, DiarizationTrace]:
        if not self.config.diarization_base_url:
            raise DiarizationError("DIARIZATION_BASE_URL is not configured")
        body, content_type = _build_multipart_form(audio_path)
        url = _join_url(self.config.diarization_base_url, self.config.diarization_path)
        last_error: Exception | None = None
        for attempt in range(self.config.diarization_max_retries + 1):
            started_at = time.monotonic()
            request = urllib_request.Request(url, data=body, method="POST", headers={"Content-Type": content_type})
            try:
                with urllib_request.urlopen(request, timeout=self.config.diarization_timeout_seconds) as response:
                    payload = json.loads(response.read().decode("utf-8"))
                    trace = DiarizationTrace(
                        endpoint=url,
                        latency_ms=int((time.monotonic() - started_at) * 1000),
                        retry_count=attempt,
                        response_preview={"speaker_segments": (payload.get("speaker_segments") or [])[:2]},
                    )
                    return self._parse_payload(payload), trace
            except urllib_error.HTTPError as exc:
                last_error = DiarizationError(f"Diarization request failed with HTTP {exc.code}: {exc.read().decode('utf-8', errors='replace')[:200]}")
                if exc.code >= 500 and attempt < self.config.diarization_max_retries:
                    time.sleep(0.2 * (attempt + 1))
                    continue
                raise last_error
            except (urllib_error.URLError, TimeoutError, json.JSONDecodeError) as exc:
                last_error = exc
                if attempt < self.config.diarization_max_retries:
                    time.sleep(0.2 * (attempt + 1))
                    continue
                raise DiarizationError(f"Diarization request to {url} failed: {exc}") from exc
        raise DiarizationError(f"Diarization request to {url} failed: {last_error}")

    def _parse_payload(self, payload: dict[str, Any]) -> DiarizationResult:
        speaker_segments = payload.get("speaker_segments")
        if not isinstance(speaker_segments, list) or not speaker_segments:
            raise DiarizationError("Diarization response is missing speaker_segments")
        return DiarizationResult(
            speaker_segments=speaker_segments,
            detected_speaker_count=int(payload.get("detected_speaker_count", len({item["speaker_id"] for item in speaker_segments if isinstance(item, dict)}))),
            overlap_regions=list(payload.get("overlap_regions") or []),
            strategy=str(payload.get("strategy") or "mono_diarization"),
            degraded=bool(payload.get("degraded", False)),
            quality_report=dict(payload.get("quality_report") or {}),
            model_name=str(payload.get("model_name") or "remote-diarization-service"),
            model_version=str(payload.get("model_version") or "v1"),
        )


class MonoHeuristicDiarizer:
    def __init__(self, config: AppConfig) -> None:
        self.config = config

    def diarize(self, audio_path: Path) -> DiarizationResult:
        samples, sample_rate = self._read_pcm_mono(audio_path)
        if not samples:
            return self._single_speaker(duration_ms=0, degraded=True, reason="empty_audio")

        duration_ms = int(round(len(samples) / sample_rate * 1000))
        windows = self._extract_windows(samples=samples, sample_rate=sample_rate, duration_ms=duration_ms)
        voiced_windows = [window for window in windows if window.voiced]
        if len(voiced_windows) < 2:
            return self._single_speaker(
                duration_ms=duration_ms,
                degraded=True,
                reason="insufficient_voiced_windows",
                extra={"voiced_window_count": len(voiced_windows)},
            )

        dominant_values = [window.dominant_hz for window in voiced_windows]
        min_hz = min(dominant_values)
        max_hz = max(dominant_values)
        hz_range = max_hz - min_hz
        if hz_range < self.config.diarization_frequency_delta_hz:
            return self._single_speaker(
                duration_ms=duration_ms,
                degraded=True,
                reason="frequency_separation_too_small",
                extra={
                    "voiced_window_count": len(voiced_windows),
                    "dominant_hz_range": round(hz_range, 2),
                },
            )

        pivot = median(dominant_values)
        labeled_windows: list[dict[str, Any]] = []
        for window in windows:
            if window.voiced:
                speaker_id = "spk_0" if window.dominant_hz <= pivot else "spk_1"
            else:
                speaker_id = labeled_windows[-1]["speaker_id"] if labeled_windows else "spk_0"
            labeled_windows.append(
                {
                    "speaker_id": speaker_id,
                    "start_ms": window.start_ms,
                    "end_ms": window.end_ms,
                    "channel_id": None,
                    "overlap": False,
                    "voiced": window.voiced,
                    "dominant_hz": round(window.dominant_hz, 2),
                }
            )

        speaker_segments = self._merge_windows(labeled_windows, duration_ms=duration_ms)
        detected_speakers = sorted({segment["speaker_id"] for segment in speaker_segments})
        degraded = len(detected_speakers) < 2
        quality_report = {
            "voiced_window_count": len(voiced_windows),
            "dominant_hz_range": round(hz_range, 2),
            "frequency_split_hz": round(float(pivot), 2),
            "speaker_window_counts": {
                speaker_id: sum(1 for window in labeled_windows if window["speaker_id"] == speaker_id and window["voiced"])
                for speaker_id in {"spk_0", "spk_1"}
            },
        }
        return DiarizationResult(
            speaker_segments=speaker_segments,
            detected_speaker_count=len(detected_speakers),
            overlap_regions=[],
            strategy="mono_diarization",
            degraded=degraded,
            quality_report=quality_report,
            model_name="heuristic-mono-diarizer",
            model_version="energy-zcr-v1",
        )

    def _read_pcm_mono(self, audio_path: Path) -> tuple[list[int], int]:
        try:
            with wave.open(str(audio_path), "rb") as wav_file:
                channels = wav_file.getnchannels()
                sample_width = wav_file.getsampwidth()
                sample_rate = wav_file.getframerate()
                frame_count = wav_file.getnframes()
                raw_frames = wav_file.readframes(frame_count)
        except wave.Error as exc:
            raise DiarizationError(f"Unable to read WAV for diarization: {exc}") from exc
        if channels != 1:
            raise DiarizationError(f"Mono diarization expects mono WAV input, got {channels} channels")
        if sample_width != 2:
            raise DiarizationError(f"Mono diarization expects 16-bit PCM WAV input, got {sample_width * 8}-bit")
        pcm = array("h")
        pcm.frombytes(raw_frames)
        return pcm.tolist(), sample_rate

    def _extract_windows(self, *, samples: list[int], sample_rate: int, duration_ms: int) -> list[_WindowFeatures]:
        window_size = max(int(sample_rate * self.config.diarization_window_ms / 1000), 1)
        windows: list[_WindowFeatures] = []
        for offset in range(0, len(samples), window_size):
            window_samples = samples[offset : offset + window_size]
            if not window_samples:
                continue
            start_ms = int(round(offset / sample_rate * 1000))
            end_ms = min(duration_ms, int(round((offset + len(window_samples)) / sample_rate * 1000)))
            rms = math.sqrt(sum(sample * sample for sample in window_samples) / len(window_samples))
            zero_crossings = 0
            previous = window_samples[0]
            for sample in window_samples[1:]:
                if (previous >= 0 > sample) or (previous < 0 <= sample):
                    zero_crossings += 1
                previous = sample
            dominant_hz = zero_crossings * sample_rate / (2 * len(window_samples))
            voiced = rms >= self.config.diarization_silence_rms_threshold
            windows.append(
                _WindowFeatures(
                    start_ms=start_ms,
                    end_ms=end_ms,
                    rms=rms,
                    dominant_hz=dominant_hz,
                    voiced=voiced,
                )
            )
        return windows

    def _merge_windows(self, labeled_windows: list[dict[str, Any]], *, duration_ms: int) -> list[dict[str, Any]]:
        if not labeled_windows:
            return [{"speaker_id": "spk_0", "channel_id": None, "start_ms": 0, "end_ms": duration_ms, "overlap": False}]
        merged: list[dict[str, Any]] = []
        for window in labeled_windows:
            if not merged or merged[-1]["speaker_id"] != window["speaker_id"]:
                merged.append(
                    {
                        "speaker_id": window["speaker_id"],
                        "channel_id": None,
                        "start_ms": window["start_ms"],
                        "end_ms": window["end_ms"],
                        "overlap": False,
                    }
                )
            else:
                merged[-1]["end_ms"] = window["end_ms"]

        min_segment_ms = self.config.diarization_min_segment_ms
        normalized: list[dict[str, Any]] = []
        for segment in merged:
            if normalized and segment["end_ms"] - segment["start_ms"] < min_segment_ms:
                normalized[-1]["end_ms"] = segment["end_ms"]
                continue
            normalized.append(segment)
        if normalized:
            normalized[0]["start_ms"] = 0
            normalized[-1]["end_ms"] = duration_ms
        return normalized

    def _single_speaker(self, *, duration_ms: int, degraded: bool, reason: str, extra: dict[str, Any] | None = None) -> DiarizationResult:
        return DiarizationResult(
            speaker_segments=[
                {
                    "speaker_id": "spk_0",
                    "channel_id": None,
                    "start_ms": 0,
                    "end_ms": duration_ms,
                    "overlap": False,
                }
            ],
            detected_speaker_count=1,
            overlap_regions=[],
            strategy="mono_diarization",
            degraded=degraded,
            quality_report={"degraded_reason": reason, **(extra or {})},
            model_name="heuristic-mono-diarizer",
            model_version="energy-zcr-v1",
        )


class CompositeDiarizer:
    def __init__(self, config: AppConfig) -> None:
        self.config = config
        self.remote = RemoteDiarizationClient(config) if config.diarization_base_url else None
        self.heuristic = MonoHeuristicDiarizer(config)

    def healthcheck(self) -> dict[str, Any]:
        if self.remote:
            return self.remote.healthcheck()
        return {
            "ready": True,
            "backend": "heuristic",
            "degraded": True,
            "reason": "remote_diarization_not_configured",
        }

    def diarize(self, audio_path: Path) -> DiarizationResult:
        if self.remote:
            try:
                result, trace = self.remote.diarize(audio_path)
                result.quality_report = {
                    **result.quality_report,
                    "trace": {
                        "endpoint": trace.endpoint,
                        "latency_ms": trace.latency_ms,
                        "retry_count": trace.retry_count,
                    },
                }
                return result
            except DiarizationError:
                if not self.config.allow_heuristic_diarization_fallback:
                    raise
        fallback = self.heuristic.diarize(audio_path)
        fallback.quality_report = {
            **fallback.quality_report,
            "fallback_backend": "heuristic",
        }
        return fallback
