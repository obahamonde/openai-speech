import typing as tp
from fastapi import APIRouter
from fastapi.responses import StreamingResponse
from openai.types.audio.speech_create_params import SpeechCreateParams
from .service import SpeechGenerationService
from .lib.utils import b64_id


app = APIRouter(prefix="/speech")
service = SpeechGenerationService()


@app.post("")
def create_speech(params: SpeechCreateParams):
    iterator = service.generate(params=params)
    assert isinstance(iterator, tp.Iterator)
    return StreamingResponse(
        iterator,
        media_type="audio/mpeg",
        headers={"Content-Disposition": f"inline; filename={b64_id()}.mp3"},
    )
