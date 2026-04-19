from __future__ import annotations

from pathlib import Path

from pydantic import BaseModel, ConfigDict

from evals.datasets.common import Segment, load_jsonl


class SpeakerSegment(BaseModel):
    model_config = ConfigDict(extra="forbid")

    start_ts: float
    end_ts: float
    speaker: str


class E2ESample(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    audio_path: Path
    expected_text: str
    expected_segments: list[Segment]
    expected_speaker_segments: list[SpeakerSegment] = []


def load_e2e_dataset(path: Path) -> list[E2ESample]:
    samples: list[E2ESample] = []
    for record in load_jsonl(path):
        sample = E2ESample.model_validate(record)
        sample.audio_path = (path.parent / sample.audio_path).resolve()
        samples.append(sample)
    return samples
