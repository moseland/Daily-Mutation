"""
Audio Mixer Module
Orchestrates the assembly of the final broadcast MP3 by splicing news segments, 
weather reports, commercials, and intro music.
"""
import os
import random
import logging
from pydub import AudioSegment

logger = logging.getLogger(__name__)

def mix_broadcast_audio(intro_audio_path, news_audio_path_1, news_audio_path_2, weather_audio_path, commercials_dir, output_path):
    """
    Takes the optional intro audio, generated news parts and weather audio, selects a random commercial,
    and splices them together into a final MP3 file using pydub.
    """
    logger.info("Starting audio mixing process...")
    
    # Load news part 1
    if not os.path.exists(news_audio_path_1):
        logger.error(f"News part 1 audio missing: {news_audio_path_1}")
        return False
        
    try:
        news_audio_1 = AudioSegment.from_file(news_audio_path_1)
    except Exception as e:
        logger.error(f"Failed to load news part 1 audio: {e}")
        return False
        
    # Load news part 2
    news_audio_2 = None
    if os.path.exists(news_audio_path_2):
        try:
            news_audio_2 = AudioSegment.from_file(news_audio_path_2)
        except Exception as e:
            logger.error(f"Failed to load news part 2 audio: {e}")

    # Load weather
    if not os.path.exists(weather_audio_path):
        logger.error(f"Weather audio missing: {weather_audio_path}")
        return False

    try:
        weather_audio = AudioSegment.from_file(weather_audio_path)
    except Exception as e:
        logger.error(f"Failed to load weather audio: {e}")
        return False
        
    # Pick a random commercial
    commercial_audio = None
    if os.path.isdir(commercials_dir):
        commercials = [f for f in os.listdir(commercials_dir) if f.endswith(('.mp3', '.wav', '.m4a'))]
        if commercials:
            chosen = random.choice(commercials)
            c_path = os.path.join(commercials_dir, chosen)
            logger.info(f"Selected commercial: {chosen}")
            try:
                commercial_audio = AudioSegment.from_file(c_path)
            except Exception as e:
                logger.error(f"Failed to load commercial {chosen}: {e}")
        else:
            logger.warning("No commercials found in assets/commercials directory.")
            
    # Mix components together with brief silence in between
    silence = AudioSegment.silent(duration=1500) # 1.5 seconds
    
    # Load intro if exists
    intro_audio = None
    if intro_audio_path and os.path.exists(intro_audio_path):
        try:
            intro_audio = AudioSegment.from_file(intro_audio_path)
            logger.info("Loaded intro audio.")
        except Exception as e:
            logger.error(f"Failed to load intro audio: {e}")

    if intro_audio:
        final_audio = intro_audio + silence + news_audio_1
    else:
        final_audio = news_audio_1
        
    final_audio = final_audio + silence
    
    # Weather
    final_audio = final_audio.append(weather_audio, crossfade=500)
    final_audio = final_audio + silence
    
    if commercial_audio:
        # Crossfade commercial
        final_audio = final_audio.append(commercial_audio, crossfade=500)
        final_audio = final_audio + silence
        
    if news_audio_2:
        final_audio = final_audio.append(news_audio_2, crossfade=500)
    
    # Export
    try:
        os.makedirs(os.path.dirname(output_path), exist_ok=True)
        final_audio.export(output_path, format="mp3", bitrate="192k")
        logger.info(f"Successfully exported final broadcast to {output_path}")
        return True
    except Exception as e:
        logger.error(f"Failed to export final audio: {e}")
        return False
