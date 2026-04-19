from __future__ import annotations

from dataclasses import dataclass

from evals.datasets.common import Segment


@dataclass
class SegmentMatchResult:
    true_positives: int
    false_positives: int
    false_negatives: int
    matched_pairs: list[tuple[Segment, Segment]]
    unmatched_predicted: list[Segment]
    unmatched_expected: list[Segment]

    @property
    def precision(self) -> float:
        denominator = self.true_positives + self.false_positives
        return self.true_positives / denominator if denominator else 0.0

    @property
    def recall(self) -> float:
        denominator = self.true_positives + self.false_negatives
        return self.true_positives / denominator if denominator else 0.0

    @property
    def f1(self) -> float:
        denominator = self.precision + self.recall
        return 2 * self.precision * self.recall / denominator if denominator else 0.0


def _is_match(predicted: Segment, expected: Segment, tolerance_seconds: float) -> bool:
    return (
        abs(predicted.start_ts - expected.start_ts) <= tolerance_seconds
        and abs(predicted.end_ts - expected.end_ts) <= tolerance_seconds
    )


def match_segments(
    predicted_segments: list[Segment],
    expected_segments: list[Segment],
    tolerance_seconds: float,
) -> SegmentMatchResult:
    unmatched_expected = expected_segments.copy()
    matched_pairs: list[tuple[Segment, Segment]] = []
    unmatched_predicted: list[Segment] = []

    for predicted in predicted_segments:
        match_index = next(
            (
                index
                for index, expected in enumerate(unmatched_expected)
                if _is_match(predicted, expected, tolerance_seconds)
            ),
            None,
        )

        if match_index is None:
            unmatched_predicted.append(predicted)
            continue

        expected = unmatched_expected.pop(match_index)
        matched_pairs.append((predicted, expected))

    return SegmentMatchResult(
        true_positives=len(matched_pairs),
        false_positives=len(unmatched_predicted),
        false_negatives=len(unmatched_expected),
        matched_pairs=matched_pairs,
        unmatched_predicted=unmatched_predicted,
        unmatched_expected=unmatched_expected,
    )
