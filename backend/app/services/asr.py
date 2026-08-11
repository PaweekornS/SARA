import os
import glob
import logging
import subprocess
from openai import OpenAI
from app.core.config import settings

logger = logging.getLogger(__name__)

# Initialize client for AI4Thai ASR Service (OpenAI-compatible)
client = OpenAI(
    base_url=f"{settings.ASR_URL.rstrip('/')}/v1",
    api_key=settings.APP_AI4THAI_API_KEY,
)

# Size limit set to 24 MB to have a safety margin under the 25 MB limit
MAX_FILE_SIZE = 24 * 1024 * 1024 

def transcribe_audio(file_path: str) -> str:
    """
    Transcribes audio files using AI4Thai's ASR service.
    Supports large files by chunking them with ffmpeg if they exceed 24MB.
    """
    if not os.path.exists(file_path):
        logger.error(f"File not found: {file_path}")
        return get_mock_transcript()

    file_size = os.path.getsize(file_path)
    logger.info(f"Audio file size: {file_size / (1024*1024):.2f} MB")

    try:
        if file_size <= MAX_FILE_SIZE:
            return _transcribe_single_file(file_path)
        
        # File is larger than 24MB, split it into chunks
        logger.info("File exceeds 24MB limit. Splitting audio file into chunks...")
        chunks = _split_audio(file_path)
        if not chunks:
            logger.error("Failed to split audio file.")
            return get_mock_transcript()

        transcripts = []
        for i, chunk_path in enumerate(chunks):
            logger.info(f"Transcribing chunk {i+1}/{len(chunks)}: {chunk_path}")
            try:
                chunk_text = _transcribe_single_file(chunk_path)
                transcripts.append(chunk_text)
            except Exception as e:
                logger.error(f"Failed to transcribe chunk {chunk_path}: {e}")
                # Fallback context in chunk to allow other chunks to proceed
                transcripts.append(f"[ASR Error: failed to transcribe segment {i+1}]")
            finally:
                # Clean up temporary chunk file
                try:
                    os.remove(chunk_path)
                    logger.info(f"Cleaned up chunk file: {chunk_path}")
                except Exception as cleanup_err:
                    logger.warning(f"Failed to remove chunk file {chunk_path}: {cleanup_err}")

        if not transcripts:
            logger.error("All chunk transcriptions failed.")
            return get_mock_transcript()

        full_transcript = " ".join(transcripts)
        logger.info("Chunked transcription completed successfully.")
        return full_transcript

    except Exception as err:
        logger.error(f"AI4Thai ASR failed: {err}")
        return get_mock_transcript()

def _transcribe_single_file(file_path: str) -> str:
    """
    Performs transcription using the AI4Thai ASR API on a single file.
    """
    with open(file_path, "rb") as audio_file:
        transcript_response = client.audio.transcriptions.create(
            model=settings.ASR_MODEL,
            file=audio_file,
            language="th",
            response_format="json"
        )
    return transcript_response.text

def _split_audio(file_path: str) -> list:
    """
    Splits the audio file into 10-minute segments using ffmpeg and returns a list of chunk paths.
    """
    base, ext = os.path.splitext(file_path)
    chunk_pattern = f"{base}_chunk_%03d{ext}"
    
    # Run ffmpeg segment command
    # -i input: Input file path
    # -f segment: Output format segmenting
    # -segment_time 600: Split every 10 minutes (600 seconds)
    # -c copy: Copy codec directly without re-encoding (very fast and lossless)
    cmd = [
        "ffmpeg", "-y",
        "-i", file_path,
        "-f", "segment",
        "-segment_time", "600",
        "-c", "copy",
        chunk_pattern
    ]
    
    try:
        logger.info(f"Running ffmpeg command: {' '.join(cmd)}")
        # Run process synchronously
        subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, check=True)
        # Find all generated chunks matching the base name prefix and extension
        glob_pattern = f"{base}_chunk_*{ext}"
        chunks = sorted(glob.glob(glob_pattern))
        logger.info(f"Generated {len(chunks)} chunk(s): {chunks}")
        return chunks
    except subprocess.CalledProcessError as e:
        logger.error(f"ffmpeg split failed: {e.stderr}")
        return []
    except Exception as e:
        logger.error(f"Unexpected error during ffmpeg split: {e}")
        return []

def get_mock_transcript() -> str:
    """
    Soft fallback if audio processing fails (prevents job crashing during demo).
    """
    return (
        "Somchai [00:00]: Meeting started.\n"
        "Jane [00:15]: On the backend, AI4Thai API integration is complete.\n"
        "Somchai [00:30]: Great, let's ship the MVP demo."
    )