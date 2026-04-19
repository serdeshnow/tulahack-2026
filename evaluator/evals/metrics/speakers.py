from __future__ import annotations

from dataclasses import dataclass
from itertools import permutations

from evals.datasets.e2e import SpeakerSegment


def _overlap_duration(first: SpeakerSegment, second: SpeakerSegment) -> float:
    overlap = min(first.end_ts, second.end_ts) - max(first.start_ts, second.start_ts)
    return max(0.0, overlap)


@dataclass
class SpeakerMatchResult:
    accuracy: float
    matched_duration: float
    total_expected_duration: float
    mapping: dict[str, str]
    expected_speakers: list[str]
    predicted_speakers: list[str]
    overlap_matrix: dict[str, dict[str, float]]


def _best_mapping(
    expected_labels: list[str],
    predicted_labels: list[str],
    weights: dict[tuple[str, str], float],
) -> tuple[dict[str, str], float]:
    if not expected_labels or not predicted_labels:
        return {}, 0.0

    best_mapping: dict[str, str] = {}
    best_score = -1.0

    if len(predicted_labels) <= len(expected_labels):
        for expected_permutation in permutations(expected_labels, len(predicted_labels)):
            mapping = dict(zip(predicted_labels, expected_permutation, strict=False))
            score = sum(weights.get((predicted, expected), 0.0) for predicted, expected in mapping.items())
            if score > best_score:
                best_mapping = mapping
                best_score = score
    else:
        for predicted_permutation in permutations(predicted_labels, len(expected_labels)):
            mapping = dict(zip(predicted_permutation, expected_labels, strict=False))
            score = sum(weights.get((predicted, expected), 0.0) for predicted, expected in mapping.items())
            if score > best_score:
                best_mapping = mapping
                best_score = score

    return best_mapping, max(best_score, 0.0)


def score_speaker_segments(
    *,
    expected_segments: list[SpeakerSegment],
    predicted_segments: list[SpeakerSegment],
) -> SpeakerMatchResult:
    total_expected_duration = sum(
        max(0.0, segment.end_ts - segment.start_ts) for segment in expected_segments
    )
    expected_labels = sorted({segment.speaker for segment in expected_segments})
    predicted_labels = sorted({segment.speaker for segment in predicted_segments})

    overlap_matrix: dict[str, dict[str, float]] = {
        predicted: {expected: 0.0 for expected in expected_labels}
        for predicted in predicted_labels
    }
    weights: dict[tuple[str, str], float] = {}

    for predicted in predicted_segments:
        for expected in expected_segments:
            overlap = _overlap_duration(predicted, expected)
            if overlap <= 0:
                continue
            key = (predicted.speaker, expected.speaker)
            weights[key] = weights.get(key, 0.0) + overlap
            overlap_matrix[predicted.speaker][expected.speaker] += overlap

    mapping, matched_duration = _best_mapping(expected_labels, predicted_labels, weights)

    if total_expected_duration == 0:
        accuracy = 1.0 if not predicted_segments else 0.0
    else:
        accuracy = matched_duration / total_expected_duration

    return SpeakerMatchResult(
        accuracy=accuracy,
        matched_duration=matched_duration,
        total_expected_duration=total_expected_duration,
        mapping=mapping,
        expected_speakers=expected_labels,
        predicted_speakers=predicted_labels,
        overlap_matrix=overlap_matrix,
    )
