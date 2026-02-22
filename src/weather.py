"""
Weather Module
Fetches weather forecasts from the Open-Meteo API and generates a 
conversational weather report using LLM personalities.
"""
import logging
import requests
import litellm
import re
import datetime

logger = logging.getLogger(__name__)

def clean_llm_output(text):
    """
    Strips LLM intros, metadata, labels, and markdown from weather scripts.
    Uses XML tag extraction for bulletproof chatter removal.
    """
    if not text:
        return ""
    
    # BULLETPROOF EXTRACTION: Look for content strictly inside <script> tags
    match = re.search(r'<script>(.*?)</script>', text, re.IGNORECASE | re.DOTALL)
    if match:
        text = match.group(1)
    else:
        # Fallback regex if the LLM forgets the tags
        text = re.sub(r'^(Final|Polished|Refined|Script|Report|Here|Sure|The|Based|Correction|Optimized|Rules).*?:\s*', '', text, flags=re.IGNORECASE | re.MULTILINE)
    
    # Remove markdown formatting (bold, italics) which TTS might try to interpret literally
    text = text.replace("**", "").replace("*", "").replace("__", "")
    
    # Final trim to remove whitespace or accidental trailing quotes
    return text.strip().strip('"').strip("'")

def get_weather(latitude, longitude):
    """
    Fetches the daily weather forecast from Open-Meteo API.
    Returns Fahrenheit and 3 days of data.
    """
    url = (
        f"https://api.open-meteo.com/v1/forecast?latitude={latitude}&longitude={longitude}"
        f"&daily=temperature_2m_max,temperature_2m_min,weathercode&temperature_unit=fahrenheit"
        f"&timezone=auto&forecast_days=3"
    )
    
    try:
        response = requests.get(url, timeout=10)
        response.raise_for_status()
        data = response.json()
        
        daily = data.get('daily', {})
        if not daily or 'temperature_2m_max' not in daily:
            return None
            
        weather_descriptions = {
            0: "Clear sky", 1: "Mainly clear", 2: "Partly cloudy", 3: "Overcast",
            45: "Fog", 48: "Depositing rime fog",
            51: "Light drizzle", 53: "Moderate drizzle", 55: "Dense drizzle",
            61: "Slight rain", 63: "Moderate rain", 65: "Heavy rain",
            71: "Slight snow fall", 73: "Moderate snow fall", 75: "Heavy snow fall",
            95: "Thunderstorm"
        }

        forecasts = []
        for i in range(len(daily['time'])):
            wcode = daily['weathercode'][i]
            forecasts.append({
                "date": daily['time'][i], # Format: YYYY-MM-DD
                "max_temp": daily['temperature_2m_max'][i],
                "min_temp": daily['temperature_2m_min'][i],
                "description": weather_descriptions.get(wcode, "Variable conditions")
            })
        
        return {
            "today": forecasts[0],
            "upcoming": forecasts[1:]
        }
    except Exception as e:
        logger.error(f"Failed to fetch weather: {e}")
        return None

def generate_weather_script(weather_data, config=None, current_date=None):
    """
    Generates Olivia's upbeat weather report with personality and a 3-day outlook.
    """
    if not weather_data:
        return "Thanks Igor! Well, my weather satellite is currently being chased by space debris, so just look outside! Back to you Igor."
        
    from src.summarizer import get_model_name
    model = get_model_name(config, key='scriptwriter_model')
    proofreader_model = get_model_name(config, key='proofreader_model')
        
    # Automatically compute the exact localized date in US Eastern Time
    try:
        import zoneinfo
        tz = zoneinfo.ZoneInfo("America/New_York")
    except Exception:
        # Fallback for older python versions
        tz = datetime.timezone(datetime.timedelta(hours=-5))
        
    localized_date = datetime.datetime.now(tz).strftime("%A, %B %d, %Y")

    city = config.get("weather", {}).get("city", "your area")
    state = config.get("weather", {}).get("state", "")
    
    today = weather_data['today']
    upcoming_data = weather_data['upcoming']
    
    upcoming_str = ""
    for day in upcoming_data:
        upcoming_str += f"- Date: {day['date']}, Conditions: {day['description']}, High: {day['max_temp']}F\n"
        
    system_instruction = (
        "You are 'Olivia', the upbeat, and high-energy weather reporter for 'The Morning Mutation'. "
        "You are known for your sunny disposition even when the forecast is gloomy. Use fun adjectives! "
        "MANDATORY OPENING: You MUST start with 'Thanks Igor!' "
        "MANDATORY CLOSING: You MUST end with 'Back to you Igor.' "
        f"CRITICAL CALENDAR GUARD: Today's exact date is {localized_date}. "
        "Output ONLY the spoken words. No sound effects, labels, or directions."
    )

    user_prompt = f"""
    Write a fun, personality-filled weather report for {city}, {state}.
    
    DATA:
    Today ({localized_date}): {today['description']}, High {today['max_temp']}F, Low {today['min_temp']}F.
    Next Two Days:
    {upcoming_str}
    
    RULES:
    1. 3-DAY OUTLOOK: Explicitly cover today's weather AND the next two dates.
    2. CHRONOLOGY: Use {localized_date} to correctly name tomorrow and the day after.
    3. PERSONALITY: Be bubbly!
    4. NO INTRO: Start immediately with 'Thanks Igor!'.
    5. Back to you Igor: End exactly with that phrase.
    """
    
    try:
        response = litellm.completion(
            model=model,
            messages=[
                {"role": "system", "content": system_instruction},
                {"role": "user", "content": user_prompt}
            ]
        )
        weather_script = response.choices[0].message.content.strip()
        
        # Pass 2: The Proofreader - Strict constraints with XML requirement
        proof_system = (
            "You are a technical script formatter for a broadcast. Your job is to clean text for Text-To-Speech (TTS). "
            f"CALENDAR ADVISORY: Today is strictly {localized_date}. Verify that the spoken day of the week matches this exactly.\n"
            "CRITICAL: Output ONLY the spoken weather report. "
            "NEVER include introductory remarks. "
            "ENSURE the script starts with 'Thanks Igor!' and ends with 'Back to you Igor.'\n"
            "MANDATORY: You MUST wrap the entire spoken output inside <script> and </script> XML tags."
        )
        
        proof_response = litellm.completion(
            model=proofreader_model,
            messages=[
                {"role": "system", "content": proof_system},
                {"role": "user", "content": f"Please clean and optimize this weather script for TTS. Fix any incorrect days of the week based on {localized_date}. Wrap the final script in <script> tags.\n\nRaw Script:\n{weather_script}"}
            ]
        )
        
        # Apply the hardened XML cleaning utility to the result
        return clean_llm_output(proof_response.choices[0].message.content)
        
    except Exception as e:
        logger.error(f"Failed to generate weather script: {e}")
        return f"Thanks Igor! Today in {city} expect {today['description']} with a high of {today['max_temp']}. Back to you Igor."

def get_weather_broadcast(config, current_date=None):
    lat = config.get('weather', {}).get('latitude', 40.7128)
    lon = config.get('weather', {}).get('longitude', -74.0060)
    
    data = get_weather(lat, lon)
    if data:
        data['city'] = config.get('weather', {}).get('city', '')
        data['state'] = config.get('weather', {}).get('state', '')
    return generate_weather_script(data, config, current_date=current_date), data