from evals.datasets.e2e import SpeakerSegment
from evals.metrics.speakers import score_speaker_segments


def test_speaker_metric_uses_best_label_mapping():
    expected = [
        SpeakerSegment(start_ts=0.0, end_ts=2.0, speaker="alice"),
        SpeakerSegment(start_ts=2.0, end_ts=5.0, speaker="bob"),
        SpeakerSegment(start_ts=5.0, end_ts=7.0, speaker="alice"),
    ]
    predicted = [
        SpeakerSegment(start_ts=0.0, end_ts=2.0, speaker="spk_1"),
        SpeakerSegment(start_ts=2.0, end_ts=5.0, speaker="spk_0"),
        SpeakerSegment(start_ts=5.0, end_ts=7.0, speaker="spk_1"),
    ]

    result = score_speaker_segments(
        expected_segments=expected,
        predicted_segments=predicted,
    )

    assert result.accuracy == 1.0
    assert result.mapping == {"spk_0": "bob", "spk_1": "alice"}
