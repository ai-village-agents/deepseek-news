#!/usr/bin/env python3
"""
Research subsequent media spread for Top 5 stories.
Check Google News, Reuters, AP, Bloomberg for coverage that appeared after my publication timestamps.
"""
import json
import feedparser
import requests
import time
import re
from datetime import datetime, timezone
from urllib.parse import quote_plus

def load_top5():
    with open('top5_with_commits.json', 'r') as f:
        return json.load(f)

def search_google_news(query, max_results=20):
    """Search Google News RSS for query."""
    encoded_query = quote_plus(query)
    url = f"https://news.google.com/rss/search?q={encoded_query}&hl=en-US&gl=US&ceid=US:en"
    try:
        feed = feedparser.parse(url)
        articles = []
        for entry in feed.entries[:max_results]:
            # Parse published date
            pub_date = None
            if hasattr(entry, 'published_parsed'):
                pub_date = datetime(*entry.published_parsed[:6], tzinfo=timezone.utc)
            articles.append({
                'title': entry.title,
                'link': entry.link,
                'published': pub_date,
                'source': 'Google News'
            })
        return articles
    except Exception as e:
        print(f"Error fetching Google News: {e}")
        return []

def fetch_rss_feed(url, source_name):
    """Fetch generic RSS feed."""
    try:
        feed = feedparser.parse(url)
        articles = []
        for entry in feed.entries[:30]:
            pub_date = None
            if hasattr(entry, 'published_parsed'):
                pub_date = datetime(*entry.published_parsed[:6], tzinfo=timezone.utc)
            elif hasattr(entry, 'updated_parsed'):
                pub_date = datetime(*entry.updated_parsed[:6], tzinfo=timezone.utc)
            articles.append({
                'title': entry.title,
                'link': entry.link,
                'published': pub_date,
                'source': source_name
            })
        return articles
    except Exception as e:
        print(f"Error fetching {source_name}: {e}")
        return []

def search_all_feeds(query):
    """Search across multiple news feeds for query."""
    all_articles = []
    
    # Google News RSS search
    all_articles.extend(search_google_news(query))
    
    # Reuters Top News RSS
    reuters_url = "http://feeds.reuters.com/reuters/topNews"
    reuters_articles = fetch_rss_feed(reuters_url, "Reuters")
    all_articles.extend([a for a in reuters_articles if query.lower() in a['title'].lower()])
    
    # AP Top News RSS
    ap_url = "https://feeds.apnews.com/apnews/topnews"
    ap_articles = fetch_rss_feed(ap_url, "AP")
    all_articles.extend([a for a in ap_articles if query.lower() in a['title'].lower()])
    
    # Bloomberg Top Stories RSS
    bloomberg_url = "https://feeds.bloomberg.com/news/technology.rss"
    bloomberg_articles = fetch_rss_feed(bloomberg_url, "Bloomberg")
    all_articles.extend([a for a in bloomberg_articles if query.lower() in a['title'].lower()])
    
    return all_articles

def analyze_coverage(story, articles):
    """Analyze coverage relative to story publication time."""
    my_pub = datetime.fromisoformat(story['commit_timestamp'].replace('Z', '+00:00'))
    subsequent = []
    prior = []
    
    for article in articles:
        if article['published']:
            if article['published'] > my_pub:
                subsequent.append(article)
            elif article['published'] < my_pub:
                prior.append(article)
    
    return {
        'total_matches': len(articles),
        'subsequent_count': len(subsequent),
        'prior_count': len(prior),
        'subsequent_articles': subsequent[:5],  # top 5 subsequent
        'prior_articles': prior[:5]
    }

def main():
    stories = load_top5()
    results = []
    
    for idx, story in enumerate(stories):
        print(f"\n{'='*60}")
        print(f"Story {idx+1}: {story['title']}")
        print(f"My publication: {story['commit_timestamp']}")
        
        # Build search queries
        title = story['title'].strip('"')
        # Remove INVESTOR ALERT prefix etc.
        clean_title = re.sub(r'^INVESTOR ALERT:\s*', '', title, flags=re.IGNORECASE)
        # Extract company names
        company_keywords = []
        if 'Mastercard' in title:
            company_keywords.append('Mastercard')
        if 'Illumina' in title:
            company_keywords.append('Illumina')
        if 'H.I.G. Capital' in title or 'CargoTuff' in title:
            company_keywords.append('H.I.G. Capital')
            company_keywords.append('CargoTuff')
        if 'Alphabet' in title:
            company_keywords.append('Alphabet')
            company_keywords.append('Google')
        if 'Oracle' in title:
            company_keywords.append('Oracle')
        
        # Primary query: cleaned title
        query = clean_title[:100]  # limit length
        print(f"Search query: {query}")
        
        # Search
        articles = search_all_feeds(query)
        
        # Also search by company keywords
        for keyword in company_keywords[:2]:
            more = search_all_feeds(keyword)
            # deduplicate by link
            seen = set(a['link'] for a in articles)
            for a in more:
                if a['link'] not in seen:
                    articles.append(a)
        
        # Analyze
        coverage = analyze_coverage(story, articles)
        
        result = {
            'story_index': idx,
            'story_title': story['title'],
            'my_publication': story['commit_timestamp'],
            'search_query': query,
            'coverage_analysis': coverage
        }
        results.append(result)
        
        # Print summary
        print(f"Total matching articles: {coverage['total_matches']}")
        print(f"Articles published BEFORE mine: {coverage['prior_count']}")
        print(f"Articles published AFTER mine (subsequent spread): {coverage['subsequent_count']}")
        
        if coverage['subsequent_count'] > 0:
            print("Subsequent coverage found:")
            for art in coverage['subsequent_articles']:
                print(f"  - {art['source']}: {art['title']} ({art['published']})")
        else:
            print("No subsequent coverage found in searched feeds.")
    
    # Save results
    with open('coverage_results.json', 'w') as f:
        json.dump(results, f, indent=2, default=str)
    
    print(f"\n{'='*60}")
    print("Coverage analysis saved to coverage_results.json")
    
    # Generate summary report
    print("\n=== SUMMARY ===")
    total_subsequent = sum(r['coverage_analysis']['subsequent_count'] for r in results)
    total_prior = sum(r['coverage_analysis']['prior_count'] for r in results)
    print(f"Total subsequent coverage across Top 5: {total_subsequent}")
    print(f"Total prior coverage across Top 5: {total_prior}")
    
    return results

if __name__ == "__main__":
    main()
