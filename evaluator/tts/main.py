from io import BytesIO
from threading import Lock
import re

import numpy as np
import soundfile as sf
from fastapi import FastAPI, HTTPException
from fastapi.responses import Response
from pydantic import BaseModel, Field
from silero import silero_tts
from num2words import num2words

app = FastAPI(title="RU TTS API", version="1.0.2")

_model = None
_model_init_lock = Lock()
_tts_lock = Lock()

DEFAULT_SPEAKER = "xenia"
DEFAULT_SAMPLE_RATE = 24000
ALLOWED_SAMPLE_RATES = {8000, 24000, 48000}

SPEAKER_ALIASES = {
    "xenia": "xenia",
    "kseniya": "kseniya",
    "aidar": "aidar",
    "baya": "baya",
    "eugene": "eugene",
}


class TTSRequest(BaseModel):
    text: str = Field(..., min_length=1, max_length=2000)
    speaker: str = Field(default=DEFAULT_SPEAKER)
    sample_rate: int = Field(default=DEFAULT_SAMPLE_RATE)


def number_to_words_ru(value: str) -> str:
    return num2words(int(value), lang="ru")


def replace_fractions(text: str) -> str:
    # 3/1 -> три делить на один
    def repl(match):
        left = match.group(1)
        right = match.group(2)
        try:
            left_words = number_to_words_ru(left)
            right_words = number_to_words_ru(right)
            return f"{left_words} делить на {right_words}"
        except Exception:
            return match.group(0)

    return re.sub(r'(?<!\d)(\d+)\s*/\s*(\d+)(?!\d)', repl, text)


def replace_numbers(text: str) -> str:
    # Обычные целые числа -> слова
    def repl(match):
        value = match.group(0)
        try:
            return number_to_words_ru(value)
        except Exception:
            return value

    return re.sub(r'(?<![\d/])\d+(?![\d/])', repl, text)


def normalize_text(text: str) -> str:
    text = text.strip()
    text = " ".join(text.split())
    text = replace_fractions(text)
    text = replace_numbers(text)
    return text


def normalize_speaker(speaker: str) -> str:
    speaker = speaker.strip().lower()
    if speaker not in SPEAKER_ALIASES:
        raise HTTPException(
            status_code=400,
            detail=f"speaker должен быть одним из: {sorted(SPEAKER_ALIASES.keys())}"
        )
    return SPEAKER_ALIASES[speaker]


def get_model():
    global _model
    if _model is None:
        with _model_init_lock:
            if _model is None:
                model, _ = silero_tts(language="ru", speaker="v5_ru")
                _model = model
    return _model


@app.get("/health")
def health():
    return {"status": "ok"}


@app.post("/tts")
def tts(req: TTSRequest):
    text = normalize_text(req.text)

    if not text:
        raise HTTPException(status_code=400, detail="text не должен быть пустым")

    if req.sample_rate not in ALLOWED_SAMPLE_RATES:
        raise HTTPException(
            status_code=400,
            detail=f"sample_rate должен быть одним из: {sorted(ALLOWED_SAMPLE_RATES)}"
        )

    speaker = normalize_speaker(req.speaker)

    try:
        model = get_model()

        with _tts_lock:
            audio = model.apply_tts(
                text=text,
                speaker=speaker,
                sample_rate=req.sample_rate,
            )

        if hasattr(audio, "detach"):
            audio = audio.detach()
        if hasattr(audio, "cpu"):
            audio = audio.cpu()
        if hasattr(audio, "numpy"):
            audio = audio.numpy()

        audio = np.asarray(audio, dtype=np.float32)

        if audio.ndim != 1 or audio.size == 0:
            raise RuntimeError(f"Некорректный аудиомассив: shape={getattr(audio, 'shape', None)}")

        wav_io = BytesIO()
        sf.write(wav_io, audio, req.sample_rate, format="WAV")
        wav_bytes = wav_io.getvalue()

        return Response(
            content=wav_bytes,
            media_type="audio/wav",
            headers={"Content-Disposition": 'inline; filename="speech.wav"'},
        )

    except HTTPException:
        raise
    except Exception as e:
        error_name = type(e).__name__
        error_text = str(e).strip() or repr(e)
        raise HTTPException(status_code=500, detail=f"TTS error [{error_name}]: {error_text}")
