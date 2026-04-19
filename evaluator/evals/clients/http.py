from __future__ import annotations

from pathlib import Path
from typing import Any

import httpx

from evals.config import PlatformConfig


def _headers(platform: PlatformConfig) -> dict[str, str]:
    headers = dict(platform.headers)
    if platform.x_role:
        headers["X-Role"] = platform.x_role
    jwt_token = platform.resolved_jwt_token()
    if jwt_token:
        prefix = platform.authorization_prefix.strip()
        headers["Authorization"] = f"{prefix} {jwt_token}".strip() if prefix else jwt_token
    return headers


def init_upload(
    client: httpx.Client,
    platform: PlatformConfig,
    audio_path: Path,
) -> dict[str, Any]:
    response = client.post(
        f"{platform.base_url}/v1/uploads:init",
        headers=_headers(platform),
        json={
            "filename": audio_path.name,
            "content_type": platform.upload_content_type,
            "size_bytes": audio_path.stat().st_size,
        },
    )
    response.raise_for_status()
    return response.json()


def upload_content(
    client: httpx.Client,
    platform: PlatformConfig,
    upload_url: str,
    audio_path: Path,
) -> None:
    with audio_path.open("rb") as audio_file:
        response = client.put(
            upload_url,
            headers={
                **_headers(platform),
                "content-type": platform.upload_content_type,
            },
            content=audio_file.read(),
        )
    response.raise_for_status()


def create_job(
    client: httpx.Client,
    platform: PlatformConfig,
    upload_id: str,
) -> dict[str, Any]:
    response = client.post(
        f"{platform.base_url}/v1/jobs",
        headers=_headers(platform),
        json={
            "upload_id": upload_id,
            "profile": platform.profile,
        },
    )
    response.raise_for_status()
    return response.json()


def get_job_status(
    client: httpx.Client,
    platform: PlatformConfig,
    job_id: str,
) -> dict[str, Any]:
    response = client.get(
        f"{platform.base_url}/v1/jobs/{job_id}",
        headers=_headers(platform),
    )
    response.raise_for_status()
    return response.json()


def get_transcript(
    client: httpx.Client,
    platform: PlatformConfig,
    job_id: str,
    variant: str,
) -> dict[str, Any]:
    response = client.get(
        f"{platform.base_url}/v1/jobs/{job_id}/transcript",
        headers=_headers(platform),
        params={"variant": variant, "format": "json"},
    )
    response.raise_for_status()
    return response.json()


def get_events(
    client: httpx.Client,
    platform: PlatformConfig,
    job_id: str,
) -> dict[str, Any]:
    response = client.get(
        f"{platform.base_url}/v1/jobs/{job_id}/events",
        headers=_headers(platform),
    )
    response.raise_for_status()
    return response.json()
