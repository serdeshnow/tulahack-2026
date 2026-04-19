from __future__ import annotations

import time
from pathlib import Path
from typing import Any

import httpx

from evals.clients.http import (
    create_job,
    get_events,
    get_job_status,
    get_transcript,
    init_upload,
    upload_content,
)
from evals.config import PlatformConfig


def wait_for_job_completion(
    client: httpx.Client,
    platform: PlatformConfig,
    job_id: str,
    *,
    log_prefix: str = "",
) -> dict[str, Any]:
    prefix = f"{log_prefix} " if log_prefix else ""
    final_status: dict[str, Any] = {}

    for attempt in range(platform.max_poll_attempts):
        final_status = get_job_status(client, platform, job_id)
        status = str(final_status.get("status", "")).lower()
        stage = str(final_status.get("stage", "")).lower()
        print(
            f"{prefix}poll {attempt + 1}/{platform.max_poll_attempts}: "
            f"status={final_status.get('status')} "
            f"stage={final_status.get('stage')} "
            f"progress={final_status.get('progress')}"
        )
        if status in {"completed", "succeeded", "done"} or stage in {"completed", "done"}:
            return final_status
        if attempt == platform.max_poll_attempts - 1:
            raise RuntimeError(
                f"Job {job_id} did not complete after {platform.max_poll_attempts} polls"
            )
        if platform.poll_interval_seconds > 0:
            time.sleep(platform.poll_interval_seconds)

    return final_status


def run_platform_job(
    platform: PlatformConfig,
    audio_path: Path,
    transcript_variant: str,
    *,
    log_prefix: str = "",
) -> tuple[str, dict[str, Any], dict[str, Any]]:
    prefix = f"{log_prefix} " if log_prefix else ""
    with httpx.Client(timeout=platform.timeout_seconds) as client:
        print(f"{prefix}init upload for {audio_path.name}")
        upload = init_upload(client, platform, audio_path)
        upload_id = str(upload["upload_id"])
        upload_url = str(upload["upload_url"])
        print(f"{prefix}upload created: upload_id={upload_id}")

        print(f"{prefix}uploading audio bytes")
        upload_content(client, platform, upload_url, audio_path)
        print(f"{prefix}upload completed")

        print(f"{prefix}creating processing job")
        job = create_job(client, platform, upload_id)
        job_id = str(job["job_id"])
        print(
            f"{prefix}job created: job_id={job_id} "
            f"status={job.get('status')} stage={job.get('stage')}"
        )

        final_status = wait_for_job_completion(
            client,
            platform,
            job_id,
            log_prefix=log_prefix,
        )

        print(f"{prefix}fetching transcript variant={transcript_variant}")
        transcript = get_transcript(client, platform, job_id, transcript_variant)
        print(f"{prefix}transcript fetched")
        return job_id, final_status, transcript


def run_platform_job_with_artifacts(
    platform: PlatformConfig,
    audio_path: Path,
    *,
    source_variant: str,
    redacted_variant: str,
    log_prefix: str = "",
) -> tuple[str, dict[str, Any], dict[str, Any], dict[str, Any], dict[str, Any]]:
    prefix = f"{log_prefix} " if log_prefix else ""
    with httpx.Client(timeout=platform.timeout_seconds) as client:
        print(f"{prefix}init upload for {audio_path.name}")
        upload = init_upload(client, platform, audio_path)
        upload_id = str(upload["upload_id"])
        upload_url = str(upload["upload_url"])
        print(f"{prefix}upload created: upload_id={upload_id}")

        print(f"{prefix}uploading audio bytes")
        upload_content(client, platform, upload_url, audio_path)
        print(f"{prefix}upload completed")

        print(f"{prefix}creating processing job")
        job = create_job(client, platform, upload_id)
        job_id = str(job["job_id"])
        print(
            f"{prefix}job created: job_id={job_id} "
            f"status={job.get('status')} stage={job.get('stage')}"
        )

        final_status = wait_for_job_completion(
            client,
            platform,
            job_id,
            log_prefix=log_prefix,
        )

        print(f"{prefix}fetching transcript variant={source_variant}")
        source_transcript = get_transcript(client, platform, job_id, source_variant)
        print(f"{prefix}source transcript fetched")

        print(f"{prefix}fetching transcript variant={redacted_variant}")
        redacted_transcript = get_transcript(client, platform, job_id, redacted_variant)
        print(f"{prefix}redacted transcript fetched")

        print(f"{prefix}fetching events")
        events = get_events(client, platform, job_id)
        print(f"{prefix}events fetched")

        return job_id, final_status, source_transcript, redacted_transcript, events
