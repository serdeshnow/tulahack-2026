from evals.transcript_artifact import (
    extract_event_segments,
    extract_plain_text,
    extract_redacted_segments,
    extract_speaker_segments,
    extract_status_redaction_segments,
)


def test_extract_plain_text_prefers_canonical_segments_when_full_text_is_missing():
    transcript = {
        "canonical_segments": [{"text": "Привет"}, {"text": "мир"}],
        "segments": [{"text": "не должен использоваться"}],
    }

    assert extract_plain_text(transcript) == "Привет мир"


def test_extract_redacted_segments_merges_adjacent_words_with_same_reason():
    transcript = {
        "segments": [
            {
                "text": "[PHONE]",
                "words": [
                    {
                        "text": "[PHONE_A]",
                        "start_ms": 1000,
                        "end_ms": 1400,
                        "is_redacted": True,
                        "redaction_reason": "PHONE",
                    },
                    {
                        "text": "[PHONE_B]",
                        "start_ms": 1450,
                        "end_ms": 1900,
                        "is_redacted": True,
                        "redaction_reason": "PHONE",
                    },
                    {
                        "text": "ok",
                        "start_ms": 2000,
                        "end_ms": 2200,
                    },
                ],
            }
        ]
    }

    segments = extract_redacted_segments(transcript)

    assert len(segments) == 1
    assert segments[0].start_ts == 1.0
    assert segments[0].end_ts == 1.9
    assert segments[0].reason == "PHONE"


def test_extract_event_segments_finds_nested_payload_spans():
    events = {
        "events": [
            {
                "kind": "pii_detected",
                "payload": {
                    "entity_type": "PHONE",
                    "start_ms": 15000,
                    "end_ms": 18000,
                },
            }
        ]
    }

    segments = extract_event_segments(events)

    assert len(segments) == 1
    assert segments[0].start_ts == 15.0
    assert segments[0].end_ts == 18.0
    assert segments[0].reason == "PHONE"


def test_extract_status_redaction_segments_reads_alignment_details():
    status = {
        "stage_executions": [
            {
                "name": "alignment",
                "details": {
                    "redaction_spans": [
                        {
                            "entity_type": "PHONE",
                            "start_ms": 15000,
                            "end_ms": 18000,
                        }
                    ]
                },
            }
        ]
    }

    segments = extract_status_redaction_segments(status)

    assert len(segments) == 1
    assert segments[0].start_ts == 15.0
    assert segments[0].end_ts == 18.0
    assert segments[0].reason == "PHONE"


def test_extract_speaker_segments_merges_adjacent_segments_of_same_speaker():
    transcript = {
        "canonical_segments": [
            {"speaker_id": "spk_0", "start_ms": 0, "end_ms": 1000, "text": "Привет"},
            {"speaker_id": "spk_0", "start_ms": 1050, "end_ms": 2000, "text": "мир"},
            {"speaker_id": "spk_1", "start_ms": 2500, "end_ms": 3000, "text": "ок"},
        ]
    }

    segments = extract_speaker_segments(transcript)

    assert len(segments) == 2
    assert segments[0].speaker == "spk_0"
    assert segments[0].start_ts == 0.0
    assert segments[0].end_ts == 2.0
    assert segments[1].speaker == "spk_1"
