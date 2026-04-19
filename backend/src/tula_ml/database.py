from __future__ import annotations

from datetime import datetime
from pathlib import Path
from sqlite3 import Row
from typing import Iterable, Sequence
import json
import sqlite3

from .config import AppConfig
from .json_utils import to_jsonable
from .models import (
    AccessLevel,
    ArtifactKind,
    ArtifactRecord,
    JobResultRecord,
    JobRecord,
    JobStatus,
    ModelRun,
    PIPELINE_STAGES,
    ProcessingProfile,
    StageExecution,
    StageName,
    StageStatus,
    UploadSession,
    UploadStatus,
)


class Database:
    def __init__(self, path: Path) -> None:
        self.path = path
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._init_schema()

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.path, check_same_thread=False)
        connection.row_factory = Row
        return connection

    def _init_schema(self) -> None:
        statements = (
            """
            CREATE TABLE IF NOT EXISTS upload_sessions (
                upload_id TEXT PRIMARY KEY,
                filename TEXT NOT NULL,
                content_type TEXT NOT NULL,
                size_bytes INTEGER NOT NULL,
                object_key TEXT NOT NULL,
                upload_token TEXT NOT NULL,
                created_at TEXT NOT NULL,
                expires_at TEXT NOT NULL,
                status TEXT NOT NULL,
                checksum TEXT,
                bytes_received INTEGER NOT NULL,
                metadata_json TEXT NOT NULL
            )
            """,
            """
            CREATE TABLE IF NOT EXISTS jobs (
                job_id TEXT PRIMARY KEY,
                upload_id TEXT NOT NULL,
                profile_json TEXT NOT NULL,
                webhook_url TEXT,
                idempotency_key TEXT,
                status TEXT NOT NULL,
                stage TEXT NOT NULL,
                progress REAL NOT NULL,
                trace_id TEXT NOT NULL,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                last_error TEXT,
                retry_count INTEGER NOT NULL DEFAULT 0,
                quality_flags_json TEXT NOT NULL
            )
            """,
            """
            CREATE UNIQUE INDEX IF NOT EXISTS idx_jobs_idempotency
            ON jobs(idempotency_key)
            WHERE idempotency_key IS NOT NULL
            """,
            """
            CREATE TABLE IF NOT EXISTS stage_executions (
                job_id TEXT NOT NULL,
                name TEXT NOT NULL,
                status TEXT NOT NULL,
                attempt INTEGER NOT NULL,
                started_at TEXT NOT NULL,
                completed_at TEXT,
                details_json TEXT NOT NULL,
                PRIMARY KEY (job_id, name)
            )
            """,
            """
            CREATE TABLE IF NOT EXISTS artifacts (
                artifact_id TEXT PRIMARY KEY,
                job_id TEXT NOT NULL,
                kind TEXT NOT NULL,
                variant TEXT NOT NULL,
                storage_key TEXT NOT NULL,
                access_level TEXT NOT NULL,
                content_type TEXT NOT NULL,
                created_at TEXT NOT NULL,
                expires_at TEXT,
                metadata_json TEXT NOT NULL,
                UNIQUE(job_id, kind, variant)
            )
            """,
            """
            CREATE TABLE IF NOT EXISTS events (
                event_id TEXT PRIMARY KEY,
                job_id TEXT NOT NULL,
                entity_type TEXT NOT NULL,
                speaker_id TEXT NOT NULL,
                start_ms INTEGER NOT NULL,
                end_ms INTEGER NOT NULL,
                confidence REAL NOT NULL,
                sources_json TEXT NOT NULL,
                action TEXT NOT NULL,
                payload_json TEXT NOT NULL
            )
            """,
            """
            CREATE TABLE IF NOT EXISTS model_runs (
                run_id TEXT PRIMARY KEY,
                job_id TEXT NOT NULL,
                stage_name TEXT NOT NULL,
                model_name TEXT NOT NULL,
                model_version TEXT NOT NULL,
                threshold_profile TEXT NOT NULL,
                trace_id TEXT NOT NULL,
                created_at TEXT NOT NULL,
                extra_json TEXT NOT NULL
            )
            """,
            """
            CREATE TABLE IF NOT EXISTS job_results (
                job_id TEXT PRIMARY KEY,
                upload_id TEXT NOT NULL,
                trace_id TEXT NOT NULL,
                status TEXT NOT NULL,
                stage TEXT NOT NULL,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                completed_at TEXT,
                retry_count INTEGER NOT NULL DEFAULT 0,
                source_filename TEXT,
                source_content_type TEXT,
                source_size_bytes INTEGER,
                source_duration_ms INTEGER,
                source_channels INTEGER,
                source_sample_rate INTEGER,
                source_checksum TEXT,
                processing_profile TEXT,
                model_bundle TEXT,
                audio_redaction_mode TEXT,
                language TEXT,
                speaker_strategy_used TEXT,
                timing_source TEXT,
                title TEXT,
                source_text TEXT,
                anonymized_text TEXT,
                summary_text TEXT,
                summary_bullets_json TEXT NOT NULL DEFAULT '[]',
                summary_confidence REAL,
                events_json TEXT NOT NULL DEFAULT '[]',
                event_count INTEGER NOT NULL DEFAULT 0,
                entity_counts_json TEXT NOT NULL DEFAULT '{}',
                quality_flags_json TEXT NOT NULL DEFAULT '{}',
                pii_confidence_report_json TEXT,
                evaluation_summary_json TEXT,
                total_processing_ms INTEGER,
                queue_wait_ms INTEGER,
                transcription_ms INTEGER,
                pii_detection_ms INTEGER,
                alignment_ms INTEGER,
                audio_redaction_ms INTEGER,
                summary_generation_ms INTEGER,
                source_audio_artifact_id TEXT,
                redacted_audio_artifact_id TEXT,
                source_transcript_artifact_id TEXT,
                redacted_transcript_artifact_id TEXT,
                summary_artifact_id TEXT,
                events_artifact_id TEXT,
                text_snippet TEXT,
                anonymized_snippet TEXT,
                last_error TEXT,
                audio_redaction_error TEXT,
                has_summary INTEGER NOT NULL DEFAULT 0,
                has_redacted_audio INTEGER NOT NULL DEFAULT 0
            )
            """,
            "CREATE INDEX IF NOT EXISTS idx_job_results_created_at ON job_results(created_at DESC)",
            "CREATE INDEX IF NOT EXISTS idx_job_results_status_created_at ON job_results(status, created_at DESC)",
            "CREATE INDEX IF NOT EXISTS idx_job_results_processing_profile ON job_results(processing_profile)",
            """
            CREATE INDEX IF NOT EXISTS idx_job_results_completed_at
            ON job_results(completed_at DESC)
            WHERE status IN ('completed', 'partial_completed')
            """,
        )
        with self._connect() as connection:
            for statement in statements:
                connection.execute(statement)
            self._migrate(connection)
            connection.commit()

    def _migrate(self, connection: sqlite3.Connection) -> None:
        job_columns = {row["name"] for row in connection.execute("PRAGMA table_info(jobs)").fetchall()}
        if "retry_count" not in job_columns:
            connection.execute("ALTER TABLE jobs ADD COLUMN retry_count INTEGER NOT NULL DEFAULT 0")

    def create_upload_session(self, session: UploadSession) -> None:
        with self._connect() as connection:
            connection.execute(
                """
                INSERT INTO upload_sessions (
                    upload_id, filename, content_type, size_bytes, object_key, upload_token,
                    created_at, expires_at, status, checksum, bytes_received, metadata_json
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    session.upload_id,
                    session.filename,
                    session.content_type,
                    session.size_bytes,
                    session.object_key,
                    session.upload_token,
                    session.created_at.isoformat(),
                    session.expires_at.isoformat(),
                    session.status.value,
                    session.checksum,
                    session.bytes_received,
                    json.dumps(to_jsonable(session.metadata), ensure_ascii=False),
                ),
            )
            connection.commit()

    def update_upload_session(self, session: UploadSession) -> None:
        with self._connect() as connection:
            connection.execute(
                """
                UPDATE upload_sessions
                SET filename = ?, content_type = ?, size_bytes = ?, object_key = ?, upload_token = ?,
                    created_at = ?, expires_at = ?, status = ?, checksum = ?, bytes_received = ?,
                    metadata_json = ?
                WHERE upload_id = ?
                """,
                (
                    session.filename,
                    session.content_type,
                    session.size_bytes,
                    session.object_key,
                    session.upload_token,
                    session.created_at.isoformat(),
                    session.expires_at.isoformat(),
                    session.status.value,
                    session.checksum,
                    session.bytes_received,
                    json.dumps(to_jsonable(session.metadata), ensure_ascii=False),
                    session.upload_id,
                ),
            )
            connection.commit()

    def get_upload_session(self, upload_id: str) -> UploadSession | None:
        with self._connect() as connection:
            row = connection.execute(
                "SELECT * FROM upload_sessions WHERE upload_id = ?",
                (upload_id,),
            ).fetchone()
        return self._row_to_upload(row) if row else None

    def create_job(self, job: JobRecord) -> None:
        with self._connect() as connection:
            connection.execute(
                """
                INSERT INTO jobs (
                    job_id, upload_id, profile_json, webhook_url, idempotency_key, status, stage,
                    progress, trace_id, created_at, updated_at, last_error, retry_count, quality_flags_json
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    job.job_id,
                    job.upload_id,
                    json.dumps(to_jsonable(job.profile), ensure_ascii=False),
                    job.webhook_url,
                    job.idempotency_key,
                    job.status.value,
                    job.stage.value,
                    job.progress,
                    job.trace_id,
                    job.created_at.isoformat(),
                    job.updated_at.isoformat(),
                    job.last_error,
                    job.retry_count,
                    json.dumps(to_jsonable(job.quality_flags), ensure_ascii=False),
                ),
            )
            connection.commit()

    def update_job(self, job: JobRecord) -> None:
        with self._connect() as connection:
            connection.execute(
                """
                UPDATE jobs
                SET upload_id = ?, profile_json = ?, webhook_url = ?, idempotency_key = ?, status = ?,
                    stage = ?, progress = ?, trace_id = ?, created_at = ?, updated_at = ?,
                    last_error = ?, retry_count = ?, quality_flags_json = ?
                WHERE job_id = ?
                """,
                (
                    job.upload_id,
                    json.dumps(to_jsonable(job.profile), ensure_ascii=False),
                    job.webhook_url,
                    job.idempotency_key,
                    job.status.value,
                    job.stage.value,
                    job.progress,
                    job.trace_id,
                    job.created_at.isoformat(),
                    job.updated_at.isoformat(),
                    job.last_error,
                    job.retry_count,
                    json.dumps(to_jsonable(job.quality_flags), ensure_ascii=False),
                    job.job_id,
                ),
            )
            connection.commit()

    def get_job(self, job_id: str) -> JobRecord | None:
        with self._connect() as connection:
            row = connection.execute("SELECT * FROM jobs WHERE job_id = ?", (job_id,)).fetchone()
        return self._row_to_job(row) if row else None

    def get_job_by_idempotency_key(self, idempotency_key: str) -> JobRecord | None:
        with self._connect() as connection:
            row = connection.execute(
                "SELECT * FROM jobs WHERE idempotency_key = ?",
                (idempotency_key,),
            ).fetchone()
        return self._row_to_job(row) if row else None

    def list_jobs(self) -> list[JobRecord]:
        with self._connect() as connection:
            rows = connection.execute("SELECT * FROM jobs ORDER BY created_at DESC").fetchall()
        return [self._row_to_job(row) for row in rows]

    def list_jobs_by_status(self, statuses: Iterable[JobStatus]) -> list[JobRecord]:
        statuses = list(statuses)
        if not statuses:
            return []
        placeholders = ",".join("?" for _ in statuses)
        with self._connect() as connection:
            rows = connection.execute(
                f"SELECT * FROM jobs WHERE status IN ({placeholders}) ORDER BY created_at",
                tuple(status.value for status in statuses),
            ).fetchall()
        return [self._row_to_job(row) for row in rows]

    def count_jobs_by_status(self) -> dict[str, int]:
        with self._connect() as connection:
            rows = connection.execute(
                "SELECT status, COUNT(*) AS total FROM jobs GROUP BY status"
            ).fetchall()
        return {row["status"]: int(row["total"]) for row in rows}

    def upsert_stage_execution(self, stage_execution: StageExecution) -> None:
        with self._connect() as connection:
            connection.execute(
                """
                INSERT INTO stage_executions (
                    job_id, name, status, attempt, started_at, completed_at, details_json
                ) VALUES (?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(job_id, name) DO UPDATE SET
                    status = excluded.status,
                    attempt = excluded.attempt,
                    started_at = excluded.started_at,
                    completed_at = excluded.completed_at,
                    details_json = excluded.details_json
                """,
                (
                    stage_execution.job_id,
                    stage_execution.name.value,
                    stage_execution.status.value,
                    stage_execution.attempt,
                    stage_execution.started_at.isoformat(),
                    stage_execution.completed_at.isoformat() if stage_execution.completed_at else None,
                    json.dumps(to_jsonable(stage_execution.details), ensure_ascii=False),
                ),
            )
            connection.commit()

    def list_stage_executions(self, job_id: str) -> list[StageExecution]:
        with self._connect() as connection:
            rows = connection.execute(
                "SELECT * FROM stage_executions WHERE job_id = ?",
                (job_id,),
            ).fetchall()
        stage_order = {stage.value: index for index, stage in enumerate(PIPELINE_STAGES)}
        rows = sorted(rows, key=lambda row: stage_order.get(row["name"], 999))
        return [self._row_to_stage(row) for row in rows]

    def store_artifact(self, artifact: ArtifactRecord) -> None:
        with self._connect() as connection:
            connection.execute(
                """
                INSERT INTO artifacts (
                    artifact_id, job_id, kind, variant, storage_key, access_level,
                    content_type, created_at, expires_at, metadata_json
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(job_id, kind, variant) DO UPDATE SET
                    artifact_id = excluded.artifact_id,
                    storage_key = excluded.storage_key,
                    access_level = excluded.access_level,
                    content_type = excluded.content_type,
                    created_at = excluded.created_at,
                    expires_at = excluded.expires_at,
                    metadata_json = excluded.metadata_json
                """,
                (
                    artifact.artifact_id,
                    artifact.job_id,
                    artifact.kind.value,
                    artifact.variant,
                    artifact.storage_key,
                    artifact.access_level.value,
                    artifact.content_type,
                    artifact.created_at.isoformat(),
                    artifact.expires_at.isoformat() if artifact.expires_at else None,
                    json.dumps(to_jsonable(artifact.metadata), ensure_ascii=False),
                ),
            )
            connection.commit()

    def list_artifacts(self, job_id: str) -> list[ArtifactRecord]:
        with self._connect() as connection:
            rows = connection.execute(
                "SELECT * FROM artifacts WHERE job_id = ? ORDER BY created_at",
                (job_id,),
            ).fetchall()
        return [self._row_to_artifact(row) for row in rows]

    def count_artifacts_by_access_level(self) -> dict[str, int]:
        with self._connect() as connection:
            rows = connection.execute(
                "SELECT access_level, COUNT(*) AS total FROM artifacts GROUP BY access_level"
            ).fetchall()
        return {row["access_level"]: int(row["total"]) for row in rows}

    def get_artifact(self, job_id: str, kind: ArtifactKind, variant: str) -> ArtifactRecord | None:
        with self._connect() as connection:
            row = connection.execute(
                "SELECT * FROM artifacts WHERE job_id = ? AND kind = ? AND variant = ?",
                (job_id, kind.value, variant),
            ).fetchone()
        return self._row_to_artifact(row) if row else None

    def get_artifact_by_id(self, artifact_id: str) -> ArtifactRecord | None:
        with self._connect() as connection:
            row = connection.execute(
                "SELECT * FROM artifacts WHERE artifact_id = ?",
                (artifact_id,),
            ).fetchone()
        return self._row_to_artifact(row) if row else None

    def list_expired_artifacts(self, now: datetime) -> list[ArtifactRecord]:
        with self._connect() as connection:
            rows = connection.execute(
                "SELECT * FROM artifacts WHERE expires_at IS NOT NULL AND expires_at <= ?",
                (now.isoformat(),),
            ).fetchall()
        return [self._row_to_artifact(row) for row in rows]

    def delete_artifact(self, artifact_id: str) -> None:
        with self._connect() as connection:
            connection.execute("DELETE FROM artifacts WHERE artifact_id = ?", (artifact_id,))
            connection.commit()

    def replace_events(self, job_id: str, events: Sequence[dict[str, object]]) -> None:
        with self._connect() as connection:
            connection.execute("DELETE FROM events WHERE job_id = ?", (job_id,))
            connection.executemany(
                """
                INSERT INTO events (
                    event_id, job_id, entity_type, speaker_id, start_ms, end_ms,
                    confidence, sources_json, action, payload_json
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                [
                    (
                        event["event_id"],
                        job_id,
                        event["entity_type"],
                        event["speaker_id"],
                        event["start_ms"],
                        event["end_ms"],
                        event["confidence"],
                        json.dumps(event["sources"], ensure_ascii=False),
                        event["action"],
                        json.dumps(event["payload"], ensure_ascii=False),
                    )
                    for event in events
                ],
            )
            connection.commit()

    def list_events(self, job_id: str) -> list[dict[str, object]]:
        with self._connect() as connection:
            rows = connection.execute(
                "SELECT * FROM events WHERE job_id = ? ORDER BY start_ms, end_ms",
                (job_id,),
            ).fetchall()
        return [
            {
                "event_id": row["event_id"],
                "entity_type": row["entity_type"],
                "speaker_id": row["speaker_id"],
                "start_ms": row["start_ms"],
                "end_ms": row["end_ms"],
                "confidence": row["confidence"],
                "sources": json.loads(row["sources_json"]),
                "action": row["action"],
                "payload": json.loads(row["payload_json"]),
            }
            for row in rows
        ]

    def store_model_run(self, run: ModelRun) -> None:
        with self._connect() as connection:
            connection.execute(
                """
                INSERT INTO model_runs (
                    run_id, job_id, stage_name, model_name, model_version,
                    threshold_profile, trace_id, created_at, extra_json
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    run.run_id,
                    run.job_id,
                    run.stage_name.value,
                    run.model_name,
                    run.model_version,
                    run.threshold_profile,
                    run.trace_id,
                    run.created_at.isoformat(),
                    json.dumps(to_jsonable(run.extra), ensure_ascii=False),
                ),
            )
            connection.commit()

    def list_model_runs(self, job_id: str) -> list[ModelRun]:
        with self._connect() as connection:
            rows = connection.execute(
                "SELECT * FROM model_runs WHERE job_id = ? ORDER BY created_at",
                (job_id,),
            ).fetchall()
        return [self._row_to_model_run(row) for row in rows]

    def ping(self) -> bool:
        with self._connect() as connection:
            row = connection.execute("SELECT 1 AS ok").fetchone()
        return bool(row["ok"])

    def upsert_job_result(self, result: JobResultRecord) -> None:
        with self._connect() as connection:
            connection.execute(
                """
                INSERT INTO job_results (
                    job_id, upload_id, trace_id, status, stage, created_at, updated_at, completed_at, retry_count,
                    source_filename, source_content_type, source_size_bytes, source_duration_ms, source_channels, source_sample_rate,
                    source_checksum, processing_profile, model_bundle, audio_redaction_mode, language, speaker_strategy_used,
                    timing_source, title, source_text, anonymized_text, summary_text, summary_bullets_json, summary_confidence,
                    events_json, event_count, entity_counts_json, quality_flags_json, pii_confidence_report_json, evaluation_summary_json,
                    total_processing_ms, queue_wait_ms, transcription_ms, pii_detection_ms, alignment_ms, audio_redaction_ms,
                    summary_generation_ms, source_audio_artifact_id, redacted_audio_artifact_id, source_transcript_artifact_id,
                    redacted_transcript_artifact_id, summary_artifact_id, events_artifact_id, text_snippet, anonymized_snippet,
                    last_error, audio_redaction_error, has_summary, has_redacted_audio
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(job_id) DO UPDATE SET
                    upload_id = excluded.upload_id,
                    trace_id = excluded.trace_id,
                    status = excluded.status,
                    stage = excluded.stage,
                    created_at = excluded.created_at,
                    updated_at = excluded.updated_at,
                    completed_at = excluded.completed_at,
                    retry_count = excluded.retry_count,
                    source_filename = excluded.source_filename,
                    source_content_type = excluded.source_content_type,
                    source_size_bytes = excluded.source_size_bytes,
                    source_duration_ms = excluded.source_duration_ms,
                    source_channels = excluded.source_channels,
                    source_sample_rate = excluded.source_sample_rate,
                    source_checksum = excluded.source_checksum,
                    processing_profile = excluded.processing_profile,
                    model_bundle = excluded.model_bundle,
                    audio_redaction_mode = excluded.audio_redaction_mode,
                    language = excluded.language,
                    speaker_strategy_used = excluded.speaker_strategy_used,
                    timing_source = excluded.timing_source,
                    title = excluded.title,
                    source_text = excluded.source_text,
                    anonymized_text = excluded.anonymized_text,
                    summary_text = excluded.summary_text,
                    summary_bullets_json = excluded.summary_bullets_json,
                    summary_confidence = excluded.summary_confidence,
                    events_json = excluded.events_json,
                    event_count = excluded.event_count,
                    entity_counts_json = excluded.entity_counts_json,
                    quality_flags_json = excluded.quality_flags_json,
                    pii_confidence_report_json = excluded.pii_confidence_report_json,
                    evaluation_summary_json = excluded.evaluation_summary_json,
                    total_processing_ms = excluded.total_processing_ms,
                    queue_wait_ms = excluded.queue_wait_ms,
                    transcription_ms = excluded.transcription_ms,
                    pii_detection_ms = excluded.pii_detection_ms,
                    alignment_ms = excluded.alignment_ms,
                    audio_redaction_ms = excluded.audio_redaction_ms,
                    summary_generation_ms = excluded.summary_generation_ms,
                    source_audio_artifact_id = excluded.source_audio_artifact_id,
                    redacted_audio_artifact_id = excluded.redacted_audio_artifact_id,
                    source_transcript_artifact_id = excluded.source_transcript_artifact_id,
                    redacted_transcript_artifact_id = excluded.redacted_transcript_artifact_id,
                    summary_artifact_id = excluded.summary_artifact_id,
                    events_artifact_id = excluded.events_artifact_id,
                    text_snippet = excluded.text_snippet,
                    anonymized_snippet = excluded.anonymized_snippet,
                    last_error = excluded.last_error,
                    audio_redaction_error = excluded.audio_redaction_error,
                    has_summary = excluded.has_summary,
                    has_redacted_audio = excluded.has_redacted_audio
                """,
                self._job_result_params(result),
            )
            connection.commit()

    def get_job_result(self, job_id: str) -> JobResultRecord | None:
        with self._connect() as connection:
            row = connection.execute("SELECT * FROM job_results WHERE job_id = ?", (job_id,)).fetchone()
        return self._row_to_job_result(row) if row else None

    def list_job_results(
        self,
        *,
        statuses: list[str] | None = None,
        processing_profile: str | None = None,
        created_after: str | None = None,
        created_before: str | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> list[JobResultRecord]:
        clauses: list[str] = []
        params: list[object] = []
        if statuses:
            placeholders = ",".join("?" for _ in statuses)
            clauses.append(f"status IN ({placeholders})")
            params.extend(statuses)
        if processing_profile:
            clauses.append("processing_profile = ?")
            params.append(processing_profile)
        if created_after:
            clauses.append("created_at >= ?")
            params.append(created_after)
        if created_before:
            clauses.append("created_at <= ?")
            params.append(created_before)
        where = f"WHERE {' AND '.join(clauses)}" if clauses else ""
        query = f"SELECT * FROM job_results {where} ORDER BY created_at DESC LIMIT ? OFFSET ?"
        params.extend([max(limit, 0), max(offset, 0)])
        with self._connect() as connection:
            rows = connection.execute(query, tuple(params)).fetchall()
        return [self._row_to_job_result(row) for row in rows]

    def _row_to_upload(self, row: Row) -> UploadSession:
        return UploadSession(
            upload_id=row["upload_id"],
            filename=row["filename"],
            content_type=row["content_type"],
            size_bytes=row["size_bytes"],
            object_key=row["object_key"],
            upload_token=row["upload_token"],
            created_at=datetime.fromisoformat(row["created_at"]),
            expires_at=datetime.fromisoformat(row["expires_at"]),
            status=UploadStatus(row["status"]),
            checksum=row["checksum"],
            bytes_received=row["bytes_received"],
            metadata=json.loads(row["metadata_json"]),
        )

    def _row_to_job(self, row: Row) -> JobRecord:
        return JobRecord(
            job_id=row["job_id"],
            upload_id=row["upload_id"],
            profile=ProcessingProfile.from_dict(json.loads(row["profile_json"])),
            webhook_url=row["webhook_url"],
            idempotency_key=row["idempotency_key"],
            status=JobStatus(row["status"]),
            stage=StageName(row["stage"]),
            progress=row["progress"],
            trace_id=row["trace_id"],
            created_at=datetime.fromisoformat(row["created_at"]),
            updated_at=datetime.fromisoformat(row["updated_at"]),
            last_error=row["last_error"],
            retry_count=row["retry_count"],
            quality_flags=json.loads(row["quality_flags_json"]),
        )

    def _row_to_stage(self, row: Row) -> StageExecution:
        return StageExecution(
            job_id=row["job_id"],
            name=StageName(row["name"]),
            status=StageStatus(row["status"]),
            attempt=row["attempt"],
            started_at=datetime.fromisoformat(row["started_at"]),
            completed_at=datetime.fromisoformat(row["completed_at"]) if row["completed_at"] else None,
            details=json.loads(row["details_json"]),
        )

    def _row_to_artifact(self, row: Row) -> ArtifactRecord:
        return ArtifactRecord(
            artifact_id=row["artifact_id"],
            job_id=row["job_id"],
            kind=ArtifactKind(row["kind"]),
            variant=row["variant"],
            storage_key=row["storage_key"],
            access_level=AccessLevel(row["access_level"]),
            content_type=row["content_type"],
            created_at=datetime.fromisoformat(row["created_at"]),
            expires_at=datetime.fromisoformat(row["expires_at"]) if row["expires_at"] else None,
            metadata=json.loads(row["metadata_json"]),
        )

    def _row_to_model_run(self, row: Row) -> ModelRun:
        return ModelRun(
            run_id=row["run_id"],
            job_id=row["job_id"],
            stage_name=StageName(row["stage_name"]),
            model_name=row["model_name"],
            model_version=row["model_version"],
            threshold_profile=row["threshold_profile"],
            trace_id=row["trace_id"],
            created_at=datetime.fromisoformat(row["created_at"]),
            extra=json.loads(row["extra_json"]),
        )

    def _row_to_job_result(self, row: Row) -> JobResultRecord:
        return JobResultRecord(
            job_id=row["job_id"],
            upload_id=row["upload_id"],
            trace_id=row["trace_id"],
            status=row["status"],
            stage=row["stage"],
            created_at=datetime.fromisoformat(row["created_at"]),
            updated_at=datetime.fromisoformat(row["updated_at"]),
            completed_at=datetime.fromisoformat(row["completed_at"]) if row["completed_at"] else None,
            retry_count=row["retry_count"],
            source_filename=row["source_filename"],
            source_content_type=row["source_content_type"],
            source_size_bytes=row["source_size_bytes"],
            source_duration_ms=row["source_duration_ms"],
            source_channels=row["source_channels"],
            source_sample_rate=row["source_sample_rate"],
            source_checksum=row["source_checksum"],
            processing_profile=row["processing_profile"],
            model_bundle=row["model_bundle"],
            audio_redaction_mode=row["audio_redaction_mode"],
            language=row["language"],
            speaker_strategy_used=row["speaker_strategy_used"],
            timing_source=row["timing_source"],
            title=row["title"],
            source_text=row["source_text"],
            anonymized_text=row["anonymized_text"],
            summary_text=row["summary_text"],
            summary_bullets=json.loads(row["summary_bullets_json"]),
            summary_confidence=row["summary_confidence"],
            events=json.loads(row["events_json"]),
            event_count=row["event_count"],
            entity_counts=json.loads(row["entity_counts_json"]),
            quality_flags=json.loads(row["quality_flags_json"]),
            pii_confidence_report=json.loads(row["pii_confidence_report_json"]) if row["pii_confidence_report_json"] else None,
            evaluation_summary=json.loads(row["evaluation_summary_json"]) if row["evaluation_summary_json"] else None,
            total_processing_ms=row["total_processing_ms"],
            queue_wait_ms=row["queue_wait_ms"],
            transcription_ms=row["transcription_ms"],
            pii_detection_ms=row["pii_detection_ms"],
            alignment_ms=row["alignment_ms"],
            audio_redaction_ms=row["audio_redaction_ms"],
            summary_generation_ms=row["summary_generation_ms"],
            source_audio_artifact_id=row["source_audio_artifact_id"],
            redacted_audio_artifact_id=row["redacted_audio_artifact_id"],
            source_transcript_artifact_id=row["source_transcript_artifact_id"],
            redacted_transcript_artifact_id=row["redacted_transcript_artifact_id"],
            summary_artifact_id=row["summary_artifact_id"],
            events_artifact_id=row["events_artifact_id"],
            text_snippet=row["text_snippet"],
            anonymized_snippet=row["anonymized_snippet"],
            last_error=row["last_error"],
            audio_redaction_error=row["audio_redaction_error"],
            has_summary=bool(row["has_summary"]),
            has_redacted_audio=bool(row["has_redacted_audio"]),
        )

    def _job_result_params(self, result: JobResultRecord) -> tuple[object, ...]:
        return (
            result.job_id,
            result.upload_id,
            result.trace_id,
            result.status,
            result.stage,
            result.created_at.isoformat(),
            result.updated_at.isoformat(),
            result.completed_at.isoformat() if result.completed_at else None,
            result.retry_count,
            result.source_filename,
            result.source_content_type,
            result.source_size_bytes,
            result.source_duration_ms,
            result.source_channels,
            result.source_sample_rate,
            result.source_checksum,
            result.processing_profile,
            result.model_bundle,
            result.audio_redaction_mode,
            result.language,
            result.speaker_strategy_used,
            result.timing_source,
            result.title,
            result.source_text,
            result.anonymized_text,
            result.summary_text,
            json.dumps(to_jsonable(result.summary_bullets), ensure_ascii=False),
            result.summary_confidence,
            json.dumps(to_jsonable(result.events), ensure_ascii=False),
            result.event_count,
            json.dumps(to_jsonable(result.entity_counts), ensure_ascii=False),
            json.dumps(to_jsonable(result.quality_flags), ensure_ascii=False),
            json.dumps(to_jsonable(result.pii_confidence_report), ensure_ascii=False) if result.pii_confidence_report is not None else None,
            json.dumps(to_jsonable(result.evaluation_summary), ensure_ascii=False) if result.evaluation_summary is not None else None,
            result.total_processing_ms,
            result.queue_wait_ms,
            result.transcription_ms,
            result.pii_detection_ms,
            result.alignment_ms,
            result.audio_redaction_ms,
            result.summary_generation_ms,
            result.source_audio_artifact_id,
            result.redacted_audio_artifact_id,
            result.source_transcript_artifact_id,
            result.redacted_transcript_artifact_id,
            result.summary_artifact_id,
            result.events_artifact_id,
            result.text_snippet,
            result.anonymized_snippet,
            result.last_error,
            result.audio_redaction_error,
            int(result.has_summary),
            int(result.has_redacted_audio),
        )


def build_database(config: AppConfig) -> Database | object:
    if config.database_backend == "postgres":
        from .postgres_database import PostgresDatabase

        if not config.postgres_dsn:
            raise RuntimeError("TULA_POSTGRES_DSN is required when TULA_DATABASE_BACKEND=postgres")
        return PostgresDatabase(config.postgres_dsn)
    return Database(config.runtime_dir / "service.db")
