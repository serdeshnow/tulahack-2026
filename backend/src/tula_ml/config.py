from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import os
import secrets


def load_env_file(path: str | os.PathLike[str] | None = None, *, override: bool = False) -> Path | None:
    candidates: list[Path] = []
    if path is not None:
        candidates.append(Path(path))
    else:
        candidates.append(Path.cwd() / ".env")
        project_env = Path(__file__).resolve().parents[2] / ".env"
        if project_env not in candidates:
            candidates.append(project_env)
    for candidate in candidates:
        if not candidate.is_file():
            continue
        for raw_line in candidate.read_text(encoding="utf-8").splitlines():
            line = raw_line.strip()
            if not line or line.startswith("#"):
                continue
            if line.startswith("export "):
                line = line.removeprefix("export ").strip()
            if "=" not in line:
                continue
            key, value = line.split("=", 1)
            key = key.strip()
            value = value.strip()
            if value[:1] == value[-1:] and value.startswith(("'", '"')):
                value = value[1:-1]
            if override or key not in os.environ:
                os.environ[key] = value
        return candidate
    return None


@dataclass(slots=True)
class AppConfig:
    runtime_dir: Path
    backend_profile: str = "development"
    database_backend: str = "sqlite"
    postgres_dsn: str | None = None
    object_store_backend: str = "local"
    s3_bucket: str | None = None
    s3_prefix: str = ""
    s3_endpoint_url: str | None = None
    s3_region: str | None = None
    s3_access_key_id: str | None = None
    s3_secret_access_key: str | None = None
    host: str = "127.0.0.1"
    port: int = 8080
    ffmpeg_bin: str = "ffmpeg"
    ffprobe_bin: str = "ffprobe"
    signing_secret: str = ""
    upload_ttl_seconds: int = 900
    download_ttl_seconds: int = 900
    source_ttl_hours: int = 24
    normalized_ttl_hours: int = 4
    redacted_ttl_hours: int = 24 * 7
    audit_ttl_hours: int = 24 * 30
    worker_poll_interval_seconds: float = 0.2
    retention_cleanup_interval_seconds: float = 300.0
    job_max_retries: int = 0
    auth_mode: str = "header_role"
    auth_secret: str = ""
    allow_legacy_role_header: bool = True
    whisper_base_url: str = "http://127.0.0.1:8091"
    whisper_transcript_path: str = "/inference"
    whisper_health_path: str = "/"
    whisper_model_name: str = "medium"
    whisper_model_path: str = ""
    whisper_timeout_seconds: float = 120.0
    whisper_max_retries: int = 2
    whisper_language: str = "ru"
    whisper_response_format: str = "verbose_json"
    whisper_server_bin: str = "whisper-server"
    whisper_validate_on_startup: bool = True
    diarization_window_ms: int = 250
    diarization_min_segment_ms: int = 400
    diarization_frequency_delta_hz: float = 45.0
    diarization_silence_rms_threshold: float = 350.0
    diarization_base_url: str | None = None
    diarization_path: str = "/v1/diarize"
    diarization_health_path: str = "/health"
    diarization_timeout_seconds: float = 30.0
    diarization_max_retries: int = 1
    allow_heuristic_diarization_fallback: bool = True
    alignment_left_padding_ms: int = 150
    alignment_right_padding_ms: int = 220
    alignment_hybrid_padding_bonus_ms: int = 40
    lmstudio_base_url: str = "http://127.0.0.1:1234"
    lmstudio_llm_model: str = "openai/gpt-oss-20b"
    lmstudio_transport_mode: str = "openai_compatible"
    lmstudio_chat_path: str = "/v1/chat/completions"
    lmstudio_native_chat_path: str = "/api/v1/chat"
    lmstudio_models_path: str = "/v1/models"
    lmstudio_timeout_seconds: float = 60.0
    lmstudio_max_retries: int = 2
    lmstudio_api_key: str | None = None
    lmstudio_cookie: str | None = None
    token_ner_backend: str = "contextual_rules"
    token_ner_model_name: str = "contextual-rules"
    token_ner_model_path: str = ""
    webhook_timeout_seconds: float = 5.0
    webhook_max_retries: int = 2
    webhook_signing_secret: str = ""
    api_x_token: str = ""

    @classmethod
    def from_env(cls, root: str | os.PathLike[str] | None = None) -> "AppConfig":
        runtime_dir = Path(root or os.getenv("TULA_RUNTIME_DIR") or ".runtime").resolve()
        signing_secret = os.getenv("TULA_SIGNING_SECRET") or secrets.token_hex(16)
        auth_secret = os.getenv("TULA_AUTH_SECRET") or signing_secret
        webhook_signing_secret = os.getenv("TULA_WEBHOOK_SIGNING_SECRET") or signing_secret
        api_x_token = os.getenv("TULA_API_X_TOKEN")
        if not api_x_token:
            raise ValueError("TULA_API_X_TOKEN must be configured")
        return cls(
            runtime_dir=runtime_dir,
            backend_profile=os.getenv("TULA_BACKEND_PROFILE", "development"),
            database_backend=os.getenv("TULA_DATABASE_BACKEND", "sqlite"),
            postgres_dsn=os.getenv("TULA_POSTGRES_DSN") or None,
            object_store_backend=os.getenv("TULA_OBJECT_STORE_BACKEND", "local"),
            s3_bucket=os.getenv("TULA_S3_BUCKET") or None,
            s3_prefix=os.getenv("TULA_S3_PREFIX", ""),
            s3_endpoint_url=os.getenv("TULA_S3_ENDPOINT_URL") or None,
            s3_region=os.getenv("TULA_S3_REGION") or None,
            s3_access_key_id=os.getenv("TULA_S3_ACCESS_KEY_ID") or None,
            s3_secret_access_key=os.getenv("TULA_S3_SECRET_ACCESS_KEY") or None,
            host=os.getenv("TULA_HOST", "127.0.0.1"),
            port=int(os.getenv("TULA_PORT", "8080")),
            ffmpeg_bin=os.getenv("FFMPEG_BIN", "ffmpeg"),
            ffprobe_bin=os.getenv("FFPROBE_BIN", "ffprobe"),
            signing_secret=signing_secret,
            retention_cleanup_interval_seconds=float(os.getenv("TULA_RETENTION_CLEANUP_INTERVAL_SECONDS", "300")),
            job_max_retries=int(os.getenv("TULA_JOB_MAX_RETRIES", "0")),
            auth_mode=os.getenv("TULA_AUTH_MODE", "header_role"),
            auth_secret=auth_secret,
            allow_legacy_role_header=os.getenv("TULA_ALLOW_LEGACY_ROLE_HEADER", "true").lower() not in {"0", "false", "no"},
            whisper_base_url=os.getenv("WHISPER_BASE_URL", "http://127.0.0.1:8091"),
            whisper_transcript_path=os.getenv("WHISPER_TRANSCRIPT_PATH", "/inference"),
            whisper_health_path=os.getenv("WHISPER_HEALTH_PATH", "/"),
            whisper_model_name=os.getenv("WHISPER_MODEL_NAME", "medium"),
            whisper_model_path=os.getenv("WHISPER_MODEL_PATH", ""),
            whisper_timeout_seconds=float(os.getenv("WHISPER_TIMEOUT_SECONDS", "120")),
            whisper_max_retries=int(os.getenv("WHISPER_MAX_RETRIES", "2")),
            whisper_language=os.getenv("WHISPER_LANGUAGE", "ru"),
            whisper_response_format=os.getenv("WHISPER_RESPONSE_FORMAT", "verbose_json"),
            whisper_server_bin=os.getenv("WHISPER_SERVER_BIN", "whisper-server"),
            whisper_validate_on_startup=os.getenv("WHISPER_VALIDATE_ON_STARTUP", "true").lower() not in {"0", "false", "no"},
            diarization_window_ms=int(os.getenv("DIARIZATION_WINDOW_MS", "250")),
            diarization_min_segment_ms=int(os.getenv("DIARIZATION_MIN_SEGMENT_MS", "400")),
            diarization_frequency_delta_hz=float(os.getenv("DIARIZATION_FREQUENCY_DELTA_HZ", "45")),
            diarization_silence_rms_threshold=float(os.getenv("DIARIZATION_SILENCE_RMS_THRESHOLD", "350")),
            diarization_base_url=os.getenv("DIARIZATION_BASE_URL") or None,
            diarization_path=os.getenv("DIARIZATION_PATH", "/v1/diarize"),
            diarization_health_path=os.getenv("DIARIZATION_HEALTH_PATH", "/health"),
            diarization_timeout_seconds=float(os.getenv("DIARIZATION_TIMEOUT_SECONDS", "30")),
            diarization_max_retries=int(os.getenv("DIARIZATION_MAX_RETRIES", "1")),
            allow_heuristic_diarization_fallback=os.getenv("ALLOW_HEURISTIC_DIARIZATION_FALLBACK", "true").lower() not in {"0", "false", "no"},
            alignment_left_padding_ms=int(os.getenv("ALIGNMENT_LEFT_PADDING_MS", "150")),
            alignment_right_padding_ms=int(os.getenv("ALIGNMENT_RIGHT_PADDING_MS", "220")),
            alignment_hybrid_padding_bonus_ms=int(os.getenv("ALIGNMENT_HYBRID_PADDING_BONUS_MS", "40")),
            lmstudio_base_url=os.getenv("LMSTUDIO_BASE_URL", "http://127.0.0.1:1234"),
            lmstudio_llm_model=os.getenv("LMSTUDIO_LLM_MODEL", "openai/gpt-oss-20b"),
            lmstudio_transport_mode=os.getenv("LMSTUDIO_TRANSPORT_MODE", "openai_compatible"),
            lmstudio_chat_path=os.getenv("LMSTUDIO_CHAT_PATH", "/v1/chat/completions"),
            lmstudio_native_chat_path=os.getenv("LMSTUDIO_NATIVE_CHAT_PATH", "/api/v1/chat"),
            lmstudio_models_path=os.getenv("LMSTUDIO_MODELS_PATH", "/v1/models"),
            lmstudio_timeout_seconds=float(os.getenv("LMSTUDIO_TIMEOUT_SECONDS", "60")),
            lmstudio_max_retries=int(os.getenv("LMSTUDIO_MAX_RETRIES", "2")),
            lmstudio_api_key=os.getenv("LMSTUDIO_API_KEY") or None,
            lmstudio_cookie=os.getenv("LMSTUDIO_COOKIE") or None,
            token_ner_backend=os.getenv("TOKEN_NER_BACKEND", "contextual_rules"),
            token_ner_model_name=os.getenv("TOKEN_NER_MODEL_NAME", "contextual-rules"),
            token_ner_model_path=os.getenv("TOKEN_NER_MODEL_PATH", ""),
            webhook_timeout_seconds=float(os.getenv("TULA_WEBHOOK_TIMEOUT_SECONDS", "5")),
            webhook_max_retries=int(os.getenv("TULA_WEBHOOK_MAX_RETRIES", "2")),
            webhook_signing_secret=webhook_signing_secret,
            api_x_token=api_x_token,
        )
