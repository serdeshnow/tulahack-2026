from __future__ import annotations

from evals.config import E2EEvalConfig
from evals.datasets.e2e import load_e2e_dataset
from evals.metrics.segments import match_segments
from evals.metrics.speakers import score_speaker_segments
from evals.metrics.wer import normalize_text, word_error_rate
from evals.reporting import EvalReport
from evals.services.platform import run_platform_job_with_artifacts
from evals.transcript_artifact import (
    extract_event_segments,
    extract_plain_text,
    extract_redacted_segments,
    extract_speaker_segments,
    extract_status_redaction_segments,
)


def _pick_predicted_segments(
    *,
    events: dict,
    final_status: dict,
    redacted_transcript: dict,
) -> tuple[str, list]:
    event_segments = extract_event_segments(events)
    if event_segments:
        return "events", event_segments

    status_segments = extract_status_redaction_segments(final_status)
    if status_segments:
        return "job_status", status_segments

    transcript_segments = extract_redacted_segments(redacted_transcript)
    if transcript_segments:
        return "redacted_transcript", transcript_segments

    return "none", []


def run_e2e_eval(config: E2EEvalConfig) -> EvalReport:
    dataset = load_e2e_dataset(config.dataset_path)
    sample_reports: list[dict] = []

    total_tp = 0
    total_fp = 0
    total_fn = 0
    wer_values: list[float] = []
    speaker_accuracy_values: list[float] = []

    for index, sample in enumerate(dataset, start=1):
        log_prefix = f"[e2e {index}/{len(dataset)} id={sample.id}]"
        print(f"{log_prefix} started")
        (
            job_id,
            final_status,
            source_transcript,
            redacted_transcript,
            events,
        ) = run_platform_job_with_artifacts(
            platform=config.platform,
            audio_path=sample.audio_path,
            source_variant=config.transcript.source_variant,
            redacted_variant=config.transcript.redacted_variant,
            log_prefix=log_prefix,
        )

        predicted_text = extract_plain_text(source_transcript)
        redacted_text = extract_plain_text(redacted_transcript)
        predicted_speaker_segments = extract_speaker_segments(source_transcript)
        sample_wer = word_error_rate(sample.expected_text, predicted_text)
        wer_values.append(sample_wer)
        speaker_result = score_speaker_segments(
            expected_segments=sample.expected_speaker_segments,
            predicted_segments=predicted_speaker_segments,
        )
        speaker_accuracy_values.append(speaker_result.accuracy)

        predicted_segments_source, predicted_segments = _pick_predicted_segments(
            events=events,
            final_status=final_status,
            redacted_transcript=redacted_transcript,
        )
        match_result = match_segments(
            predicted_segments=predicted_segments,
            expected_segments=sample.expected_segments,
            tolerance_seconds=config.matching.tolerance_seconds,
        )
        total_tp += match_result.true_positives
        total_fp += match_result.false_positives
        total_fn += match_result.false_negatives

        print(
            f"{log_prefix} completed with "
            f"wer={sample_wer:.4f} "
            f"speaker_accuracy={speaker_result.accuracy:.4f} "
            f"precision={match_result.precision:.4f} "
            f"recall={match_result.recall:.4f} "
            f"f1={match_result.f1:.4f} "
            f"predicted_segments_source={predicted_segments_source}"
        )

        sample_reports.append(
            {
                "id": sample.id,
                "job_id": job_id,
                "job_status": final_status.get("status"),
                "audio_path": str(sample.audio_path),
                "expected_text": sample.expected_text,
                "predicted_text": predicted_text,
                "predicted_redacted_text": redacted_text,
                "normalized_expected_text": normalize_text(sample.expected_text),
                "normalized_predicted_text": normalize_text(predicted_text),
                "expected_speaker_segments": [
                    segment.model_dump(mode="json")
                    for segment in sample.expected_speaker_segments
                ],
                "predicted_speaker_segments": [
                    segment.model_dump(mode="json")
                    for segment in predicted_speaker_segments
                ],
                "speaker_attribution_accuracy": speaker_result.accuracy,
                "speaker_mapping": speaker_result.mapping,
                "speaker_overlap_matrix": speaker_result.overlap_matrix,
                "speaker_matched_duration": speaker_result.matched_duration,
                "speaker_total_expected_duration": speaker_result.total_expected_duration,
                "expected_segments": [
                    segment.model_dump(mode="json") for segment in sample.expected_segments
                ],
                "predicted_segments_source": predicted_segments_source,
                "predicted_segments": [
                    segment.model_dump(mode="json") for segment in predicted_segments
                ],
                "matched_pairs": [
                    {
                        "predicted": predicted.model_dump(mode="json"),
                        "expected": expected.model_dump(mode="json"),
                    }
                    for predicted, expected in match_result.matched_pairs
                ],
                "wer": sample_wer,
                "precision": match_result.precision,
                "recall": match_result.recall,
                "f1": match_result.f1,
                "false_positives": [
                    segment.model_dump(mode="json")
                    for segment in match_result.unmatched_predicted
                ],
                "false_negatives": [
                    segment.model_dump(mode="json")
                    for segment in match_result.unmatched_expected
                ],
                "artifacts": {
                    "source_transcript": source_transcript,
                    "redacted_transcript": redacted_transcript,
                    "events": events,
                },
            }
        )

    mean_wer = sum(wer_values) / len(wer_values) if wer_values else 0.0
    mean_speaker_accuracy = (
        sum(speaker_accuracy_values) / len(speaker_accuracy_values)
        if speaker_accuracy_values
        else 0.0
    )
    precision = total_tp / (total_tp + total_fp) if (total_tp + total_fp) else 0.0
    recall = total_tp / (total_tp + total_fn) if (total_tp + total_fn) else 0.0
    f1 = 2 * precision * recall / (precision + recall) if (precision + recall) else 0.0
    print(
        f"[e2e] finished all samples: "
        f"mean_wer={mean_wer:.4f} speaker_attribution_accuracy={mean_speaker_accuracy:.4f} "
        f"precision={precision:.4f} "
        f"recall={recall:.4f} f1={f1:.4f}"
    )

    report = EvalReport(
        task="e2e",
        dataset_path=str(config.dataset_path),
        sample_count=len(dataset),
        metrics={
            "mean_wer": mean_wer,
            "speaker_attribution_accuracy": mean_speaker_accuracy,
            "precision": precision,
            "recall": recall,
            "f1": f1,
        },
        samples=sample_reports,
    )
    report.save(config.output.report_path)
    return report
