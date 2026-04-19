from __future__ import annotations

import re
import string


PUNCT_TRANSLATION_TABLE = str.maketrans("", "", string.punctuation)


def normalize_text(text: str) -> str:
    lowered = text.lower().translate(PUNCT_TRANSLATION_TABLE)
    return re.sub(r"\s+", " ", lowered).strip()


def word_error_rate(expected: str, predicted: str) -> float:
    expected_words = normalize_text(expected).split()
    predicted_words = normalize_text(predicted).split()

    if not expected_words:
        return 0.0 if not predicted_words else 1.0

    rows = len(expected_words) + 1
    cols = len(predicted_words) + 1
    dp = [[0] * cols for _ in range(rows)]

    for row in range(rows):
        dp[row][0] = row
    for col in range(cols):
        dp[0][col] = col

    for row in range(1, rows):
        for col in range(1, cols):
            substitution_cost = 0 if expected_words[row - 1] == predicted_words[col - 1] else 1
            dp[row][col] = min(
                dp[row - 1][col] + 1,
                dp[row][col - 1] + 1,
                dp[row - 1][col - 1] + substitution_cost,
            )

    return dp[-1][-1] / len(expected_words)
