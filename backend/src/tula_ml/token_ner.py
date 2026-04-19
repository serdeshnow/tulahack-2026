from __future__ import annotations

from dataclasses import dataclass
from typing import Any
import re

from .config import AppConfig
from .models import EntitySpan, ProcessingProfile, TranscriptSegment, make_id
from .pii import ADDRESS_MARKERS, TEXTUAL_DATE_RE, email_like_normalize, is_address_like_token, normalize_token


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
DATE_RE = re.compile(r"\b\d{1,2}[.\-/]\d{1,2}[.\-/](?:\d{2}|\d{4})\b")
UNIT_CODE_RE = re.compile(r"\b\d{3}[- ]?\d{3}\b")
PASSPORT_ISSUER_STOPWORDS = {"код", "подразделения", "дата", "выдачи", "серия", "номер", "действителен"}


class TokenNerError(RuntimeError):
    pass


@dataclass(slots=True)
class TokenNerResult:
    entities: list[EntitySpan]
    report: dict[str, Any]
    model_name: str
    model_version: str
    degraded: bool


def _tokenize_text(text: str) -> list[str]:
    return [token for token in text.replace("\n", " ").split(" ") if token]


def _is_alpha_token(token: str) -> bool:
    return bool(re.fullmatch(r"[A-Za-zА-Яа-яЁё-]+", token))


class SelfHostedTokenNerRecognizer:
    SUPPORTED_TYPES = {
        "PERSON_NAME",
        "DATE_OF_BIRTH",
        "PLACE_OF_BIRTH",
        "RU_PASSPORT_ISSUER",
        "RU_PASSPORT_UNIT_CODE",
        "ADDRESS",
    }

    def __init__(self, config: AppConfig) -> None:
        self.config = config
        self._transformers_pipeline = None
        self._backend_name = "contextual-rules"
        self._backend_version = "v1"
        self._degraded = False
        if config.token_ner_backend == "transformers":
            self._setup_transformers_backend()

    def _setup_transformers_backend(self) -> None:
        try:
            from transformers import pipeline  # type: ignore
        except ImportError:
            self._degraded = True
            self._backend_name = "contextual-rules"
            self._backend_version = "fallback-no-transformers"
            return
        model_ref = self.config.token_ner_model_path or self.config.token_ner_model_name
        try:
            self._transformers_pipeline = pipeline(
                "token-classification",
                model=model_ref,
                aggregation_strategy="simple",
            )
            self._backend_name = str(model_ref)
            self._backend_version = "transformers"
        except Exception:  # noqa: BLE001 - fallback is an explicit runtime mode.
            self._degraded = True
            self._transformers_pipeline = None
            self._backend_name = "contextual-rules"
            self._backend_version = "fallback-load-failed"

    def detect(self, segments: list[TranscriptSegment], profile: ProcessingProfile) -> TokenNerResult:
        enabled_types = set(profile.pii_entities).intersection(self.SUPPORTED_TYPES)
        if self._transformers_pipeline:
            entities = self._detect_with_transformers(segments, enabled_types)
        else:
            entities = self._detect_with_contextual_rules(segments, enabled_types)
        report = {
            "backend": self._backend_name,
            "backend_version": self._backend_version,
            "degraded": self._degraded,
            "supported_types": sorted(enabled_types),
            "entity_count": len(entities),
            "counts_by_type": {
                entity_type: sum(1 for entity in entities if entity.type == entity_type)
                for entity_type in sorted(enabled_types)
            },
        }
        return TokenNerResult(
            entities=entities,
            report=report,
            model_name=self._backend_name,
            model_version=self._backend_version,
            degraded=self._degraded,
        )

    def _detect_with_transformers(self, segments: list[TranscriptSegment], enabled_types: set[str]) -> list[EntitySpan]:
        entities: list[EntitySpan] = []
        assert self._transformers_pipeline is not None
        for segment in segments:
            raw_results = self._transformers_pipeline(segment.text)
            for item in raw_results:
                entity_type = str(item.get("entity_group") or item.get("entity") or "").upper()
                if entity_type not in enabled_types:
                    continue
                mapped = self._map_text_candidate(
                    segment=segment,
                    entity_type=entity_type,
                    text=str(item.get("word") or "").strip(),
                    normalized_value=str(item.get("word") or "").strip().lower(),
                    confidence=float(item.get("score") or 0.75),
                    sources=["token_ner_transformers"],
                )
                if mapped:
                    entities.append(mapped)
        return entities

    def _detect_with_contextual_rules(self, segments: list[TranscriptSegment], enabled_types: set[str]) -> list[EntitySpan]:
        entities: list[EntitySpan] = []
        for segment in segments:
            normalized_words = [normalize_token(word.text) for word in segment.words]
            if "DATE_OF_BIRTH" in enabled_types:
                entities.extend(self._detect_date_of_birth(segment))
            if "RU_PASSPORT_UNIT_CODE" in enabled_types:
                entities.extend(self._detect_passport_unit_code(segment, normalized_words))
            if "RU_PASSPORT_ISSUER" in enabled_types:
                entities.extend(self._detect_passport_issuer(segment, normalized_words))
            if "PLACE_OF_BIRTH" in enabled_types:
                entities.extend(self._detect_place_of_birth(segment, normalized_words))
            if "PERSON_NAME" in enabled_types:
                entities.extend(self._detect_person_name(segment, normalized_words))
            if "ADDRESS" in enabled_types:
                entities.extend(self._detect_address_context(segment, normalized_words))
        return self._resolve_overlaps(entities)

    def _detect_date_of_birth(self, segment: TranscriptSegment) -> list[EntitySpan]:
        entities: list[EntitySpan] = []
        joined_text = " ".join(word.text for word in segment.words)
        char_spans = self._build_char_spans(segment.words)
        for match in DATE_RE.finditer(joined_text):
            start_word_index, end_word_index = self._char_span_to_word_indices(char_spans, match.start(), match.end())
            entities.append(
                self._build_entity(
                    segment,
                    "DATE_OF_BIRTH",
                    match.group(0),
                    match.group(0),
                    start_word_index,
                    end_word_index,
                    0.88,
                    ["token_ner_contextual", "date_regex"],
                )
            )
        for match in TEXTUAL_DATE_RE.finditer(joined_text):
            start_word_index, end_word_index = self._char_span_to_word_indices(char_spans, match.start(), match.end())
            entities.append(
                self._build_entity(
                    segment,
                    "DATE_OF_BIRTH",
                    match.group(0),
                    match.group(0).lower(),
                    start_word_index,
                    end_word_index,
                    0.9,
                    ["token_ner_contextual", "date_textual_regex"],
                )
            )
        normalized_words = [normalize_token(word.text) for word in segment.words]
        for index in range(0, len(normalized_words) - 2):
            window = normalized_words[index : index + 3]
            if window[1] in MONTHS and window[0].isdigit() and window[2].isdigit() and len(window[2]) == 4:
                entities.append(
                    self._build_entity(
                        segment,
                        "DATE_OF_BIRTH",
                        " ".join(word.text for word in segment.words[index : index + 3]),
                        " ".join(window),
                        index,
                        index + 2,
                        0.82,
                        ["token_ner_contextual", "date_month_phrase"],
                    )
                )
        return entities

    def _detect_passport_unit_code(self, segment: TranscriptSegment, normalized_words: list[str]) -> list[EntitySpan]:
        entities: list[EntitySpan] = []
        joined_text = " ".join(word.text for word in segment.words)
        char_spans = self._build_char_spans(segment.words)
        for match in UNIT_CODE_RE.finditer(joined_text):
            start_word_index, end_word_index = self._char_span_to_word_indices(char_spans, match.start(), match.end())
            context = normalized_words[max(0, start_word_index - 3) : min(len(normalized_words), end_word_index + 4)]
            if {"код", "подразделения"}.intersection(context):
                normalized_value = re.sub(r"\D", "", match.group(0))
                entities.append(
                    self._build_entity(
                        segment,
                        "RU_PASSPORT_UNIT_CODE",
                        match.group(0),
                        normalized_value,
                        start_word_index,
                        end_word_index,
                        0.93,
                        ["token_ner_contextual", "passport_unit_code"],
                    )
                )
        return entities

    def _detect_passport_issuer(self, segment: TranscriptSegment, normalized_words: list[str]) -> list[EntitySpan]:
        markers = {"выдан", "кем", "паспорт"}
        entities: list[EntitySpan] = []
        for index, token in enumerate(normalized_words):
            if token != "выдан":
                continue
            start = index + 1
            end = start
            while end < len(normalized_words) and end - start < 12:
                if normalized_words[end] in PASSPORT_ISSUER_STOPWORDS:
                    break
                end += 1
            if start < end:
                text = " ".join(word.text for word in segment.words[start:end]).strip()
                if text and len(text.split()) >= 2 and markers.intersection(normalized_words[max(0, index - 2) : min(len(normalized_words), end + 1)]):
                    entities.append(
                        self._build_entity(
                            segment,
                            "RU_PASSPORT_ISSUER",
                            text,
                            text.lower(),
                            start,
                            end - 1,
                            0.76,
                            ["token_ner_contextual", "passport_issuer_context"],
                        )
                    )
        return entities

    def _detect_place_of_birth(self, segment: TranscriptSegment, normalized_words: list[str]) -> list[EntitySpan]:
        entities: list[EntitySpan] = []
        for index in range(len(normalized_words)):
            if normalized_words[index:index + 2] == ["место", "рождения"]:
                start = min(index + 2, len(normalized_words))
                end = min(len(normalized_words), start + 6)
            elif normalized_words[index:index + 2] == ["родился", "в"]:
                start = min(index + 2, len(normalized_words))
                end = min(len(normalized_words), start + 6)
            elif normalized_words[index:index + 2] == ["родом", "из"]:
                start = min(index + 2, len(normalized_words))
                end = min(len(normalized_words), start + 6)
            elif normalized_words[index] in {"уроженец", "уроженка"}:
                start = min(index + 1, len(normalized_words))
                end = min(len(normalized_words), start + 6)
            else:
                continue
            if start >= end:
                continue
            text = " ".join(word.text for word in segment.words[start:end]).strip()
            if text:
                entities.append(
                    self._build_entity(
                        segment,
                        "PLACE_OF_BIRTH",
                        text,
                        text.lower(),
                        start,
                        end - 1,
                        0.74,
                        ["token_ner_contextual", "birth_place_context"],
                    )
                )
        return entities

    def _detect_person_name(self, segment: TranscriptSegment, normalized_words: list[str]) -> list[EntitySpan]:
        entities: list[EntitySpan] = []
        name_markers = {("меня", "зовут"), ("имя",), ("фамилия",), ("фио",), ("фамилия", "имя", "отчество"), ("я",), ("это",)}
        for index in range(len(normalized_words)):
            matched = None
            for marker in name_markers:
                if normalized_words[index : index + len(marker)] == list(marker):
                    matched = len(marker)
                    break
            if matched is None:
                continue
            start = index + matched
            end = start
            while end < len(segment.words) and end - start < 3:
                token = segment.words[end].text.strip(",. ")
                if not _is_alpha_token(token):
                    break
                if normalize_token(token) in ADDRESS_MARKERS:
                    break
                end += 1
            if start < end:
                text = " ".join(word.text for word in segment.words[start:end]).strip()
                if len(text.split()) >= 1:
                    entities.append(
                        self._build_entity(
                            segment,
                            "PERSON_NAME",
                            text,
                            text.lower(),
                            start,
                            end - 1,
                            0.72,
                            ["token_ner_contextual", "person_name_context"],
                        )
                    )
        return entities

    def _detect_address_context(self, segment: TranscriptSegment, normalized_words: list[str]) -> list[EntitySpan]:
        entities: list[EntitySpan] = []
        for index, token in enumerate(normalized_words):
            if token != "адрес":
                continue
            start = min(index + 1, len(normalized_words))
            end = min(len(normalized_words), start + 12)
            if start >= end:
                continue
            phrase = normalized_words[start:end]
            if not set(phrase).intersection(ADDRESS_MARKERS):
                continue
            while end > start and not is_address_like_token(normalized_words[end - 1]):
                end -= 1
            if end <= start:
                continue
            text = " ".join(word.text for word in segment.words[start:end]).strip()
            if text:
                entities.append(
                    self._build_entity(
                        segment,
                        "ADDRESS",
                        text,
                        text.lower(),
                        start,
                        end - 1,
                        0.71,
                        ["token_ner_contextual", "address_context"],
                    )
                )
        return entities

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
            action="beep_and_mask",
        )

    def _build_char_spans(self, words: list[Any]) -> list[tuple[int, int]]:
        spans: list[tuple[int, int]] = []
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

    def _map_text_candidate(
        self,
        *,
        segment: TranscriptSegment,
        entity_type: str,
        text: str,
        normalized_value: str,
        confidence: float,
        sources: list[str],
    ) -> EntitySpan | None:
        if not text:
            return None
        normalized_words = [normalize_token(word.text) for word in segment.words]
        candidate_tokens = [normalize_token(token) for token in _tokenize_text(text)]
        if entity_type == "EMAIL":
            email_text = email_like_normalize(text)
            for start in range(len(segment.words)):
                for end in range(start, min(len(segment.words), start + 12)):
                    candidate = " ".join(word.text for word in segment.words[start : end + 1])
                    if email_like_normalize(candidate) == email_text:
                        return self._build_entity(
                            segment,
                            entity_type,
                            text,
                            normalized_value,
                            start,
                            end,
                            confidence,
                            sources,
                        )
        if not candidate_tokens:
            return None
        for index in range(0, len(normalized_words) - len(candidate_tokens) + 1):
            if normalized_words[index : index + len(candidate_tokens)] == candidate_tokens:
                return self._build_entity(
                    segment,
                    entity_type,
                    text,
                    normalized_value,
                    index,
                    index + len(candidate_tokens) - 1,
                    confidence,
                    sources,
                )
        return None

    def _resolve_overlaps(self, entities: list[EntitySpan]) -> list[EntitySpan]:
        resolved: list[EntitySpan] = []
        for entity in sorted(entities, key=lambda item: (item.segment_id, item.start_word_index, -item.confidence)):
            conflict = next(
                (
                    existing
                    for existing in resolved
                    if existing.segment_id == entity.segment_id
                    and not (entity.end_word_index < existing.start_word_index or entity.start_word_index > existing.end_word_index)
                ),
                None,
            )
            if conflict is None or entity.confidence > conflict.confidence:
                if conflict is not None:
                    resolved.remove(conflict)
                resolved.append(entity)
        return sorted(resolved, key=lambda item: (item.segment_id, item.start_word_index))
