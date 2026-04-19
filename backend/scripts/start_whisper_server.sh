#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
MODEL_DIR="${WHISPER_MODEL_DIR:-$ROOT_DIR/.runtime/whisper/models}"
MODEL_NAME="${WHISPER_MODEL_NAME:-medium}"
HOST="${WHISPER_HOST:-127.0.0.1}"
PORT="${WHISPER_PORT:-8091}"
SERVER_BIN="${WHISPER_SERVER_BIN:-whisper-server}"
MODEL_PATH="${WHISPER_MODEL_PATH:-$MODEL_DIR/ggml-$MODEL_NAME.bin}"
ENABLE_CONVERT="${WHISPER_ENABLE_CONVERT:-1}"
NO_GPU="${WHISPER_NO_GPU:-0}"
NO_FLASH_ATTN="${WHISPER_NO_FLASH_ATTN:-0}"

mkdir -p "$MODEL_DIR"

if [[ ! -f "$MODEL_PATH" ]]; then
  echo "Downloading Whisper model '$MODEL_NAME' into $MODEL_DIR"
  curl -fsSL https://raw.githubusercontent.com/ggml-org/whisper.cpp/master/models/download-ggml-model.sh -o "$MODEL_DIR/download-ggml-model.sh"
  chmod +x "$MODEL_DIR/download-ggml-model.sh"
  "$MODEL_DIR/download-ggml-model.sh" "$MODEL_NAME" "$MODEL_DIR"
fi

echo "Starting whisper-server on http://$HOST:$PORT"
ARGS=(-m "$MODEL_PATH" --host "$HOST" --port "$PORT")
if [[ "$NO_GPU" == "1" || "$NO_GPU" == "true" || "$NO_GPU" == "yes" ]]; then
  ARGS+=(-ng)
fi
if [[ "$NO_FLASH_ATTN" == "1" || "$NO_FLASH_ATTN" == "true" || "$NO_FLASH_ATTN" == "yes" ]]; then
  ARGS+=(-nfa)
fi
if [[ "$ENABLE_CONVERT" == "0" || "$ENABLE_CONVERT" == "false" || "$ENABLE_CONVERT" == "no" ]]; then
  exec "$SERVER_BIN" "${ARGS[@]}"
fi
exec "$SERVER_BIN" "${ARGS[@]}" --convert
