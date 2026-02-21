"""
TTS Module
Generates high-quality speech audio using the Inworld AI API. 
Handles text splitting for long segments and applies natural pauses.
"""
import os
import logging
import requests
import base64
import tempfile
from pydub import AudioSegment

logger = logging.getLogger(__name__)

def split_text(text, max_length=1900):
    """Splits long text into chunks that fit within Inworld's character limits."""
    sentences = text.replace('\n', ' ').split('. ')
    chunks = []
    current_chunk = ""
    for sentence in sentences:
        if len(current_chunk) + len(sentence) + 2 <= max_length:
            current_chunk += sentence + ". "
        else:
            if current_chunk:
                chunks.append(current_chunk.strip())
            current_chunk = sentence + ". "
    if current_chunk:
        chunks.append(current_chunk.strip())
    return chunks

def generate_audio(text, output_path, config=None, voice_override=None):
    """
    Generates TTS audio using the Inworld API and saves it to output_path.
    Requires INWORLD_API_KEY in the environment.
    """
    api_key = os.getenv("INWORLD_API_KEY")
    
    if not api_key:
        logger.error("Missing INWORLD_API_KEY in environment. Cannot generate TTS.")
        return False
        
    character_name = voice_override or config.get("tts", {}).get("character_name", "carter")
    logger.info(f"Generating TTS via Inworld for character: {character_name}")
    model = config.get("tts", {}).get("model", "inworld-tts-1.5-mini") if config else "inworld-tts-1.5-mini"

    url = "https://api.inworld.ai/tts/v1/voice"
    
    headers = {
        "Authorization": f"Basic {api_key}" if " " not in api_key else api_key, # Supports basic or Bearer
        "Content-Type": "application/json"
    }
    
    valid_segments = [s for s in text.split('[PAUSE]') if s.strip()]
    combined_audio = AudioSegment.empty()
    silence = AudioSegment.silent(duration=1500)
    
    for s_idx, segment in enumerate(valid_segments):
        chunks = split_text(segment, 1900)
        segment_audio = AudioSegment.empty()
        
        for i, chunk in enumerate(chunks):
            if not chunk: continue
            
            payload = {
                "text": chunk,
                "voiceId": character_name,
                "modelId": model,
                "timestampType": "WORD"
            }
            
            try:
                response = requests.post(url, json=payload, headers=headers, timeout=30)
                response.raise_for_status()
                
                result = response.json()
                audio_content = base64.b64decode(result['audioContent'])
                
                with tempfile.NamedTemporaryFile(delete=False, suffix=".mp3") as tmp:
                    tmp.write(audio_content)
                    tmp_path = tmp.name
                    
                chunk_audio = AudioSegment.from_file(tmp_path)
                segment_audio += chunk_audio
                os.remove(tmp_path)
                logger.info(f"Generated text chunk {i+1}/{len(chunks)} for segment {s_idx+1}/{len(valid_segments)}")
                
            except Exception as e:
                logger.error(f"Inworld TTS chunk {i+1} failed: {e}")
                if hasattr(e, 'response') and e.response:
                    logger.error(f"Response: {e.response.text}")
                return False
                
        combined_audio += segment_audio
        if s_idx < len(valid_segments) - 1:
            combined_audio += silence
            
    try:
        combined_audio.export(output_path, format="mp3", bitrate="192k")
        logger.info(f"Successfully saved audio to {output_path}")
        return True
    except Exception as e:
        logger.error(f"Failed to export combined audio to {output_path}: {e}")
        return False
