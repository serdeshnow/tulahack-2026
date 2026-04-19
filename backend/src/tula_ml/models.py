from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from enum import StrEnum
from typing import Any
import uuid


UTC = timezone.utc


def utcnow() -> datetime:
    return datetime.now(tz=UTC)


def make_id(prefix: str) -> str:
    return f"{prefix}_{uuid.uuid4().hex[:12]}"


class UploadStatus(StrEnum):
    PENDING = "pending"
    UPLOADED = "uploaded"
    EXPIRED = "expired"


class JobStatus(StrEnum):
    QUEUED = "queued"
    PROCESSING = "processing"
    COMPLETED = "completed"
    PARTIAL_COMPLETED = "partial_completed"
    FAILED = "failed"
    DELETED = "deleted"


class StageStatus(StrEnum):
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"
    SKIPPED = "skipped"


class AccessLevel(StrEnum):
    RESTRICTED = "restricted"
    REDACTED = "redacted"
    AUDIT = "audit"
    INTERNAL = "internal"


class SpeakerStrategy(StrEnum):
    AUTO = "auto"
    CHANNEL_FIRST = "channel_first"
    DIARIZATION = "diarization"


class AlignmentMode(StrEnum):
    NATIVE = "native"
    HYBRID = "hybrid"


class QualityBias(StrEnum):
    RECALL_FIRST = "recall_first"
    BALANCED = "balanced"
    PRECISION_FIRST = "precision_first"


class StageName(StrEnum):
    QUEUED = "queued"
    INGESTION = "ingestion"
    NORMALIZATION = "normalization"
    SPEAKER_ATTRIBUTION = "speaker_attribution"
    TRANSCRIPTION = "transcription"
    PII_DETECTION = "pii_detection"
    ALIGNMENT = "alignment"
    TRANSCRIPT_REDACTION = "transcript_redaction"
    AUDIO_REDACTION = "audio_redaction"
    FINALIZATION = "finalization"


class ArtifactKind(StrEnum):
    SOURCE_AUDIO = "source_audio"
    NORMALIZED_AUDIO = "normalized_audio"
    CHANNEL_AUDIO = "channel_audio"
    SOURCE_TRANSCRIPT = "source_transcript"
    CANONICAL_TRANSCRIPT = "canonical_transcript"
    REDACTED_TRANSCRIPT = "redacted_transcript"
    SUMMARY = "summary"
    REDACTION_SPANS = "redaction_spans"
    ENTITY_CANDIDATES = "entity_candidates"
    ENTITY_DECISIONS = "entity_decisions"
    EVENT_LOG = "event_log"
    SPEAKER_SEGMENTS = "speaker_segments"
    REDACTED_AUDIO = "redacted_audio"
    QUALITY_EVAL_SNAPSHOT = "quality_eval_snapshot"
    MODEL_DEBUG = "model_debug"


PIPELINE_STAGES: tuple[StageName, ...] = (
    StageName.INGESTION,
    StageName.NORMALIZATION,
    StageName.SPEAKER_ATTRIBUTION,
    StageName.TRANSCRIPTION,
    StageName.PII_DETECTION,
    StageName.ALIGNMENT,
    StageName.TRANSCRIPT_REDACTION,
    StageName.AUDIO_REDACTION,
    StageName.FINALIZATION,
)


DEFAULT_PII_ENTITIES = (
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
)


@dataclass(slots=True)
class ExpectedSpeakerRange:
    min: int = 1
    max: int = 6

    @classmethod
    def from_dict(cls, payload: dict[str, Any] | None) -> "ExpectedSpeakerRange":
        payload = payload or {}
        return cls(min=int(payload.get("min", 1)), max=int(payload.get("max", 6)))


@dataclass(slots=True)
class ProcessingProfile:
    language: str = "auto"
    speaker_strategy: str = SpeakerStrategy.AUTO.value
    expected_speakers: ExpectedSpeakerRange = field(default_factory=ExpectedSpeakerRange)
    pii_entities: list[str] = field(default_factory=lambda: list(DEFAULT_PII_ENTITIES))
    audio_redaction_mode: str = "beep"
    include_summary: bool = False
    processing_profile: str = "standard"
    asr_tier: str = "primary"
    asr_profile: str = "whisper_cpp_large_v3"
    asr_hotwords: list[str] = field(default_factory=list)
    model_bundle: str = "whisper-qwen-default"
    entity_set_version: str = "ru_common_personal_v1"
    diarization_profile: str = "auto"
    pii_profile: str = "ru_common_personal_high_recall"
    quality_bias: str = QualityBias.RECALL_FIRST.value
    policy_version: str = "v1"
    threshold_profile: str = "balanced"
    transcript_cleanup_enabled: bool = True
    llm_ner_enabled: bool = True
    llm_ner_threshold: float = 0.82
    alignment_mode: str = AlignmentMode.HYBRID.value
    force_single_speaker_for_mono: bool = True
    pii_strict_span_mode: bool = True
    email_asr_reconstruction: bool = True
    numeric_pii_join_window_ms: int = 1200
    llm_transport_mode: str = "openai_compatible"
    whisper_request_overrides: dict[str, Any] = field(default_factory=dict)
    lmstudio_request_overrides: dict[str, Any] = field(default_factory=dict)
    metadata: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_dict(cls, payload: dict[str, Any] | None) -> "ProcessingProfile":
        payload = payload or {}
        known_keys = {
            "language",
            "speaker_strategy",
            "expected_speakers",
            "pii_entities",
            "audio_redaction_mode",
            "include_summary",
            "processing_profile",
            "asr_tier",
            "asr_profile",
            "asr_hotwords",
            "model_bundle",
            "entity_set_version",
            "diarization_profile",
            "pii_profile",
            "quality_bias",
            "policy_version",
            "threshold_profile",
            "transcript_cleanup_enabled",
            "llm_ner_enabled",
            "llm_ner_threshold",
            "alignment_mode",
            "force_single_speaker_for_mono",
            "pii_strict_span_mode",
            "email_asr_reconstruction",
            "numeric_pii_join_window_ms",
            "llm_transport_mode",
            "whisper_request_overrides",
            "lmstudio_request_overrides",
            "metadata",
        }
        metadata = dict(payload.get("metadata") or {})
        for key, value in payload.items():
            if key not in known_keys:
                metadata[key] = value
        return cls(
            language=payload.get("language", "auto"),
            speaker_strategy=payload.get("speaker_strategy", SpeakerStrategy.AUTO.value),
            expected_speakers=ExpectedSpeakerRange.from_dict(payload.get("expected_speakers")),
            pii_entities=list(payload.get("pii_entities") or DEFAULT_PII_ENTITIES),
            audio_redaction_mode=payload.get("audio_redaction_mode", "beep"),
            include_summary=bool(payload.get("include_summary", False)),
            processing_profile=payload.get("processing_profile", "standard"),
            asr_tier=payload.get("asr_tier", "primary"),
            asr_profile=payload.get("asr_profile", "whisper_cpp_large_v3"),
            asr_hotwords=list(payload.get("asr_hotwords") or []),
            model_bundle=payload.get("model_bundle", "whisper-qwen-default"),
            entity_set_version=payload.get("entity_set_version", "ru_common_personal_v1"),
            diarization_profile=payload.get("diarization_profile", "auto"),
            pii_profile=payload.get("pii_profile", "ru_common_personal_high_recall"),
            quality_bias=payload.get("quality_bias", QualityBias.RECALL_FIRST.value),
            policy_version=payload.get("policy_version", "v1"),
            threshold_profile=payload.get("threshold_profile", "balanced"),
            transcript_cleanup_enabled=bool(payload.get("transcript_cleanup_enabled", True)),
            llm_ner_enabled=bool(payload.get("llm_ner_enabled", True)),
            llm_ner_threshold=float(payload.get("llm_ner_threshold", 0.82)),
            alignment_mode=payload.get("alignment_mode", AlignmentMode.HYBRID.value),
            force_single_speaker_for_mono=bool(payload.get("force_single_speaker_for_mono", True)),
            pii_strict_span_mode=bool(payload.get("pii_strict_span_mode", True)),
            email_asr_reconstruction=bool(payload.get("email_asr_reconstruction", True)),
            numeric_pii_join_window_ms=int(payload.get("numeric_pii_join_window_ms", 1200)),
            llm_transport_mode=str(payload.get("llm_transport_mode", "openai_compatible")),
            whisper_request_overrides=dict(payload.get("whisper_request_overrides") or {}),
            lmstudio_request_overrides=dict(payload.get("lmstudio_request_overrides") or {}),
            metadata=metadata,
        )


@dataclass(slots=True)
class UploadSession:
    upload_id: str
    filename: str
    content_type: str
    size_bytes: int
    object_key: str
    upload_token: str
    created_at: datetime
    expires_at: datetime
    status: UploadStatus = UploadStatus.PENDING
    checksum: str | None = None
    bytes_received: int = 0
    metadata: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def new(cls, *, filename: str, content_type: str, size_bytes: int, object_key: str, upload_token: str, ttl_seconds: int) -> "UploadSession":
        created_at = utcnow()
        return cls(
            upload_id=make_id("upl"),
            filename=filename,
            content_type=content_type,
            size_bytes=size_bytes,
            object_key=object_key,
            upload_token=upload_token,
            created_at=created_at,
            expires_at=created_at + timedelta(seconds=ttl_seconds),
        )


@dataclass(slots=True)
class JobRecord:
    job_id: str
    upload_id: str
    profile: ProcessingProfile
    webhook_url: str | None
    idempotency_key: str | None
    status: JobStatus
    stage: StageName
    progress: float
    trace_id: str
    created_at: datetime
    updated_at: datetime
    last_error: str | None = None
    retry_count: int = 0
    quality_flags: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def new(
        cls,
        *,
        upload_id: str,
        profile: ProcessingProfile,
        webhook_url: str | None,
        idempotency_key: str | None,
    ) -> "JobRecord":
        now = utcnow()
        return cls(
            job_id=make_id("job"),
            upload_id=upload_id,
            profile=profile,
            webhook_url=webhook_url,
            idempotency_key=idempotency_key,
            status=JobStatus.QUEUED,
            stage=StageName.QUEUED,
            progress=0.0,
            trace_id=make_id("trace"),
            created_at=now,
            updated_at=now,
        )


@dataclass(slots=True)
class StageExecution:
    job_id: str
    name: StageName
    status: StageStatus
    attempt: int
    started_at: datetime
    completed_at: datetime | None = None
    details: dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class ArtifactRecord:
    artifact_id: str
    job_id: str
    kind: ArtifactKind
    variant: str
    storage_key: str
    access_level: AccessLevel
    content_type: str
    created_at: datetime
    expires_at: datetime | None
    metadata: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def new(
        cls,
        *,
        job_id: str,
        kind: ArtifactKind,
        variant: str,
        storage_key: str,
        access_level: AccessLevel,
        content_type: str,
        expires_at: datetime | None,
        metadata: dict[str, Any] | None = None,
    ) -> "ArtifactRecord":
        return cls(
            artifact_id=make_id("art"),
            job_id=job_id,
            kind=kind,
            variant=variant,
            storage_key=storage_key,
            access_level=access_level,
            content_type=content_type,
            created_at=utcnow(),
            expires_at=expires_at,
            metadata=metadata or {},
        )


@dataclass(slots=True)
class ModelRun:
    run_id: str
    job_id: str
    stage_name: StageName
    model_name: str
    model_version: str
    threshold_profile: str
    trace_id: str
    created_at: datetime
    extra: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def new(
        cls,
        *,
        job_id: str,
        stage_name: StageName,
        model_name: str,
        model_version: str,
        threshold_profile: str,
        trace_id: str,
        extra: dict[str, Any] | None = None,
    ) -> "ModelRun":
        return cls(
            run_id=make_id("run"),
            job_id=job_id,
            stage_name=stage_name,
            model_name=model_name,
            model_version=model_version,
            threshold_profile=threshold_profile,
            trace_id=trace_id,
            created_at=utcnow(),
            extra=extra or {},
        )


@dataclass(slots=True)
class JobResultRecord:
    job_id: str
    upload_id: str
    trace_id: str
    status: str
    stage: str
    created_at: datetime
    updated_at: datetime
    completed_at: datetime | None = None
    retry_count: int = 0
    source_filename: str | None = None
    source_content_type: str | None = None
    source_size_bytes: int | None = None
    source_duration_ms: int | None = None
    source_channels: int | None = None
    source_sample_rate: int | None = None
    source_checksum: str | None = None
    processing_profile: str | None = None
    model_bundle: str | None = None
    audio_redaction_mode: str | None = None
    language: str | None = None
    speaker_strategy_used: str | None = None
    timing_source: str | None = None
    title: str | None = None
    source_text: str | None = None
    anonymized_text: str | None = None
    summary_text: str | None = None
    summary_bullets: list[str] = field(default_factory=list)
    summary_confidence: float | None = None
    events: list[dict[str, Any]] = field(default_factory=list)
    event_count: int = 0
    entity_counts: dict[str, int] = field(default_factory=dict)
    quality_flags: dict[str, Any] = field(default_factory=dict)
    pii_confidence_report: dict[str, Any] | None = None
    evaluation_summary: dict[str, Any] | None = None
    total_processing_ms: int | None = None
    queue_wait_ms: int | None = None
    transcription_ms: int | None = None
    pii_detection_ms: int | None = None
    alignment_ms: int | None = None
    audio_redaction_ms: int | None = None
    summary_generation_ms: int | None = None
    source_audio_artifact_id: str | None = None
    redacted_audio_artifact_id: str | None = None
    source_transcript_artifact_id: str | None = None
    redacted_transcript_artifact_id: str | None = None
    summary_artifact_id: str | None = None
    events_artifact_id: str | None = None
    text_snippet: str | None = None
    anonymized_snippet: str | None = None
    last_error: str | None = None
    audio_redaction_error: str | None = None
    has_summary: bool = False
    has_redacted_audio: bool = False


@dataclass(slots=True)
class AudioMetadata:
    duration_ms: int
    channels: int
    sample_rate: int
    bitrate: int
    codec: str
    checksum: str
    content_type: str
    file_size: int


@dataclass(slots=True)
class SpeakerSegment:
    speaker_id: str
    start_ms: int
    end_ms: int
    channel_id: int | None = None
    overlap: bool = False


@dataclass(slots=True)
class TranscriptWord:
    text: str
    start_ms: int
    end_ms: int
    confidence: float
    speaker_id: str
    channel_id: int | None = None


@dataclass(slots=True)
class TranscriptSegment:
    segment_id: str
    speaker_id: str
    start_ms: int
    end_ms: int
    text: str
    words: list[TranscriptWord]
    avg_confidence: float
    overlap: bool = False
    channel_id: int | None = None


@dataclass(slots=True)
class AsrResult:
    segments: list[TranscriptSegment]
    words: list[TranscriptWord]
    language_detected: str
    model_name: str
    model_version: str
    timing_mode: str = "segment_distributed_timestamps"
    raw_response: dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class EntitySpan:
    entity_id: str
    type: str
    text: str
    normalized_value: str
    speaker_id: str
    segment_id: str
    start_word_index: int
    end_word_index: int
    confidence: float
    sources: list[str]
    action: str


@dataclass(slots=True)
class RedactionSpan:
    span_id: str
    entity_type: str
    start_ms: int
    end_ms: int
    mode: str
    replacement_text: str
    confidence: float
    speaker_id: str
    sources: list[str]
    entity_id: str
    timing_source: str = "segment_distributed_fallback"
    alignment_confidence: float = 0.0


@dataclass(slots=True)
class EventLogEntry:
    event_id: str
    entity_type: str
    speaker_id: str
    start_ms: int
    end_ms: int
    confidence: float
    sources: list[str]
    action: str
    payload: dict[str, Any]


def retention_deadline(hours: int) -> datetime:
    return utcnow() + timedelta(hours=hours)
