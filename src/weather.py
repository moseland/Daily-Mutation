"""
Weather Module
Fetches weather forecasts from the Open-Meteo API and generates a 
conversational weather report using LLM personalities.
"""
import logging
import requests
import litellm
import re

logger = logging.getLogger(__name__)

def clean_llm_output(text):
    """
    Strips LLM intros and metadata from weather scripts.
    """
    if not text:
        return ""
    text = re.sub(r'^(Final|Polished|Refined|Script|Here|Sure|The).*?:\s*', '', text, flags=re.IGNORECASE | re.MULTILINE)
    text = text.replace("**", "").replace("*", "").replace("__", "")
    return text.strip()

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
        
    city = config.get("weather", {}).get("city", "your area")
    state = config.get("weather", {}).get("state", "")
    
    today = weather_data['today']
    upcoming_data = weather_data['upcoming']
    
    upcoming_str = ""
    for day in upcoming_data:
        upcoming_str += f"- Date: {day['date']}, Conditions: {day['description']}, High: {day['max_temp']}F\n"
        
    system_instruction = (
        "You are 'Olivia', the upbeat, bubbly, and high-energy weather reporter for 'The Morning Mutation'. "
        "You are known for your sunny disposition even when the forecast is gloomy. Use fun adjectives! "
        "MANDATORY OPENING: You MUST start with 'Thanks Igor!' "
        "MANDATORY CLOSING: You MUST end with 'Back to you Igor.' "
        f"TIMEZONE ADVISORY: The server clock says {current_date}. If it is early Sunday UTC, it is still SATURDAY for the audience. "
        "Output ONLY the spoken words. No sound effects or directions."
    )

    user_prompt = f"""
    Write a fun, personality-filled weather report for {city}, {state}.
    
    DATA:
    Today's Forecast: {today['description']}, High {today['max_temp']}F, Low {today['min_temp']}F.
    Next Two Days:
    {upcoming_str}
    
    RULES:
    1. 3-DAY OUTLOOK: You must explicitly cover today's weather AND the weather for the next two dates provided. 
    2. CHRONOLOGY: Use the dates to name the days correctly. If today is Saturday, tomorrow is Sunday, and the day after is Monday.
    3. PERSONALITY: Be bubbly! Use phrases like 'grab your umbrellas' or 'soak up that vitamin D'.
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
        
        proof_system = (
            "You are a script editor. Ensure Olivia sounds bubbly and energetic. "
            "Check that she opens with 'Thanks Igor!' and ends with 'Back to you Igor.' "
            "Verify that she covers all three days of data provided."
        )
        
        proof_response = litellm.completion(
            model=proofreader_model,
            messages=[
                {"role": "system", "content": proof_system},
                {"role": "user", "content": weather_script}
            ]
        )
        
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