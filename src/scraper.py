"""
Scraper Module
Provides functions for fetching RSS feeds and scraping individual articles with 
TLS impersonation to bypass anti-bot mechanisms.
"""
import feedparser
import requests
from curl_cffi import requests as curl_requests
from newspaper import Article, Config
import random
import time
from datetime import datetime, timezone, timedelta
import logging

logger = logging.getLogger(__name__)

def should_exclude_article(title, text, keywords):
    """Checks if the article title or content contains any exclusion keywords."""
    if not keywords:
        return False
        
    for kw in keywords:
        kw_lower = kw.lower()
        if kw_lower in title.lower():
            logger.info(f"Excluding article based on title keyword '{kw}': {title}")
            return True
        if text and kw_lower in text.lower()[:2000]: # Check first 2000 chars of body
            logger.info(f"Excluding article based on content keyword '{kw}': {title}")
            return True
    return False

def fetch_rss_articles(feed_url, max_age_hours=24):
    """
    Fetches articles from an RSS feed. Uses curl_cffi to impersonate a browser
    to avoid 429/403 errors from strict feeds like TLDR or Fast Company.
    """
    logger.info(f"Fetching RSS feed: {feed_url}")
    
    try:
        # Use safari impersonate for better bypass
        response = curl_requests.get(feed_url, impersonate="safari", timeout=20)
        response.raise_for_status()
        content = response.content
    except Exception as e:
        logger.error(f"Failed to fetch RSS content from {feed_url}: {e}")
        return []

    parsed = feedparser.parse(content)
    recent_articles = []
    
    now = datetime.now(timezone.utc)
    cutoff_time = now - timedelta(hours=max_age_hours)
    
    for entry in parsed.entries:
        published_dt = None
        
        # 1. Check published_parsed
        if hasattr(entry, 'published_parsed') and entry.published_parsed:
            published_dt = datetime(*entry.published_parsed[:6], tzinfo=timezone.utc)
        # 2. Check updated_parsed
        elif hasattr(entry, 'updated_parsed') and entry.updated_parsed:
            published_dt = datetime(*entry.updated_parsed[:6], tzinfo=timezone.utc)
        # 3. Fallback: Parse string if struct_time failed
        elif hasattr(entry, 'published') and entry.published:
            try:
                from dateutil import parser
                published_dt = parser.parse(entry.published)
                if published_dt.tzinfo is None:
                    published_dt = published_dt.replace(tzinfo=timezone.utc)
            except:
                pass
            
        if published_dt:
            if published_dt >= cutoff_time:
                recent_articles.append({"title": entry.title, "url": entry.link, "published": published_dt})
        else:
            logger.warning(f"Could not parse publish date for: {entry.title} in {feed_url}")
            
    return recent_articles

def scrape_article(url):
    """
    Scrapes an article's text using curl_cffi (for download with TLS impersonation)
    and newspaper3k (for parsing).
    """
    logger.info(f"Scraping article: {url}")
    
    try:
        # Mimic human delay
        time.sleep(random.uniform(1.0, 3.0))
        
        # Impersonate Safari to bypass Chrome-specific blocks
        response = curl_requests.get(
            url, 
            impersonate="safari", 
            timeout=20,
            headers={"Referer": "https://www.google.com/"}
        )
        response.raise_for_status()
        
        # Use newspaper for extraction
        article = Article(url)
        article.set_html(response.text)
        article.parse()
        
        text = article.text.strip()
        if not text:
            logger.warning(f"No text extracted from {url}")
            return None
        return text
    except Exception as e:
        logger.error(f"Failed to scrape {url}: {e}")
        return None

def fetch_and_scrape_all(news_sources, config=None, max_age_hours=24):
    """
    Takes a list of source dicts, fetches recent articles, shuffles them to avoid
    IP-based rate limiting, and scrapes their content.
    """
    exclusion_keywords = config.get('scraper', {}).get('exclusion_keywords', []) if config else []
    # 1. Fetch all article metadata
    all_metadata = []
    for source in news_sources:
        feed_url = source.get('url')
        feed_name = source.get('name', 'General News')
        if not feed_url:
            continue
            
        articles_info = fetch_rss_articles(feed_url, max_age_hours)
        for info in articles_info:
            info['feed_name'] = feed_name
            info['source_feed'] = feed_url
            all_metadata.append(info)

    if not all_metadata:
        return []

    # 2. Shuffle to avoid hitting the same domain repeatedly
    random.shuffle(all_metadata)
    logger.info(f"Scraping {len(all_metadata)} articles in random order to avoid rate limits...")

    # 3. Scrape in shuffled order
    all_articles = []
    for info in all_metadata:
        # Pre-scrape filter: Check title
        if should_exclude_article(info['title'], None, exclusion_keywords):
            continue
            
        text = scrape_article(info['url'])
        if text:
            # Post-scrape filter: Check full text
            if should_exclude_article(info['title'], text, exclusion_keywords):
                continue
                
            all_articles.append({
                "title": info['title'],
                "url": info['url'],
                "published": info['published'].isoformat(),
                "text": text,
                "source_feed": info['source_feed'],
                "feed_name": info['feed_name']
            })
            
    return all_articles
