"""
Summarizer Module
Uses LLMs (via LiteLLM) to synthesize multi-source news clusters into cohesive 
summaries and generate a persona-driven broadcast script.
"""
import logging
import litellm
import os
import re

logger = logging.getLogger(__name__)

def clean_llm_output(text):
    """
    Removes common LLM conversational filler, labels, and markdown artifacts.
    Ensures the script starts exactly where the dialogue starts.
    """
    if not text:
        return ""
    # Remove common lead-ins like "Here is the polished script:" or "Refined Script:"
    text = re.sub(r'^(Final|Polished|Refined|Script|Here|Sure|The).*?:\s*', '', text, flags=re.IGNORECASE | re.MULTILINE)
    # Remove markdown formatting (bold, italics) which TTS might try to interpret
    text = text.replace("**", "").replace("*", "").replace("__", "")
    return text.strip()

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
            "You are an expert news editor. Your task is to synthesize multiple articles "
            "into one cohesive, objective, and engaging summary. Avoid shopping deals or fluff."
        )

        user_prompt = f"""
        Synthesize the following sources into 1-2 paragraphs.
        
        REQUIRED FORMAT:
        CATEGORIES: [List applicable categories from: Tech, World, Political, Entertainment, Sports]
        SUMMARY:
        [Your Synthesized Summary]
        
        Sources to synthesize:
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
            
            categories = [feed_name]
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
            logger.info(f"Synthesized cluster {i+1}/{len(clusters)}.")
            
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
    Generates a cohesive script with markers for pauses and weather.
    Uses a two-pass system: 1. Creative Writing, 2. TTS Optimization.
    """
    model = get_model_name(config, key='scriptwriter_model')
    proofreader_model = get_model_name(config, key='proofreader_model')
    
    if not summaries:
        return "Hey folks, EE-gore here! We didn't find any breaking news today, so go back to sleep. Just kidding, have a great day!"
        
    logger.info("Generating final broadcast script...")
    joined_summaries = "\n---\n".join([f"CATEGORIES: {', '.join(s['categories'])}\nSUMMARY:\n{s['summary']}" for s in summaries])
    
    # PASS 1: THE WRITER
    writer_system = (
        f"You are 'Igor', the AI host of 'The Morning Mutation with Igor'. Date: {current_date if current_date else 'unknown'}. "
        "Your style is punchy, funny, and witty. Output ONLY the spoken words and the markers [PAUSE] and [WEATHER_BREAK]. "
        "No stage directions, no markdown, and no intro/outro filler text."
    )
    
    writer_prompt = f"""
    Write a cohesive news script from these summaries.
    
    CRITICAL INSTRUCTIONS:
    1. Output exactly [PAUSE] on its own line after every segment.
    2. Halfway through, say "And let's go to Olivia for the weather." followed by [WEATHER_BREAK] on its own line.
    3. Skip any categories that are just shopping deals or product sales.
    4. Only joke about articles mentioned in the summary.
    
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
        
        # PASS 2: THE TTS OPTIMIZER
        proof_system = (
            "You are a meticulous broadcast script editor for Text-To-Speech (TTS). "
            "Your ONLY goal is to optimize for pronunciation and protect system markers. "
            "DO NOT add conversational filler like 'Here is your polished script'."
        )
        
        proof_prompt = f"""
        Optimize this script for TTS.
        
        RULES:
        1. PHONETIC: Use 'EE-gore' for Igor and 'en-VID-ee-uh' for NVIDIA. 
        2. ACRONYMS: Hyphenate letter-by-letter acronyms (e.g., F-B-I).
        3. MARKERS: The tags [PAUSE] and [WEATHER_BREAK] are SYSTEM COMMANDS. 
           - They MUST remain on their own lines. 
           - NEVER change them into dialogue (do not say "Let's take a pause").
        4. CLEANUP: Remove all markdown, sound effect cues, or domain extensions like '.com'.
        
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