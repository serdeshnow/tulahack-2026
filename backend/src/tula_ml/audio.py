from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import hashlib
import json
import shutil
import subprocess

from .models import AudioMetadata, RedactionSpan


class AudioProcessingError(RuntimeError):
    pass


@dataclass(slots=True)
class AudioProcessor:
    ffmpeg_bin: str
    ffprobe_bin: str

    def checksum(self, path: Path) -> str:
        digest = hashlib.sha256()
        with path.open("rb") as handle:
            for chunk in iter(lambda: handle.read(1024 * 1024), b""):
                digest.update(chunk)
        return digest.hexdigest()

    def probe(self, path: Path, *, content_type: str) -> AudioMetadata:
        command = [
            self.ffprobe_bin,
            "-v",
            "error",
            "-show_format",
            "-show_streams",
            "-print_format",
            "json",
            str(path),
        ]
        result = subprocess.run(command, check=False, capture_output=True, text=True)
        if result.returncode != 0:
            raise AudioProcessingError(result.stderr.strip() or "ffprobe failed")
        payload = json.loads(result.stdout)
        audio_stream = next((stream for stream in payload.get("streams", []) if stream.get("codec_type") == "audio"), None)
        if not audio_stream:
            raise AudioProcessingError("No audio stream found")
        duration_seconds = float(
            payload.get("format", {}).get("duration")
            or audio_stream.get("duration")
            or 0.0
        )
        bitrate = int(payload.get("format", {}).get("bit_rate") or audio_stream.get("bit_rate") or 0)
        sample_rate = int(audio_stream.get("sample_rate") or 0)
        channels = int(audio_stream.get("channels") or 1)
        return AudioMetadata(
            duration_ms=int(round(duration_seconds * 1000)),
            channels=channels,
            sample_rate=sample_rate,
            bitrate=bitrate,
            codec=str(audio_stream.get("codec_name") or "unknown"),
            checksum=self.checksum(path),
            content_type=content_type,
            file_size=path.stat().st_size,
        )

    def normalize(self, source_path: Path, destination_path: Path) -> dict[str, object]:
        destination_path.parent.mkdir(parents=True, exist_ok=True)
        command = [
            self.ffmpeg_bin,
            "-y",
            "-i",
            str(source_path),
            "-vn",
            "-ar",
            "16000",
            "-ac",
            "1",
            "-c:a",
            "pcm_s16le",
            str(destination_path),
        ]
        result = subprocess.run(command, check=False, capture_output=True, text=True)
        if result.returncode != 0:
            raise AudioProcessingError(result.stderr.strip() or "ffmpeg normalization failed")
        return {
            "command": command,
            "output": str(destination_path),
            "format": "wav",
            "sample_rate": 16000,
            "channels": 1,
        }

    def extract_channel(self, source_path: Path, *, channel_index: int, destination_path: Path) -> None:
        destination_path.parent.mkdir(parents=True, exist_ok=True)
        filter_complex = f"[0:a]pan=mono|c0=c{channel_index}[out]"
        command = [
            self.ffmpeg_bin,
            "-y",
            "-i",
            str(source_path),
            "-filter_complex",
            filter_complex,
            "-map",
            "[out]",
            "-ar",
            "16000",
            "-ac",
            "1",
            "-c:a",
            "pcm_s16le",
            str(destination_path),
        ]
        result = subprocess.run(command, check=False, capture_output=True, text=True)
        if result.returncode != 0:
            raise AudioProcessingError(result.stderr.strip() or f"channel extraction failed for channel {channel_index}")

    def render_redacted_audio(
        self,
        *,
        source_path: Path,
        destination_path: Path,
        spans: list[RedactionSpan],
        mode: str,
        sample_rate: int,
        duration_ms: int,
    ) -> dict[str, object]:
        destination_path.parent.mkdir(parents=True, exist_ok=True)
        if not spans:
            shutil.copy2(source_path, destination_path)
            return {"mode": mode, "span_count": 0, "copied_without_redaction": True}

        normalized_spans = sorted(spans, key=lambda span: (span.start_ms, span.end_ms))
        expression = "+".join(
            f"between(t,{span.start_ms / 1000:.3f},{span.end_ms / 1000:.3f})" for span in normalized_spans
        )
        duration_seconds = max(duration_ms / 1000, 0.001)
        if mode == "mute":
            filter_complex = f"[0:a]volume='if({expression},0,1)'[out]"
        else:
            filter_complex = (
                f"[0:a]volume='if({expression},0,1)'[base];"
                f"sine=f=1000:sample_rate={sample_rate}:duration={duration_seconds:.3f},"
                f"volume='if({expression},0.5,0)'[tone];"
                "[base][tone]amix=inputs=2:normalize=0[out]"
            )
        command = [
            self.ffmpeg_bin,
            "-y",
            "-i",
            str(source_path),
            "-filter_complex",
            filter_complex,
            "-map",
            "[out]",
            "-ar",
            str(sample_rate),
            "-c:a",
            "pcm_s16le",
            str(destination_path),
        ]
        result = subprocess.run(command, check=False, capture_output=True, text=True)
        if result.returncode != 0:
            raise AudioProcessingError(result.stderr.strip() or "audio redaction failed")
        return {
            "mode": mode,
            "span_count": len(normalized_spans),
            "render_source": str(source_path),
            "render_output": str(destination_path),
            "duration_ms": duration_ms,
            "spans": [
                {
                    "span_id": span.span_id,
                    "entity_type": span.entity_type,
                    "start_ms": span.start_ms,
                    "end_ms": span.end_ms,
                    "mode": span.mode,
                    "replacement_text": span.replacement_text,
                    "confidence": span.confidence,
                    "speaker_id": span.speaker_id,
                    "sources": list(span.sources),
                    "entity_id": span.entity_id,
                    "timing_source": span.timing_source,
                    "alignment_confidence": span.alignment_confidence,
                }
                for span in normalized_spans
            ],
        }
