from __future__ import annotations

from datetime import UTC, datetime
from uuid import uuid4

from fastapi import FastAPI, HTTPException, Request
from pydantic import BaseModel

from mock_service.fixtures import TRANSCRIPT_FIXTURES


app = FastAPI(title="Voice Data Redaction Platform Mock")

UPLOADS: dict[str, dict] = {}
JOBS: dict[str, dict] = {}


class UploadInitRequest(BaseModel):
    filename: str
    content_type: str
    size_bytes: int


class CreateJobRequest(BaseModel):
    upload_id: str
    profile: dict
    webhook_url: str | None = None
    idempotency_key: str | None = None


def _now() -> str:
    return datetime.now(UTC).isoformat()


@app.get("/healthz")
def healthz() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/readyz")
def readyz() -> dict[str, str]:
    return {"status": "ready", "checks": {"mock": "ok"}}


@app.post("/v1/uploads:init")
def create_upload_session(request: UploadInitRequest, http_request: Request) -> dict[str, str]:
    upload_id = f"upl_{uuid4().hex[:12]}"
    UPLOADS[upload_id] = {
        "filename": request.filename,
        "content_type": request.content_type,
        "size_bytes": request.size_bytes,
        "uploaded": False,
    }
    base_url = str(http_request.base_url).rstrip("/")
    return {
        "upload_id": upload_id,
        "upload_url": f"{base_url}/v1/uploads/{upload_id}/content",
        "expires_at": _now(),
    }


@app.put("/v1/uploads/{upload_id}/content")
async def put_upload_content(upload_id: str, request: Request) -> dict[str, bool]:
    if upload_id not in UPLOADS:
        raise HTTPException(status_code=404, detail="upload not found")
    UPLOADS[upload_id]["payload"] = await request.body()
    UPLOADS[upload_id]["uploaded"] = True
    return {"ok": True}


@app.post("/v1/jobs")
def create_job(request: CreateJobRequest) -> dict[str, str]:
    upload = UPLOADS.get(request.upload_id)
    if upload is None or not upload.get("uploaded"):
        raise HTTPException(status_code=422, detail="upload is missing or not uploaded")

    filename = upload["filename"]
    if filename not in TRANSCRIPT_FIXTURES:
        raise HTTPException(status_code=422, detail="fixture not found for uploaded audio")

    job_id = f"job_{uuid4().hex[:12]}"
    now = _now()
    JOBS[job_id] = {
        "upload_id": request.upload_id,
        "filename": filename,
        "status_checks": 0,
        "created_at": now,
        "updated_at": now,
        "profile": request.profile,
    }
    return {"job_id": job_id, "status": "queued", "stage": "accepted"}


@app.get("/v1/jobs/{job_id}")
def get_job_status(job_id: str) -> dict:
    job = JOBS.get(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="job not found")

    job["status_checks"] += 1
    completed = job["status_checks"] >= 2
    status = "completed" if completed else "processing"
    stage = "completed" if completed else "transcribing"
    progress = 1.0 if completed else 0.65
    job["updated_at"] = _now()

    return {
        "job_id": job_id,
        "status": status,
        "stage": stage,
        "progress": progress,
        "created_at": job["created_at"],
        "updated_at": job["updated_at"],
        "retry_count": 0,
        "processing_profile": job["profile"].get("processing_profile", "standard"),
        "model_bundle": "mock-whisper-qwen-bundle",
        "stages": [
            {"name": "upload", "status": "completed"},
            {"name": "transcription", "status": stage},
            {"name": "redaction", "status": stage if completed else "pending"},
        ],
        "stage_executions": [
            {
                "name": "transcription",
                "status": stage,
                "attempt": 1,
                "started_at": job["created_at"],
                "completed_at": job["updated_at"] if completed else None,
                "details": {"mock": True},
            },
            {
                "name": "alignment",
                "status": stage,
                "attempt": 1,
                "started_at": job["created_at"],
                "completed_at": job["updated_at"] if completed else None,
                "details": {
                    "redaction_spans": [
                        {
                            "start_ms": 15000,
                            "end_ms": 18000,
                            "entity_type": "PHONE",
                        }
                    ]
                },
            },
        ],
        "artifacts": [
            {
                "kind": "transcript",
                "variant": "source",
                "access_level": "internal",
                "content_type": "application/json",
            },
            {
                "kind": "transcript",
                "variant": "redacted",
                "access_level": "internal",
                "content_type": "application/json",
            },
        ],
        "model_runs": [
            {
                "stage_name": "transcription",
                "model_name": "mock-whisper",
                "model_version": "0.1",
                "extra": {},
            },
            {
                "stage_name": "redaction",
                "model_name": "mock-redactor",
                "model_version": "0.1",
                "extra": {},
            },
        ],
    }


@app.get("/v1/jobs/{job_id}/transcript")
def get_transcript(job_id: str, variant: str = "redacted", format: str = "json") -> dict:
    if format != "json":
        raise HTTPException(status_code=422, detail="mock supports only json transcript format")

    job = JOBS.get(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="job not found")

    fixture = TRANSCRIPT_FIXTURES[job["filename"]]
    if variant not in fixture:
        raise HTTPException(status_code=404, detail="transcript variant not found")

    return {
        "job_id": job_id,
        "variant": variant,
        **fixture[variant],
    }


@app.get("/v1/jobs/{job_id}/events")
def get_events(job_id: str) -> dict:
    job = JOBS.get(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="job not found")

    fixture = TRANSCRIPT_FIXTURES[job["filename"]]
    return {
        "job_id": job_id,
        **fixture.get("events", {"events": []}),
    }
