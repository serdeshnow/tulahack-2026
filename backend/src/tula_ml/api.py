from __future__ import annotations

from contextlib import asynccontextmanager
from datetime import datetime, timezone
from typing import Any, Literal
from urllib.parse import parse_qs, urlparse

from fastapi import Depends, FastAPI, File, Header, HTTPException, Query, Request, Response, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from pydantic import BaseModel, ConfigDict, Field

from .pipeline import ServiceError, VoiceRedactionService


def _base_url_from_request(request: Request) -> str:
    return str(request.base_url).rstrip("/")


def _service_error_payload(message: str, *, code: str | None = None, details: Any = None) -> dict[str, Any]:
    return {"message": message, "code": code, "details": details}


def _verify_signature(service: VoiceRedactionService, *, method: str, request: Request) -> None:
    parsed = urlparse(str(request.url))
    query = parse_qs(parsed.query)
    expires = int(query.get("expires", ["0"])[0])
    signature = query.get("signature", [""])[0]
    if expires <= 0 or not signature:
        raise ServiceError("signed URL is missing expires or signature")
    if datetime.now(tz=timezone.utc).timestamp() > expires:
        raise ServiceError("signed URL has expired")
    if not service.signer.verify(method=method, path=request.url.path, expires=expires, signature=signature):
        raise ServiceError("signed URL signature is invalid")


class ErrorResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")
    message: str
    code: str | None = None
    details: Any = None


class FoundEntityBadge(BaseModel):
    model_config = ConfigDict(extra="forbid")
    type: str
    count: int | None = Field(default=None, ge=0)


class AudioRecord(BaseModel):
    model_config = ConfigDict(extra="forbid")
    id: str
    title: str
    originalFileName: str
    processedFileName: str | None
    originalFileUrl: str | None
    processedFileUrl: str | None
    createdAt: str
    durationSec: float
    status: Literal["uploaded", "queued", "processing", "completed", "failed"]
    foundEntities: list[FoundEntityBadge]
    errorMessage: str | None = None
    processingStartedAt: str | None = None
    processingCompletedAt: str | None = None
    canDownloadProcessedAudio: bool = False


class AudioCatalogResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")
    items: list[AudioRecord]
    page: int = Field(ge=1)
    pageSize: int = Field(ge=1)
    totalItems: int = Field(ge=0)
    totalPages: int = Field(ge=1)


class UploadAudioResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")
    items: list[AudioRecord]


class TranscriptMention(BaseModel):
    model_config = ConfigDict(extra="forbid")
    entityId: str
    startOffset: int = Field(ge=0)
    endOffset: int = Field(ge=0)


class TranscriptSegment(BaseModel):
    model_config = ConfigDict(extra="forbid")
    id: str
    startMs: int = Field(ge=0)
    endMs: int = Field(ge=0)
    speakerLabel: str | None
    originalText: str
    redactedText: str
    hasRedactions: bool
    entityRefs: list[str]
    mentions: list[TranscriptMention]


class PiiEntity(BaseModel):
    model_config = ConfigDict(extra="forbid")
    id: str
    type: str
    startMs: int = Field(ge=0)
    endMs: int = Field(ge=0)
    segmentIds: list[str]
    originalValue: str | None = None
    redactedValue: str
    confidence: float = Field(ge=0, le=1)
    isApplied: bool


class SummaryBlock(BaseModel):
    model_config = ConfigDict(extra="forbid")
    id: str
    kind: Literal["short", "full", "compliance"]
    text: str
    generatedAt: str


class ProcessingLogEntry(BaseModel):
    model_config = ConfigDict(extra="forbid")
    id: str
    at: str
    level: Literal["debug", "info", "warn", "error"]
    stage: str
    message: str
    meta: dict[str, Any] | None = None


class WaveformRegion(BaseModel):
    model_config = ConfigDict(extra="forbid")
    id: str
    startMs: int = Field(ge=0)
    endMs: int = Field(ge=0)
    entityTypes: list[str]
    entityIds: list[str] | None = None
    severity: Literal["low", "medium", "high"] | None = None
    redacted: bool


class AudioRecordDetailsResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")
    record: AudioRecord
    transcript: list[TranscriptSegment]
    entities: list[PiiEntity]
    summaries: list[SummaryBlock]
    logs: list[ProcessingLogEntry]
    waveform: list[WaveformRegion]
    availableViews: list[Literal["redacted", "original"]]


class AudioRecordStatusResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")
    id: str
    status: Literal["uploaded", "queued", "processing", "completed", "failed"]
    errorMessage: str | None = None
    processingStartedAt: str | None = None
    processingCompletedAt: str | None = None


class AudioDownloadResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")
    job_id: str
    variant: Literal["source", "redacted"]
    download_url: str
    expires_at: str


class StatsPeriodPoint(BaseModel):
    model_config = ConfigDict(extra="forbid")
    periodStart: str
    label: str
    value: int = Field(ge=0)


class StatsEntityDetectionItem(BaseModel):
    model_config = ConfigDict(extra="forbid")
    type: str
    count: int = Field(ge=0)


class StatsStatusDistributionItem(BaseModel):
    model_config = ConfigDict(extra="forbid")
    status: Literal["completed", "processing", "failed", "queued"]
    count: int = Field(ge=0)


class StatsOverviewResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")
    processedFiles: int = Field(ge=0)
    processedAudioHours: float = Field(ge=0)
    averageProcessingTimeSec: float = Field(ge=0)
    averageProcessingTimeChangePct: float
    timingCompliancePct: float = Field(ge=0, le=100)
    detectedEntities: int = Field(ge=0)
    detectedEntitiesChangePct: float
    topEntityTypes: list[str]
    recognitionAccuracyPct: float = Field(ge=0, le=100)
    recognitionAccuracyChangePct: float
    monthlyProcessedFilesChangePct: float
    monthlyProcessedFiles: list[StatsPeriodPoint]
    entityDetections: list[StatsEntityDetectionItem]
    statusDistribution: list[StatsStatusDistributionItem]


class ApiHeader(BaseModel):
    model_config = ConfigDict(extra="forbid")
    name: str
    value: str
    required: bool


class ApiEndpointDoc(BaseModel):
    model_config = ConfigDict(extra="forbid")
    id: str
    title: str
    method: Literal["GET", "POST", "PUT", "PATCH", "DELETE"]
    path: str
    description: str
    headers: list[ApiHeader]
    requestExample: str
    responseExample: str
    curlExample: str


class ApiDocsConfigResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")
    baseUrl: str
    tokenLabel: str
    tokenValue: str | None = None
    endpoints: list[ApiEndpointDoc]


def create_app(service: VoiceRedactionService) -> FastAPI:
    @asynccontextmanager
    async def lifespan(_: FastAPI):
        try:
            yield
        finally:
            service.shutdown()

    app = FastAPI(
        title="Voice Data Redaction API",
        version="0.1.0",
        docs_url="/docs",
        redoc_url="/redoc",
        openapi_url="/openapi.json",
        servers=[{"url": "/api/v1", "description": "Relative API base used by frontend"}],
        lifespan=lifespan,
    )
    app.state.service = service
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=False,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    def _require_x_token(x_token: str | None = Header(default=None, alias="X-Token")) -> None:
        if not x_token or x_token != service.config.api_x_token:
            raise HTTPException(status_code=401, detail="Missing or invalid X-Token")

    @app.exception_handler(ServiceError)
    async def handle_service_error(_: Request, exc: ServiceError) -> JSONResponse:
        return JSONResponse(status_code=exc.status_code, content=_service_error_payload(str(exc)))

    @app.exception_handler(HTTPException)
    async def handle_http_exception(_: Request, exc: HTTPException) -> JSONResponse:
        if exc.status_code == 401:
            return JSONResponse(status_code=401, content=_service_error_payload(str(exc.detail)))
        return JSONResponse(status_code=exc.status_code, content={"detail": exc.detail})

    @app.get(
        "/api/v1/audio",
        response_model=AudioCatalogResponse,
        responses={401: {"model": ErrorResponse}},
        tags=["catalog"],
        summary="List audio records",
        dependencies=[Depends(_require_x_token)],
    )
    @app.get(
        "/api/v1/api/v1/audio",
        response_model=AudioCatalogResponse,
        responses={401: {"model": ErrorResponse}},
        tags=["catalog"],
        summary="List audio records",
        dependencies=[Depends(_require_x_token)],
        include_in_schema=False,
    )
    @app.get(
        "/audio",
        response_model=AudioCatalogResponse,
        responses={401: {"model": ErrorResponse}},
        tags=["catalog"],
        summary="List audio records",
        dependencies=[Depends(_require_x_token)],
        include_in_schema=False,
    )
    async def list_audio(
        request: Request,
        search: str | None = Query(default=None),
        status: str | None = Query(default=None),
        entityType: str | None = Query(default=None),
        sortBy: str | None = Query(default=None),
        sortOrder: str | None = Query(default=None),
        page: int = Query(default=1, ge=1),
        pageSize: int = Query(default=20, ge=1),
        dateFrom: str | None = Query(default=None),
        dateTo: str | None = Query(default=None),
    ) -> dict[str, Any]:
        return service.list_audio_records(
            base_url=_base_url_from_request(request),
            search=search,
            status=status,
            entity_type=entityType,
            sort_by=sortBy,
            sort_order=sortOrder,
            page=page,
            page_size=pageSize,
            date_from=dateFrom,
            date_to=dateTo,
        )

    @app.post(
        "/api/v1/audio",
        response_model=UploadAudioResponse,
        responses={400: {"model": ErrorResponse}, 401: {"model": ErrorResponse}},
        tags=["upload"],
        summary="Upload audio files and start processing",
        dependencies=[Depends(_require_x_token)],
    )
    @app.post(
        "/api/v1/api/v1/audio",
        response_model=UploadAudioResponse,
        responses={400: {"model": ErrorResponse}, 401: {"model": ErrorResponse}},
        tags=["upload"],
        summary="Upload audio files and start processing",
        dependencies=[Depends(_require_x_token)],
        include_in_schema=False,
    )
    @app.post(
        "/audio",
        response_model=UploadAudioResponse,
        responses={400: {"model": ErrorResponse}, 401: {"model": ErrorResponse}},
        tags=["upload"],
        summary="Upload audio files and start processing",
        dependencies=[Depends(_require_x_token)],
        include_in_schema=False,
    )
    async def upload_audio(request: Request, files: list[UploadFile] = File(...)) -> dict[str, Any]:
        if not files:
            raise HTTPException(status_code=400, detail="files are required")
        items: list[dict[str, Any]] = []
        for file in files:
            body = await file.read()
            if not body:
                raise HTTPException(status_code=400, detail="uploaded file is empty")
            item = service.create_audio_record_from_upload(
                filename=file.filename or "unknown.wav",
                content_type=file.content_type or "application/octet-stream",
                body=body,
                base_url=_base_url_from_request(request),
            )
            items.append(item)
        return {"items": items}

    @app.get(
        "/api/v1/audio/{audioId}",
        response_model=AudioRecordDetailsResponse,
        responses={401: {"model": ErrorResponse}, 404: {"model": ErrorResponse}},
        tags=["details"],
        summary="Get record details",
        dependencies=[Depends(_require_x_token)],
    )
    @app.get(
        "/api/v1/api/v1/audio/{audioId}",
        response_model=AudioRecordDetailsResponse,
        responses={401: {"model": ErrorResponse}, 404: {"model": ErrorResponse}},
        tags=["details"],
        summary="Get record details",
        dependencies=[Depends(_require_x_token)],
        include_in_schema=False,
    )
    @app.get(
        "/audio/{audioId}",
        response_model=AudioRecordDetailsResponse,
        responses={401: {"model": ErrorResponse}, 404: {"model": ErrorResponse}},
        tags=["details"],
        summary="Get record details",
        dependencies=[Depends(_require_x_token)],
        include_in_schema=False,
    )
    async def get_audio(audioId: str, request: Request) -> dict[str, Any]:
        return service.get_audio_record_details(audio_id=audioId, base_url=_base_url_from_request(request))

    @app.get(
        "/api/v1/audio/{audioId}/status",
        response_model=AudioRecordStatusResponse,
        responses={401: {"model": ErrorResponse}, 404: {"model": ErrorResponse}},
        tags=["details"],
        summary="Get current processing status",
        dependencies=[Depends(_require_x_token)],
    )
    @app.get(
        "/api/v1/api/v1/audio/{audioId}/status",
        response_model=AudioRecordStatusResponse,
        responses={401: {"model": ErrorResponse}, 404: {"model": ErrorResponse}},
        tags=["details"],
        summary="Get current processing status",
        dependencies=[Depends(_require_x_token)],
        include_in_schema=False,
    )
    @app.get(
        "/audio/{audioId}/status",
        response_model=AudioRecordStatusResponse,
        responses={401: {"model": ErrorResponse}, 404: {"model": ErrorResponse}},
        tags=["details"],
        summary="Get current processing status",
        dependencies=[Depends(_require_x_token)],
        include_in_schema=False,
    )
    async def get_audio_status(audioId: str) -> dict[str, Any]:
        return service.get_audio_record_status(audio_id=audioId)

    @app.get(
        "/api/v1/jobs/{jobId}/audio",
        response_model=AudioDownloadResponse,
        responses={401: {"model": ErrorResponse}, 404: {"model": ErrorResponse}},
        tags=["artifacts"],
        summary="Get signed URL for audio artifact",
        dependencies=[Depends(_require_x_token)],
    )
    @app.get(
        "/api/v1/api/v1/jobs/{jobId}/audio",
        response_model=AudioDownloadResponse,
        responses={401: {"model": ErrorResponse}, 404: {"model": ErrorResponse}},
        tags=["artifacts"],
        summary="Get signed URL for audio artifact",
        dependencies=[Depends(_require_x_token)],
        include_in_schema=False,
    )
    @app.get(
        "/jobs/{jobId}/audio",
        response_model=AudioDownloadResponse,
        responses={401: {"model": ErrorResponse}, 404: {"model": ErrorResponse}},
        tags=["artifacts"],
        summary="Get signed URL for audio artifact",
        dependencies=[Depends(_require_x_token)],
        include_in_schema=False,
    )
    async def get_job_audio(
        jobId: str,
        request: Request,
        variant: Literal["source", "redacted"] = Query(default="redacted"),
    ) -> dict[str, Any]:
        return service.get_public_audio_download(job_id=jobId, variant=variant, base_url=_base_url_from_request(request))

    @app.get(
        "/api/v1/stats/overview",
        response_model=StatsOverviewResponse,
        responses={401: {"model": ErrorResponse}},
        tags=["stats"],
        summary="Get overview statistics",
        dependencies=[Depends(_require_x_token)],
    )
    @app.get(
        "/api/v1/api/v1/stats/overview",
        response_model=StatsOverviewResponse,
        responses={401: {"model": ErrorResponse}},
        tags=["stats"],
        summary="Get overview statistics",
        dependencies=[Depends(_require_x_token)],
        include_in_schema=False,
    )
    @app.get(
        "/stats/overview",
        response_model=StatsOverviewResponse,
        responses={401: {"model": ErrorResponse}},
        tags=["stats"],
        summary="Get overview statistics",
        dependencies=[Depends(_require_x_token)],
        include_in_schema=False,
    )
    async def get_stats_overview() -> dict[str, Any]:
        return service.get_stats_overview()

    @app.get(
        "/api/v1/docs/config",
        response_model=ApiDocsConfigResponse,
        responses={401: {"model": ErrorResponse}},
        tags=["docs"],
        summary="Get API docs config for frontend page",
        dependencies=[Depends(_require_x_token)],
    )
    @app.get(
        "/api/v1/api/v1/docs/config",
        response_model=ApiDocsConfigResponse,
        responses={401: {"model": ErrorResponse}},
        tags=["docs"],
        summary="Get API docs config for frontend page",
        dependencies=[Depends(_require_x_token)],
        include_in_schema=False,
    )
    @app.get(
        "/docs/config",
        response_model=ApiDocsConfigResponse,
        responses={401: {"model": ErrorResponse}},
        tags=["docs"],
        summary="Get API docs config for frontend page",
        dependencies=[Depends(_require_x_token)],
        include_in_schema=False,
    )
    async def get_docs_config() -> dict[str, Any]:
        return service.get_docs_config()

    @app.get(
        "/v1/download/{artifact_id}",
        responses={400: {"model": ErrorResponse}, 403: {"model": ErrorResponse}, 404: {"model": ErrorResponse}},
        tags=["artifacts"],
        summary="Download artifact via signed URL",
        include_in_schema=False,
    )
    async def download_artifact(artifact_id: str, request: Request) -> FileResponse:
        _verify_signature(service, method="GET", request=request)
        path, content_type = service.download_artifact(artifact_id)
        return FileResponse(path, media_type=content_type, filename=path.name)

    @app.get(
        "/healthz",
        include_in_schema=False,
    )
    async def get_health() -> dict[str, Any]:
        return service.get_health()

    @app.get(
        "/readyz",
        include_in_schema=False,
    )
    async def get_readiness() -> JSONResponse:
        payload, ready = service.get_readiness()
        return JSONResponse(status_code=200 if ready else 503, content=payload)

    @app.get(
        "/metrics",
        include_in_schema=False,
    )
    async def get_metrics() -> Response:
        return Response(content=service.get_metrics(), media_type="text/plain; version=0.0.4")

    return app
