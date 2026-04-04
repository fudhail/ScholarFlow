"""Voice Service: Local STT (faster-whisper) and TTS (edge-tts)

This service handles all voice interactions for the ScholarMate avatar.
- STT: Converts user speech to text using faster-whisper (local, no API cost)
- TTS: Converts assistant responses to speech using edge-tts (free Microsoft voices)
"""

import asyncio
import logging
from pathlib import Path
from typing import Optional
import uuid
import tempfile

logger = logging.getLogger(__name__)

# Lazy imports to avoid loading heavy models on startup
_whisper_model = None
_edge_tts_available = False

def _get_whisper_model():
    """Lazy load Whisper model"""
    global _whisper_model
    if _whisper_model is None:
        try:
            from faster_whisper import WhisperModel
            logger.info("Loading faster-whisper model (base)...")
            _whisper_model = WhisperModel("base", device="cpu", compute_type="int8")
            logger.info("Whisper model loaded successfully")
        except ImportError:
            logger.warning("faster-whisper not installed. STT will not be available.")
            _whisper_model = False
        except Exception as e:
            logger.error(f"Failed to load Whisper model: {e}")
            _whisper_model = False
    return _whisper_model if _whisper_model else None


class VoiceService:
    """Handles voice input/output for the avatar"""
    
    def __init__(self):
        self.temp_dir = Path(tempfile.gettempdir()) / "scholarmate_voice"
        self.temp_dir.mkdir(parents=True, exist_ok=True)
        
        # Default voice - Microsoft neural voice
        self.tts_voice = "en-US-ChristopherNeural"  # Male academic voice
        # Alternatives:
        # "en-US-JennyNeural" - Female
        # "en-GB-RyanNeural" - British male
        # "en-AU-WilliamNeural" - Australian male
    
    async def transcribe(self, audio_path: Path) -> Optional[str]:
        """
        Transcribe audio file to text using faster-whisper
        
        Args:
            audio_path: Path to audio file (WAV, MP3, etc.)
            
        Returns:
            Transcribed text or None if failed
        """
        model = _get_whisper_model()
        if model is None:
            logger.error("Whisper model not available")
            return None
        
        try:
            logger.info(f"Transcribing audio: {audio_path}")
            
            # Run transcription in thread pool (Whisper is sync)
            loop = asyncio.get_event_loop()
            segments, info = await loop.run_in_executor(
                None,
                lambda: model.transcribe(str(audio_path), beam_size=5)
            )
            
            # Combine all segments
            text = " ".join([segment.text.strip() for segment in segments])
            logger.info(f"Transcription complete: {len(text)} chars")
            
            return text
            
        except Exception as e:
            logger.error(f"Transcription failed: {e}")
            return None
    
    async def synthesize(self, text: str, voice: Optional[str] = None) -> Optional[Path]:
        """
        Convert text to speech using edge-tts
        
        Args:
            text: Text to convert to speech
            voice: Voice name (optional, uses default if not specified)
            
        Returns:
            Path to generated audio file or None if failed
        """
        try:
            import edge_tts
        except ImportError:
            logger.error("edge-tts not installed. Run: pip install edge-tts")
            return None
        
        voice = voice or self.tts_voice
        output_path = self.temp_dir / f"tts_{uuid.uuid4().hex[:8]}.mp3"
        
        try:
            logger.info(f"Synthesizing speech: {len(text)} chars with voice {voice}")
            
            communicate = edge_tts.Communicate(text, voice)
            await communicate.save(str(output_path))
            
            logger.info(f"Speech saved to: {output_path}")
            return output_path
            
        except Exception as e:
            logger.error(f"Speech synthesis failed: {e}")
            return None
    
    async def synthesize_streaming(self, text: str, voice: Optional[str] = None):
        """
        Stream audio chunks as they're generated (for low-latency playback)
        
        Args:
            text: Text to convert to speech
            voice: Voice name
            
        Yields:
            Audio data chunks (bytes)
        """
        try:
            import edge_tts
        except ImportError:
            logger.error("edge-tts not installed")
            return
        
        voice = voice or self.tts_voice
        communicate = edge_tts.Communicate(text, voice)
        
        async for chunk in communicate.stream():
            if chunk["type"] == "audio":
                yield chunk["data"]
    
    def cleanup_temp_files(self, max_age_seconds: int = 3600):
        """Remove old temporary audio files"""
        import time
        now = time.time()
        
        for file in self.temp_dir.glob("*.mp3"):
            if now - file.stat().st_mtime > max_age_seconds:
                try:
                    file.unlink()
                except Exception:
                    pass
    
    @staticmethod
    async def list_available_voices() -> list:
        """Get list of available TTS voices"""
        try:
            import edge_tts
            voices = await edge_tts.list_voices()
            return [
                {"name": v["Name"], "locale": v["Locale"], "gender": v["Gender"]}
                for v in voices
                if v["Locale"].startswith("en-")  # English voices only
            ]
        except Exception as e:
            logger.error(f"Failed to list voices: {e}")
            return []


# Singleton instance
voice_service = VoiceService()
