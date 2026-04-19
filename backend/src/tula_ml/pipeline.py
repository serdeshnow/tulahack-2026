from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any
from urllib.parse import urlencode
import queue
import re
import threading
import time

from .audio import AudioProcessingError, AudioProcessor
from .auth import AuthError, ClaimsAuth
from .config import AppConfig
from .database import Database, build_database
from .diarization import CompositeDiarizer, DiarizationError
from .json_utils import json_dumps, to_jsonable
from .lmstudio import (
    LMStudioClient,
    LMStudioSchemaError,
    LMStudioTransportError,
    LlmNerRecognizer,
    PiiMerger,
    SummaryGenerator,
    TranscriptRefiner,
)
from .models import (
    AccessLevel,
    AlignmentMode,
    ArtifactKind,
    ArtifactRecord,
    EventLogEntry,
    EntitySpan,
    JobResultRecord,
    JobRecord,
    JobStatus,
    ModelRun,
    PIPELINE_STAGES,
    ProcessingProfile,
    RedactionSpan,
    SpeakerStrategy,
    StageExecution,
    StageName,
    StageStatus,
    TranscriptSegment,
    TranscriptWord,
    UploadSession,
    UploadStatus,
    make_id,
    retention_deadline,
    utcnow,
)
from .pii import PiiCascade, TranscriptCanonicalizer, entity_severity
from .security import UrlSigner
from .storage import build_object_store
from .token_ner import SelfHostedTokenNerRecognizer, TokenNerError
from .webhooks import WebhookNotifier
from .whisper import AsrTranscriber, WhisperClient, WhisperSchemaError, WhisperTransportError


class ServiceError(RuntimeError):
    status_code = 400


class NotFoundError(ServiceError):
    status_code = 404


class AuthorizationError(ServiceError):
    status_code = 403


class ValidationError(ServiceError):
    status_code = 422


class NotReadyError(ServiceError):
    status_code = 409


def _content_type_for_transcript(format_name: str) -> str:
    if format_name == "vtt":
        return "text/vtt; charset=utf-8"
    if format_name == "srt":
        return "text/plain; charset=utf-8"
    return "application/json"


def _tokenize_text(text: str) -> list[str]:
    return re.findall(r"[A-Za-zА-Яа-я0-9@._%+\-]+", text, flags=re.UNICODE)


def _format_timestamp(milliseconds: int, *, separator: str) -> str:
    seconds, ms = divmod(max(milliseconds, 0), 1000)
    minutes, sec = divmod(seconds, 60)
    hours, minute = divmod(minutes, 60)
    return f"{hours:02d}:{minute:02d}:{sec:02d}{separator}{ms:03d}"


def transcript_to_srt(payload: dict[str, Any]) -> str:
    lines: list[str] = []
    for index, segment in enumerate(payload["segments"], start=1):
        lines.extend(
            [
                str(index),
                f"{_format_timestamp(segment['start_ms'], separator=',')} --> {_format_timestamp(segment['end_ms'], separator=',')}",
                f"{segment['speaker_id']}: {segment['text']}",
                "",
            ]
        )
    return "\n".join(lines)


def transcript_to_vtt(payload: dict[str, Any]) -> str:
    lines = ["WEBVTT", ""]
    for segment in payload["segments"]:
        lines.extend(
            [
                f"{_format_timestamp(segment['start_ms'], separator='.')} --> {_format_timestamp(segment['end_ms'], separator='.')}",
                f"{segment['speaker_id']}: {segment['text']}",
                "",
            ]
        )
    return "\n".join(lines)


def _collapse_text(text: str | None) -> str:
    return re.sub(r"\s+", " ", (text or "")).strip()


def _snippet(text: str | None, length: int = 200) -> str | None:
    collapsed = _collapse_text(text)
    if not collapsed:
        return None
    return collapsed[:length].rstrip()


def _title_from_text(*candidates: str | None, limit: int = 120) -> str | None:
    for candidate in candidates:
        collapsed = _collapse_text(candidate)
        if collapsed:
            return collapsed[:limit].rstrip()
    return None


def _to_record_status(job_status: str) -> str:
    mapping = {
        JobStatus.QUEUED.value: "queued",
        JobStatus.PROCESSING.value: "processing",
        JobStatus.COMPLETED.value: "completed",
        JobStatus.PARTIAL_COMPLETED.value: "completed",
        JobStatus.FAILED.value: "failed",
        JobStatus.DELETED.value: "completed",
    }
    return mapping.get(job_status, "uploaded")


class PipelineRunner:
    def __init__(
        self,
        *,
        config: AppConfig,
        db: Database,
        object_store: Any,
        audio_processor: AudioProcessor,
        pii_cascade: PiiCascade,
        transcript_canonicalizer: Any,
        asr_transcriber: Any,
        transcript_refiner: Any,
        token_ner_recognizer: Any,
        llm_ner_recognizer: Any,
        pii_merger: Any,
        diarizer: Any,
        webhook_notifier: Any,
        retention_callback: Any | None = None,
        sync_job_result_callback: Any | None = None,
    ) -> None:
        self.config = config
        self.db = db
        self.object_store = object_store
        self.audio_processor = audio_processor
        self.pii_cascade = pii_cascade
        self.transcript_canonicalizer = transcript_canonicalizer
        self.asr_transcriber = asr_transcriber
        self.transcript_refiner = transcript_refiner
        self.token_ner_recognizer = token_ner_recognizer
        self.llm_ner_recognizer = llm_ner_recognizer
        self.pii_merger = pii_merger
        self.diarizer = diarizer
        self.webhook_notifier = webhook_notifier
        self.retention_callback = retention_callback
        self.sync_job_result_callback = sync_job_result_callback
        self.job_queue: queue.Queue[str] = queue.Queue()
        self._stop_event = threading.Event()
        self._worker: threading.Thread | None = None
        self._last_retention_run_at = 0.0

    def start(self) -> None:
        if self._worker and self._worker.is_alive():
            return
        for job in self.db.list_jobs_by_status((JobStatus.QUEUED, JobStatus.PROCESSING)):
            self.job_queue.put(job.job_id)
        self._worker = threading.Thread(target=self._worker_loop, name="pipeline-runner", daemon=True)
        self._worker.start()

    def stop(self) -> None:
        self._stop_event.set()
        if self._worker and self._worker.is_alive():
            self._worker.join(timeout=2.0)

    def enqueue(self, job_id: str) -> None:
        self.job_queue.put(job_id)

    def wait_until_idle(self, timeout: float = 10.0) -> None:
        deadline = time.time() + timeout
        while time.time() < deadline:
            if self.job_queue.unfinished_tasks == 0:
                return
            time.sleep(0.05)
        raise TimeoutError("pipeline runner did not become idle in time")

    def run_job(self, job_id: str) -> None:
        job = self.db.get_job(job_id)
        if not job:
            raise NotFoundError(f"Unknown job: {job_id}")
        if job.status == JobStatus.DELETED:
            return

        try:
            upload = self._require_upload(job.upload_id)
            job.status = JobStatus.PROCESSING
            job.stage = StageName.INGESTION
            job.updated_at = utcnow()
            self.db.update_job(job)
            self._sync_job_result(job.job_id)

            ingestion = self._run_stage(job, StageName.INGESTION, lambda: self._stage_ingestion(job, upload))
            normalization = self._run_stage(job, StageName.NORMALIZATION, lambda: self._stage_normalization(job, ingestion))
            attribution = self._run_stage(job, StageName.SPEAKER_ATTRIBUTION, lambda: self._stage_speaker_attribution(job, ingestion, normalization))
            transcription = self._run_stage(job, StageName.TRANSCRIPTION, lambda: self._stage_transcription(job, ingestion, normalization, attribution))
            pii = self._run_stage(job, StageName.PII_DETECTION, lambda: self._stage_pii_detection(job, transcription))
            alignment = self._run_stage(job, StageName.ALIGNMENT, lambda: self._stage_alignment(job, transcription, pii))
            redacted_transcript = self._run_stage(job, StageName.TRANSCRIPT_REDACTION, lambda: self._stage_transcript_redaction(job, transcription, pii))

            audio_redaction_failed = None
            try:
                self._run_stage(job, StageName.AUDIO_REDACTION, lambda: self._stage_audio_redaction(job, ingestion, normalization, alignment))
            except Exception as exc:  # noqa: BLE001 - partial completion is a product requirement.
                audio_redaction_failed = str(exc)
                job.quality_flags["audio_redaction_error"] = str(exc)

            self._run_stage(job, StageName.FINALIZATION, lambda: self._stage_finalization(job, pii, alignment, redacted_transcript, audio_redaction_failed))
            job.status = JobStatus.PARTIAL_COMPLETED if audio_redaction_failed else JobStatus.COMPLETED
            job.stage = StageName.FINALIZATION
            job.progress = 1.0
            job.updated_at = utcnow()
            self.db.update_job(job)
            self._sync_job_result(job.job_id)
        except Exception as exc:  # noqa: BLE001 - pipeline must never crash silently.
            if job.retry_count < self.config.job_max_retries:
                job.retry_count += 1
                job.status = JobStatus.QUEUED
                job.stage = StageName.QUEUED
                job.last_error = str(exc)
                job.quality_flags["retry_scheduled"] = {
                    "retry_count": job.retry_count,
                    "max_retries": self.config.job_max_retries,
                    "reason": str(exc),
                }
                job.updated_at = utcnow()
                self.db.update_job(job)
                self._sync_job_result(job.job_id)
                self.enqueue(job.job_id)
                return
            job.status = JobStatus.FAILED
            job.last_error = str(exc)
            job.quality_flags["failure_mode"] = "stage_failure"
            job.updated_at = utcnow()
            self.db.update_job(job)
            self._sync_job_result(job.job_id)
            raise

    def _worker_loop(self) -> None:
        while not self._stop_event.is_set():
            if self.retention_callback and (time.time() - self._last_retention_run_at) >= self.config.retention_cleanup_interval_seconds:
                try:
                    self.retention_callback()
                finally:
                    self._last_retention_run_at = time.time()
            try:
                job_id = self.job_queue.get(timeout=self.config.worker_poll_interval_seconds)
            except queue.Empty:
                continue
            try:
                self.run_job(job_id)
            except Exception as exc:  # noqa: BLE001 - keep worker alive after job-level failures.
                # `run_job` already persists terminal status and error details for the job.
                print(f"pipeline worker recovered from job failure {job_id}: {exc}")
            finally:
                self.job_queue.task_done()

    def _require_upload(self, upload_id: str) -> UploadSession:
        upload = self.db.get_upload_session(upload_id)
        if not upload:
            raise NotFoundError(f"Unknown upload: {upload_id}")
        if upload.status != UploadStatus.UPLOADED:
            raise ValidationError("Upload exists but file content has not been uploaded yet")
        return upload

    def _run_stage(self, job: JobRecord, stage: StageName, fn) -> dict[str, Any]:
        started_at = utcnow()
        self.db.upsert_stage_execution(
            StageExecution(
                job_id=job.job_id,
                name=stage,
                status=StageStatus.PROCESSING,
                attempt=1,
                started_at=started_at,
                details={},
            )
        )
        job.stage = stage
        job.updated_at = utcnow()
        self.db.update_job(job)
        try:
            details = fn()
        except Exception as exc:  # noqa: BLE001
            self.db.upsert_stage_execution(
                StageExecution(
                    job_id=job.job_id,
                    name=stage,
                    status=StageStatus.FAILED,
                    attempt=1,
                    started_at=started_at,
                    completed_at=utcnow(),
                    details={"error": str(exc)},
                )
            )
            raise

        self.db.upsert_stage_execution(
            StageExecution(
                job_id=job.job_id,
                name=stage,
                status=StageStatus.COMPLETED,
                attempt=1,
                started_at=started_at,
                completed_at=utcnow(),
                details=details,
            )
        )
        completed_stages = len([stage_row for stage_row in self.db.list_stage_executions(job.job_id) if stage_row.status == StageStatus.COMPLETED])
        job.progress = min(completed_stages / len(PIPELINE_STAGES), 1.0)
        job.updated_at = utcnow()
        self.db.update_job(job)
        self._sync_job_result(job.job_id)
        return details

    def _stage_ingestion(self, job: JobRecord, upload: UploadSession) -> dict[str, Any]:
        source_path = self.object_store.resolve(upload.object_key)
        metadata = self.audio_processor.probe(source_path, content_type=upload.content_type)
        upload.checksum = metadata.checksum
        upload.metadata = {
            **upload.metadata,
            "duration_ms": metadata.duration_ms,
            "channels": metadata.channels,
            "sample_rate": metadata.sample_rate,
            "bitrate": metadata.bitrate,
        }
        self.db.update_upload_session(upload)
        artifact = ArtifactRecord.new(
            job_id=job.job_id,
            kind=ArtifactKind.SOURCE_AUDIO,
            variant="source",
            storage_key=upload.object_key,
            access_level=AccessLevel.RESTRICTED,
            content_type=upload.content_type,
            expires_at=retention_deadline(self.config.source_ttl_hours),
            metadata=to_jsonable(metadata),
        )
        self.db.store_artifact(artifact)
        return {
            "source_audio_uri": upload.object_key,
            "duration_ms": metadata.duration_ms,
            "channels": metadata.channels,
            "sample_rate": metadata.sample_rate,
            "checksum": metadata.checksum,
            "content_type": metadata.content_type,
        }

    def _stage_normalization(self, job: JobRecord, ingestion: dict[str, Any]) -> dict[str, Any]:
        source_path = self.object_store.resolve(ingestion["source_audio_uri"])
        destination_key = f"jobs/{job.job_id}/normalized/normalized.wav"
        destination_path = self.object_store.resolve(destination_key)
        report = self.audio_processor.normalize(source_path, destination_path)
        artifact = ArtifactRecord.new(
            job_id=job.job_id,
            kind=ArtifactKind.NORMALIZED_AUDIO,
            variant="internal",
            storage_key=destination_key,
            access_level=AccessLevel.INTERNAL,
            content_type="audio/wav",
            expires_at=retention_deadline(self.config.normalized_ttl_hours),
            metadata={"normalization_report": report, "channel_map": {"mode": "mono_16khz"}},
        )
        self.db.store_artifact(artifact)
        return {
            "normalized_audio_uri": destination_key,
            "normalization_report": report,
            "channel_map": {"source_channels": ingestion["channels"], "normalized_channels": 1},
        }

    def _stage_speaker_attribution(self, job: JobRecord, ingestion: dict[str, Any], normalization: dict[str, Any]) -> dict[str, Any]:
        duration_ms = int(ingestion["duration_ms"])
        channels = int(ingestion["channels"])
        requested_strategy = job.profile.speaker_strategy or SpeakerStrategy.AUTO.value
        strategy = SpeakerStrategy.CHANNEL_FIRST.value if channels > 1 else SpeakerStrategy.DIARIZATION.value
        if channels == 1 and requested_strategy == SpeakerStrategy.CHANNEL_FIRST.value:
            job.quality_flags["speaker_strategy_degraded"] = "channel_first_requested_for_mono"
        speaker_segments = []
        overlap_regions: list[dict[str, int]] = []
        channel_map: dict[str, int] = {}
        degraded = False
        quality_report: dict[str, Any] = {}

        if strategy == SpeakerStrategy.CHANNEL_FIRST.value:
            source_path = self.object_store.resolve(ingestion["source_audio_uri"])
            for channel_index in range(channels):
                channel_key = f"jobs/{job.job_id}/channels/channel_{channel_index}.wav"
                self.audio_processor.extract_channel(
                    source_path,
                    channel_index=channel_index,
                    destination_path=self.object_store.resolve(channel_key),
                )
                self.db.store_artifact(
                    ArtifactRecord.new(
                        job_id=job.job_id,
                        kind=ArtifactKind.CHANNEL_AUDIO,
                        variant=f"channel_{channel_index}",
                        storage_key=channel_key,
                        access_level=AccessLevel.INTERNAL,
                        content_type="audio/wav",
                        expires_at=retention_deadline(self.config.normalized_ttl_hours),
                        metadata={"channel_id": channel_index},
                    )
                )
                speaker_id = f"spk_{channel_index}"
                channel_map[speaker_id] = channel_index
                speaker_segments.append(
                    {
                        "speaker_id": speaker_id,
                        "channel_id": channel_index,
                        "start_ms": 0,
                        "end_ms": duration_ms,
                        "overlap": False,
                    }
                )
            model_name = "channel-first-router"
            model_version = "v1"
            quality_report = {"routing_mode": "per_channel", "requested_strategy": requested_strategy}
        else:
            normalized_path = self.object_store.resolve(normalization["normalized_audio_uri"])
            try:
                diarization = self.diarizer.diarize(normalized_path)
            except DiarizationError as exc:
                job.quality_flags["diarization_failure"] = str(exc)
                raise
            speaker_segments = diarization.speaker_segments
            overlap_regions = diarization.overlap_regions
            degraded = diarization.degraded
            quality_report = {
                **diarization.quality_report,
                "requested_strategy": requested_strategy,
            }
            model_name = diarization.model_name
            model_version = diarization.model_version
            if degraded:
                job.quality_flags["diarization_degraded"] = quality_report

        payload = {
            "speaker_segments": speaker_segments,
            "detected_speaker_count": len({segment["speaker_id"] for segment in speaker_segments}),
            "overlap_regions": overlap_regions,
            "strategy": strategy,
            "speaker_strategy_requested": requested_strategy,
            "degraded": degraded,
            "quality_report": quality_report,
            "channel_map": channel_map,
        }
        self.object_store.put_json(f"jobs/{job.job_id}/speaker_attribution.json", payload)
        self.db.store_artifact(
            ArtifactRecord.new(
                job_id=job.job_id,
                kind=ArtifactKind.SPEAKER_SEGMENTS,
                variant="internal",
                storage_key=f"jobs/{job.job_id}/speaker_attribution.json",
                access_level=AccessLevel.INTERNAL,
                content_type="application/json",
                expires_at=retention_deadline(self.config.normalized_ttl_hours),
                metadata={"strategy": strategy},
            )
        )
        self.db.store_model_run(
            ModelRun.new(
                job_id=job.job_id,
                stage_name=StageName.SPEAKER_ATTRIBUTION,
                model_name=model_name,
                model_version=model_version,
                threshold_profile=job.profile.threshold_profile,
                trace_id=job.trace_id,
                extra={"strategy": strategy, "degraded": degraded, "quality_report": quality_report},
            )
        )
        return payload

    def _stage_transcription(self, job: JobRecord, ingestion: dict[str, Any], normalization: dict[str, Any], attribution: dict[str, Any]) -> dict[str, Any]:
        duration_ms = int(ingestion["duration_ms"])
        channels = int(ingestion["channels"])
        segments: list[TranscriptSegment] = []
        raw_asr_responses: list[dict[str, Any]] = []
        timing_modes: list[str] = []
        request_traces: list[dict[str, Any]] = []
        try:
            if channels > 1:
                for channel_index in range(channels):
                    artifact = self.db.get_artifact(job.job_id, ArtifactKind.CHANNEL_AUDIO, f"channel_{channel_index}")
                    if not artifact:
                        raise NotFoundError(f"Missing extracted channel artifact for channel {channel_index}")
                    result, trace = self.asr_transcriber.transcribe(
                        audio_path=self.object_store.resolve(artifact.storage_key),
                        duration_ms=duration_ms,
                        speaker_id=f"spk_{channel_index}",
                        channel_id=channel_index,
                        profile=job.profile,
                        trace_id=job.trace_id,
                    )
                    segments.extend(result.segments)
                    raw_asr_responses.append({"channel_id": channel_index, "response": result.raw_response})
                    timing_modes.append(result.timing_mode)
                    request_traces.append({"channel_id": channel_index, **to_jsonable(trace)})
                    model_name = result.model_name
                    model_version = result.model_version
                    language = result.language_detected
            else:
                result, trace = self.asr_transcriber.transcribe(
                    audio_path=self.object_store.resolve(normalization["normalized_audio_uri"]),
                    duration_ms=duration_ms,
                    speaker_id="spk_0",
                    channel_id=None,
                    profile=job.profile,
                    trace_id=job.trace_id,
                )
                segments = self._apply_speaker_segments_to_transcript(result.segments, attribution["speaker_segments"])
                raw_asr_responses.append({"channel_id": None, "response": result.raw_response})
                timing_modes.append(result.timing_mode)
                request_traces.append({"channel_id": None, **to_jsonable(trace)})
                model_name = result.model_name
                model_version = result.model_version
                language = result.language_detected
        except WhisperTransportError as exc:
            job.quality_flags["asr_transport_failure"] = str(exc)
            raise
        except WhisperSchemaError as exc:
            job.quality_flags["asr_parse_failure"] = str(exc)
            raise

        segments = sorted(segments, key=lambda item: (item.start_ms, item.channel_id or -1))
        pre_cleanup_segments = [self._clone_segment(segment) for segment in segments]
        cleanup_metadata: dict[str, Any] = {
            "enabled": False,
            "edits_applied": [],
            "speaker_changes": [],
            "validation_report": {},
            "speaker_reassignment_ratio": 0.0,
        }
        if job.profile.transcript_cleanup_enabled:
            try:
                cleanup_result = self.transcript_refiner.refine(segments, job.profile)
                segments = cleanup_result.segments
                language = cleanup_result.language or language
                word_coverage_ratio = self._calculate_word_coverage_ratio(pre_cleanup_segments, segments)
                speaker_reassignment_ratio = self._calculate_speaker_reassignment_ratio(pre_cleanup_segments, segments)
                validation_report = self._validate_cleanup_result(
                    job=job,
                    original_segments=pre_cleanup_segments,
                    word_coverage_ratio=word_coverage_ratio,
                    speaker_reassignment_ratio=speaker_reassignment_ratio,
                    speaker_changes=cleanup_result.speaker_changes,
                )
                cleanup_metadata = {
                    "enabled": True,
                    "prompt_version": cleanup_result.prompt_version,
                    "trace": to_jsonable(cleanup_result.trace),
                    "edits_applied": cleanup_result.edits_applied,
                    "speaker_changes": cleanup_result.speaker_changes,
                    "validation_report": {
                        **cleanup_result.validation_report,
                        **validation_report,
                    },
                    "speaker_reassignment_ratio": speaker_reassignment_ratio,
                }
                self.db.store_model_run(
                    ModelRun.new(
                        job_id=job.job_id,
                        stage_name=StageName.TRANSCRIPTION,
                        model_name=self.config.lmstudio_llm_model,
                        model_version="lmstudio",
                        threshold_profile=job.profile.threshold_profile,
                        trace_id=job.trace_id,
                        extra={
                            "component": "transcript_cleanup",
                            "prompt_version": cleanup_result.prompt_version,
                            "trace": to_jsonable(cleanup_result.trace),
                            "speaker_change_count": len(cleanup_result.speaker_changes),
                            "speaker_reassignment_ratio": speaker_reassignment_ratio,
                            "parse_status": "ok",
                        },
                    )
                )
                self._store_internal_artifact(
                    job_id=job.job_id,
                    variant="transcript_cleanup",
                    payload={
                        "raw_response": cleanup_result.raw_response,
                        "edits_applied": cleanup_result.edits_applied,
                        "speaker_changes": cleanup_result.speaker_changes,
                        "validation_report": cleanup_metadata["validation_report"],
                    },
                )
            except (LMStudioTransportError, LMStudioSchemaError) as exc:
                job.quality_flags["llm_cleanup_failure"] = str(exc)
                raise
        word_coverage_ratio = self._calculate_word_coverage_ratio(pre_cleanup_segments, segments)
        speaker_reassignment_ratio = self._calculate_speaker_reassignment_ratio(pre_cleanup_segments, segments)
        cleanup_metadata["word_coverage_ratio"] = word_coverage_ratio
        cleanup_metadata["speaker_reassignment_ratio"] = speaker_reassignment_ratio
        cleanup_metadata["forced_realignment_recommended"] = word_coverage_ratio < 0.95
        canonicalization_result = self.transcript_canonicalizer.canonicalize(segments, hotwords=job.profile.asr_hotwords)
        canonical_segments = canonicalization_result.segments
        timing_mode = timing_modes[0] if len(set(timing_modes)) == 1 else "mixed"
        payload = {
            "job_id": job.job_id,
            "variant": "source",
            "language": language,
            "segments": to_jsonable(segments),
            "canonical_segments": to_jsonable(canonical_segments),
            "asr_model_version": model_version,
            "timing_mode": timing_mode,
            "speaker_strategy_used": attribution["strategy"],
            "speaker_strategy_requested": attribution.get("speaker_strategy_requested", SpeakerStrategy.AUTO.value),
            "diarization_degraded": attribution.get("degraded", False),
            "word_coverage_ratio": word_coverage_ratio,
            "speaker_reassignment_ratio": speaker_reassignment_ratio,
            "canonicalization_report": canonicalization_result.report,
        }
        transcript_key = f"jobs/{job.job_id}/transcripts/source.json"
        self.object_store.put_json(transcript_key, payload)
        self.db.store_artifact(
            ArtifactRecord.new(
                job_id=job.job_id,
                kind=ArtifactKind.SOURCE_TRANSCRIPT,
                variant="source",
                storage_key=transcript_key,
                access_level=AccessLevel.RESTRICTED,
                content_type="application/json",
                expires_at=retention_deadline(self.config.source_ttl_hours),
                metadata={
                    "language": language,
                    "segments": len(segments),
                    "timing_mode": timing_mode,
                    "cleanup": cleanup_metadata,
                    "word_coverage_ratio": word_coverage_ratio,
                    "speaker_reassignment_ratio": speaker_reassignment_ratio,
                },
            )
        )
        canonical_key = f"jobs/{job.job_id}/transcripts/canonical.json"
        self.object_store.put_json(
            canonical_key,
            {
                "job_id": job.job_id,
                "variant": "canonical",
                "language": language,
                "segments": to_jsonable(canonical_segments),
                "report": canonicalization_result.report,
            },
        )
        self.db.store_artifact(
            ArtifactRecord.new(
                job_id=job.job_id,
                kind=ArtifactKind.CANONICAL_TRANSCRIPT,
                variant="internal",
                storage_key=canonical_key,
                access_level=AccessLevel.INTERNAL,
                content_type="application/json",
                expires_at=retention_deadline(self.config.normalized_ttl_hours),
                metadata={
                    "word_coverage_ratio": word_coverage_ratio,
                    "speaker_reassignment_ratio": speaker_reassignment_ratio,
                },
            )
        )
        self._store_internal_artifact(
            job_id=job.job_id,
            variant="transcription_raw",
            payload={
                "raw_asr_responses": raw_asr_responses,
                "cleanup": cleanup_metadata,
                "canonicalization": canonicalization_result.report,
            },
        )
        self.db.store_model_run(
            ModelRun.new(
                job_id=job.job_id,
                stage_name=StageName.TRANSCRIPTION,
                model_name=model_name,
                model_version=model_version,
                threshold_profile=job.profile.threshold_profile,
                trace_id=job.trace_id,
                extra={
                    "component": "asr",
                    "language": language,
                    "timing_mode": timing_mode,
                    "speaker_strategy_used": attribution["strategy"],
                    "word_coverage_ratio": word_coverage_ratio,
                    "speaker_reassignment_ratio": speaker_reassignment_ratio,
                    "traces": request_traces,
                    "parse_status": "ok",
                },
            )
        )
        return payload

    def _apply_speaker_segments_to_transcript(
        self,
        segments: list[TranscriptSegment],
        speaker_segments: list[dict[str, Any]],
    ) -> list[TranscriptSegment]:
        if not segments or not speaker_segments:
            return segments
        distinct_speakers = {segment["speaker_id"] for segment in speaker_segments}
        if len(distinct_speakers) <= 1:
            speaker_id = next(iter(distinct_speakers), "spk_0")
            for segment in segments:
                segment.speaker_id = speaker_id
                for word in segment.words:
                    word.speaker_id = speaker_id
            return segments

        words: list[TranscriptWord] = []
        for segment in segments:
            for word in segment.words:
                assigned_speaker = self._speaker_for_word(word, speaker_segments)
                words.append(
                    TranscriptWord(
                        text=word.text,
                        start_ms=word.start_ms,
                        end_ms=word.end_ms,
                        confidence=word.confidence,
                        speaker_id=assigned_speaker,
                        channel_id=word.channel_id,
                    )
                )
        if not words:
            return segments
        words.sort(key=lambda word: (word.start_ms, word.end_ms))
        rebuilt: list[TranscriptSegment] = []
        current_words: list[TranscriptWord] = [words[0]]
        for word in words[1:]:
            previous = current_words[-1]
            if word.speaker_id != previous.speaker_id or word.start_ms - previous.end_ms > 800:
                rebuilt.append(self._build_segment_from_words(current_words))
                current_words = [word]
                continue
            current_words.append(word)
        rebuilt.append(self._build_segment_from_words(current_words))
        return rebuilt

    def _speaker_for_word(self, word: TranscriptWord, speaker_segments: list[dict[str, Any]]) -> str:
        midpoint_ms = (word.start_ms + word.end_ms) // 2
        containing = next(
            (
                segment
                for segment in speaker_segments
                if segment["start_ms"] <= midpoint_ms <= segment["end_ms"]
            ),
            None,
        )
        if containing:
            return str(containing["speaker_id"])
        nearest = min(
            speaker_segments,
            key=lambda segment: min(abs(midpoint_ms - segment["start_ms"]), abs(midpoint_ms - segment["end_ms"])),
        )
        return str(nearest["speaker_id"])

    def _build_segment_from_words(self, words: list[TranscriptWord]) -> TranscriptSegment:
        return TranscriptSegment(
            segment_id=make_id("seg"),
            speaker_id=words[0].speaker_id,
            start_ms=words[0].start_ms,
            end_ms=words[-1].end_ms,
            text=" ".join(word.text for word in words),
            words=words,
            avg_confidence=sum(word.confidence for word in words) / len(words),
            overlap=False,
            channel_id=words[0].channel_id,
        )

    def _clone_segment(self, segment: TranscriptSegment) -> TranscriptSegment:
        return TranscriptSegment(
            segment_id=segment.segment_id,
            speaker_id=segment.speaker_id,
            start_ms=segment.start_ms,
            end_ms=segment.end_ms,
            text=segment.text,
            words=[
                TranscriptWord(
                    text=word.text,
                    start_ms=word.start_ms,
                    end_ms=word.end_ms,
                    confidence=word.confidence,
                    speaker_id=word.speaker_id,
                    channel_id=word.channel_id,
                )
                for word in segment.words
            ],
            avg_confidence=segment.avg_confidence,
            overlap=segment.overlap,
            channel_id=segment.channel_id,
        )

    def _calculate_word_coverage_ratio(self, original_segments: list[TranscriptSegment], cleaned_segments: list[TranscriptSegment]) -> float:
        original_words = sum(len(segment.words) for segment in original_segments)
        cleaned_words = sum(len(segment.words) for segment in cleaned_segments)
        if original_words == 0 and cleaned_words == 0:
            return 1.0
        if original_words == 0 or cleaned_words == 0:
            return 0.0
        return round(min(original_words, cleaned_words) / max(original_words, cleaned_words), 4)

    def _calculate_speaker_reassignment_ratio(self, original_segments: list[TranscriptSegment], cleaned_segments: list[TranscriptSegment]) -> float:
        if not original_segments and not cleaned_segments:
            return 0.0
        cleaned_by_id = {segment.segment_id: segment for segment in cleaned_segments}
        comparable_segments = [segment for segment in original_segments if segment.segment_id in cleaned_by_id]
        if not comparable_segments:
            return 0.0
        changed = sum(1 for segment in comparable_segments if cleaned_by_id[segment.segment_id].speaker_id != segment.speaker_id)
        return round(changed / len(comparable_segments), 4)

    def _validate_cleanup_result(
        self,
        *,
        job: JobRecord,
        original_segments: list[TranscriptSegment],
        word_coverage_ratio: float,
        speaker_reassignment_ratio: float,
        speaker_changes: list[dict[str, Any]],
    ) -> dict[str, Any]:
        distinct_speakers = {segment.speaker_id for segment in original_segments}
        validation_report = {
            "status": "ok",
            "word_coverage_ratio": word_coverage_ratio,
            "speaker_reassignment_ratio": speaker_reassignment_ratio,
            "speaker_change_count": len(speaker_changes),
            "distinct_speaker_count": len(distinct_speakers),
            "min_word_coverage_ratio": 0.25,
            "max_speaker_reassignment_ratio": 0.5,
        }
        if "diarization_degraded" in job.quality_flags:
            validation_report["diarization_degraded"] = True
            validation_report["max_speaker_reassignment_ratio"] = 0.15
        if word_coverage_ratio < 0.25:
            validation_report["status"] = "rejected"
            validation_report["reason"] = "cleanup_word_coverage_too_low"
            job.quality_flags["llm_cleanup_suspect"] = validation_report
            raise LMStudioSchemaError("Transcript cleanup changed transcript length too aggressively")
        if len(distinct_speakers) > 1 and speaker_reassignment_ratio > float(validation_report["max_speaker_reassignment_ratio"]):
            validation_report["status"] = "rejected"
            validation_report["reason"] = "cleanup_speaker_reassignment_too_high"
            job.quality_flags["llm_cleanup_suspect"] = validation_report
            raise LMStudioSchemaError("Transcript cleanup reassigned too many speakers")
        return validation_report

    def _entity_to_candidate(self, entity: EntitySpan, *, layer: str) -> dict[str, Any]:
        return {
            "candidate_id": entity.entity_id,
            "layer": layer,
            "entity_type": entity.type,
            "severity": entity_severity(entity.type),
            "segment_id": entity.segment_id,
            "speaker_id": entity.speaker_id,
            "text": entity.text,
            "normalized_value": entity.normalized_value,
            "start_word_index": entity.start_word_index,
            "end_word_index": entity.end_word_index,
            "confidence": entity.confidence,
            "sources": list(entity.sources),
        }

    def _project_entity_to_source_words(self, entity: EntitySpan, source_segment_map: dict[str, TranscriptSegment]) -> EntitySpan:
        source_segment = source_segment_map.get(entity.segment_id)
        if not source_segment or not source_segment.words:
            return entity
        max_index = len(source_segment.words) - 1
        return EntitySpan(
            entity_id=entity.entity_id,
            type=entity.type,
            text=entity.text,
            normalized_value=entity.normalized_value,
            speaker_id=source_segment.speaker_id,
            segment_id=source_segment.segment_id,
            start_word_index=max(0, min(entity.start_word_index, max_index)),
            end_word_index=max(0, min(entity.end_word_index, max_index)),
            confidence=entity.confidence,
            sources=list(entity.sources),
            action=entity.action,
        )

    def _stage_pii_detection(self, job: JobRecord, transcription: dict[str, Any]) -> dict[str, Any]:
        source_segments = [self._segment_from_dict(item) for item in transcription["segments"]]
        canonical_segments = [self._segment_from_dict(item) for item in (transcription.get("canonical_segments") or transcription["segments"])]
        rule_result = self.pii_cascade.detect(
            canonical_segments,
            pii_entities=job.profile.pii_entities,
            action_mode=job.profile.audio_redaction_mode,
        )
        token_ner_entities: list[EntitySpan] = []
        token_ner_report: dict[str, Any] = {"enabled": True, "degraded": False}
        try:
            token_ner_result = self.token_ner_recognizer.detect(canonical_segments, job.profile)
            token_ner_entities = token_ner_result.entities
            token_ner_report = token_ner_result.report
            self.db.store_model_run(
                ModelRun.new(
                    job_id=job.job_id,
                    stage_name=StageName.PII_DETECTION,
                    model_name=token_ner_result.model_name,
                    model_version=token_ner_result.model_version,
                    threshold_profile=job.profile.threshold_profile,
                    trace_id=job.trace_id,
                    extra={
                        "component": "token_ner",
                        "degraded": token_ner_result.degraded,
                        "report": token_ner_result.report,
                    },
                )
            )
            if token_ner_result.degraded:
                job.quality_flags["token_ner_degraded"] = token_ner_result.report
        except TokenNerError as exc:
            job.quality_flags["token_ner_failure"] = str(exc)
            token_ner_report = {"enabled": False, "error": str(exc)}

        llm_entities = []
        llm_report: dict[str, Any] = {"enabled": False, "role": "verifier_reranker"}
        if job.profile.llm_ner_enabled:
            try:
                llm_result = self.llm_ner_recognizer.detect(canonical_segments, job.profile)
                llm_entities = llm_result.entities
                llm_report = {
                    "enabled": True,
                    "role": "verifier_reranker",
                    "prompt_version": llm_result.prompt_version,
                    "trace": to_jsonable(llm_result.trace),
                    "report": llm_result.report,
                }
                self.db.store_model_run(
                    ModelRun.new(
                        job_id=job.job_id,
                        stage_name=StageName.PII_DETECTION,
                        model_name=self.config.lmstudio_llm_model,
                        model_version="lmstudio",
                        threshold_profile=job.profile.threshold_profile,
                        trace_id=job.trace_id,
                        extra={
                            "component": "llm_verifier",
                            "prompt_version": llm_result.prompt_version,
                            "trace": to_jsonable(llm_result.trace),
                            "parse_status": "ok",
                        },
                    )
                )
                self._store_internal_artifact(
                    job_id=job.job_id,
                    variant="pii_llm_ner",
                    payload={"raw_response": llm_result.raw_response, "report": llm_result.report},
                )
            except (LMStudioTransportError, LMStudioSchemaError) as exc:
                job.quality_flags["llm_ner_failure"] = str(exc)
                raise

        merged_entities, merge_report, merge_decisions = self.pii_merger.merge(
            rule_entities=rule_result.entity_spans,
            token_ner_entities=token_ner_entities,
            llm_entities=llm_entities,
            llm_threshold=job.profile.llm_ner_threshold,
            action_mode=job.profile.audio_redaction_mode,
        )
        source_segment_map = {segment.segment_id: segment for segment in source_segments}
        projected_entities = [self._project_entity_to_source_words(entity, source_segment_map) for entity in merged_entities]
        entity_candidates = list(rule_result.entity_candidates)
        entity_candidates.extend(self._entity_to_candidate(entity, layer="token_ner") for entity in token_ner_entities)
        entity_candidates.extend(self._entity_to_candidate(entity, layer="llm_verifier") for entity in llm_entities)
        entity_decisions = [*rule_result.decision_log, *merge_decisions]
        candidate_stats = {
            "total_candidates": len(entity_candidates),
            "rule_candidates": len(rule_result.entity_candidates),
            "token_ner_candidates": len(token_ner_entities),
            "llm_verifier_candidates": len(llm_entities),
            "severity_counts": {
                severity: sum(1 for candidate in entity_candidates if candidate["severity"] == severity)
                for severity in ("critical", "high", "medium")
            },
        }
        entity_metrics = {
            "detected_entities": len(projected_entities),
            "critical_entities": sum(1 for entity in projected_entities if entity_severity(entity.type) == "critical"),
            "high_entities": sum(1 for entity in projected_entities if entity_severity(entity.type) == "high"),
            "medium_entities": sum(1 for entity in projected_entities if entity_severity(entity.type) == "medium"),
        }
        payload = {
            "entity_spans": to_jsonable(projected_entities),
            "normalized_candidates": rule_result.normalized_candidates,
            "entity_candidates": entity_candidates,
            "entity_decisions": entity_decisions,
            "candidate_stats": candidate_stats,
            "entity_metrics": entity_metrics,
            "regex_matches_by_type": rule_result.regex_matches_by_type,
            "email_reconstruction_candidates": rule_result.email_reconstruction_candidates,
            "pii_confidence_report": {
                **rule_result.confidence_report,
                **merge_report,
                "token_ner": token_ner_report,
                "llm_ner": llm_report,
            },
        }
        entity_candidates_key = f"jobs/{job.job_id}/pii/entity_candidates.json"
        self.object_store.put_json(entity_candidates_key, {"job_id": job.job_id, "candidates": entity_candidates})
        self.db.store_artifact(
            ArtifactRecord.new(
                job_id=job.job_id,
                kind=ArtifactKind.ENTITY_CANDIDATES,
                variant="internal",
                storage_key=entity_candidates_key,
                access_level=AccessLevel.INTERNAL,
                content_type="application/json",
                expires_at=retention_deadline(self.config.normalized_ttl_hours),
                metadata={"candidate_count": len(entity_candidates)},
            )
        )
        entity_decisions_key = f"jobs/{job.job_id}/pii/entity_decisions.json"
        self.object_store.put_json(entity_decisions_key, {"job_id": job.job_id, "decisions": entity_decisions})
        self.db.store_artifact(
            ArtifactRecord.new(
                job_id=job.job_id,
                kind=ArtifactKind.ENTITY_DECISIONS,
                variant="internal",
                storage_key=entity_decisions_key,
                access_level=AccessLevel.INTERNAL,
                content_type="application/json",
                expires_at=retention_deadline(self.config.normalized_ttl_hours),
                metadata={"decision_count": len(entity_decisions)},
            )
        )
        self.db.store_model_run(
            ModelRun.new(
                job_id=job.job_id,
                stage_name=StageName.PII_DETECTION,
                model_name="microsoft/presidio",
                model_version="ru-custom-v2",
                threshold_profile=job.profile.threshold_profile,
                trace_id=job.trace_id,
                extra={
                    "component": "rule_pii",
                    "policy_version": job.profile.policy_version,
                    "pii_profile": job.profile.pii_profile,
                    "entity_set_version": job.profile.entity_set_version,
                    "parse_status": "ok",
                },
            )
        )
        return payload

    def _stage_alignment(self, job: JobRecord, transcription: dict[str, Any], pii: dict[str, Any]) -> dict[str, Any]:
        segments = {segment.segment_id: segment for segment in [self._segment_from_dict(item) for item in transcription["segments"]]}
        redaction_spans: list[RedactionSpan] = []
        timing_source_counts: dict[str, int] = {}
        for entity in pii["entity_spans"]:
            segment = segments[entity["segment_id"]]
            span = self._build_redaction_span(job=job, segment=segment, entity=entity, transcription=transcription)
            timing_source_counts[span.timing_source] = timing_source_counts.get(span.timing_source, 0) + 1
            redaction_spans.append(span)
        payload = {
            "redaction_spans": to_jsonable(redaction_spans),
            "alignment_confidence": round(
                sum(span.alignment_confidence for span in redaction_spans) / len(redaction_spans),
                3,
            ) if redaction_spans else 1.0,
            "padding_applied": {
                "left_pad_ms": self.config.alignment_left_padding_ms,
                "right_pad_ms": self.config.alignment_right_padding_ms,
                "hybrid_bonus_ms": self.config.alignment_hybrid_padding_bonus_ms,
            },
            "timing_source": self._dominant_timing_source(timing_source_counts),
            "timing_source_breakdown": timing_source_counts,
        }
        span_key = f"jobs/{job.job_id}/redaction/spans.json"
        self.object_store.put_json(span_key, payload)
        self.db.store_artifact(
            ArtifactRecord.new(
                job_id=job.job_id,
                kind=ArtifactKind.REDACTION_SPANS,
                variant="internal",
                storage_key=span_key,
                access_level=AccessLevel.INTERNAL,
                content_type="application/json",
                expires_at=retention_deadline(self.config.normalized_ttl_hours),
                metadata={"span_count": len(redaction_spans), "timing_source": payload["timing_source"]},
            )
        )
        self.db.store_model_run(
            ModelRun.new(
                job_id=job.job_id,
                stage_name=StageName.ALIGNMENT,
                model_name="hybrid-word-aligner",
                model_version="local-v1",
                threshold_profile=job.profile.threshold_profile,
                trace_id=job.trace_id,
                extra={
                    "alignment_mode": job.profile.alignment_mode,
                    "timing_source": payload["timing_source"],
                    "timing_source_breakdown": timing_source_counts,
                },
            )
        )
        return payload

    def _build_redaction_span(
        self,
        *,
        job: JobRecord,
        segment: TranscriptSegment,
        entity: dict[str, Any],
        transcription: dict[str, Any],
    ) -> RedactionSpan:
        left_padding_ms = self.config.alignment_left_padding_ms
        right_padding_ms = self.config.alignment_right_padding_ms
        start_index = int(entity["start_word_index"])
        end_index = int(entity["end_word_index"])
        source_mode = transcription.get("timing_mode", "segment_distributed_timestamps")
        alignment_mode = job.profile.alignment_mode or AlignmentMode.HYBRID.value
        timing_source = "segment_distributed_fallback"
        alignment_confidence = 0.68

        if segment.words and start_index < len(segment.words) and end_index < len(segment.words):
            start_word = segment.words[start_index]
            end_word = segment.words[end_index]
            start_ms = start_word.start_ms
            end_ms = end_word.end_ms
            if alignment_mode == AlignmentMode.NATIVE.value and source_mode == "word_timestamps_native":
                timing_source = "native_words"
                alignment_confidence = 0.93
            elif source_mode == "word_timestamps_native":
                timing_source = "native_words"
                alignment_confidence = 0.91
            else:
                span_duration = max(start_word.end_ms - start_word.start_ms, 1)
                hybrid_bonus = min(self.config.alignment_hybrid_padding_bonus_ms, max(span_duration // 2, 10))
                start_ms = max(segment.start_ms, start_ms - hybrid_bonus)
                end_ms = min(segment.end_ms, end_ms + hybrid_bonus)
                timing_source = "hybrid_realigned" if alignment_mode == AlignmentMode.HYBRID.value else "segment_distributed_fallback"
                alignment_confidence = 0.82 if timing_source == "hybrid_realigned" else 0.7
        else:
            start_ms = segment.start_ms
            end_ms = segment.end_ms

        start_ms = max(0, start_ms - left_padding_ms)
        end_ms = min(segment.end_ms, end_ms + right_padding_ms)
        return RedactionSpan(
            span_id=make_id("span"),
            entity_type=entity["type"],
            start_ms=start_ms,
            end_ms=end_ms,
            mode=job.profile.audio_redaction_mode,
            replacement_text=f"[{entity['type']}]",
            confidence=entity["confidence"],
            speaker_id=entity["speaker_id"],
            sources=list(entity["sources"]) + [timing_source],
            entity_id=entity["entity_id"],
            timing_source=timing_source,
            alignment_confidence=alignment_confidence,
        )

    def _dominant_timing_source(self, timing_source_counts: dict[str, int]) -> str:
        if not timing_source_counts:
            return "segment_distributed_fallback"
        return max(timing_source_counts.items(), key=lambda item: item[1])[0]

    def _stage_transcript_redaction(self, job: JobRecord, transcription: dict[str, Any], pii: dict[str, Any]) -> dict[str, Any]:
        source_segments = [self._segment_from_dict(item) for item in transcription["segments"]]
        redacted_segments = self._build_redacted_segments(source_segments, pii["entity_spans"])
        payload = {
            "job_id": job.job_id,
            "variant": "redacted",
            "language": transcription["language"],
            "segments": to_jsonable(redacted_segments),
        }
        transcript_key = f"jobs/{job.job_id}/transcripts/redacted.json"
        self.object_store.put_json(transcript_key, payload)
        self.db.store_artifact(
            ArtifactRecord.new(
                job_id=job.job_id,
                kind=ArtifactKind.REDACTED_TRANSCRIPT,
                variant="redacted",
                storage_key=transcript_key,
                access_level=AccessLevel.REDACTED,
                content_type="application/json",
                expires_at=retention_deadline(self.config.redacted_ttl_hours),
                metadata={"segments": len(redacted_segments)},
            )
        )
        return payload

    def _stage_audio_redaction(
        self,
        job: JobRecord,
        ingestion: dict[str, Any],
        normalization: dict[str, Any],
        alignment: dict[str, Any],
    ) -> dict[str, Any]:
        source_path = self.object_store.resolve(normalization["normalized_audio_uri"])
        destination_key = f"jobs/{job.job_id}/audio/redacted.wav"
        destination_path = self.object_store.resolve(destination_key)
        redaction_spans = [self._redaction_span_from_dict(item) for item in alignment["redaction_spans"]]
        result = self.audio_processor.render_redacted_audio(
            source_path=source_path,
            destination_path=destination_path,
            spans=redaction_spans,
            mode=job.profile.audio_redaction_mode,
            sample_rate=16000,
            duration_ms=max(int(ingestion["duration_ms"]), 1),
        )
        self.db.store_artifact(
            ArtifactRecord.new(
                job_id=job.job_id,
                kind=ArtifactKind.REDACTED_AUDIO,
                variant="redacted",
                storage_key=destination_key,
                access_level=AccessLevel.REDACTED,
                content_type="audio/wav",
                expires_at=retention_deadline(self.config.redacted_ttl_hours),
                metadata=result,
            )
        )
        return {
            "redacted_audio_uri": destination_key,
            "audio_redaction_report": result,
            "redaction_span_count": len(redaction_spans),
        }

    def _stage_finalization(
        self,
        job: JobRecord,
        pii: dict[str, Any],
        alignment: dict[str, Any],
        redacted_transcript: dict[str, Any],
        audio_redaction_error: str | None,
    ) -> dict[str, Any]:
        entity_by_id = {entity["entity_id"]: entity for entity in pii["entity_spans"]}
        evaluation_summary = self._build_evaluation_summary(job, pii, alignment)
        events = []
        for span in alignment["redaction_spans"]:
            entity = entity_by_id[span["entity_id"]]
            event = EventLogEntry(
                event_id=make_id("evt"),
                entity_type=span["entity_type"],
                speaker_id=span["speaker_id"],
                start_ms=span["start_ms"],
                end_ms=span["end_ms"],
                confidence=span["confidence"],
                sources=span["sources"],
                action=entity["action"],
                payload={
                    "entity_id": entity["entity_id"],
                    "entity_text": entity["text"],
                    "normalized_value": entity["normalized_value"],
                    "segment_id": entity["segment_id"],
                    "replacement_text": span["replacement_text"],
                    "raw_model_sources": entity["sources"],
                    "timing_source": span.get("timing_source", "segment_distributed_fallback"),
                    "alignment_confidence": span.get("alignment_confidence", 0.0),
                    "failure_mode": "audio_redaction_partial_failure" if audio_redaction_error else "none",
                },
            )
            events.append(to_jsonable(event))
        self.db.replace_events(job.job_id, events)
        event_key = f"jobs/{job.job_id}/events/redaction_events.json"
        event_payload = {"job_id": job.job_id, "events": events}
        self.object_store.put_json(event_key, event_payload)
        self.db.store_artifact(
            ArtifactRecord.new(
                job_id=job.job_id,
                kind=ArtifactKind.EVENT_LOG,
                variant="audit",
                storage_key=event_key,
                access_level=AccessLevel.AUDIT,
                content_type="application/json",
                expires_at=retention_deadline(self.config.audit_ttl_hours),
                metadata={"event_count": len(events)},
            )
        )
        webhook_result = self.webhook_notifier.notify(
            webhook_url=job.webhook_url,
            payload={
                "job_id": job.job_id,
                "status": JobStatus.PARTIAL_COMPLETED.value if audio_redaction_error else JobStatus.COMPLETED.value,
                "stage": StageName.FINALIZATION.value,
                "event_count": len(events),
                "redacted_transcript_segments": len(redacted_transcript["segments"]),
                "timing_source": alignment.get("timing_source", "segment_distributed_fallback"),
                "failure_mode": "audio_redaction_partial_failure" if audio_redaction_error else "none",
            },
        )
        return {
            "event_count": len(events),
            "audio_redaction_error": audio_redaction_error,
            "timing_source": alignment.get("timing_source", "segment_distributed_fallback"),
            "evaluation_summary": evaluation_summary,
            "webhook_result": webhook_result,
        }

    def _build_evaluation_summary(
        self,
        job: JobRecord,
        pii: dict[str, Any],
        alignment: dict[str, Any],
    ) -> dict[str, Any] | None:
        expected = job.profile.metadata.get("evaluation_expected")
        if not isinstance(expected, dict):
            return None
        expected_entities = expected.get("entity_types") or []
        actual_entities = [entity["type"] for entity in pii["entity_spans"]]
        expected_set = set(expected_entities)
        actual_set = set(actual_entities)
        matched = expected_set.intersection(actual_set)
        boundary_errors = []
        expected_boundaries = expected.get("boundaries_ms") or {}
        for span in alignment["redaction_spans"]:
            boundary = expected_boundaries.get(span["entity_type"])
            if not isinstance(boundary, dict):
                continue
            boundary_errors.append(
                {
                    "entity_type": span["entity_type"],
                    "start_ms_error": abs(span["start_ms"] - int(boundary.get("start_ms", span["start_ms"]))),
                    "end_ms_error": abs(span["end_ms"] - int(boundary.get("end_ms", span["end_ms"]))),
                }
            )
        return {
            "expected_entity_types": expected_entities,
            "actual_entity_types": actual_entities,
            "matched_entity_types": sorted(matched),
            "missing_entity_types": sorted(expected_set - actual_set),
            "unexpected_entity_types": sorted(actual_set - expected_set),
            "boundary_error": boundary_errors,
        }

    def _segment_from_dict(self, payload: dict[str, Any]) -> TranscriptSegment:
        return TranscriptSegment(
            segment_id=payload["segment_id"],
            speaker_id=payload["speaker_id"],
            start_ms=payload["start_ms"],
            end_ms=payload["end_ms"],
            text=payload["text"],
            words=[
                TranscriptWord(
                    text=word["text"],
                    start_ms=word["start_ms"],
                    end_ms=word["end_ms"],
                    confidence=word["confidence"],
                    speaker_id=word["speaker_id"],
                    channel_id=word.get("channel_id"),
                )
                for word in payload["words"]
            ],
            avg_confidence=payload["avg_confidence"],
            overlap=payload.get("overlap", False),
            channel_id=payload.get("channel_id"),
        )

    def _redaction_span_from_dict(self, payload: dict[str, Any]) -> RedactionSpan:
        return RedactionSpan(
            span_id=payload["span_id"],
            entity_type=payload["entity_type"],
            start_ms=payload["start_ms"],
            end_ms=payload["end_ms"],
            mode=payload["mode"],
            replacement_text=payload["replacement_text"],
            confidence=payload["confidence"],
            speaker_id=payload["speaker_id"],
            sources=list(payload["sources"]),
            entity_id=payload["entity_id"],
            timing_source=payload.get("timing_source", "segment_distributed_fallback"),
            alignment_confidence=payload.get("alignment_confidence", 0.0),
        )

    def _build_redacted_segments(self, source_segments: list[TranscriptSegment], entities: list[dict[str, Any]]) -> list[TranscriptSegment]:
        entities_by_segment: dict[str, list[dict[str, Any]]] = {}
        for entity in entities:
            entities_by_segment.setdefault(entity["segment_id"], []).append(entity)
        redacted: list[TranscriptSegment] = []
        for segment in source_segments:
            replacements = sorted(entities_by_segment.get(segment.segment_id, []), key=lambda item: item["start_word_index"])
            words: list[TranscriptWord] = []
            index = 0
            while index < len(segment.words):
                replacement = next((item for item in replacements if item["start_word_index"] == index), None)
                if replacement is None:
                    words.append(segment.words[index])
                    index += 1
                    continue
                start_word = segment.words[replacement["start_word_index"]]
                end_word = segment.words[replacement["end_word_index"]]
                words.append(
                    TranscriptWord(
                        text=f"[{replacement['type']}]",
                        start_ms=start_word.start_ms,
                        end_ms=end_word.end_ms,
                        confidence=min(word.confidence for word in segment.words[replacement["start_word_index"] : replacement["end_word_index"] + 1]),
                        speaker_id=segment.speaker_id,
                        channel_id=segment.channel_id,
                    )
                )
                index = replacement["end_word_index"] + 1
            average_confidence = sum(word.confidence for word in words) / len(words) if words else 1.0
            redacted.append(
                TranscriptSegment(
                    segment_id=segment.segment_id,
                    speaker_id=segment.speaker_id,
                    start_ms=segment.start_ms,
                    end_ms=segment.end_ms,
                    text=" ".join(word.text for word in words),
                    words=words,
                    avg_confidence=average_confidence,
                    overlap=segment.overlap,
                    channel_id=segment.channel_id,
                )
            )
        return redacted

    def _store_internal_artifact(self, *, job_id: str, variant: str, payload: dict[str, Any]) -> None:
        storage_key = f"jobs/{job_id}/debug/{variant}.json"
        self.object_store.put_json(storage_key, payload)
        self.db.store_artifact(
            ArtifactRecord.new(
                job_id=job_id,
                kind=ArtifactKind.MODEL_DEBUG,
                variant=variant,
                storage_key=storage_key,
                access_level=AccessLevel.INTERNAL,
                content_type="application/json",
                expires_at=retention_deadline(self.config.normalized_ttl_hours),
                metadata={"variant": variant},
            )
        )

    def _sync_job_result(self, job_id: str) -> None:
        if self.sync_job_result_callback is None:
            return
        self.sync_job_result_callback(job_id)


class VoiceRedactionService:
    def __init__(
        self,
        config: AppConfig,
        *,
        whisper_client: WhisperClient | None = None,
        lmstudio_client: LMStudioClient | None = None,
        asr_transcriber: Any | None = None,
        transcript_refiner: Any | None = None,
        token_ner_recognizer: Any | None = None,
        llm_ner_recognizer: Any | None = None,
        pii_merger: Any | None = None,
        diarizer: Any | None = None,
        summary_generator: Any | None = None,
        webhook_notifier: Any | None = None,
        auto_start_worker: bool = True,
    ) -> None:
        self.config = config
        self.database = build_database(config)
        self.object_store = build_object_store(config)
        self.audio_processor = AudioProcessor(config.ffmpeg_bin, config.ffprobe_bin)
        self.signer = UrlSigner(config.signing_secret)
        allow_legacy_role_header = config.allow_legacy_role_header and config.auth_mode in {"header_role", "bearer_optional"}
        self.auth = ClaimsAuth(config.auth_secret, allow_legacy_role_header=allow_legacy_role_header)
        self.whisper_client = whisper_client or WhisperClient(config)
        self.lmstudio_client = lmstudio_client or LMStudioClient(config)
        self.summary_generator = summary_generator or SummaryGenerator(self.lmstudio_client, config)
        self.webhook_notifier = webhook_notifier or WebhookNotifier(config)
        self.last_cleanup_result: dict[str, Any] = {"deleted_artifacts": 0, "deleted_storage_keys": 0}
        self.pipeline = PipelineRunner(
            config=config,
            db=self.database,
            object_store=self.object_store,
            audio_processor=self.audio_processor,
            pii_cascade=PiiCascade(),
            transcript_canonicalizer=TranscriptCanonicalizer(),
            asr_transcriber=asr_transcriber or AsrTranscriber(self.whisper_client, config),
            transcript_refiner=transcript_refiner or TranscriptRefiner(self.lmstudio_client, config),
            token_ner_recognizer=token_ner_recognizer or SelfHostedTokenNerRecognizer(config),
            llm_ner_recognizer=llm_ner_recognizer or LlmNerRecognizer(self.lmstudio_client, config),
            pii_merger=pii_merger or PiiMerger(),
            diarizer=diarizer or CompositeDiarizer(config),
            webhook_notifier=self.webhook_notifier,
            retention_callback=self.run_retention_cleanup,
            sync_job_result_callback=self.sync_job_result,
        )
        self.run_retention_cleanup()
        if auto_start_worker:
            self.pipeline.start()

    def shutdown(self) -> None:
        self.pipeline.stop()

    def sync_job_result(self, job_id: str, *, summary_generation_ms: int | None = None) -> None:
        job = self.database.get_job(job_id)
        if not job:
            return
        upload = self.database.get_upload_session(job.upload_id)
        stage_executions = self.database.list_stage_executions(job_id)
        stage_by_name = {stage.name: stage for stage in stage_executions}
        artifacts = self.database.list_artifacts(job_id)
        artifact_by_key = {(artifact.kind, artifact.variant): artifact for artifact in artifacts}

        source_audio = artifact_by_key.get((ArtifactKind.SOURCE_AUDIO, "source"))
        redacted_audio = artifact_by_key.get((ArtifactKind.REDACTED_AUDIO, "redacted"))
        source_transcript_artifact = artifact_by_key.get((ArtifactKind.SOURCE_TRANSCRIPT, "source"))
        redacted_transcript_artifact = artifact_by_key.get((ArtifactKind.REDACTED_TRANSCRIPT, "redacted"))
        summary_artifact = artifact_by_key.get((ArtifactKind.SUMMARY, "redacted"))
        events_artifact = artifact_by_key.get((ArtifactKind.EVENT_LOG, "audit"))

        source_transcript_payload = self.object_store.read_json(source_transcript_artifact.storage_key) if source_transcript_artifact else None
        redacted_transcript_payload = self.object_store.read_json(redacted_transcript_artifact.storage_key) if redacted_transcript_artifact else None
        summary_payload = self.object_store.read_json(summary_artifact.storage_key) if summary_artifact else None

        source_text = self._transcript_text(source_transcript_payload)
        anonymized_text = self._transcript_text(redacted_transcript_payload)
        summary_title = str(summary_payload.get("title")) if summary_payload else None
        summary_text = str(summary_payload.get("summary")) if summary_payload else None
        summary_bullets = list(summary_payload.get("bullets") or []) if summary_payload else []
        summary_confidence = float(summary_payload["confidence"]) if summary_payload and summary_payload.get("confidence") is not None else None

        pii_stage = stage_by_name.get(StageName.PII_DETECTION)
        alignment_stage = stage_by_name.get(StageName.ALIGNMENT)
        speaker_stage = stage_by_name.get(StageName.SPEAKER_ATTRIBUTION)
        finalization_stage = stage_by_name.get(StageName.FINALIZATION)
        events = self.database.list_events(job_id) if events_artifact else []
        entity_counts: dict[str, int] = {}
        for event in events:
            entity_type = str(event["entity_type"])
            entity_counts[entity_type] = entity_counts.get(entity_type, 0) + 1

        existing = self.database.get_job_result(job_id)
        result = JobResultRecord(
            job_id=job.job_id,
            upload_id=job.upload_id,
            trace_id=job.trace_id,
            status=job.status.value,
            stage=job.stage.value,
            created_at=job.created_at,
            updated_at=job.updated_at,
            completed_at=self._completed_at(job, stage_by_name),
            retry_count=job.retry_count,
            source_filename=upload.filename if upload else None,
            source_content_type=upload.content_type if upload else None,
            source_size_bytes=upload.size_bytes if upload else None,
            source_duration_ms=self._artifact_duration_ms(source_audio, upload),
            source_channels=int(upload.metadata.get("channels")) if upload and upload.metadata.get("channels") is not None else None,
            source_sample_rate=int(upload.metadata.get("sample_rate")) if upload and upload.metadata.get("sample_rate") is not None else None,
            source_checksum=upload.checksum if upload else None,
            processing_profile=job.profile.processing_profile,
            model_bundle=job.profile.model_bundle,
            audio_redaction_mode=job.profile.audio_redaction_mode,
            language=self._transcript_language(source_transcript_payload, redacted_transcript_payload),
            speaker_strategy_used=speaker_stage.details.get("strategy") if speaker_stage else None,
            timing_source=alignment_stage.details.get("timing_source") if alignment_stage else None,
            title=summary_title or _title_from_text(anonymized_text, source_text),
            source_text=source_text,
            anonymized_text=anonymized_text,
            summary_text=summary_text,
            summary_bullets=summary_bullets,
            summary_confidence=summary_confidence,
            events=events,
            event_count=len(events),
            entity_counts=entity_counts,
            quality_flags=dict(job.quality_flags),
            pii_confidence_report=pii_stage.details.get("pii_confidence_report") if pii_stage else None,
            evaluation_summary=finalization_stage.details.get("evaluation_summary") if finalization_stage else None,
            total_processing_ms=self._processing_window_ms(stage_by_name, StageName.INGESTION, StageName.FINALIZATION),
            queue_wait_ms=self._queue_wait_ms(job, stage_by_name),
            transcription_ms=self._stage_duration_ms(stage_by_name, StageName.TRANSCRIPTION),
            pii_detection_ms=self._stage_duration_ms(stage_by_name, StageName.PII_DETECTION),
            alignment_ms=self._stage_duration_ms(stage_by_name, StageName.ALIGNMENT),
            audio_redaction_ms=self._stage_duration_ms(stage_by_name, StageName.AUDIO_REDACTION),
            summary_generation_ms=summary_generation_ms if summary_generation_ms is not None else (existing.summary_generation_ms if existing else None),
            source_audio_artifact_id=source_audio.artifact_id if source_audio else None,
            redacted_audio_artifact_id=redacted_audio.artifact_id if redacted_audio else None,
            source_transcript_artifact_id=source_transcript_artifact.artifact_id if source_transcript_artifact else None,
            redacted_transcript_artifact_id=redacted_transcript_artifact.artifact_id if redacted_transcript_artifact else None,
            summary_artifact_id=summary_artifact.artifact_id if summary_artifact else None,
            events_artifact_id=events_artifact.artifact_id if events_artifact else None,
            text_snippet=_snippet(anonymized_text or source_text),
            anonymized_snippet=_snippet(anonymized_text),
            last_error=job.last_error,
            audio_redaction_error=self._audio_redaction_error(job, finalization_stage),
            has_summary=summary_artifact is not None,
            has_redacted_audio=redacted_audio is not None,
        )
        self.database.upsert_job_result(result)

    def _stage_duration_ms(self, stage_by_name: dict[StageName, StageExecution], stage_name: StageName) -> int | None:
        stage = stage_by_name.get(stage_name)
        if not stage or not stage.completed_at:
            return None
        return max(int((stage.completed_at - stage.started_at).total_seconds() * 1000), 0)

    def _processing_window_ms(self, stage_by_name: dict[StageName, StageExecution], start_stage: StageName, end_stage: StageName) -> int | None:
        start = stage_by_name.get(start_stage)
        end = stage_by_name.get(end_stage)
        if not start or not end or not end.completed_at:
            return None
        return max(int((end.completed_at - start.started_at).total_seconds() * 1000), 0)

    def _queue_wait_ms(self, job: JobRecord, stage_by_name: dict[StageName, StageExecution]) -> int | None:
        ingestion = stage_by_name.get(StageName.INGESTION)
        if not ingestion:
            return None
        return max(int((ingestion.started_at - job.created_at).total_seconds() * 1000), 0)

    def _completed_at(self, job: JobRecord, stage_by_name: dict[StageName, StageExecution]) -> datetime | None:
        if job.status not in {JobStatus.COMPLETED, JobStatus.PARTIAL_COMPLETED, JobStatus.DELETED}:
            return None
        finalization = stage_by_name.get(StageName.FINALIZATION)
        return finalization.completed_at if finalization and finalization.completed_at else job.updated_at

    def _artifact_duration_ms(self, source_audio: ArtifactRecord | None, upload: UploadSession | None) -> int | None:
        if source_audio and source_audio.metadata.get("duration_ms") is not None:
            return int(source_audio.metadata["duration_ms"])
        if upload and upload.metadata.get("duration_ms") is not None:
            return int(upload.metadata["duration_ms"])
        return None

    def _audio_redaction_error(self, job: JobRecord, finalization_stage: StageExecution | None) -> str | None:
        if isinstance(job.quality_flags.get("audio_redaction_error"), str):
            return str(job.quality_flags["audio_redaction_error"])
        if finalization_stage and isinstance(finalization_stage.details.get("audio_redaction_error"), str):
            return str(finalization_stage.details["audio_redaction_error"])
        return None

    def _transcript_text(self, payload: dict[str, Any] | None) -> str | None:
        if not payload:
            return None
        return _collapse_text(" ".join(str(segment.get("text") or "") for segment in payload.get("segments") or []))

    def _transcript_language(self, source_payload: dict[str, Any] | None, redacted_payload: dict[str, Any] | None) -> str | None:
        for payload in (source_payload, redacted_payload):
            if payload and payload.get("language"):
                return str(payload["language"])
        return None

    def run_retention_cleanup(self) -> dict[str, Any]:
        now = utcnow()
        expired_artifacts = self.database.list_expired_artifacts(now)
        deleted_storage_keys = 0
        for artifact in expired_artifacts:
            try:
                self.object_store.delete_key(artifact.storage_key)
                deleted_storage_keys += 1
            except Exception:  # noqa: BLE001 - cleanup must be best effort.
                pass
            self.database.delete_artifact(artifact.artifact_id)
        self.last_cleanup_result = {
            "ran_at": now.isoformat(),
            "deleted_artifacts": len(expired_artifacts),
            "deleted_storage_keys": deleted_storage_keys,
        }
        return self.last_cleanup_result

    def create_upload_session(self, *, filename: str, content_type: str, size_bytes: int, base_url: str) -> dict[str, Any]:
        object_key = self.object_store.reserve_upload_key(make_id("upltmp"), filename)
        session = UploadSession.new(
            filename=filename,
            content_type=content_type,
            size_bytes=size_bytes,
            object_key=object_key,
            upload_token=make_id("token"),
            ttl_seconds=self.config.upload_ttl_seconds,
        )
        session.object_key = self.object_store.reserve_upload_key(session.upload_id, filename)
        self.database.create_upload_session(session)
        path = f"/v1/uploads/{session.upload_id}/content"
        expires = int(session.expires_at.timestamp())
        signature = self.signer.sign(method="PUT", path=path, expires=expires)
        return {
            "upload_id": session.upload_id,
            "upload_url": f"{base_url}{path}?{urlencode({'expires': expires, 'signature': signature})}",
            "expires_at": session.expires_at.isoformat(),
        }

    def put_upload_content(self, *, upload_id: str, body: bytes) -> dict[str, Any]:
        session = self.database.get_upload_session(upload_id)
        if not session:
            raise NotFoundError(f"Unknown upload: {upload_id}")
        if utcnow() > session.expires_at:
            session.status = UploadStatus.EXPIRED
            self.database.update_upload_session(session)
            raise ValidationError("Upload session has expired")
        self.object_store.put_bytes(session.object_key, body)
        session.status = UploadStatus.UPLOADED
        session.bytes_received = len(body)
        self.database.update_upload_session(session)
        return {"upload_id": upload_id, "status": session.status.value, "bytes_received": len(body)}

    def create_job(self, payload: dict[str, Any]) -> dict[str, Any]:
        upload_id = payload.get("upload_id")
        if not upload_id:
            raise ValidationError("upload_id is required")
        upload = self.database.get_upload_session(upload_id)
        if not upload or upload.status != UploadStatus.UPLOADED:
            raise ValidationError("upload_id is unknown or not uploaded yet")
        idempotency_key = payload.get("idempotency_key")
        if idempotency_key:
            existing = self.database.get_job_by_idempotency_key(idempotency_key)
            if existing:
                return {"job_id": existing.job_id, "status": existing.status.value, "stage": existing.stage.value}
        profile = ProcessingProfile.from_dict(payload.get("profile"))
        job = JobRecord.new(
            upload_id=upload_id,
            profile=profile,
            webhook_url=payload.get("webhook_url"),
            idempotency_key=idempotency_key,
        )
        self.database.create_job(job)
        self.sync_job_result(job.job_id)
        self.pipeline.enqueue(job.job_id)
        return {"job_id": job.job_id, "status": job.status.value, "stage": job.stage.value}

    def list_jobs(
        self,
        *,
        statuses: list[str] | None = None,
        created_after: str | None = None,
        created_before: str | None = None,
        processing_profile: str | None = None,
        failure_mode: str | None = None,
    ) -> list[dict[str, Any]]:
        jobs = self.database.list_jobs()
        if statuses:
            allowed = set(statuses)
            jobs = [job for job in jobs if job.status.value in allowed]
        if created_after:
            created_after_dt = datetime.fromisoformat(created_after)
            jobs = [job for job in jobs if job.created_at >= created_after_dt]
        if created_before:
            created_before_dt = datetime.fromisoformat(created_before)
            jobs = [job for job in jobs if job.created_at <= created_before_dt]
        if processing_profile:
            jobs = [job for job in jobs if job.profile.processing_profile == processing_profile]
        if failure_mode:
            jobs = [job for job in jobs if job.quality_flags.get("failure_mode") == failure_mode]
        return [
            {
                "job_id": job.job_id,
                "status": job.status.value,
                "stage": job.stage.value,
                "created_at": job.created_at.isoformat(),
                "updated_at": job.updated_at.isoformat(),
                "retry_count": job.retry_count,
                "processing_profile": job.profile.processing_profile,
                "model_bundle": job.profile.model_bundle,
                "quality_flags": job.quality_flags,
                "last_error": job.last_error,
            }
            for job in jobs
        ]

    def retry_job(self, job_id: str) -> dict[str, Any]:
        original = self.database.get_job(job_id)
        if not original:
            raise NotFoundError(f"Unknown job: {job_id}")
        if original.status not in {JobStatus.FAILED, JobStatus.PARTIAL_COMPLETED, JobStatus.COMPLETED}:
            raise ValidationError("Only completed, partial_completed, or failed jobs can be retried")
        upload = self.database.get_upload_session(original.upload_id)
        if not upload or upload.status != UploadStatus.UPLOADED:
            raise ValidationError("Original upload is not available for retry")
        profile = ProcessingProfile.from_dict(
            {
                **to_jsonable(original.profile),
                "metadata": {
                    **dict(original.profile.metadata),
                    "retry_of_job_id": original.job_id,
                    "retry_requested_at": utcnow().isoformat(),
                },
            }
        )
        job = JobRecord.new(
            upload_id=original.upload_id,
            profile=profile,
            webhook_url=original.webhook_url,
            idempotency_key=None,
        )
        self.database.create_job(job)
        self.sync_job_result(job.job_id)
        self.pipeline.enqueue(job.job_id)
        return {"job_id": job.job_id, "status": job.status.value, "stage": job.stage.value}

    def list_job_results(
        self,
        *,
        statuses: list[str] | None = None,
        processing_profile: str | None = None,
        created_after: str | None = None,
        created_before: str | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> list[dict[str, Any]]:
        requested_statuses = statuses or [JobStatus.COMPLETED.value, JobStatus.PARTIAL_COMPLETED.value]
        rows = self.database.list_job_results(
            statuses=requested_statuses,
            processing_profile=processing_profile,
            created_after=created_after,
            created_before=created_before,
            limit=limit,
            offset=offset,
        )
        return [
            {
                "job_id": row.job_id,
                "title": row.title,
                "text_snippet": row.text_snippet,
                "status": row.status,
                "created_at": row.created_at.isoformat(),
                "completed_at": row.completed_at.isoformat() if row.completed_at else None,
                "total_processing_ms": row.total_processing_ms,
                "event_count": row.event_count,
                "source_duration_ms": row.source_duration_ms,
                "processing_profile": row.processing_profile,
                "model_bundle": row.model_bundle,
                "has_summary": row.has_summary,
                "has_redacted_audio": row.has_redacted_audio,
                "last_error": row.last_error,
            }
            for row in rows
        ]

    def get_job_result_detail(
        self,
        *,
        job_id: str,
        base_url: str,
        role: str | None = None,
        authorization: str | None = None,
    ) -> dict[str, Any]:
        row = self.database.get_job_result(job_id)
        if not row:
            raise NotFoundError(f"Unknown job result: {job_id}")
        can_view_source = self._can_access(AccessLevel.RESTRICTED, role=role, authorization=authorization)
        can_view_audit = self._can_access(AccessLevel.AUDIT, role=role, authorization=authorization)
        return {
            "job_id": row.job_id,
            "upload_id": row.upload_id,
            "trace_id": row.trace_id,
            "status": row.status,
            "stage": row.stage,
            "created_at": row.created_at.isoformat(),
            "updated_at": row.updated_at.isoformat(),
            "completed_at": row.completed_at.isoformat() if row.completed_at else None,
            "retry_count": row.retry_count,
            "title": row.title,
            "source_file": {
                "filename": row.source_filename,
                "content_type": row.source_content_type,
                "size_bytes": row.source_size_bytes,
                "duration_ms": row.source_duration_ms,
                "channels": row.source_channels,
                "sample_rate": row.source_sample_rate,
                "checksum": row.source_checksum if can_view_source else None,
            },
            "profile": {
                "processing_profile": row.processing_profile,
                "model_bundle": row.model_bundle,
                "audio_redaction_mode": row.audio_redaction_mode,
                "language": row.language,
                "speaker_strategy_used": row.speaker_strategy_used,
                "timing_source": row.timing_source,
            },
            "source_text": row.source_text if can_view_source else None,
            "anonymized_text": row.anonymized_text,
            "summary": {
                "title": row.title,
                "summary": row.summary_text,
                "bullets": row.summary_bullets,
                "confidence": row.summary_confidence,
            } if row.has_summary else None,
            "events": row.events if can_view_audit else None,
            "entity_counts": row.entity_counts,
            "timings": {
                "total_processing_ms": row.total_processing_ms,
                "queue_wait_ms": row.queue_wait_ms,
                "transcription_ms": row.transcription_ms,
                "pii_detection_ms": row.pii_detection_ms,
                "alignment_ms": row.alignment_ms,
                "audio_redaction_ms": row.audio_redaction_ms,
                "summary_generation_ms": row.summary_generation_ms,
            },
            "artifacts": {
                "source_audio": self._signed_download_url(row.source_audio_artifact_id, base_url) if can_view_source else None,
                "redacted_audio": self._signed_download_url(row.redacted_audio_artifact_id, base_url),
                "source_transcript_artifact_id": row.source_transcript_artifact_id if can_view_source else None,
                "redacted_transcript_artifact_id": row.redacted_transcript_artifact_id,
                "summary_artifact_id": row.summary_artifact_id,
                "events_artifact_id": row.events_artifact_id if can_view_audit else None,
            },
            "quality_flags": row.quality_flags,
            "pii_confidence_report": row.pii_confidence_report,
            "evaluation_summary": row.evaluation_summary,
            "last_error": row.last_error,
            "audio_redaction_error": row.audio_redaction_error,
        }

    def get_job_status(self, job_id: str) -> dict[str, Any]:
        job = self.database.get_job(job_id)
        if not job:
            raise NotFoundError(f"Unknown job: {job_id}")
        stage_executions = self.database.list_stage_executions(job_id)
        recorded = {stage.name: stage for stage in stage_executions}
        stages = []
        for stage in PIPELINE_STAGES:
            stage_record = recorded.get(stage)
            stages.append(
                {
                    "name": stage.value,
                    "status": stage_record.status.value if stage_record else StageStatus.PENDING.value,
                }
            )
        artifacts = self.database.list_artifacts(job_id)
        speaker_stage = recorded.get(StageName.SPEAKER_ATTRIBUTION)
        alignment_stage = recorded.get(StageName.ALIGNMENT)
        pii_stage = recorded.get(StageName.PII_DETECTION)
        finalization_stage = recorded.get(StageName.FINALIZATION)
        return {
            "job_id": job.job_id,
            "status": job.status.value,
            "stage": job.stage.value,
            "progress": round(job.progress, 3),
            "created_at": job.created_at.isoformat(),
            "updated_at": job.updated_at.isoformat(),
            "retry_count": job.retry_count,
            "processing_profile": job.profile.processing_profile,
            "model_bundle": job.profile.model_bundle,
            "stages": stages,
            "stage_executions": [
                {
                    "name": stage.name.value,
                    "status": stage.status.value,
                    "attempt": stage.attempt,
                    "started_at": stage.started_at.isoformat(),
                    "completed_at": stage.completed_at.isoformat() if stage.completed_at else None,
                    "details": stage.details,
                }
                for stage in stage_executions
            ],
            "artifacts": [
                {
                    "kind": artifact.kind.value,
                    "variant": artifact.variant,
                    "access_level": artifact.access_level.value,
                    "content_type": artifact.content_type,
                }
                for artifact in artifacts
            ],
            "speaker_strategy_used": (speaker_stage.details.get("strategy") if speaker_stage else None),
            "timing_source": (alignment_stage.details.get("timing_source") if alignment_stage else None),
            "pii_confidence_report": (pii_stage.details.get("pii_confidence_report") if pii_stage else None),
            "evaluation_summary": (finalization_stage.details.get("evaluation_summary") if finalization_stage else None),
            "quality_flags": job.quality_flags,
            "last_error": job.last_error,
            "model_runs": [
                {
                    "stage_name": run.stage_name.value,
                    "model_name": run.model_name,
                    "model_version": run.model_version,
                    "extra": run.extra,
                }
                for run in self.database.list_model_runs(job_id)
            ],
        }

    def get_transcript(
        self,
        *,
        job_id: str,
        variant: str,
        format_name: str,
        role: str | None = None,
        authorization: str | None = None,
    ) -> tuple[bytes, str]:
        kind = ArtifactKind.SOURCE_TRANSCRIPT if variant == "source" else ArtifactKind.REDACTED_TRANSCRIPT
        self._require_role(role, AccessLevel.RESTRICTED if variant == "source" else AccessLevel.REDACTED, authorization=authorization)
        artifact = self.database.get_artifact(job_id, kind, variant)
        if not artifact:
            raise NotReadyError(f"{variant} transcript is not ready yet")
        payload = self.object_store.read_json(artifact.storage_key)
        if format_name == "srt":
            return transcript_to_srt(payload).encode("utf-8"), _content_type_for_transcript("srt")
        if format_name == "vtt":
            return transcript_to_vtt(payload).encode("utf-8"), _content_type_for_transcript("vtt")
        return json_dumps(payload, indent=2).encode("utf-8"), _content_type_for_transcript("json")

    def get_events(self, *, job_id: str, role: str | None = None, authorization: str | None = None) -> tuple[bytes, str]:
        self._require_role(role, AccessLevel.AUDIT, authorization=authorization)
        artifact = self.database.get_artifact(job_id, ArtifactKind.EVENT_LOG, "audit")
        if not artifact:
            raise NotReadyError("event log is not ready yet")
        payload = self.object_store.read_json(artifact.storage_key)
        return json_dumps(payload, indent=2).encode("utf-8"), "application/json"

    def get_audio_download(
        self,
        *,
        job_id: str,
        variant: str,
        role: str | None,
        base_url: str,
        authorization: str | None = None,
    ) -> dict[str, Any]:
        kind = ArtifactKind.SOURCE_AUDIO if variant == "source" else ArtifactKind.REDACTED_AUDIO
        self._require_role(role, AccessLevel.RESTRICTED if variant == "source" else AccessLevel.REDACTED, authorization=authorization)
        artifact = self.database.get_artifact(job_id, kind, variant)
        if not artifact:
            raise NotReadyError(f"{variant} audio is not ready yet")
        path = f"/v1/download/{artifact.artifact_id}"
        expires_at = int((utcnow().timestamp()) + self.config.download_ttl_seconds)
        signature = self.signer.sign(method="GET", path=path, expires=expires_at)
        return {
            "job_id": job_id,
            "variant": variant,
            "download_url": f"{base_url}{path}?{urlencode({'expires': expires_at, 'signature': signature})}",
            "expires_at": datetime.fromtimestamp(expires_at, tz=utcnow().tzinfo).isoformat(),
        }

    def download_artifact(self, artifact_id: str) -> tuple[Path, str]:
        artifact = self.database.get_artifact_by_id(artifact_id)
        if not artifact:
            raise NotFoundError(f"Unknown artifact: {artifact_id}")
        path = self.object_store.resolve(artifact.storage_key)
        if not path.exists():
            raise NotFoundError("Artifact file is missing from storage")
        return path, artifact.content_type

    def generate_summary(self, job_id: str) -> dict[str, Any]:
        summary_started_at = utcnow()
        job = self.database.get_job(job_id)
        if not job:
            raise NotFoundError(f"Unknown job: {job_id}")
        if job.status not in {JobStatus.COMPLETED, JobStatus.PARTIAL_COMPLETED}:
            raise NotReadyError("Summary can only be generated after job completion")
        existing = self.database.get_artifact(job_id, ArtifactKind.SUMMARY, "redacted")
        if existing:
            self.sync_job_result(job_id)
            return self.object_store.read_json(existing.storage_key)
        transcript_artifact = self.database.get_artifact(job_id, ArtifactKind.REDACTED_TRANSCRIPT, "redacted")
        if not transcript_artifact:
            raise NotReadyError("Redacted transcript is not ready yet")
        transcript_payload = self.object_store.read_json(transcript_artifact.storage_key)
        segments = [self.pipeline._segment_from_dict(item) for item in transcript_payload["segments"]]
        try:
            summary_result = self.summary_generator.generate(segments, job.profile)
        except (LMStudioTransportError, LMStudioSchemaError) as exc:
            job.quality_flags["summary_generation_failure"] = str(exc)
            self.database.update_job(job)
            self.sync_job_result(job_id)
            raise
        payload = {
            "job_id": job_id,
            "variant": "redacted",
            "title": summary_result.title,
            "summary": summary_result.summary,
            "bullets": summary_result.bullets,
            "confidence": summary_result.confidence,
        }
        summary_key = f"jobs/{job_id}/summary/redacted_summary.json"
        self.object_store.put_json(summary_key, payload)
        self.database.store_artifact(
            ArtifactRecord.new(
                job_id=job_id,
                kind=ArtifactKind.SUMMARY,
                variant="redacted",
                storage_key=summary_key,
                access_level=AccessLevel.REDACTED,
                content_type="application/json",
                expires_at=retention_deadline(self.config.redacted_ttl_hours),
                metadata={"prompt_version": summary_result.prompt_version},
            )
        )
        self.database.store_model_run(
            ModelRun.new(
                job_id=job_id,
                stage_name=StageName.FINALIZATION,
                model_name=self.config.lmstudio_llm_model,
                model_version="lmstudio",
                threshold_profile=job.profile.threshold_profile,
                trace_id=job.trace_id,
                extra={
                    "component": "summary",
                    "prompt_version": summary_result.prompt_version,
                    "trace": to_jsonable(summary_result.trace),
                },
            )
        )
        elapsed_ms = max(int((utcnow() - summary_started_at).total_seconds() * 1000), 0)
        self.sync_job_result(job_id, summary_generation_ms=elapsed_ms)
        return payload

    def get_summary(self, *, job_id: str, role: str | None = None, authorization: str | None = None) -> tuple[bytes, str]:
        self._require_role(role, AccessLevel.REDACTED, authorization=authorization)
        artifact = self.database.get_artifact(job_id, ArtifactKind.SUMMARY, "redacted")
        if not artifact:
            raise NotReadyError("summary is not ready yet")
        return json_dumps(self.object_store.read_json(artifact.storage_key), indent=2).encode("utf-8"), "application/json"

    def get_health(self) -> dict[str, Any]:
        return {
            "status": "ok",
            "backend_profile": self.config.backend_profile,
            "database_backend": self.config.database_backend,
            "object_store_backend": self.config.object_store_backend,
        }

    def get_readiness(self) -> tuple[dict[str, Any], bool]:
        checks: dict[str, Any] = {}
        ready = True
        try:
            checks["database"] = {"ready": bool(self.database.ping())}
        except Exception as exc:  # noqa: BLE001
            checks["database"] = {"ready": False, "error": str(exc)}
            ready = False
        try:
            checks["object_store"] = self.object_store.healthcheck()
        except Exception as exc:  # noqa: BLE001
            checks["object_store"] = {"ready": False, "error": str(exc)}
            ready = False
        try:
            report, trace = self.whisper_client.healthcheck()
            checks["whisper"] = {"ready": True, "report": report, "trace": to_jsonable(trace)}
        except Exception as exc:  # noqa: BLE001
            checks["whisper"] = {"ready": False, "error": str(exc)}
            ready = False
        try:
            models = self.lmstudio_client.list_models()
            checks["lmstudio"] = {"ready": True, "model_count": len(models.get("data", []))}
        except Exception as exc:  # noqa: BLE001
            checks["lmstudio"] = {"ready": False, "error": str(exc)}
            ready = False
        if self.config.diarization_base_url:
            try:
                checks["diarization"] = self.diarizer.healthcheck()
            except Exception as exc:  # noqa: BLE001
                checks["diarization"] = {"ready": False, "error": str(exc)}
                ready = False
        return {"status": "ready" if ready else "degraded", "checks": checks}, ready

    def get_metrics(self) -> str:
        jobs_by_status = self.database.count_jobs_by_status()
        artifacts_by_access_level = self.database.count_artifacts_by_access_level()
        lines = [
            "# TYPE tula_jobs_total gauge",
        ]
        for status, total in sorted(jobs_by_status.items()):
            lines.append(f'tula_jobs_total{{status="{status}"}} {total}')
        lines.append("# TYPE tula_artifacts_total gauge")
        for access_level, total in sorted(artifacts_by_access_level.items()):
            lines.append(f'tula_artifacts_total{{access_level="{access_level}"}} {total}')
        lines.append("# TYPE tula_worker_queue_depth gauge")
        lines.append(f"tula_worker_queue_depth {self.pipeline.job_queue.qsize()}")
        lines.append("# TYPE tula_retention_cleanup_deleted_total counter")
        lines.append(f"tula_retention_cleanup_deleted_total {self.last_cleanup_result.get('deleted_artifacts', 0)}")
        return "\n".join(lines) + "\n"

    def delete_job(self, job_id: str) -> dict[str, Any]:
        job = self.database.get_job(job_id)
        if not job:
            raise NotFoundError(f"Unknown job: {job_id}")
        upload = self.database.get_upload_session(job.upload_id)
        self.object_store.delete_prefix(f"jobs/{job_id}")
        if upload:
            self.object_store.delete_prefix(f"uploads/{upload.upload_id}")
        job.status = JobStatus.DELETED
        job.updated_at = utcnow()
        self.database.update_job(job)
        self.sync_job_result(job_id)
        return {"job_id": job_id, "status": job.status.value}

    def create_audio_record_from_upload(self, *, filename: str, content_type: str, body: bytes, base_url: str) -> dict[str, Any]:
        upload = self.create_upload_session(
            filename=filename,
            content_type=content_type,
            size_bytes=len(body),
            base_url=base_url,
        )
        self.put_upload_content(upload_id=upload["upload_id"], body=body)
        session = self.database.get_upload_session(upload["upload_id"])
        if not session:
            raise ServiceError("Failed to load upload session")
        source_path = self.object_store.resolve(session.object_key)
        try:
            metadata = self.audio_processor.probe(source_path, content_type=session.content_type)
        except AudioProcessingError as exc:
            session.metadata = {
                **session.metadata,
                "upload_validation_error": str(exc),
            }
            self.database.update_upload_session(session)
            raise ServiceError(f"Invalid audio file '{filename}': {exc}") from exc
        session.checksum = metadata.checksum
        session.metadata = {
            **session.metadata,
            "duration_ms": metadata.duration_ms,
            "channels": metadata.channels,
            "sample_rate": metadata.sample_rate,
            "bitrate": metadata.bitrate,
            "validated_on_upload": True,
        }
        self.database.update_upload_session(session)
        job = self.create_job({"upload_id": upload["upload_id"], "profile": {}})
        self.sync_job_result(job["job_id"])
        row = self.database.get_job_result(job["job_id"])
        if not row:
            raise ServiceError("Failed to initialize job result")
        return self._audio_record_from_job_result(row=row, base_url=base_url)

    def list_audio_records(
        self,
        *,
        base_url: str,
        search: str | None = None,
        status: str | None = None,
        entity_type: str | None = None,
        sort_by: str | None = None,
        sort_order: str | None = None,
        page: int = 1,
        page_size: int = 20,
        date_from: str | None = None,
        date_to: str | None = None,
    ) -> dict[str, Any]:
        rows = self.database.list_job_results(limit=10000, offset=0)
        if search:
            needle = search.strip().lower()
            rows = [row for row in rows if needle in (row.title or "").lower() or needle in (row.source_filename or "").lower()]
        if status and status != "all":
            rows = [row for row in rows if _to_record_status(row.status) == status]
        if entity_type and entity_type != "all":
            rows = [row for row in rows if int(row.entity_counts.get(entity_type, 0)) > 0]
        if date_from:
            threshold = datetime.fromisoformat(date_from)
            rows = [row for row in rows if row.created_at >= threshold]
        if date_to:
            threshold = datetime.fromisoformat(date_to)
            rows = [row for row in rows if row.created_at <= threshold]

        reverse = (sort_order or "desc").lower() != "asc"
        if sort_by == "title":
            rows = sorted(rows, key=lambda row: (row.title or row.source_filename or "").lower(), reverse=reverse)
        elif sort_by == "durationSec":
            rows = sorted(rows, key=lambda row: int(row.source_duration_ms or 0), reverse=reverse)
        elif sort_by == "status":
            rows = sorted(rows, key=lambda row: _to_record_status(row.status), reverse=reverse)
        else:
            rows = sorted(rows, key=lambda row: row.created_at, reverse=reverse)

        safe_page = max(int(page), 1)
        safe_page_size = max(int(page_size), 1)
        total_items = len(rows)
        total_pages = max((total_items + safe_page_size - 1) // safe_page_size, 1)
        start = (safe_page - 1) * safe_page_size
        paged = rows[start : start + safe_page_size]
        return {
            "items": [self._audio_record_from_job_result(row=row, base_url=base_url) for row in paged],
            "page": safe_page,
            "pageSize": safe_page_size,
            "totalItems": total_items,
            "totalPages": total_pages,
        }

    def get_audio_record_status(self, *, audio_id: str) -> dict[str, Any]:
        row = self.database.get_job_result(audio_id)
        if not row:
            raise NotFoundError(f"Unknown audio record: {audio_id}")
        return {
            "id": row.job_id,
            "status": _to_record_status(row.status),
            "errorMessage": row.last_error,
            "processingStartedAt": row.created_at.isoformat(),
            "processingCompletedAt": row.completed_at.isoformat() if row.completed_at else None,
        }

    def get_audio_record_details(self, *, audio_id: str, base_url: str) -> dict[str, Any]:
        row = self.database.get_job_result(audio_id)
        if not row:
            raise NotFoundError(f"Unknown audio record: {audio_id}")
        record = self._audio_record_from_job_result(row=row, base_url=base_url)
        source_payload = self._read_transcript_payload(row.source_transcript_artifact_id)
        redacted_payload = self._read_transcript_payload(row.redacted_transcript_artifact_id)
        summary_payload = self._read_json_artifact(row.summary_artifact_id)
        events_payload = self._read_json_artifact(row.events_artifact_id) or {"events": row.events}
        stage_executions = self.database.list_stage_executions(row.job_id)

        entities: list[dict[str, Any]] = []
        entities_by_segment: dict[str, list[dict[str, Any]]] = {}
        for event in list(events_payload.get("events") or []):
            payload = event.get("payload") or {}
            entity_id = str(payload.get("entity_id") or event.get("event_id"))
            segment_id = str(payload.get("segment_id") or "")
            entity = {
                "id": entity_id,
                "type": event.get("entity_type"),
                "startMs": int(event.get("start_ms") or 0),
                "endMs": int(event.get("end_ms") or 0),
                "segmentIds": [segment_id] if segment_id else [],
                "originalValue": payload.get("entity_text"),
                "redactedValue": payload.get("replacement_text") or f"[{event.get('entity_type')}]",
                "confidence": float(event.get("confidence") or 0.0),
                "isApplied": str(event.get("action") or "").lower() == "redact",
            }
            entities.append(entity)
            if segment_id:
                entities_by_segment.setdefault(segment_id, []).append(entity)

        source_segments = list((source_payload or {}).get("segments") or [])
        redacted_by_id = {str(item.get("segment_id")): item for item in list((redacted_payload or {}).get("segments") or [])}
        transcript: list[dict[str, Any]] = []
        for source in source_segments:
            segment_id = str(source.get("segment_id"))
            redacted = redacted_by_id.get(segment_id, source)
            original_text = str(source.get("text") or "")
            redacted_text = str(redacted.get("text") or original_text)
            segment_entities = entities_by_segment.get(segment_id, [])
            mentions: list[dict[str, Any]] = []
            for entity in segment_entities:
                token = str(entity["redactedValue"])
                start = redacted_text.find(token)
                if start >= 0:
                    mentions.append({"entityId": entity["id"], "startOffset": start, "endOffset": start + len(token)})
            transcript.append(
                {
                    "id": segment_id,
                    "startMs": int(source.get("start_ms") or 0),
                    "endMs": int(source.get("end_ms") or 0),
                    "speakerLabel": source.get("speaker_id"),
                    "originalText": original_text,
                    "redactedText": redacted_text,
                    "hasRedactions": original_text != redacted_text,
                    "entityRefs": [entity["id"] for entity in segment_entities],
                    "mentions": mentions,
                }
            )

        summaries: list[dict[str, Any]] = []
        if summary_payload:
            summaries.append(
                {
                    "id": f"summary_{row.job_id}",
                    "kind": "short",
                    "text": str(summary_payload.get("summary") or ""),
                    "generatedAt": (row.completed_at or row.updated_at).isoformat(),
                }
            )
        logs = [
            {
                "id": f"log_{stage.name.value}",
                "at": stage.started_at.isoformat(),
                "level": "error" if stage.status == StageStatus.FAILED else "info",
                "stage": stage.name.value,
                "message": f"Stage {stage.name.value} -> {stage.status.value}",
                "meta": stage.details,
            }
            for stage in stage_executions
        ]
        waveform = [
            {
                "id": f"region_{index}",
                "startMs": int(entity["startMs"]),
                "endMs": int(entity["endMs"]),
                "entityTypes": [entity["type"]],
                "entityIds": [entity["id"]],
                "severity": self._to_contract_severity(entity_severity(str(entity["type"]))),
                "redacted": bool(entity["isApplied"]),
            }
            for index, entity in enumerate(entities, start=1)
        ]
        available_views = ["redacted"] if row.source_text is None else ["redacted", "original"]
        return {
            "record": record,
            "transcript": transcript,
            "entities": entities,
            "summaries": summaries,
            "logs": logs,
            "waveform": waveform,
            "availableViews": available_views,
        }

    def get_stats_overview(self) -> dict[str, Any]:
        rows = self.database.list_job_results(limit=10000, offset=0)
        processed_rows = [row for row in rows if row.status in {JobStatus.COMPLETED.value, JobStatus.PARTIAL_COMPLETED.value}]
        processed_files = len(processed_rows)
        total_duration_ms = sum(int(row.source_duration_ms or 0) for row in processed_rows)
        processing_ms = [int(row.total_processing_ms or 0) for row in processed_rows if row.total_processing_ms is not None]
        avg_processing_sec = (sum(processing_ms) / len(processing_ms) / 1000.0) if processing_ms else 0.0
        detected_entities = sum(int(row.event_count or 0) for row in processed_rows)
        entity_totals: dict[str, int] = {}
        for row in processed_rows:
            for key, value in row.entity_counts.items():
                entity_totals[key] = entity_totals.get(key, 0) + int(value)
        top_entity_types = [key for key, _ in sorted(entity_totals.items(), key=lambda item: item[1], reverse=True)[:5]]
        monthly_totals: dict[str, int] = {}
        for row in processed_rows:
            period = row.created_at.strftime("%Y-%m-01")
            monthly_totals[period] = monthly_totals.get(period, 0) + 1
        monthly_processed_files = [
            {"periodStart": period, "label": period[:7], "value": count}
            for period, count in sorted(monthly_totals.items())
        ]
        status_counts = {"completed": 0, "processing": 0, "failed": 0, "queued": 0}
        for row in rows:
            status = _to_record_status(row.status)
            if status in status_counts:
                status_counts[status] += 1
        status_distribution = [{"status": key, "count": value} for key, value in status_counts.items()]
        return {
            "processedFiles": processed_files,
            "processedAudioHours": round(total_duration_ms / 3_600_000, 4),
            "averageProcessingTimeSec": round(avg_processing_sec, 3),
            "averageProcessingTimeChangePct": 0.0,
            "timingCompliancePct": 100.0 if processed_files > 0 else 0.0,
            "detectedEntities": detected_entities,
            "detectedEntitiesChangePct": 0.0,
            "topEntityTypes": top_entity_types,
            "recognitionAccuracyPct": 0.0,
            "recognitionAccuracyChangePct": 0.0,
            "monthlyProcessedFilesChangePct": 0.0,
            "monthlyProcessedFiles": monthly_processed_files,
            "entityDetections": [{"type": key, "count": value} for key, value in sorted(entity_totals.items())],
            "statusDistribution": status_distribution,
        }

    def get_docs_config(self) -> dict[str, Any]:
        endpoints = [
            {
                "id": "audio_list",
                "title": "List audio records",
                "method": "GET",
                "path": "/audio",
                "description": "Returns paginated audio records.",
                "headers": [{"name": "X-Token", "value": "<token>", "required": True}],
                "requestExample": "GET /audio?page=1&pageSize=20",
                "responseExample": '{"items":[],"page":1,"pageSize":20,"totalItems":0,"totalPages":1}',
                "curlExample": "curl -H 'X-Token: <token>' http://localhost:8080/audio",
            },
            {
                "id": "audio_upload",
                "title": "Upload and enqueue audio",
                "method": "POST",
                "path": "/audio",
                "description": "Uploads one or more files and starts processing jobs.",
                "headers": [{"name": "X-Token", "value": "<token>", "required": True}],
                "requestExample": "multipart/form-data files[]",
                "responseExample": '{"items":[{"id":"job_...","status":"queued"}]}',
                "curlExample": "curl -H 'X-Token: <token>' -F 'files=@call.wav' http://localhost:8080/audio",
            },
            {
                "id": "audio_details",
                "title": "Get record details",
                "method": "GET",
                "path": "/audio/{audioId}",
                "description": "Returns detailed transcript, entities, logs, and waveform.",
                "headers": [{"name": "X-Token", "value": "<token>", "required": True}],
                "requestExample": "GET /audio/job_123",
                "responseExample": '{"record":{"id":"job_123"},"transcript":[],"entities":[],"summaries":[],"logs":[],"waveform":[],"availableViews":["redacted"]}',
                "curlExample": "curl -H 'X-Token: <token>' http://localhost:8080/audio/job_123",
            },
        ]
        return {
            "baseUrl": "/api/v1",
            "tokenLabel": "X-Token",
            "tokenValue": None,
            "endpoints": endpoints,
        }

    def get_public_audio_download(self, *, job_id: str, variant: str, base_url: str) -> dict[str, Any]:
        return self.get_audio_download(
            job_id=job_id,
            variant=variant,
            role="privileged",
            authorization=None,
            base_url=base_url,
        )

    def _read_json_artifact(self, artifact_id: str | None) -> dict[str, Any] | None:
        if not artifact_id:
            return None
        artifact = self.database.get_artifact_by_id(artifact_id)
        if not artifact:
            return None
        return self.object_store.read_json(artifact.storage_key)

    def _read_transcript_payload(self, artifact_id: str | None) -> dict[str, Any] | None:
        payload = self._read_json_artifact(artifact_id)
        if not payload:
            return None
        return payload

    def _audio_record_from_job_result(self, *, row: JobResultRecord, base_url: str) -> dict[str, Any]:
        source_url_payload = self._signed_download_url(row.source_audio_artifact_id, base_url) if row.source_audio_artifact_id else None
        redacted_url_payload = self._signed_download_url(row.redacted_audio_artifact_id, base_url) if row.redacted_audio_artifact_id else None
        return {
            "id": row.job_id,
            "title": row.title or row.source_filename or row.job_id,
            "originalFileName": row.source_filename or "unknown",
            "processedFileName": f"{Path(row.source_filename).stem}_redacted.wav" if row.source_filename else None,
            "originalFileUrl": source_url_payload["download_url"] if source_url_payload else None,
            "processedFileUrl": redacted_url_payload["download_url"] if redacted_url_payload else None,
            "createdAt": row.created_at.isoformat(),
            "durationSec": round((int(row.source_duration_ms or 0) / 1000.0), 3),
            "status": _to_record_status(row.status),
            "foundEntities": [{"type": entity_type, "count": int(count)} for entity_type, count in sorted(row.entity_counts.items())],
            "errorMessage": row.last_error,
            "processingStartedAt": row.created_at.isoformat(),
            "processingCompletedAt": row.completed_at.isoformat() if row.completed_at else None,
            "canDownloadProcessedAudio": bool(row.redacted_audio_artifact_id),
        }

    def _to_contract_severity(self, severity: str | None) -> str | None:
        if severity in {"low", "medium", "high"}:
            return severity
        if severity in {"critical", "severe"}:
            return "high"
        return None

    def _require_role(self, role: str | None, required: AccessLevel, *, authorization: str | None = None) -> None:
        try:
            permissions = self.auth.resolve_access_levels(authorization=authorization, legacy_role=role)
        except AuthError as exc:
            raise AuthorizationError(str(exc)) from exc
        if required not in permissions:
            raise AuthorizationError("The caller does not have access to the requested artifact")

    def _can_access(self, required: AccessLevel, *, role: str | None, authorization: str | None) -> bool:
        try:
            self._require_role(role, required, authorization=authorization)
        except AuthorizationError:
            return False
        return True

    def _signed_download_url(self, artifact_id: str | None, base_url: str) -> dict[str, Any] | None:
        if not artifact_id:
            return None
        path = f"/v1/download/{artifact_id}"
        expires_at = int((utcnow().timestamp()) + self.config.download_ttl_seconds)
        signature = self.signer.sign(method="GET", path=path, expires=expires_at)
        return {
            "artifact_id": artifact_id,
            "download_url": f"{base_url}{path}?{urlencode({'expires': expires_at, 'signature': signature})}",
            "expires_at": datetime.fromtimestamp(expires_at, tz=utcnow().tzinfo).isoformat(),
        }
