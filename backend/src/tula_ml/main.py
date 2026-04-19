from __future__ import annotations

from argparse import ArgumentParser
import uvicorn

from .api import create_app
from .config import AppConfig, load_env_file
from .pipeline import VoiceRedactionService
from .whisper import WhisperClient, WhisperRuntimeValidator


def main() -> None:
    load_env_file()
    parser = ArgumentParser(description="Voice Data Redaction Platform v1")
    parser.add_argument("--host", default=None)
    parser.add_argument("--port", type=int, default=None)
    parser.add_argument("--runtime-dir", default=None)
    args = parser.parse_args()

    config = AppConfig.from_env(args.runtime_dir)
    if args.host:
        config.host = args.host
    if args.port:
        config.port = args.port
    if config.whisper_validate_on_startup:
        WhisperRuntimeValidator(WhisperClient(config), config).validate()

    service = VoiceRedactionService(config)
    app = create_app(service)
    print(f"Serving Voice Data Redaction Platform on http://{config.host}:{config.port}")
    print(f"Swagger UI: http://{config.host}:{config.port}/docs")
    uvicorn.run(app, host=config.host, port=config.port)
