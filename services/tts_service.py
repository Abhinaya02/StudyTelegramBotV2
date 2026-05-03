import logging
import re
import asyncio
from io import BytesIO
import wave
from gtts import gTTS
from google import genai
from google.genai import types
from config import GEMINI_API_KEY

logger = logging.getLogger(__name__)
try:
    client = genai.Client(api_key=GEMINI_API_KEY)
except Exception:
    client = None

async def generate_tts_audio_once(text: str) -> tuple[bytes | None, str]:
    """Generates TTS using Gemini TTS Model, falls back to gTTS."""
    if not client:
        return await _fallback_gtts(text)

    for attempt in range(3):
        try:
            tts_prompt = f"As a professional news reporter, say the following fast: {text}"
            response = await client.aio.models.generate_content(
                model="gemini-2.5-flash-preview-tts",
                contents=tts_prompt,
                config=types.GenerateContentConfig(
                    response_modalities=["AUDIO"],
                    speech_config=types.SpeechConfig(
                        voice_config=types.VoiceConfig(
                            prebuilt_voice_config=types.PrebuiltVoiceConfig(voice_name="Kore")
                        )
                    )
                )
            )

            audio_bytes = b""
            mimetype = ""

            for candidate in response.candidates:
                if not candidate.content:
                    continue
                for part in candidate.content.parts:
                    inline = getattr(part, "inline_data", None)
                    if inline and getattr(inline, "data", None):
                        data_field = inline.data
                        mimetype = getattr(inline, "mimetype", mimetype)
                        audio_bytes = data_field if isinstance(data_field, bytes) else bytes(data_field)

            if audio_bytes:
                sample_rate = 24000
                if "rate" in mimetype:
                    try:
                        sample_rate = int(re.search(r"rate=(\d+)", mimetype).group(1))
                    except Exception:
                        pass

                audio_stream = BytesIO()
                if "pcm" in mimetype.lower() or not mimetype:
                    with wave.open(audio_stream, 'wb') as wav_file:
                        wav_file.setnchannels(1)
                        wav_file.setsampwidth(2)
                        wav_file.setframerate(sample_rate)
                        wav_file.writeframes(audio_bytes)
                else:
                    audio_stream.write(audio_bytes)

                return audio_stream.getvalue(), "Neural"

        except Exception as e:
            if "500" in str(e):
                await asyncio.sleep(5)
            else:
                break

    return await _fallback_gtts(text)

async def _fallback_gtts(text: str) -> tuple[bytes | None, str]:
    """Fallback to standard gTTS generator."""
    try:
        voice_text = text.replace("<b>", "").replace("</b>", "")
        # Run gTTS synchronously since it's blocking
        tts = gTTS(text=voice_text, lang='en', tld='co.in')
        buf = BytesIO()
        tts.write_to_fp(buf)
        return buf.getvalue(), "gTTS"
    except Exception as e:
        logger.error(f"Total Audio Failure: {e}")
        return None, "Failed"
