"""Voice API endpoints for STT and TTS"""

from fastapi import APIRouter, UploadFile, File, HTTPException, Query
from fastapi.responses import FileResponse, StreamingResponse
from pathlib import Path
import tempfile
import uuid
import logging

from app.services.voice_service import voice_service

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/v1/voice", tags=["voice"])


@router.post("/transcribe")
async def transcribe_audio(file: UploadFile = File(...)):
    """
    Convert speech to text (STT)
    
    Accepts audio file (WAV, MP3, WebM) and returns transcribed text.
    Uses faster-whisper running locally.
    """
    # Validate file type
    allowed_types = ["audio/wav", "audio/mpeg", "audio/webm", "audio/mp3", "audio/x-wav"]
    if file.content_type and file.content_type not in allowed_types:
        raise HTTPException(400, f"Unsupported file type: {file.content_type}")
    
    # Save uploaded file temporarily
    suffix = Path(file.filename).suffix if file.filename else ".wav"
    temp_path = Path(tempfile.gettempdir()) / f"upload_{uuid.uuid4().hex}{suffix}"
    
    try:
        # Write uploaded file
        content = await file.read()
        temp_path.write_bytes(content)
        
        # Transcribe
        text = await voice_service.transcribe(temp_path)
        
        if text is None:
            raise HTTPException(500, "Transcription failed")
        
        return {"text": text, "duration_hint": len(content) / 16000}  # Rough estimate
        
    finally:
        # Cleanup
        if temp_path.exists():
            temp_path.unlink()


@router.post("/synthesize")
async def synthesize_speech(
    text: str,
    voice: str = Query(default="en-US-ChristopherNeural", description="Voice name")
):
    """
    Convert text to speech (TTS)
    
    Returns MP3 audio file of the spoken text.
    Uses edge-tts with Microsoft neural voices (free).
    """
    if not text or len(text.strip()) == 0:
        raise HTTPException(400, "Text cannot be empty")
    
    if len(text) > 5000:
        raise HTTPException(400, "Text too long (max 5000 characters)")
    
    audio_path = await voice_service.synthesize(text, voice)
    
    if audio_path is None:
        raise HTTPException(500, "Speech synthesis failed")
    
    return FileResponse(
        audio_path,
        media_type="audio/mpeg",
        filename="speech.mp3",
        headers={"Content-Disposition": "inline"}  # Allow playback in browser
    )


@router.post("/synthesize/stream")
async def synthesize_speech_stream(
    text: str,
    voice: str = Query(default="en-US-ChristopherNeural")
):
    """
    Stream synthesized speech (lower latency)
    
    Streams audio chunks as they're generated for real-time playback.
    """
    if not text or len(text.strip()) == 0:
        raise HTTPException(400, "Text cannot be empty")
    
    async def audio_stream():
        async for chunk in voice_service.synthesize_streaming(text, voice):
            yield chunk
    
    return StreamingResponse(
        audio_stream(),
        media_type="audio/mpeg"
    )


@router.get("/voices")
async def list_voices():
    """
    Get available TTS voices
    
    Returns list of English neural voices available for synthesis.
    """
    voices = await voice_service.list_available_voices()
    return {"voices": voices}


@router.get("/health")
async def voice_health():
    """Check voice service health"""
    from app.services.voice_service import _get_whisper_model
    
    whisper_ok = _get_whisper_model() is not None
    
    try:
        import edge_tts
        tts_ok = True
    except ImportError:
        tts_ok = False
    
    return {
        "stt_available": whisper_ok,
        "tts_available": tts_ok,
        "model": "faster-whisper (base)" if whisper_ok else None
    }
