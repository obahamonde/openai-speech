import os
import typing as tp
import tempfile
import random

import torch
from openai.types.audio.speech_create_params import SpeechCreateParams
from TTS.api import TTS  # type: ignore
from .lib import ttl_cache, get_device
from .lib import get_logger, GenerativeProtocol, GenerationResponse, handle

MODEL_NAME = "tts_models/multilingual/multi-dataset/xtts_v2"
CHUNK_SIZE = 1024
logger = get_logger(__name__)


@ttl_cache()
def load_tts() -> TTS:
    return TTS(model_name=MODEL_NAME).to(torch.device("cuda:1"))  # type: ignore


tts = load_tts()


class SpeechGenerationService(GenerativeProtocol[SpeechCreateParams, bytes]):
    @handle
    def generate(
        self, *, params: SpeechCreateParams
    ) -> tp.Union[GenerationResponse[bytes], tp.Iterator[bytes]]:
        response_format = params.get("response_format") or "wav"
        if response_format == "opus":
            response_format = "ogg"
        speaker_wav = (
            f"/workspace/assets/voices/{params['voice']}/{random.randint(0,9)}.mp3"
        )
        with tempfile.NamedTemporaryFile(
            delete=False, suffix=f".{response_format}", mode="wb"
        ) as audio_buffer:
            tts.tts_to_file(  # type: ignore
                text=params["input"],
                language=params.get("language") or "es",
                file_path=audio_buffer.name,
                speed=params.get("speed") or 1,
                emotion=params.get("emotion") or "neutral",
                split_sentences=True,
                speaker_wav=speaker_wav,
            )
            try:
                with open(audio_buffer.name, "rb") as audio_file:
                    while chunk := audio_file.read(CHUNK_SIZE):
                        yield chunk
            except Exception as e:
                logger.error(f"Error streaming audio: {str(e)}")
                raise
            finally:
                try:
                    os.unlink(audio_buffer.name)
                    audio_buffer.close()
                except Exception as e:
                    logger.error(f"Error cleaning up temporary file: {str(e)}")
