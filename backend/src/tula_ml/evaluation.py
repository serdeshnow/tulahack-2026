from __future__ import annotations

from collections import Counter


def levenshtein_distance(left: list[str], right: list[str]) -> int:
    if not left:
        return len(right)
    if not right:
        return len(left)
    previous = list(range(len(right) + 1))
    for left_index, left_item in enumerate(left, start=1):
        current = [left_index]
        for right_index, right_item in enumerate(right, start=1):
            insert_cost = current[right_index - 1] + 1
            delete_cost = previous[right_index] + 1
            replace_cost = previous[right_index - 1] + (0 if left_item == right_item else 1)
            current.append(min(insert_cost, delete_cost, replace_cost))
        previous = current
    return previous[-1]


def wer(reference: str, hypothesis: str) -> float:
    reference_tokens = reference.split()
    hypothesis_tokens = hypothesis.split()
    if not reference_tokens:
        return 0.0 if not hypothesis_tokens else 1.0
    return levenshtein_distance(reference_tokens, hypothesis_tokens) / len(reference_tokens)


def cer(reference: str, hypothesis: str) -> float:
    if not reference:
        return 0.0 if not hypothesis else 1.0
    return levenshtein_distance(list(reference), list(hypothesis)) / len(reference)


def precision_recall_f1(gold: list[str], predicted: list[str]) -> dict[str, float]:
    gold_counter = Counter(gold)
    predicted_counter = Counter(predicted)
    true_positive = sum((gold_counter & predicted_counter).values())
    predicted_total = sum(predicted_counter.values())
    gold_total = sum(gold_counter.values())
    precision = true_positive / predicted_total if predicted_total else 0.0
    recall = true_positive / gold_total if gold_total else 0.0
    f1 = (2 * precision * recall / (precision + recall)) if precision and recall else 0.0
    return {"precision": precision, "recall": recall, "f1": f1}


def leakage_rate(total_sensitive_spans: int, redacted_spans: int) -> float:
    if total_sensitive_spans <= 0:
        return 0.0
    return max(total_sensitive_spans - redacted_spans, 0) / total_sensitive_spans


def over_redaction_rate(total_redacted_spans: int, gold_sensitive_spans: int) -> float:
    if total_redacted_spans <= 0:
        return 0.0
    extra = max(total_redacted_spans - gold_sensitive_spans, 0)
    return extra / total_redacted_spans


def boundary_error_ms(gold_spans: list[tuple[int, int]], predicted_spans: list[tuple[int, int]]) -> float:
    if not gold_spans or not predicted_spans:
        return 0.0
    paired = zip(gold_spans, predicted_spans)
    errors = [abs(gold_start - pred_start) + abs(gold_end - pred_end) for (gold_start, gold_end), (pred_start, pred_end) in paired]
    return sum(errors) / (2 * len(errors))
