"""
Summarizer Module
Uses LLMs (via LiteLLM) to synthesize multi-source news clusters into cohesive 
summaries and generate a persona-driven broadcast script.
"""
import logging
import litellm
import os

logger = logging.getLogger(__name__)

def get_model_name(config=None, key='model'):
    """
    Parses model path from config or defaults to Gemini 3 Flash.
    Now supports retrieving specific models like 'summarizer_model'.
    """
    if config and 'llm' in config:
        llm_cfg = config['llm']
        # Try finding the specific model key, or fallback to the generic 'model' key
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
        
        # Build a rich payload including which source said what
        text_payload = ""
        for idx, article in enumerate(articles):
            source_label = article.get('feed_name', f'Source {idx+1}')
            text_payload += f"--- SOURCE: {source_label} ---\n"
            text_payload += f"TITLE: {article.get('title')}\n"
            text_payload += f"CONTENT: {article.get('text', '')[:3000]}\n\n"

        prompt = f"""
        You are an expert news editor. Below are multiple articles (potentially from different sources) 
        covering the SAME news event. 
        
        Your task:
        1. Synthesize all information into one cohesive, objective, and engaging summary (1-2 paragraphs).
        2. Identify 2-6 high-level key takeaways.
        3. Assign one or more CATEGORIES from this strict list: **Tech, World, Political, Entertainment, Sports**. 
           If the story fits multiple categories, list them all.
        
        Ensure the summary notes if different sources provide different details.
        
        Format your response EXACTLY like this:
        CATEGORIES: [Category1, Category2]
        SUMMARY:
        [Your Synthesized Summary]
        
        Sources to synthesize:
        {text_payload}
        """
        
        try:
            response = litellm.completion(
                model=model,
                messages=[{"role": "user", "content": prompt}]
            )
            response_text = response.choices[0].message.content.strip()
            
            categories = [feed_name]
            summary_text = response_text
            
            if "CATEGORIES:" in response_text and "SUMMARY:" in response_text:
                parts = response_text.split("SUMMARY:")
                cat_part = parts[0].replace("CATEGORIES:", "").strip()
                if cat_part:
                    # Parse comma separated categories and clean up
                    categories = [c.strip().strip('*').strip() for c in cat_part.split(",")]
                    # Ensure they are valid or default to 'General'
                    valid_cats = ["Tech", "World", "Political", "Entertainment", "Sports"]
                    categories = [c for c in categories if c in valid_cats]
                    if not categories:
                        categories = ["World"] # Fallback
                summary_text = parts[1].strip()
            
            # Extract ALL unique article links for the UI to display multiple sources
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
            logger.info(f"Synthesized cluster {i+1}/{len(clusters)} with {len(articles)} sources.")
            
        except Exception as e:
            logger.error(f"Failed to summarize cluster {i}: {e}")
            summaries.append({
                "feed_name": feed_name,
                "summary": "Error synthesizing these sources.",
                "articles": []
            })
            
    return summaries

def generate_broadcast_script(summaries, config=None, current_date=None):
    """
    Takes the summarized topics and generates a cohesive broadcast script.
    Includes a two-pass system to optimize for TTS pronunciation.
    """
    model = get_model_name(config, key='scriptwriter_model')
    proofreader_model = get_model_name(config, key='proofreader_model')
    
    if not summaries:
        return "Hey folks, IGOR here! We didn't find any breaking news for today's broadcast, so go back to sleep. Just kidding, have a great day!"
        
    logger.info("Generating final broadcast script...")
    joined_summaries = "\n---\n".join([f"CATEGORIES: {', '.join(s['categories'])}\nSUMMARY:\n{s['summary']}" for s in summaries])
    
    prompt = f"""
    You are 'Igor', the AI host of a daily morning news broadcast called 'The Morning Mutation with Igor'.
    Today's date is {current_date if current_date else 'unknown'}.
    Using the following news summaries (which are grouped by category), write a cohesive, punchy, funny, and witty broadcast script.

    CRITICAL INSTRUCTIONS:
    1. Organize the broadcast into thematic segments based on the categories provided (e.g., AI, World News, Tech).
    2. Introduce each topic segment conversationally (for example: 'And today in AI...', 'Now let's check World news...').
    3. At the end of EACH segment, output the exact word [PAUSE] on a new line so we can insert a natural pause in the audio.
    4. Roughly halfway through the broadcast, between two segments, transition to the weather by saying exactly: "And let's go to Olivia for the weather." followed by the exact word [WEATHER_BREAK] on a new line. After [WEATHER_BREAK], continue with the rest of the news. DO NOT write the weather report yourself.
    5. Do not include any sound effect cues, stage directions, or markdown bold/italics formatting. Output ONLY the spoken words and the [PAUSE] and [WEATHER_BREAK] markers.

    News Summaries:
    {joined_summaries}
    
    Broadcast Script:
    """
    
    try:
        # Pass 1: Initial Draft
        logger.info("Drafting initial script...")
        draft_response = litellm.completion(
            model=model,
            messages=[{"role": "user", "content": prompt}]
        )
        draft_script = draft_response.choices[0].message.content.strip()
        
        # Pass 2: Proofreader for TTS Optimization
        logger.info("Proofreading script for AI artifacts and TTS pronunciation...")
        proofread_prompt = f"""
        You are a meticulous broadcast script editor. The following is a raw script for 'The Morning Mutation with Igor'. 
        Your job is to proofread and optimize the text for a Text-To-Speech (TTS) engine.
        
        CRITICAL PRONUNCIATION RULES:
        1. PHONETIC RESPELLING: For difficult or non-English names and terms, use phonetic respelling in the text so the AI says it correctly. 
           - EXAMPLE: Use "en-VID-ee-uh" instead of "NVIDIA".
           - Use this sparingly—only for terms Igor consistently gets wrong.
        2. ACRONYMS: If an acronym should be read letter-by-letter, use hyphens between the letters (e.g., "I-C-E" or "N-A-S-A"). If it should be read as a word, leave it as is (e.g., "Laser").
        3. NUMBERS: Write out numbers if they sound better in a specific format (e.g., "twenty twenty-six" for the year 2026).
        4. NO SYMBOLS: Remove or write out symbols like #, @, or & that the TTS might read literally as "hashtag" or "at sign" unless intended.
        5. CLEANUP: Remove random domain extensions (like ".com") unless they are part of a spoken brand name.
        6. FLOW: Fix jokes that trail off and ensure natural cadence. Keep the witty, sharp tone.
        
        Do NOT remove or modify the [PAUSE] or [WEATHER_BREAK] tags. They must remain exactly as they are on their own lines. Do NOT add markdown formatting like **bold** around them.
        Output ONLY the final spoken words and markers without markdown bold/italics or stage directions.
        
        Raw Script:
        {draft_script}
        
        Final Polished Script:
        """
        
        final_response = litellm.completion(
            model=proofreader_model,
            messages=[{"role": "user", "content": proofread_prompt}]
        )
        
        script = final_response.choices[0].message.content.strip()
        logger.info("Successfully polished broadcast script.")
        return script
    except Exception as e:
        logger.error(f"Failed to generate broadcast script: {e}")
        return "Warning: Failed to generate broadcast script due to an error."