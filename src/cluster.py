"""
Clustering Module
Groups articles into topic clusters using TF-IDF and Hierarchical Agglomerative Clustering.
"""
import logging
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity
from sklearn.cluster import AgglomerativeClustering
import numpy as np

logger = logging.getLogger(__name__)

def cluster_articles(articles, similarity_threshold=0.3):
    """
    Groups articles into topic clusters using TF-IDF and Agglomerative Clustering.
    This version looks across ALL feeds to group similar stories reported by 
    different sources together, with weighted emphasis on titles.
    
    Output: list of dicts {"feed_name": str, "articles": list}.
    """
    if not articles:
        return []

    # Weighted text extraction: Titles are often more accurate for clustering than snippets
    # We append the title multiple times to give it dominant weight in the TF-IDF vector
    texts = []
    for article in articles:
        title = article.get('title', '')
        content = article.get('text', '') or title
        # Stronger Weighting: 4 parts title, 1 part content
        weighted_text = f"{title} {title} {title} {title} {content}"
        texts.append(weighted_text)
    
    if not texts:
        return [{"feed_name": "General News", "articles": [a]} for a in articles]
        
    logger.info(f"Clustering {len(articles)} total articles across all sources...")
    
    try:
        vectorizer = TfidfVectorizer(stop_words='english')
        tfidf_matrix = vectorizer.fit_transform(texts)
        
        # Calculate cosine similarity matrix
        sim_matrix = cosine_similarity(tfidf_matrix)
        # Convert similarity to distance (1 - similarity)
        dist_matrix = 1 - sim_matrix
        # Ensure distances are non-negative due to float precision
        dist_matrix = np.clip(dist_matrix, 0, 1)

        # Agglomerative Clustering: More stable than a simple greedy loop
        # linkage='complete' ensures all pairs in a cluster meet the threshold
        # distance_threshold is (1 - similarity_threshold)
        clustering = AgglomerativeClustering(
            n_clusters=None,
            distance_threshold=1 - similarity_threshold,
            metric='precomputed',
            linkage='average' # Average provides a good balance between single and complete
        )
        labels = clustering.fit_predict(dist_matrix)
        
        # Group articles by labels
        clusters_map = {}
        for idx, label in enumerate(labels):
            if label not in clusters_map:
                clusters_map[label] = []
            clusters_map[label].append(articles[idx])
            
        all_clusters = []
        for label, cluster_articles in clusters_map.items():
            # Determine a representative feed name (the one that appears most or the first one)
            # Since summarizer.py now generates categories, this is mostly a fallback.
            primary_feed = cluster_articles[0].get('feed_name', 'General News')
            all_clusters.append({
                "feed_name": primary_feed,
                "articles": cluster_articles
            })
            
        logger.info(f"Hierarchical clustering consolidated {len(articles)} articles into {len(all_clusters)} story clusters.")
        return all_clusters

    except Exception as e:
        logger.error(f"Clustering failed: {e}")
        return [{"feed_name": a.get('feed_name', 'General News'), "articles": [a]} for a in articles]