"""
Weather Module
Fetches weather forecasts from the Open-Meteo API and generates a 
conversational weather report using LLM personalities.
"""
import logging
import requests
import litellm

logger = logging.getLogger(__name__)

def get_weather(latitude, longitude):
    """
    Fetches the daily weather forecast from Open-Meteo API.
    Updated to return Fahrenheit and 3 days of data.
    """
    # Added temperature_unit=fahrenheit and increased forecast_days to 3
    url = f"https://api.open-meteo.com/v1/forecast?latitude={latitude}&longitude={longitude}&daily=temperature_2m_max,temperature_2m_min,weathercode&temperature_unit=fahrenheit&timezone=auto&forecast_days=3"
    
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

        # Parse current day + upcoming days
        forecasts = []
        for i in range(len(daily['time'])):
            wcode = daily['weathercode'][i]
            forecasts.append({
                "date": daily['time'][i],
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
    Generates a conversational weather script using the LLM.
    Updated to include the 'Later this week' outlook in Fahrenheit.
    """
    if not weather_data:
        return "And looking at the weather... well, my sensors are down, so just stick your head out the window and figure it out!"
        
    from src.summarizer import get_model_name
    model = get_model_name(config, key='scriptwriter_model')
        
    city = config.get("weather", {}).get("city", "your area")
    state = config.get("weather", {}).get("state", "")
    
    today = weather_data['today']
    upcoming_str = "\n".join([f"- {day['date']}: {day['description']}, High {day['max_temp']}F" for day in weather_data['upcoming']])
        
    prompt = f"""
    You are 'Olivia', the upbeat, energetic weather reporter on 'The Morning Mutation'. 
    Today's date is {current_date if current_date else 'unknown'}.
    Write a short and fun weather update for {city}, {state}.
    
    Current Forecast (Today, {today['date']}): {today['description']} with a high of {today['max_temp']}F and a low of {today['min_temp']}F.
    
    Upcoming Outlook:
    {upcoming_str}
    
    INSTRUCTIONS:
    1. Focus heavily on today's weather.
    2. Briefly mention what to expect later this week (the upcoming outlook provided).
    3. Use ONLY Fahrenheit.
    4. Do not include sound effect cues, stage directions, or markdown. Output only the spoken words.
    5. End with "And back to you Igor."
    """
    
    try:
        response = litellm.completion(
            model=model,
            messages=[{"role": "user", "content": prompt}]
        )
        weather_script = response.choices[0].message.content.strip()
        
        # Pass 2: Proofreader to fix repetitions and AI quirks
        proofreader_model = get_model_name(config, key='proofreader_model')
        proof_prompt = f"""
        You are a weather script editor. The following is a raw weather report for 'The Morning Mutation'. 
        Your job is to fix any weird AI-isms, awkward repetitions, or trailing sentences.
        Make it sound natural, upbeat, and punchy. Keep it in Fahrenheit.
        
        CRITICAL: Output ONLY the spoken words. Do not include introductory text, markdown formatting, or labels like "Final Polished Script".
        End with exactly: "And back to you Igor."
        
        Raw Script:
        {weather_script}
        
        Final Polished Script:
        """
        
        proof_response = litellm.completion(
            model=proofreader_model,
            messages=[{"role": "user", "content": proof_prompt}]
        )
        content = proof_response.choices[0].message.content.strip()
        
        # Cleanup: sometimes LLMs include the label despite instructions
        if "Final Polished Script:" in content:
            content = content.split("Final Polished Script:")[-1].strip()
            
        return content
    except Exception as e:
        logger.error(f"Failed to generate weather script: {e}")
        return f"And for the weather in {city}: expect {today['description']} with a high of {today['max_temp']} degrees Fahrenheit. And back to you Igor."

def get_weather_broadcast(config, current_date=None):
    """
    Orchestrates fetching weather data and generating a conversational script.
    
    Returns:
        tuple: (script_text, raw_weather_data)
    """
    lat = config.get('weather', {}).get('latitude', 40.7128)
    lon = config.get('weather', {}).get('longitude', -74.0060)
    
    logger.info(f"Fetching weather for lat: {lat}, lon: {lon}")
    data = get_weather(lat, lon)
    if data:
        data['city'] = config.get('weather', {}).get('city', '')
        data['state'] = config.get('weather', {}).get('state', '')
    return generate_weather_script(data, config, current_date=current_date), data