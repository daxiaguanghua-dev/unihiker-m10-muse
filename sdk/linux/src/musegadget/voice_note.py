"""Bounded voice notes in the official Muse Gadget WAV attachment format."""
import base64
import io
import wave

MAX_WAV_BYTES = 160044  # Five seconds of 16 kHz mono PCM plus its WAV header.


def validate_voice_note(encoded: str) -> bytes:
    if not isinstance(encoded, str) or len(encoded) > ((MAX_WAV_BYTES + 2) // 3) * 4:
        raise ValueError("voice note must be a WAV of at most five seconds")
    try:
        raw = base64.b64decode(encoded, validate=True)
        if len(raw) > MAX_WAV_BYTES:
            raise ValueError("WAV too large")
        with wave.open(io.BytesIO(raw), "rb") as wav:
            frames = wav.getnframes()
            if (wav.getnchannels(), wav.getsampwidth(), wav.getframerate(), wav.getcomptype()) != (1, 2, 16000, "NONE"):
                raise ValueError("expected 16 kHz mono PCM16 WAV")
            if not 1 <= frames <= 80000 or len(wav.readframes(frames)) != frames * 2:
                raise ValueError("empty, truncated or overlong WAV")
    except (ValueError, EOFError, wave.Error) as exc:
        raise ValueError("invalid voice note: " + str(exc)) from exc
    return raw
