from __future__ import annotations

from pathlib import Path
from typing import Any, TypeVar

import yaml
from pydantic import BaseModel, ConfigDict, Field, TypeAdapter


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


class PlatformConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")

    base_url: str
    timeout_seconds: float = 30.0
    headers: dict[str, str] = Field(default_factory=dict)
    x_role: str = "privileged"
    jwt_token: str | None = None
    jwt_token_file: Path | None = None
    authorization_prefix: str = ""
    poll_interval_seconds: float = 0.0
    max_poll_attempts: int = 10
    upload_content_type: str = "audio/wav"
    profile: dict[str, Any] = Field(
        default_factory=lambda: {
            "processing_profile": "standard",
            "pii_entities": list(DEFAULT_PII_ENTITIES),
            "audio_redaction_mode": "beep",
            "include_summary": False,
        }
    )

    def resolved_jwt_token(self) -> str | None:
        if self.jwt_token and self.jwt_token.strip():
            return self.jwt_token.strip()
        if self.jwt_token_file and self.jwt_token_file.exists():
            token = self.jwt_token_file.read_text(encoding="utf-8").strip()
            return token or None
        return None


class OutputConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")

    report_path: Path


class TranscriptConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")

    source_variant: str = "source"
    redacted_variant: str = "redacted"


class MatchingConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")

    tolerance_seconds: float = 0.0


class E2EEvalConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")

    dataset_path: Path
    platform: PlatformConfig
    transcript: TranscriptConfig = Field(default_factory=TranscriptConfig)
    matching: MatchingConfig = Field(default_factory=MatchingConfig)
    output: OutputConfig


ConfigT = TypeVar("ConfigT", bound=BaseModel)


def load_yaml_config(path: Path, config_model: type[ConfigT]) -> ConfigT:
    raw_data: Any = yaml.safe_load(path.read_text(encoding="utf-8"))
    adapter = TypeAdapter(config_model)
    config = adapter.validate_python(raw_data)

    if hasattr(config, "dataset_path"):
        config.dataset_path = (path.parent / config.dataset_path).resolve()  # type: ignore[attr-defined]
    if hasattr(config, "output"):
        config.output.report_path = (path.parent / config.output.report_path).resolve()  # type: ignore[attr-defined]
    if hasattr(config, "platform") and getattr(config.platform, "jwt_token_file", None):
        config.platform.jwt_token_file = (path.parent / config.platform.jwt_token_file).resolve()  # type: ignore[attr-defined]

    return config
