"""
Morning Mutation - Main Orchestrator
This script coordinates the entire pipeline: scraping, clustering, 
summarization, TTS generation, and audio mixing.
"""
import os
import yaml
import logging
import json
import datetime
from dotenv import load_dotenv

from src.scraper import fetch_and_scrape_all
from src.cluster import cluster_articles
from src.summarizer import summarize_clusters, generate_broadcast_script
from src.weather import get_weather_broadcast
from src.tts import generate_audio
from src.audio_mixer import mix_broadcast_audio

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

def load_config(config_path="config.yaml"):
    """Loads configuration from YAML file."""
    try:
        with open(config_path, "r") as f:
            return yaml.safe_load(f)
    except Exception as e:
        logger.error(f"Failed to load config file: {e}")
        return {}

def run_pipeline():
    """
    Executes the full Morning Mutation pipeline.
    1. Scrapes news from RSS sources.
    2. Clusters similar stories across all feeds.
    3. Synthesizes summaries and generates a witty script.
    4. Fetches and drafts weather for the specific location.
    5. Generates high-quality TTS audio via Inworld.
    6. Mixes audio segments into a final MP3 broadcast.
    7. Exports metadata for the web dashboard.
    """
    logger.info("Starting The Morning Mutation with IGOR pipeline...")
    
    # Load environment and config
    load_dotenv()
    config = load_config()
    
    # 1. Scrape Articles
    news_sources = config.get('news_sources', [])
    logger.info("Fetching articles from sources...")
    articles = fetch_and_scrape_all(news_sources, config, max_age_hours=24)
    
    if not articles:
        logger.warning("No articles found in the last 24 hours!")
    else:
        logger.info(f"Found {len(articles)} articles!")
        
    # 2. Cluster Articles (linkage between different sources)
    clusters = cluster_articles(articles, similarity_threshold=0.3)
    
    # 3. Summarize and Generate Script
    summaries = summarize_clusters(clusters, config)
    current_date_str = datetime.datetime.now().strftime("%A, %B %d, %Y")
    news_script = generate_broadcast_script(summaries, config, current_date=current_date_str)
    
    # 4. Generate Weather Script
    weather_script, weather_data = get_weather_broadcast(config, current_date=current_date_str)
    
    # 5. Prepare Output Directory
    output_dir = "output"
    os.makedirs(output_dir, exist_ok=True)
    
    # Handle weather transition break
    news_parts = news_script.split('[WEATHER_BREAK]')
    news_script_part1 = news_parts[0]
    news_script_part2 = news_parts[1] if len(news_parts) > 1 else ""
    
    news_audio_path_1 = os.path.join(output_dir, "news_1.mp3")
    news_audio_path_2 = os.path.join(output_dir, "news_2.mp3")
    
    # 6. Generate TTS Audio
    news_success_1 = generate_audio(news_script_part1, news_audio_path_1, config)
    
    news_success_2 = True
    if news_script_part2.strip():
        news_success_2 = generate_audio(news_script_part2, news_audio_path_2, config)
    
    weather_audio_path = os.path.join(output_dir, "weather.mp3")
    weather_voice = config.get("tts", {}).get("weather_character_name", "Olivia")
    weather_success = generate_audio(weather_script, weather_audio_path, config, voice_override=weather_voice)
    
    if not news_success_1 or not news_success_2 or not weather_success:
        logger.error("Failed to generate necessary TTS audio. Pipeline aborted.")
        return
        
    # 7. Mix Components to Final MP3
    intro_audio_path = "assets/intro/intro.mp3"
    commercials_dir = "assets/commercials"
    final_output_path = os.path.join(output_dir, "morning_mutation.mp3")
    
    mix_success = mix_broadcast_audio(
        intro_audio_path,
        news_audio_path_1,
        news_audio_path_2,
        weather_audio_path, 
        commercials_dir, 
        final_output_path
    )
    
    if mix_success:
        logger.info(f"Pipeline complete! Output saved to {final_output_path}")
        
        # 8. Export Data for Frontend
        try:
            import zoneinfo
            tz = zoneinfo.ZoneInfo("America/New_York")
        except Exception:
            tz = datetime.timezone(datetime.timedelta(hours=-5))

        broadcast_data = {
            "date": datetime.datetime.now(tz).isoformat(),
            "weather": weather_data,
            "news": summaries
        }
        
        json_output_path = os.path.join(output_dir, "broadcast_data.json")
        with open(json_output_path, "w") as f:
            json.dump(broadcast_data, f, indent=2)
        logger.info(f"Exported broadcast payload to {json_output_path}")
    else:
        logger.error("Audio mixing failed.")

if __name__ == "__main__":
    run_pipeline()
