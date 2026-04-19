from __future__ import annotations

from typing import Any

from evals.datasets.common import Segment
from evals.datasets.e2e import SpeakerSegment


def _normalize_reason(value: Any) -> str:
    if value is None:
        return ""
    return str(value).strip()


def _to_seconds(value: Any) -> float | None:
    if value is None:
        return None
    try:
        numeric = float(value)
    except (TypeError, ValueError):
        return None
    return round(numeric, 3)


def _extract_time_seconds(mapping: dict[str, Any], *, ts_key: str, ms_key: str) -> float | None:
    if ms_key in mapping and mapping.get(ms_key) is not None:
        try:
            return round(float(mapping[ms_key]) / 1000.0, 3)
        except (TypeError, ValueError):
            return None
    return _to_seconds(mapping.get(ts_key))


def _segment_texts(transcript: dict[str, Any], key: str) -> list[str]:
    segments = transcript.get(key, [])
    if not isinstance(segments, list):
        return []
    return [
        str(segment.get("text", "")).strip()
        for segment in segments
        if isinstance(segment, dict) and str(segment.get("text", "")).strip()
    ]


def extract_plain_text(transcript: dict[str, Any]) -> str:
    full_text = transcript.get("full_text")
    if isinstance(full_text, str) and full_text.strip():
        return full_text.strip()

    canonical_texts = _segment_texts(transcript, "canonical_segments")
    if canonical_texts:
        return " ".join(canonical_texts).strip()

    segment_texts = _segment_texts(transcript, "segments")
    return " ".join(segment_texts).strip()


def extract_speaker_segments(transcript: dict[str, Any]) -> list[SpeakerSegment]:
    def _extract_from(raw_segments: Any) -> list[SpeakerSegment]:
        extracted: list[SpeakerSegment] = []
        if not isinstance(raw_segments, list):
            return extracted

        for segment in raw_segments:
            if not isinstance(segment, dict):
                continue
            speaker = segment.get("speaker_id", segment.get("speaker", segment.get("role")))
            start_ts = _extract_time_seconds(segment, ts_key="start_ts", ms_key="start_ms")
            end_ts = _extract_time_seconds(segment, ts_key="end_ts", ms_key="end_ms")
            if not speaker or start_ts is None or end_ts is None:
                continue

            speaker_name = str(speaker).strip()
            if not speaker_name:
                continue

            if (
                extracted
                and extracted[-1].speaker == speaker_name
                and start_ts <= extracted[-1].end_ts + 0.15
            ):
                extracted[-1] = SpeakerSegment(
                    start_ts=extracted[-1].start_ts,
                    end_ts=max(extracted[-1].end_ts, end_ts),
                    speaker=speaker_name,
                )
                continue

            extracted.append(
                SpeakerSegment(
                    start_ts=start_ts,
                    end_ts=end_ts,
                    speaker=speaker_name,
                )
            )
        return extracted

    canonical = _extract_from(transcript.get("canonical_segments"))
    if canonical:
        return canonical
    return _extract_from(transcript.get("segments"))


def _merge_or_append_segments(
    segments: list[Segment],
    *,
    start_ts: float,
    end_ts: float,
    reason: str,
    max_gap_seconds: float = 0.15,
) -> None:
    if start_ts > end_ts:
        start_ts, end_ts = end_ts, start_ts
    if not segments:
        segments.append(Segment(start_ts=start_ts, end_ts=end_ts, reason=reason))
        return

    last = segments[-1]
    if last.reason == reason and start_ts <= last.end_ts + max_gap_seconds:
        segments[-1] = Segment(
            start_ts=last.start_ts,
            end_ts=max(last.end_ts, end_ts),
            reason=last.reason,
        )
        return

    segments.append(Segment(start_ts=start_ts, end_ts=end_ts, reason=reason))


def extract_redacted_segments(transcript: dict[str, Any]) -> list[Segment]:
    explicit_redactions = transcript.get("redactions")
    if isinstance(explicit_redactions, list):
        return [Segment.model_validate(item) for item in explicit_redactions]

    extracted: list[Segment] = []

    for segment in transcript.get("segments", []):
        if not isinstance(segment, dict):
            continue
        for word in segment.get("words", []):
            if not isinstance(word, dict) or not word.get("is_redacted", False):
                continue

            reason = _normalize_reason(word.get("redaction_reason"))
            start_ts = _extract_time_seconds(word, ts_key="start_ts", ms_key="start_ms")
            end_ts = _extract_time_seconds(word, ts_key="end_ts", ms_key="end_ms")
            if start_ts is None or end_ts is None:
                continue

            _merge_or_append_segments(
                extracted,
                start_ts=start_ts,
                end_ts=end_ts,
                reason=reason,
            )

    return extracted


def extract_status_redaction_segments(job_status: dict[str, Any]) -> list[Segment]:
    extracted: list[Segment] = []

    for execution in job_status.get("stage_executions", []):
        if not isinstance(execution, dict):
            continue
        details = execution.get("details", {})
        if not isinstance(details, dict):
            continue
        for span in details.get("redaction_spans", []):
            if not isinstance(span, dict):
                continue
            start_ts = _extract_time_seconds(span, ts_key="start_ts", ms_key="start_ms")
            end_ts = _extract_time_seconds(span, ts_key="end_ts", ms_key="end_ms")
            if start_ts is None or end_ts is None:
                continue
            extracted.append(
                Segment(
                    start_ts=start_ts,
                    end_ts=end_ts,
                    reason=_normalize_reason(
                        span.get("reason", span.get("entity_type", span.get("type")))
                    ),
                )
            )

    return extracted


def _extract_segment_from_mapping(candidate: dict[str, Any]) -> Segment | None:
    start_ts = _extract_time_seconds(candidate, ts_key="start_ts", ms_key="start_ms")
    end_ts = _extract_time_seconds(candidate, ts_key="end_ts", ms_key="end_ms")
    if start_ts is None and candidate.get("offset_start_ms") is not None:
        start_ts = _to_seconds(float(candidate["offset_start_ms"]) / 1000.0)
    if end_ts is None and candidate.get("offset_end_ms") is not None:
        end_ts = _to_seconds(float(candidate["offset_end_ms"]) / 1000.0)
    if start_ts is None or end_ts is None:
        return None

    return Segment(
        start_ts=start_ts,
        end_ts=end_ts,
        reason=_normalize_reason(
            candidate.get("reason", candidate.get("entity_type", candidate.get("type")))
        ),
    )


def _walk_for_segments(node: Any, *, sink: list[Segment]) -> None:
    if isinstance(node, dict):
        segment = _extract_segment_from_mapping(node)
        if segment is not None:
            sink.append(segment)
        for value in node.values():
            _walk_for_segments(value, sink=sink)
        return

    if isinstance(node, list):
        for item in node:
            _walk_for_segments(item, sink=sink)


def extract_event_segments(events_payload: dict[str, Any]) -> list[Segment]:
    extracted: list[Segment] = []
    _walk_for_segments(events_payload.get("events", []), sink=extracted)

    deduped: list[Segment] = []
    seen: set[tuple[float, float, str]] = set()
    for segment in extracted:
        key = (segment.start_ts, segment.end_ts, segment.reason)
        if key in seen:
            continue
        seen.add(key)
        deduped.append(segment)
    return deduped
