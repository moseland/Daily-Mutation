"""
Summarizer Module
Uses LLMs (via LiteLLM) to synthesize multi-source news clusters into cohesive 
summaries and generate a persona-driven broadcast script.
"""
import logging
import litellm
import os
import re
import datetime

logger = logging.getLogger(__name__)

def clean_llm_output(text):
    """
    Strips LLM intros, metadata, labels, and markdown from scripts.
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
    
    # Final trim to remove whitespace
    return text.strip().strip('"').strip("'")

def get_model_name(config=None, key='model'):
    """
    Parses model path from config or defaults to Gemini 3 Flash.
    """
    if config and 'llm' in config:
        llm_cfg = config['llm']
        model = llm_cfg.get(key, llm_cfg.get('model', 'google/gemini-3-flash-preview'))
        return f"{llm_cfg.get('provider', 'openrouter')}/{model}"
    return "openrouter/google/gemini-3-flash-preview"

def summarize_clusters(clusters, config=None):
    """
    Summarizes clusters. If a cluster contains multiple articles from different sources,
    it synthesizes them into one comprehensive summary.
    """
    model = get_model_name(config, key='summarizer_model')
    summaries = []
    
    if not clusters:
        return summaries

    for i, cluster_info in enumerate(clusters):
        feed_name = cluster_info.get("feed_name", "General News")
        articles = cluster_info.get("articles", [])
        
        text_payload = ""
        for idx, article in enumerate(articles):
            source_label = article.get('feed_name', f'Source {idx+1}')
            text_payload += f"--- SOURCE: {source_label} ---\n"
            text_payload += f"TITLE: {article.get('title')}\n"
            text_payload += f"CONTENT: {article.get('text', '')[:3000]}\n\n"

        system_instruction = (
            "You are an expert news editor and filter. Your task is to synthesize multiple articles "
            "into one cohesive, objective, and engaging summary. \n\n"
            "CRITICAL QUALITY FILTER: \n"
            "- IDENTIFY AND DISCARD 'Fluff': shopping deals, sales, gift guides, product 'best-of' lists, "
            "coupons, or clickbait listicles. If the provided sources are fluff, respond ONLY with 'DISCARD'.\n"
            "- CATEGORIZATION: Be precise. Use 'Entertainment' for movies/games, 'Tech' for hardware/software, "
            "and 'World' ONLY for global geopolitical events or major non-aligned international news."
        )

        user_prompt = f"""
        Analyze and synthesize the following sources. 
        
        STRICT CATEGORY LIST: Tech, World, Political, Entertainment, Sports.
        
        If the content is a shopping deal or fluff, output: DISCARD
        Otherwise, use this format:
        CATEGORIES: [List]
        SUMMARY:
        [Your Synthesized Summary]
        
        Sources:
        {text_payload}
        """
        
        try:
            response = litellm.completion(
                model=model,
                messages=[
                    {"role": "system", "content": system_instruction},
                    {"role": "user", "content": user_prompt}
                ]
            )
            response_text = response.choices[0].message.content.strip()
            
            # Skip discarded fluff
            if "DISCARD" in response_text.upper() and len(response_text) < 20:
                logger.info(f"Discarding cluster {i+1} as shopping fluff.")
                continue

            categories = ["World"]
            summary_text = response_text
            
            if "CATEGORIES:" in response_text and "SUMMARY:" in response_text:
                parts = response_text.split("SUMMARY:")
                cat_part = parts[0].replace("CATEGORIES:", "").strip()
                if cat_part:
                    valid_cats = ["Tech", "World", "Political", "Entertainment", "Sports"]
                    categories = [c.strip().strip('*').strip() for c in cat_part.split(",")]
                    categories = [c for c in categories if c in valid_cats]
                    if not categories:
                        categories = ["World"]
                summary_text = parts[1].strip()
            
            # Extract ALL unique article links for UI
            article_links = []
            seen_urls = set()
            for a in articles:
                url = a.get("url")
                if url and url not in seen_urls:
                    article_links.append({"title": a.get("title", ""), "url": url})
                    seen_urls.add(url)
            
            summaries.append({
                "categories": categories,
                "summary": summary_text,
                "articles": article_links
            })
            
        except Exception as e:
            logger.error(f"Failed to summarize cluster {i}: {e}")
            
    return summaries

def generate_broadcast_script(summaries, config=None, current_date=None):
    """
    Generates a cohesive script with markers for pauses and weather.
    Uses a two-pass system: 1. Creative Writing, 2. TTS Optimization.
    """
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
    
    if not summaries:
        return "Hey folks, EE-gore here! We didn't find any breaking news today, so go back to sleep. Just kidding, have a great day!"
        
    logger.info("Generating final broadcast script...")
    joined_summaries = "\n---\n".join([f"CATEGORIES: {', '.join(s['categories'])}\nSUMMARY:\n{s['summary']}" for s in summaries])
    
    writer_system = (
        f"You are 'Igor', the host of 'The Morning Mutation'. \n"
        f"CRITICAL CALENDAR GUARD: Today's date is strictly {localized_date}. Use this exact day of the week in your greetings.\n"
        f"PERSONA: You are an old-school, high-energy radio host AI. Think Howard Stern mixed with an upbeat, witty, and slightly subversive edge. "
        "You are opinionated, charismatic, and love highlighting the weirdness of the news in a fun way. "
        "Avoid being overly dark, cynical, or 'doomsday'—keep the energy high and the vibes positive. "
        "You are NOT a corporate news anchor. \n"
        "Output ONLY spoken words and markers ([PAUSE], [WEATHER_BREAK]). No markdown, no directions."
    )
    
    writer_prompt = f"""
    Write a continuous broadcast script. Give Igor his edge back!
    
    STRUCTURE:
    1. THE HOOK: A witty, snarky intro acknowledging today is {localized_date}.
    2. NEWS BLOCK A: The first half of summaries. 
    3. THE HAND-OFF: A funny transition to Olivia for the weather. 
    4. Marker: [WEATHER_BREAK] (Output this ONLY ONCE).
    5. NEWS BLOCK B: The second half of summaries.
    6. THE SIGN-OFF: A final witty remark or radio sign-off.
    
    INSTRUCTIONS:
    - CATEGORY TRANSITIONS: You MUST explicitly announce the category you are transitioning into using natural radio-host phrases. (e.g., 'And next in World news...', 'Moving over to the Tech world...', 'Let's see what's happening in Entertainment...'). Do not just start reading the news without announcing the section.
    - JOKES: Insert a quick joke or snarky comment about the news items.
    - Output [PAUSE] on its own line after every category segment.
    - Do NOT say goodbye before the [WEATHER_BREAK].
    
    Summaries:
    {joined_summaries}
    """
    
    try:
        draft_response = litellm.completion(
            model=model,
            messages=[
                {"role": "system", "content": writer_system},
                {"role": "user", "content": writer_prompt}
            ]
        )
        draft_script = draft_response.choices[0].message.content.strip()
        
        proof_system = (
            "You are a TTS editor. Your job is to make the script sound human and protect Igor's unique persona. \n"
            f"CALENDAR ADVISORY: Today is strictly {localized_date}. Verify that the spoken day of the week matches this exactly.\n"
            "MANDATORY: You MUST wrap the entire spoken output inside <script> and </script> XML tags."
        )
        
        proof_prompt = f"""
        Optimize this script for TTS.
        
        CRITICAL RULES:
        1. PRESERVE PERSONALITY: Keep the high-energy, witty edge and the jokes.
        2. CALENDAR CHECK: Today is {localized_date}. Fix any greetings that state the wrong day of the week.
        3. NO REPETITION: Ensure the second half doesn't repeat news from the first.
        4. JOKE CONTEXT: Any jokes MUST strictly relate to the news items actually included in the spoken script. NEVER make an 'off-script' joke about an article that was only in the source list.
        5. PHONETIC: Use 'EE-gore' for Igor and 'en-VID-ee-uh' for NVIDIA. 
        6. MARKERS: Keep [PAUSE] and [WEATHER_BREAK] on their own lines.
        6. XML WRAPPING: You MUST wrap the final spoken script inside <script> and </script> tags. Do not put meta-commentary outside the tags.
        
        Raw Script:
        {draft_script}
        """
        
        final_response = litellm.completion(
            model=proofreader_model,
            messages=[
                {"role": "system", "content": proof_system},
                {"role": "user", "content": proof_prompt}
            ]
        )
        
        return clean_llm_output(final_response.choices[0].message.content)
    except Exception as e:
        logger.error(f"Failed to generate broadcast script: {e}")
        return "Warning: Failed to generate broadcast script due to an error."