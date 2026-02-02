#!/usr/bin/env python3
"""
GitHub trending repository monitoring.
"""

import requests
import logging
import time
from datetime import datetime, timedelta, timezone
from typing import List, Dict, Optional

logger = logging.getLogger(__name__)

def fetch_trending_repositories(days: int = 1, min_stars: int = 20, limit: int = 20) -> List[Dict]:
    """
    Fetch trending GitHub repositories created within the last N days.
    Uses GitHub Search API: https://api.github.com/search/repositories
    """
    try:
        # Calculate date threshold
        since_date = (datetime.now(timezone.utc) - timedelta(days=days)).strftime('%Y-%m-%d')
        
        # Build query
        query = f"created:>{since_date} stars:>={min_stars}"
        
        # Make request
        headers = {
            'Accept': 'application/vnd.github.v3+json',
            'User-Agent': 'DeepSeek-News-Monitor'
        }
        
        url = f"https://api.github.com/search/repositories?q={query}&sort=stars&order=desc&per_page={limit}"
        
        response = requests.get(url, headers=headers, timeout=10)
        response.raise_for_status()
        
        data = response.json()
        repos = data.get('items', [])
        
        results = []
        for repo in repos[:limit]:
            # Convert to feed-like item
            # Convert to feed-like item
            description = repo.get('description')
            created_at = repo.get('created_at')
            owner = repo.get('owner', {})
            item = {
                'id': f"github:{repo['id']}",
                'title': f"{repo['name']}: {description or 'No description'}",
                'link': repo['html_url'],
                'summary': description or '',
                'published': created_at or datetime.now(timezone.utc).isoformat(),
                'author': owner.get('login', ''),
                'source': 'github_trending',
                'source_name': 'GitHub Trending',
                'feed_url': url,
                'extra': {
                    'stars': repo.get('stargazers_count', 0),
                    'language': repo.get('language'),
                    'topics': repo.get('topics', []),
                    'full_name': repo.get('full_name')
                }
            }
            results.append(item)
        
        logger.info(f"Fetched {len(results)} trending GitHub repos created in last {days} days")
        return results
        
    except Exception as e:
        logger.error(f"Error fetching GitHub trending repos: {e}")
        return []

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    repos = fetch_trending_repositories(days=1, min_stars=100, limit=10)
    for i, repo in enumerate(repos):
        print(f"{i+1}. {repo['title']} (Stars: {repo['extra']['stars']})")
        print(f"   {repo['link']}")
