from __future__ import annotations

from dataclasses import dataclass
from typing import Any
import re

from .models import EntitySpan, TranscriptSegment, TranscriptWord, make_id


EMAIL_RE = re.compile(r"(?i)\b[a-z0-9._%+\-]+@[a-z0-9.\-]+\.[a-z]{2,}\b")
DATE_RE = re.compile(r"\b\d{1,2}[.\-/]\d{1,2}[.\-/](?:\d{2}|\d{4})\b")
TEXTUAL_DATE_RE = re.compile(
    r"(?i)\b\d{1,2}\s+(?:января|февраля|марта|апреля|мая|июня|июля|августа|сентября|октября|ноября|декабря)\s+\d{4}\b"
)
UNIT_CODE_RE = re.compile(r"\b\d{3}[- ]?\d{3}\b")
PASSPORT_SPLIT_RE = re.compile(r"\b\d{2}[ -]?\d{2}[ -]?\d{6}\b")
CARD_NUMBER_RE = re.compile(r"\b(?:\d{4}[ -]?){3}\d{4,7}\b")
BANK_ACCOUNT_RE = re.compile(r"\b\d{20}\b")

ADDRESS_MARKERS = {
    "адрес",
    "улица",
    "ул",
    "ул.",
    "проспект",
    "пр-т",
    "просп",
    "переулок",
    "пер",
    "пер.",
    "шоссе",
    "дом",
    "д",
    "д.",
    "корпус",
    "корп",
    "корп.",
    "строение",
    "стр",
    "стр.",
    "квартира",
    "кв",
    "кв.",
    "набережная",
    "наб",
    "город",
    "гор",
    "г",
    "г.",
    "поселок",
    "пос",
    "село",
    "деревня",
    "дер",
    "район",
    "область",
    "обл",
    "обл.",
    "республика",
    "край",
    "индекс",
}
ADDRESS_STOPWORDS = {
    "мой",
    "моя",
    "мое",
    "номер",
    "телефон",
    "почта",
    "email",
    "емейл",
    "дата",
    "рождения",
    "снилс",
    "инн",
    "паспорт",
    "карта",
    "счет",
    "счёт",
    "выдан",
}
PHONE_CONTEXT = {"телефон", "номер", "звоните", "мобильный", "сотовый", "позвоните", "контакт", "связи", "дозвониться"}
PASSPORT_CONTEXT = {"паспорт", "серия", "номер", "документ"}
CARD_CONTEXT = {"карта", "карты", "карточка", "card", "cvv", "cvc"}
BANK_ACCOUNT_CONTEXT = {"счет", "счета", "счёт", "аккаунт", "bank", "банк", "расчетный", "лицевой", "корреспондентский"}
EMAIL_WORD_MAP = {
    "собака": "@",
    "собачка": "@",
    "at": "@",
    "точка": ".",
    "dot": ".",
    "тире": "-",
    "дефис": "-",
    "минус": "-",
    "подчерк": "_",
    "подчёрк": "_",
    "underscore": "_",
}
EMAIL_CONTEXT = {"email", "емейл", "почта", "электронная"}
PLACE_OF_BIRTH_CONTEXT = {
    ("место", "рождения"),
    ("родился", "в"),
    ("родилась", "в"),
    ("родом", "из"),
    ("уроженец",),
    ("уроженка",),
}
MONTHS = {
    "января",
    "февраля",
    "марта",
    "апреля",
    "мая",
    "июня",
    "июля",
    "августа",
    "сентября",
    "октября",
    "ноября",
    "декабря",
}
CANONICAL_TOKEN_MAP = {
    "ё": "е",
    "емейл": "email",
    "e-mail": "email",
    "электронная": "email",
    "почта": "email",
    "счёт": "счет",
    "карточка": "карта",
    "собачка": "собака",
    "подчёрк": "подчерк",
}
SEVERITY_BY_ENTITY = {
    "PHONE": "critical",
    "EMAIL": "critical",
    "RU_INN": "critical",
    "RU_SNILS": "critical",
    "RU_PASSPORT": "critical",
    "CARD_NUMBER": "critical",
    "BANK_ACCOUNT": "critical",
    "PERSON_NAME": "high",
    "DATE_OF_BIRTH": "high",
    "PLACE_OF_BIRTH": "high",
    "RU_PASSPORT_ISSUER": "high",
    "RU_PASSPORT_UNIT_CODE": "high",
    "ADDRESS": "medium",
}


def entity_severity(entity_type: str) -> str:
    return SEVERITY_BY_ENTITY.get(entity_type, "medium")


def normalize_token(value: str) -> str:
    cleaned = value.lower().replace("ё", "е")
    mapped = CANONICAL_TOKEN_MAP.get(cleaned, cleaned)
    return mapped.strip(".,:;!?\"'()[]{}")


def normalize_compact_text(value: str) -> str:
    return re.sub(r"[\s.\-_/]+", "", value.lower().replace("ё", "е"))


def digits_only(value: str) -> str:
    return re.sub(r"\D", "", value)


def email_like_normalize(value: str) -> str:
    tokens = [normalize_token(token) for token in re.split(r"\s+", value) if token.strip()]
    rebuilt: list[str] = []
    for token in tokens:
        if token in EMAIL_WORD_MAP:
            rebuilt.append(EMAIL_WORD_MAP[token])
            continue
        rebuilt.append(token)
    normalized = "".join(rebuilt)
    normalized = normalized.replace(" ", "")
    return normalized


def looks_like_reconstructed_email(value: str) -> bool:
    return "@" in value and "." in value.split("@", 1)[-1] and len(value.split("@", 1)[0]) >= 1


def is_address_like_token(token: str) -> bool:
    normalized = normalize_token(token)
    return normalized in ADDRESS_MARKERS or bool(re.fullmatch(r"\d+[а-яa-z]?", normalized))


def is_email_atom_token(token: str) -> bool:
    normalized = normalize_token(token)
    return bool(re.fullmatch(r"[a-zа-я0-9]+", normalized))


DIGIT_WORDS = {
    "ноль": "0",
    "нуль": "0",
    "один": "1",
    "одна": "1",
    "два": "2",
    "две": "2",
    "три": "3",
    "четыре": "4",
    "пять": "5",
    "шесть": "6",
    "семь": "7",
    "восемь": "8",
    "девять": "9",
}
TEENS = {
    "десять": 10,
    "одиннадцать": 11,
    "двенадцать": 12,
    "тринадцать": 13,
    "четырнадцать": 14,
    "пятнадцать": 15,
    "шестнадцать": 16,
    "семнадцать": 17,
    "восемнадцать": 18,
    "девятнадцать": 19,
}
TENS = {
    "двадцать": 20,
    "тридцать": 30,
    "сорок": 40,
    "пятьдесят": 50,
    "шестьдесят": 60,
    "семьдесят": 70,
    "восемьдесят": 80,
    "девяносто": 90,
}
HUNDREDS = {
    "сто": 100,
    "двести": 200,
    "триста": 300,
    "четыреста": 400,
    "пятьсот": 500,
    "шестьсот": 600,
    "семьсот": 700,
    "восемьсот": 800,
    "девятьсот": 900,
}
MULTIPLIERS = {
    "тысяча": 1000,
    "тысячи": 1000,
    "тысяч": 1000,
}


@dataclass(slots=True)
class CanonicalizationResult:
    segments: list[TranscriptSegment]
    report: dict[str, Any]


@dataclass(slots=True)
class PiiDetectionResult:
    entity_spans: list[EntitySpan]
    normalized_candidates: list[dict[str, object]]
    entity_candidates: list[dict[str, object]]
    decision_log: list[dict[str, object]]
    confidence_report: dict[str, object]
    regex_matches_by_type: dict[str, int]
    email_reconstruction_candidates: list[dict[str, object]]


class RuNumeralNormalizer:
    def normalize_number_phrase(self, tokens: list[str]) -> str | None:
        if not tokens:
            return None
        if all(token in DIGIT_WORDS for token in tokens):
            return "".join(DIGIT_WORDS[token] for token in tokens)

        total = 0
        current = 0
        seen = False
        for token in tokens:
            if token in HUNDREDS:
                current += HUNDREDS[token]
                seen = True
            elif token in TENS:
                current += TENS[token]
                seen = True
            elif token in TEENS:
                current += TEENS[token]
                seen = True
            elif token in DIGIT_WORDS:
                current += int(DIGIT_WORDS[token])
                seen = True
            elif token in MULTIPLIERS:
                factor = MULTIPLIERS[token]
                current = max(current, 1)
                total += current * factor
                current = 0
                seen = True
            else:
                return None
        if not seen:
            return None
        return str(total + current)


class TranscriptCanonicalizer:
    def canonicalize(self, segments: list[TranscriptSegment], *, hotwords: list[str] | None = None) -> CanonicalizationResult:
        hotword_set = {normalize_token(item) for item in (hotwords or []) if str(item).strip()}
        canonical_segments: list[TranscriptSegment] = []
        edits: list[dict[str, Any]] = []
        touched_segments = 0
        for segment in segments:
            new_words: list[TranscriptWord] = []
            segment_edits: list[dict[str, Any]] = []
            for word in segment.words:
                normalized = normalize_token(word.text)
                if normalized in hotword_set:
                    normalized = normalized
                if normalized != word.text:
                    segment_edits.append({"from": word.text, "to": normalized})
                new_words.append(
                    TranscriptWord(
                        text=normalized,
                        start_ms=word.start_ms,
                        end_ms=word.end_ms,
                        confidence=word.confidence,
                        speaker_id=word.speaker_id,
                        channel_id=word.channel_id,
                    )
                )
            if segment_edits:
                touched_segments += 1
                edits.append({"segment_id": segment.segment_id, "edits": segment_edits})
            canonical_segments.append(
                TranscriptSegment(
                    segment_id=segment.segment_id,
                    speaker_id=segment.speaker_id,
                    start_ms=segment.start_ms,
                    end_ms=segment.end_ms,
                    text=" ".join(word.text for word in new_words),
                    words=new_words,
                    avg_confidence=segment.avg_confidence,
                    overlap=segment.overlap,
                    channel_id=segment.channel_id,
                )
            )
        return CanonicalizationResult(
            segments=canonical_segments,
            report={
                "touched_segments": touched_segments,
                "total_segments": len(segments),
                "edits": edits,
            },
        )


class PiiCascade:
    def __init__(self) -> None:
        self.numeral_normalizer = RuNumeralNormalizer()

    def detect(self, segments: list[TranscriptSegment], *, pii_entities: list[str], action_mode: str) -> PiiDetectionResult:
        entities: list[EntitySpan] = []
        normalized_candidates: list[dict[str, object]] = []
        entity_candidates: list[dict[str, object]] = []
        email_reconstruction_candidates: list[dict[str, object]] = []
        regex_matches_by_type = {entity_type: 0 for entity_type in pii_entities}
        enabled = set(pii_entities)
        for segment in segments:
            joined_text = " ".join(word.text for word in segment.words)
            normalized_words = [normalize_token(word.text) for word in segment.words]
            char_spans = self._build_char_spans(segment.words)

            if "EMAIL" in enabled:
                for match in EMAIL_RE.finditer(joined_text):
                    word_start, word_end = self._char_span_to_word_indices(char_spans, match.start(), match.end())
                    entity = self._build_entity(
                        segment=segment,
                        entity_type="EMAIL",
                        text=match.group(0),
                        normalized_value=match.group(0).lower(),
                        start_word_index=word_start,
                        end_word_index=word_end,
                        confidence=0.99,
                        sources=["regex_email"],
                        action_mode=action_mode,
                    )
                    entities.append(entity)
                    entity_candidates.append(self._entity_candidate(entity, layer="deterministic"))
                    regex_matches_by_type["EMAIL"] += 1
                reconstructed_email = self._detect_spoken_email(segment, normalized_words, action_mode)
                if reconstructed_email is not None:
                    entities.append(reconstructed_email["entity"])
                    entity_candidates.append(self._entity_candidate(reconstructed_email["entity"], layer="document_rules"))
                    email_reconstruction_candidates.append(reconstructed_email["candidate"])
                    regex_matches_by_type["EMAIL"] += 1

            if "DATE_OF_BIRTH" in enabled:
                for match in DATE_RE.finditer(joined_text):
                    word_start, word_end = self._char_span_to_word_indices(char_spans, match.start(), match.end())
                    entity = self._build_entity(
                        segment=segment,
                        entity_type="DATE_OF_BIRTH",
                        text=match.group(0),
                        normalized_value=match.group(0),
                        start_word_index=word_start,
                        end_word_index=word_end,
                        confidence=0.86,
                        sources=["date_regex"],
                        action_mode=action_mode,
                    )
                    entities.append(entity)
                    entity_candidates.append(self._entity_candidate(entity, layer="document_rules"))
                    regex_matches_by_type["DATE_OF_BIRTH"] += 1
                for match in TEXTUAL_DATE_RE.finditer(joined_text):
                    word_start, word_end = self._char_span_to_word_indices(char_spans, match.start(), match.end())
                    entity = self._build_entity(
                        segment=segment,
                        entity_type="DATE_OF_BIRTH",
                        text=match.group(0),
                        normalized_value=match.group(0).lower(),
                        start_word_index=word_start,
                        end_word_index=word_end,
                        confidence=0.9,
                        sources=["date_textual_regex"],
                        action_mode=action_mode,
                    )
                    entities.append(entity)
                    entity_candidates.append(self._entity_candidate(entity, layer="document_rules"))
                    regex_matches_by_type["DATE_OF_BIRTH"] += 1

            numeric_candidates = self._collect_numeric_candidates(segment.words, normalized_words)
            normalized_candidates.extend(numeric_candidates)
            numeric_entities = self._entities_from_numeric_candidates(segment, numeric_candidates, enabled, action_mode)
            entities.extend(numeric_entities)
            entity_candidates.extend(self._entity_candidate(entity, layer="deterministic") for entity in numeric_entities)
            for entity in numeric_entities:
                regex_matches_by_type[entity.type] = regex_matches_by_type.get(entity.type, 0) + 1

            if "RU_PASSPORT_UNIT_CODE" in enabled:
                unit_code_entities = self._detect_passport_unit_codes(segment, normalized_words, action_mode)
                entities.extend(unit_code_entities)
                entity_candidates.extend(self._entity_candidate(entity, layer="document_rules") for entity in unit_code_entities)
                regex_matches_by_type["RU_PASSPORT_UNIT_CODE"] += len(unit_code_entities)

            if "ADDRESS" in enabled:
                address_entities = self._detect_addresses(segment, normalized_words, action_mode)
                entities.extend(address_entities)
                entity_candidates.extend(self._entity_candidate(entity, layer="document_rules") for entity in address_entities)
                regex_matches_by_type["ADDRESS"] += len(address_entities)

        resolved, decision_log = self._resolve_overlaps(entities)
        confidence_report = {
            "total_entities": len(resolved),
            "counts_by_type": {
                entity_type: sum(1 for entity in resolved if entity.type == entity_type)
                for entity_type in enabled
            },
            "candidate_count": len(entity_candidates),
            "severity_counts": {
                severity: sum(1 for entity in resolved if entity_severity(entity.type) == severity)
                for severity in ("critical", "high", "medium")
            },
        }
        return PiiDetectionResult(
            entity_spans=resolved,
            normalized_candidates=normalized_candidates,
            entity_candidates=entity_candidates,
            decision_log=decision_log,
            confidence_report=confidence_report,
            regex_matches_by_type=regex_matches_by_type,
            email_reconstruction_candidates=email_reconstruction_candidates,
        )

    def _build_char_spans(self, words: list[TranscriptWord]) -> list[tuple[int, int]]:
        spans = []
        cursor = 0
        for word in words:
            start = cursor
            end = start + len(word.text)
            spans.append((start, end))
            cursor = end + 1
        return spans

    def _char_span_to_word_indices(self, spans: list[tuple[int, int]], start_char: int, end_char: int) -> tuple[int, int]:
        start_index = 0
        end_index = len(spans) - 1
        for index, (start, end) in enumerate(spans):
            if start <= start_char < end:
                start_index = index
                break
        for index, (start, end) in enumerate(spans):
            if start < end_char <= end:
                end_index = index
                break
        return start_index, end_index

    def _collect_numeric_candidates(self, words: list[TranscriptWord], normalized_words: list[str]) -> list[dict[str, object]]:
        candidates: list[dict[str, object]] = []
        index = 0
        while index < len(words):
            token = normalized_words[index]
            if not self._is_numericish_token(token):
                index += 1
                continue
            start_index = index
            run_tokens: list[str] = []
            run_text: list[str] = []
            while index < len(words) and self._is_numericish_token(normalized_words[index]):
                run_tokens.append(normalized_words[index])
                run_text.append(words[index].text)
                index += 1
            digits = self._normalize_numeric_run(run_tokens)
            if digits:
                candidates.append(
                    {
                        "candidate_id": make_id("cand"),
                        "text": " ".join(run_text),
                        "normalized_value": digits,
                        "start_word_index": start_index,
                        "end_word_index": index - 1,
                        "sources": ["numeral_normalizer"] if any(token in DIGIT_WORDS or token in HUNDREDS or token in TENS or token in TEENS for token in run_tokens) else ["raw_digits"],
                    }
                )
        joined_text = " ".join(word.text for word in words)
        for regex_name, regex in (("passport_split", PASSPORT_SPLIT_RE), ("card_regex", CARD_NUMBER_RE), ("bank_account_regex", BANK_ACCOUNT_RE)):
            for match in regex.finditer(joined_text):
                start_word_index, end_word_index = self._char_span_to_word_indices(self._build_char_spans(words), match.start(), match.end())
                digits = digits_only(match.group(0))
                if digits:
                    candidates.append(
                        {
                            "candidate_id": make_id("cand"),
                            "text": match.group(0),
                            "normalized_value": digits,
                            "start_word_index": start_word_index,
                            "end_word_index": end_word_index,
                            "sources": [regex_name],
                        }
                    )
        return candidates

    def _normalize_numeric_run(self, tokens: list[str]) -> str | None:
        parts: list[str] = []
        current_numeral_group: list[str] = []
        for token in tokens:
            if re.search(r"\d", token):
                if current_numeral_group:
                    normalized = self.numeral_normalizer.normalize_number_phrase(current_numeral_group)
                    if not normalized:
                        return None
                    parts.append(normalized)
                    current_numeral_group = []
                parts.append(re.sub(r"\D", "", token))
            else:
                current_numeral_group.append(token)
        if current_numeral_group:
            normalized = self.numeral_normalizer.normalize_number_phrase(current_numeral_group)
            if not normalized:
                return None
            parts.append(normalized)
        value = "".join(parts)
        return value if value else None

    def _is_numericish_token(self, token: str) -> bool:
        return bool(re.search(r"\d", token)) or token in DIGIT_WORDS or token in TEENS or token in TENS or token in HUNDREDS or token in MULTIPLIERS

    def _entities_from_numeric_candidates(
        self,
        segment: TranscriptSegment,
        candidates: list[dict[str, object]],
        enabled: set[str],
        action_mode: str,
    ) -> list[EntitySpan]:
        entities: list[EntitySpan] = []
        context_tokens = [normalize_token(word.text) for word in segment.words]
        for candidate in candidates:
            digits = str(candidate["normalized_value"])
            start_word_index = int(candidate["start_word_index"])
            end_word_index = int(candidate["end_word_index"])
            context_window = context_tokens[max(start_word_index - 3, 0) : min(end_word_index + 4, len(context_tokens))]

            if "RU_SNILS" in enabled and len(digits) == 11 and self._is_valid_snils(digits):
                entities.append(self._build_entity(segment, "RU_SNILS", candidate["text"], digits, start_word_index, end_word_index, 0.98, list(candidate["sources"]) + ["checksum_snils"], action_mode))
                continue
            if "RU_INN" in enabled and len(digits) in {10, 12} and self._is_valid_inn(digits):
                entities.append(self._build_entity(segment, "RU_INN", candidate["text"], digits, start_word_index, end_word_index, 0.97, list(candidate["sources"]) + ["checksum_inn"], action_mode))
                continue
            if "RU_PASSPORT" in enabled and len(digits) == 10 and PASSPORT_CONTEXT.intersection(context_window):
                entities.append(self._build_entity(segment, "RU_PASSPORT", candidate["text"], digits, start_word_index, end_word_index, 0.95, list(candidate["sources"]) + ["passport_context"], action_mode))
                continue
            if "RU_PASSPORT" in enabled and len(digits) == 10 and any(source in {"passport_split", "raw_digits"} for source in candidate["sources"]):
                entities.append(self._build_entity(segment, "RU_PASSPORT", candidate["text"], digits, start_word_index, end_word_index, 0.91, list(candidate["sources"]) + ["passport_shape"], action_mode))
                continue
            if "CARD_NUMBER" in enabled and 16 <= len(digits) <= 19 and self._is_luhn_valid(digits):
                entities.append(self._build_entity(segment, "CARD_NUMBER", candidate["text"], digits, start_word_index, end_word_index, 0.96, list(candidate["sources"]) + ["luhn_card"], action_mode))
                continue
            if "BANK_ACCOUNT" in enabled and len(digits) == 20 and BANK_ACCOUNT_CONTEXT.intersection(context_window):
                entities.append(self._build_entity(segment, "BANK_ACCOUNT", candidate["text"], digits, start_word_index, end_word_index, 0.9, list(candidate["sources"]) + ["bank_account_context"], action_mode))
                continue
            if "BANK_ACCOUNT" in enabled and len(digits) == 20 and any(source == "bank_account_regex" for source in candidate["sources"]):
                entities.append(self._build_entity(segment, "BANK_ACCOUNT", candidate["text"], digits, start_word_index, end_word_index, 0.88, list(candidate["sources"]) + ["bank_account_shape"], action_mode))
                continue
            if "PHONE" in enabled and len(digits) in {10, 11}:
                entities.append(self._build_entity(segment, "PHONE", candidate["text"], digits, start_word_index, end_word_index, 0.93, list(candidate["sources"]) + ["phone_rules"], action_mode))
                continue
            if "PHONE" in enabled and 7 <= len(digits) <= 11 and PHONE_CONTEXT.intersection(context_window):
                entities.append(
                    self._build_entity(
                        segment,
                        "PHONE",
                        candidate["text"],
                        digits,
                        start_word_index,
                        end_word_index,
                        0.82,
                        list(candidate["sources"]) + ["phone_context_partial"],
                        action_mode,
                    )
                )
        return entities

    def _detect_spoken_email(self, segment: TranscriptSegment, normalized_words: list[str], action_mode: str) -> dict[str, object] | None:
        for index, token in enumerate(normalized_words):
            if token not in EMAIL_CONTEXT:
                continue
            start = min(index + 1, len(normalized_words))
            end = start
            seen_signal = False
            while end < len(normalized_words) and end - start < 12:
                current = normalized_words[end]
                if current in ADDRESS_STOPWORDS and end > start:
                    break
                if current in EMAIL_WORD_MAP or is_email_atom_token(current):
                    seen_signal = True
                    end += 1
                    continue
                if seen_signal:
                    break
                end += 1
            if start >= end:
                continue
            text = " ".join(word.text for word in segment.words[start:end]).strip()
            normalized_value = email_like_normalize(text)
            if not looks_like_reconstructed_email(normalized_value):
                continue
            entity = self._build_entity(
                segment,
                "EMAIL",
                text,
                normalized_value,
                start,
                end - 1,
                0.88,
                ["spoken_email_reconstruction"],
                action_mode,
            )
            return {
                "entity": entity,
                "candidate": {
                    "segment_id": segment.segment_id,
                    "spoken_text": text,
                    "normalized_value": normalized_value,
                    "start_word_index": start,
                    "end_word_index": end - 1,
                },
            }
        return None

    def _detect_passport_unit_codes(self, segment: TranscriptSegment, normalized_words: list[str], action_mode: str) -> list[EntitySpan]:
        entities: list[EntitySpan] = []
        joined_text = " ".join(word.text for word in segment.words)
        char_spans = self._build_char_spans(segment.words)
        for match in UNIT_CODE_RE.finditer(joined_text):
            start_word_index, end_word_index = self._char_span_to_word_indices(char_spans, match.start(), match.end())
            context_window = normalized_words[max(start_word_index - 3, 0) : min(end_word_index + 4, len(normalized_words))]
            if {"код", "подразделения"}.intersection(context_window):
                entities.append(
                    self._build_entity(
                        segment,
                        "RU_PASSPORT_UNIT_CODE",
                        match.group(0),
                        re.sub(r"\D", "", match.group(0)),
                        start_word_index,
                        end_word_index,
                        0.91,
                        ["passport_unit_code"],
                        action_mode,
                    )
                )
        return entities

    def _detect_addresses(self, segment: TranscriptSegment, normalized_words: list[str], action_mode: str) -> list[EntitySpan]:
        addresses: list[EntitySpan] = []
        index = 0
        while index < len(normalized_words):
            token = normalized_words[index]
            if token not in ADDRESS_MARKERS:
                index += 1
                continue
            end_index = index
            marker_count = 0
            while end_index + 1 < len(normalized_words):
                next_token = normalized_words[end_index + 1]
                if next_token in ADDRESS_STOPWORDS and marker_count > 0:
                    break
                if next_token in ADDRESS_MARKERS:
                    marker_count += 1
                elif not next_token or next_token == "-":
                    break
                end_index += 1
                if end_index - index >= 13:
                    break
            text = " ".join(word.text for word in segment.words[index : end_index + 1]).strip()
            if text:
                addresses.append(
                    self._build_entity(
                        segment=segment,
                        entity_type="ADDRESS",
                        text=text,
                        normalized_value=text.lower(),
                        start_word_index=index,
                        end_word_index=end_index,
                        confidence=0.78 if marker_count else 0.74,
                        sources=["address_ner_rules"],
                        action_mode=action_mode,
                    )
                )
            index = end_index + 1
        return addresses

    def _build_entity(
        self,
        segment: TranscriptSegment,
        entity_type: str,
        text: str,
        normalized_value: str,
        start_word_index: int,
        end_word_index: int,
        confidence: float,
        sources: list[str],
        action_mode: str,
    ) -> EntitySpan:
        return EntitySpan(
            entity_id=make_id("ent"),
            type=entity_type,
            text=text,
            normalized_value=normalized_value,
            speaker_id=segment.speaker_id,
            segment_id=segment.segment_id,
            start_word_index=start_word_index,
            end_word_index=end_word_index,
            confidence=confidence,
            sources=sources,
            action="mute_and_mask" if action_mode == "mute" else "beep_and_mask",
        )

    def _entity_candidate(self, entity: EntitySpan, *, layer: str) -> dict[str, object]:
        return {
            "candidate_id": entity.entity_id,
            "layer": layer,
            "entity_type": entity.type,
            "severity": entity_severity(entity.type),
            "segment_id": entity.segment_id,
            "speaker_id": entity.speaker_id,
            "text": entity.text,
            "normalized_value": entity.normalized_value,
            "start_word_index": entity.start_word_index,
            "end_word_index": entity.end_word_index,
            "confidence": entity.confidence,
            "sources": list(entity.sources),
        }

    def _resolve_overlaps(self, entities: list[EntitySpan]) -> tuple[list[EntitySpan], list[dict[str, object]]]:
        sorted_entities = sorted(
            entities,
            key=lambda entity: (entity.segment_id, entity.start_word_index, -(entity.end_word_index - entity.start_word_index), -entity.confidence),
        )
        chosen: list[EntitySpan] = []
        decisions: list[dict[str, object]] = []
        for entity in sorted_entities:
            conflict = next(
                (
                    other
                    for other in chosen
                    if other.segment_id == entity.segment_id
                    and not (entity.end_word_index < other.start_word_index or entity.start_word_index > other.end_word_index)
                ),
                None,
            )
            if conflict is None:
                chosen.append(entity)
                decisions.append({"entity_id": entity.entity_id, "decision": "accepted", "reason": "no_conflict"})
                continue
            if conflict.type == entity.type == "ADDRESS":
                conflict.start_word_index = min(conflict.start_word_index, entity.start_word_index)
                conflict.end_word_index = max(conflict.end_word_index, entity.end_word_index)
                if len(entity.text) > len(conflict.text):
                    conflict.text = entity.text
                    conflict.normalized_value = entity.normalized_value
                conflict.confidence = max(conflict.confidence, entity.confidence)
                conflict.sources.extend(source for source in entity.sources if source not in conflict.sources)
                decisions.append({"entity_id": entity.entity_id, "decision": "accepted", "reason": "address_overlap_expanded"})
                continue
            current_span = entity.end_word_index - entity.start_word_index
            other_span = conflict.end_word_index - conflict.start_word_index
            if entity.confidence > conflict.confidence or (entity.confidence == conflict.confidence and current_span > other_span):
                chosen.remove(conflict)
                chosen.append(entity)
                decisions.append({"entity_id": entity.entity_id, "decision": "accepted", "reason": "higher_priority_conflict"})
                decisions.append({"entity_id": conflict.entity_id, "decision": "rejected", "reason": "overlap_replaced"})
            else:
                decisions.append({"entity_id": entity.entity_id, "decision": "rejected", "reason": "lower_priority_overlap"})
        return sorted(chosen, key=lambda entity: (entity.segment_id, entity.start_word_index)), decisions

    def _is_valid_snils(self, value: str) -> bool:
        if len(value) != 11 or not value.isdigit():
            return False
        checksum = sum(int(value[index]) * (9 - index) for index in range(9))
        if checksum < 100:
            expected = checksum
        elif checksum in {100, 101}:
            expected = 0
        else:
            expected = checksum % 101
            if expected == 100:
                expected = 0
        return expected == int(value[-2:])

    def _is_valid_inn(self, value: str) -> bool:
        if len(value) == 10:
            coefficients = (2, 4, 10, 3, 5, 9, 4, 6, 8)
            check = sum(int(value[index]) * coefficients[index] for index in range(9)) % 11 % 10
            return check == int(value[9])
        if len(value) == 12:
            coefficients_1 = (7, 2, 4, 10, 3, 5, 9, 4, 6, 8)
            coefficients_2 = (3, 7, 2, 4, 10, 3, 5, 9, 4, 6, 8)
            check_1 = sum(int(value[index]) * coefficients_1[index] for index in range(10)) % 11 % 10
            check_2 = sum(int(value[index]) * coefficients_2[index] for index in range(11)) % 11 % 10
            return check_1 == int(value[10]) and check_2 == int(value[11])
        return False

    def _is_luhn_valid(self, value: str) -> bool:
        if not value.isdigit():
            return False
        checksum = 0
        reverse_digits = list(reversed(value))
        for index, digit in enumerate(reverse_digits):
            number = int(digit)
            if index % 2 == 1:
                number *= 2
                if number > 9:
                    number -= 9
            checksum += number
        return checksum % 10 == 0
