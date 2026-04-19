from __future__ import annotations

import argparse
import io
import json
import wave
from dataclasses import dataclass
from pathlib import Path

import httpx

from evals.datasets.common import load_jsonl


SCRIPT_DIR = Path(__file__).resolve().parent
REPO_ROOT = SCRIPT_DIR.parent
DEFAULT_INPUT_JSONL = REPO_ROOT / "datasets" / "synth" / "pii_text_dataset_all.jsonl"
DEFAULT_OUTPUT_JSONL = REPO_ROOT / "datasets" / "synth" / "tts_e2e_dataset.jsonl"
DEFAULT_AUDIO_DIR = REPO_ROOT / "datasets" / "synth" / "audio"
DEFAULT_TTS_URL = "http://127.0.0.1:8822/tts"

DEFAULT_GAP_MS = 1000
SPEAKER_ID = "spk_0"


@dataclass(frozen=True)
class AudioChunk:
    audio_bytes: bytes
    duration_seconds: float


@dataclass(frozen=True)
class TextChunk:
    text: str
    is_pii: bool
    reason: str = ""


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Build an audio-backed synthetic E2E dataset by synthesizing normal text "
            "chunks and PII chunks separately via a TTS-like API."
        )
    )
    parser.add_argument(
        "--input-jsonl",
        type=Path,
        default=DEFAULT_INPUT_JSONL,
        help="Source jsonl with text and expected_entities.",
    )
    parser.add_argument(
        "--output-jsonl",
        type=Path,
        default=DEFAULT_OUTPUT_JSONL,
        help="Output E2E jsonl dataset path.",
    )
    parser.add_argument(
        "--audio-dir",
        type=Path,
        default=DEFAULT_AUDIO_DIR,
        help="Directory for generated wav files.",
    )
    parser.add_argument(
        "--tts-url",
        type=str,
        default=DEFAULT_TTS_URL,
        help="TTS API endpoint.",
    )
    parser.add_argument(
        "--gap-ms",
        type=int,
        default=DEFAULT_GAP_MS,
        help="Silence gap inserted between synthesized chunks.",
    )
    parser.add_argument(
        "--max-records",
        type=int,
        default=None,
        help="Optional cap on processed input rows for debugging.",
    )
    return parser.parse_args()


def _read_wav(audio_bytes: bytes) -> tuple[wave._wave_params, bytes]:
    with wave.open(io.BytesIO(audio_bytes), "rb") as wav_file:
        params = wav_file.getparams()
        frames = wav_file.readframes(wav_file.getnframes())
    return params, frames


def _duration_from_bytes(audio_bytes: bytes) -> float:
    with wave.open(io.BytesIO(audio_bytes), "rb") as wav_file:
        frame_rate = wav_file.getframerate()
        frame_count = wav_file.getnframes()
        return frame_count / frame_rate if frame_rate else 0.0


def build_silence_chunk(*, duration_ms: int, params: wave._wave_params) -> AudioChunk:
    frame_count = int(params.framerate * duration_ms / 1000.0)
    silence_frames = b"\x00" * frame_count * params.sampwidth * params.nchannels
    return AudioChunk(
        audio_bytes=_encode_wav(params, silence_frames),
        duration_seconds=frame_count / params.framerate if params.framerate else 0.0,
    )


def _encode_wav(params: wave._wave_params, frames: bytes) -> bytes:
    buffer = io.BytesIO()
    with wave.open(buffer, "wb") as wav_file:
        wav_file.setparams(params)
        wav_file.writeframes(frames)
    return buffer.getvalue()


def split_text_into_chunks(text: str, entities: list[dict]) -> list[TextChunk]:
    sorted_entities = sorted(entities, key=lambda item: (item["start"], item["end"]))
    chunks: list[TextChunk] = []
    cursor = 0

    for entity in sorted_entities:
        start = int(entity["start"])
        end = int(entity["end"])
        if start > cursor:
            prefix = text[cursor:start]
            if prefix:
                chunks.append(TextChunk(text=prefix, is_pii=False))

        entity_text = text[start:end]
        if entity_text:
            chunks.append(
                TextChunk(
                    text=entity_text,
                    is_pii=True,
                    reason=str(entity.get("reason", "")),
                )
            )
        cursor = max(cursor, end)

    if cursor < len(text):
        suffix = text[cursor:]
        if suffix:
            chunks.append(TextChunk(text=suffix, is_pii=False))

    return chunks


def synthesize_chunk(
    client: httpx.Client,
    *,
    tts_url: str,
    chunk: TextChunk,
) -> AudioChunk:
    response = client.post(
        tts_url,
        json={"text": chunk.text, "speaker": "xenia", "sample_rate": 24000},
    )
    try:
        response.raise_for_status()
    except Exception as e:
        print(chunk.text)
        print(response.json())
        raise
    audio_bytes = response.content
    return AudioChunk(
        audio_bytes=audio_bytes,
        duration_seconds=_duration_from_bytes(audio_bytes),
    )


def build_audio_record(
    client: httpx.Client,
    *,
    tts_url: str,
    record: dict,
    audio_path: Path,
    dataset_dir: Path,
    gap_ms: int,
) -> dict:
    text = str(record["text"])
    expected_entities = list(record.get("expected_entities", []))
    chunks = split_text_into_chunks(text, expected_entities)
    if not chunks:
        raise ValueError(f"Record {record.get('id')} has no synthesizable chunks")

    synthesized_chunks = [
        synthesize_chunk(client, tts_url=tts_url, chunk=chunk)
        for chunk in chunks
    ]

    first_params, _ = _read_wav(synthesized_chunks[0].audio_bytes)
    gap_chunk = build_silence_chunk(duration_ms=gap_ms, params=first_params)

    all_frames = bytearray()
    current_time = 0.0
    expected_segments: list[dict] = []

    for index, (chunk, audio_chunk) in enumerate(zip(chunks, synthesized_chunks, strict=False)):
        params, frames = _read_wav(audio_chunk.audio_bytes)
        if (
            params.nchannels != first_params.nchannels
            or params.sampwidth != first_params.sampwidth
            or params.framerate != first_params.framerate
            or params.comptype != first_params.comptype
            or params.compname != first_params.compname
        ):
            raise ValueError("Synthesized chunks use inconsistent WAV params")

        all_frames.extend(frames)
        if chunk.is_pii:
            expected_segments.append(
                {
                    "start_ts": round(current_time, 3),
                    "end_ts": round(current_time + audio_chunk.duration_seconds, 3),
                    "reason": chunk.reason,
                }
            )
        current_time += audio_chunk.duration_seconds

        if index != len(chunks) - 1 and gap_ms > 0:
            _, gap_frames = _read_wav(gap_chunk.audio_bytes)
            all_frames.extend(gap_frames)
            current_time += gap_chunk.duration_seconds

    audio_path.parent.mkdir(parents=True, exist_ok=True)
    audio_path.write_bytes(_encode_wav(first_params, bytes(all_frames)))

    return {
        "id": record["id"],
        "audio_path": str(audio_path.relative_to(dataset_dir)),
        "expected_text": text,
        "expected_segments": expected_segments,
        "expected_speaker_segments": [
            {
                "start_ts": 0.0,
                "end_ts": round(current_time, 3),
                "speaker": SPEAKER_ID,
            }
        ],
    }


def main() -> None:
    args = parse_args()
    records = load_jsonl(args.input_jsonl)
    if args.max_records is not None:
        records = records[:args.max_records]

    args.audio_dir.mkdir(parents=True, exist_ok=True)
    args.output_jsonl.parent.mkdir(parents=True, exist_ok=True)

    built_records: list[dict] = []
    with httpx.Client(timeout=120.0) as client:
        for index, record in enumerate(records, start=1):
            audio_filename = f"{record['id']}.wav"
            audio_path = args.audio_dir / audio_filename
            print(f"[{index}/{len(records)}] synthesize {record['id']} -> {audio_filename}")
            built_records.append(
                build_audio_record(
                    client,
                    tts_url=args.tts_url,
                    record=record,
                    audio_path=audio_path,
                    dataset_dir=args.output_jsonl.parent,
                    gap_ms=args.gap_ms,
                )
            )

    with args.output_jsonl.open("w", encoding="utf-8") as output_file:
        for record in built_records:
            output_file.write(json.dumps(record, ensure_ascii=False) + "\n")

    print(f"Saved {len(built_records)} dataset rows -> {args.output_jsonl}")
    print(f"Saved audio files -> {args.audio_dir}")


if __name__ == "__main__":
    main()
