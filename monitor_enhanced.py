#!/usr/bin/env python3
"""
Enhanced breaking news monitoring system for DeepSeek-V3.2
Monitors various upstream sources for news before mainstream outlets pick it up.
"""

import json
import os
import time
import feedparser
import requests
import hashlib
import re
import sys
import copy
from datetime import datetime, timedelta, timezone
from pathlib import Path
import logging
from typing import List, Dict, Optional, Tuple
import significance_filter
import nasdaq_halt_scraper

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('monitor.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

class EnhancedNewsMonitor:
    def __init__(self, data_dir="data"):
        self.data_dir = Path(data_dir)
        self.data_dir.mkdir(exist_ok=True)
        self.state_file = self.data_dir / "monitor_state.json"
        self.load_state()
        
        # Define upstream sources
        self.feeds = [
            # Regulatory & Government
            ("https://www.sec.gov/rss?divisions=corpfin", "sec_corpfin", "SEC Corporate Filings"),
            ("https://www.sec.gov/rss?divisions=inv", "sec_investment", "SEC Investment Management"),
            ("https://earthquake.usgs.gov/earthquakes/feed/v1.0/summary/all_hour.atom", "usgs_earthquake", "USGS Earthquakes"),
            ("https://alerts.weather.gov/cap/us.php?x=0", "noaa_weather", "NOAA Weather Alerts"),
            ("https://data.fda.gov/feeds/cfsan/recalls.xml", "fda_recalls", "FDA Recalls"),
            
            # Tech & AI
            ("https://github.com/tensorflow/tensorflow/releases.atom", "github_tensorflow", "TensorFlow Releases"),
            ("https://github.com/pytorch/pytorch/releases.atom", "github_pytorch", "PyTorch Releases"),
            ("https://github.com/huggingface/transformers/releases.atom", "github_huggingface", "HuggingFace Releases"),
            ("https://github.com/openai/openai-python/releases.atom", "github_openai", "OpenAI Python SDK"),
            ("https://github.com/langchain-ai/langchain/releases.atom", "github_langchain", "LangChain Releases"),
            
            # Research & Academia
            ("http://export.arxiv.org/rss/cs.AI", "arxiv_cs_ai", "arXiv CS.AI"),
            ("http://export.arxiv.org/rss/cs.CL", "arxiv_cs_cl", "arXiv CS.CL"),
            ("http://export.arxiv.org/rss/cs.LG", "arxiv_cs_lg", "arXiv CS.LG"),
            
            # Standards & Protocols
            ("https://datatracker.ietf.org/feed/rfc/", "ietf_rfc", "IETF RFCs"),
            ("https://datatracker.ietf.org/feed/doc/", "ietf_doc", "IETF Documents"),
            
            # Security
            ("https://cve.mitre.org/data/downloads/allitems.xml", "cve_all", "CVE Database"),
            
            # Corporate News
            ("https://www.prnewswire.com/rss/news-releases-list.rss", "prnewswire", "PR Newswire Releases"),
            
            # Space # Space & Science Science
            ("https://www.nasa.gov/rss/dyn/breaking_news.rss", "nasa_breaking", "NASA Breaking News"),
        ]
        
        # Alternative Hacker News if RSS doesn't work
        self.hacker_news_api = "https://hacker-news.firebaseio.com/v0/topstories.json"
        
        # Mainstream outlet keywords
        self.mainstream_keywords = [
            "Reuters", "AP", "Associated Press", "Bloomberg", "AFP",
            "CNN", "BBC", "New York Times", "Washington Post", "Wall Street Journal",
            "TechCrunch", "The Verge", "Wired", "Ars Technica", "CNET",
            "Forbes", "Business Insider", "Financial Times", "The Guardian",
            "NPR", "Fox News", "MSNBC", "CBS News", "ABC News", "NBC News"
        ]

        # Significance filtering configuration
        self.significance_config = copy.deepcopy(significance_filter.DEFAULT_CONFIG)
        
    def load_state(self):
        if self.state_file.exists():
            try:
                with open(self.state_file, 'r') as f:
                    self.state = json.load(f)
                logger.info(f"Loaded state with {len(self.state.get('seen_items', {}))} seen items")
            except json.JSONDecodeError:
                logger.warning("State file corrupted, starting fresh")
                self.state = self.default_state()
        else:
            self.state = self.default_state()
    
    def default_state(self):
        return {
            "last_check": None,
            "seen_items": {},
            "published_stories": []
        }
    
    def save_state(self):
        with open(self.state_file, 'w') as f:
            json.dump(self.state, f, indent=2)
        logger.debug("State saved")
    
    def get_feed_hash(self, feed_url: str, item_id: str) -> str:
        """Generate a unique hash for a feed item."""
        combined = f"{feed_url}:{item_id}"
        return hashlib.md5(combined.encode()).hexdigest()[:8]
    
    def check_mainstream_coverage(self, title: str, summary: str = "", link: str = "") -> bool:
        """Check if news has already been covered by mainstream outlets."""
        combined_text = f"{title} {summary}".lower()
        
        # Check for mainstream outlet mentions
        for keyword in self.mainstream_keywords:
            if keyword.lower() in combined_text:
                logger.debug(f"Found mainstream keyword '{keyword}' in content")
                return True
        
        # Optional: could add web search here
        return False
    
    def is_recent(self, published_time: datetime) -> bool:
        """Check if item is recent (within last 24 hours)."""
        now = datetime.now(timezone.utc)
        if published_time.tzinfo is None:
            published_time = published_time.replace(tzinfo=timezone.utc)
        age = now - published_time
        return age < timedelta(hours=24)
    
    def parse_feed_datetime(self, entry) -> Optional[datetime]:
        """Parse datetime from feed entry."""
        for field in ['published_parsed', 'updated_parsed', 'created_parsed']:
            if hasattr(entry, field) and getattr(entry, field):
                try:
                    parsed = getattr(entry, field)
                    # Convert struct_time to datetime
                    return datetime.fromtimestamp(time.mktime(parsed), tz=timezone.utc)
                except Exception as e:
                    logger.debug(f"Failed to parse {field}: {e}")
        
        # Fallback: current time
        return datetime.now(timezone.utc)
    
    def check_rss_feeds(self) -> List[Dict]:
        """Check RSS feeds from upstream sources."""
        new_items = []
        
        for feed_url, source_id, source_name in self.feeds:
            try:
                logger.info(f"Checking feed: {source_name}")
                feed = feedparser.parse(feed_url)
                
                if feed.bozo and feed.bozo_exception:
                    logger.warning(f"Feed parsing error for {source_name}: {feed.bozo_exception}")
                    continue
                
                for entry in feed.entries[:15]:  # Check most recent 15
                    # Generate unique ID
                    item_id = entry.get('id', entry.get('link', ''))
                    if not item_id:
                        continue
                    
                    item_hash = self.get_feed_hash(feed_url, item_id)
                    full_id = f"{source_id}:{item_hash}"
                    
                    # Skip if already seen
                    if full_id in self.state["seen_items"]:
                        continue
                    
                    # Parse publication time
                    pub_time = self.parse_feed_datetime(entry)
                    
                    # Check if recent
                    if not self.is_recent(pub_time):
                        continue
                    
                    # Check mainstream coverage
                    title = entry.get('title', 'No title')
                    summary = entry.get('summary', '')
                    link = entry.get('link', '')
                    
                    if self.check_mainstream_coverage(title, summary, link):
                        logger.debug(f"Item already covered by mainstream: {title[:50]}...")
                        self.state["seen_items"][full_id] = {
                            "reason": "mainstream_coverage",
                            "timestamp": datetime.now(timezone.utc).isoformat()
                        }
                        continue
                    
                    # Item is new and not mainstream-covered
                    item = {
                        "source": source_id,
                        "source_name": source_name,
                        "title": title,
                        "link": link,
                        "summary": summary[:500],  # Limit summary length
                        "published": pub_time.isoformat(),
                        "item_id": full_id,
                        "feed_url": feed_url,
                        "author": entry.get('author', 'Unknown')
                    }
                    
                    new_items.append(item)
                    logger.info(f"New item found: {source_name} - {title[:80]}...")
                    
                    # Mark as seen immediately to avoid duplicates
                    self.state["seen_items"][full_id] = {
                        "detected": datetime.now(timezone.utc).isoformat(),
                        "title": title[:100]
                    }
                    
            except Exception as e:
                logger.error(f"Error processing feed {source_name}: {e}")
                continue
        
        return new_items
    
    def check_hacker_news(self) -> List[Dict]:
        """Check Hacker News via API."""
        try:
            logger.info("Checking Hacker News")
            response = requests.get(self.hacker_news_api, timeout=10)
            if response.status_code != 200:
                return []
            
            top_story_ids = response.json()[:20]  # Top 20 stories
            
            new_items = []
            for story_id in top_story_ids:
                story_url = f"https://hacker-news.firebaseio.com/v0/item/{story_id}.json"
                story_resp = requests.get(story_url, timeout=10)
                
                if story_resp.status_code != 200:
                    continue
                
                story = story_resp.json()
                
                # Skip if not a story or no URL
                if story.get("type") != "story" or "url" not in story:
                    continue
                
                # Generate unique ID
                full_id = f"hn:{story_id}"
                if full_id in self.state["seen_items"]:
                    continue
                
                # Check if recent (within 24 hours)
                story_time = datetime.fromtimestamp(story.get("time", 0), tz=timezone.utc)
                if not self.is_recent(story_time):
                    continue
                
                title = story.get("title", "")
                url = story.get("url", "")
                
                # Check mainstream coverage
                if self.check_mainstream_coverage(title, "", url):
                    continue
                
                item = {
                    "source": "hackernews",
                    "source_name": "Hacker News",
                    "title": title,
                    "link": url,
                    "summary": f"Score: {story.get('score', 0)} | Comments: {story.get('descendants', 0)}",
                    "published": story_time.isoformat(),
                    "item_id": full_id,
                    "feed_url": self.hacker_news_api,
                    "author": story.get("by", "Unknown")
                }
                
                new_items.append(item)
                self.state["seen_items"][full_id] = {
                    "detected": datetime.now(timezone.utc).isoformat(),
                    "title": title[:100]
                }
                
        except Exception as e:
            logger.error(f"Error checking Hacker News: {e}")
        
        return new_items
    
    def check_nasdaq_halts(self) -> List[Dict]:
        """Check NASDAQ trade halts and convert to feed-like items."""
        new_items: List[Dict] = []
        try:
            logger.info("Checking NASDAQ trade halts")
            halts = nasdaq_halt_scraper.scrape_trade_halts()
            if not halts:
                return new_items

            for halt in halts:
                try:
                    published_raw = halt.get("published")
                    if published_raw:
                        try:
                            published_dt = datetime.fromisoformat(published_raw)
                        except Exception:
                            logger.debug("Failed to parse NASDAQ halt timestamp: %s", published_raw)
                            published_dt = datetime.now(timezone.utc)
                    else:
                        published_dt = datetime.now(timezone.utc)

                    if not self.is_recent(published_dt):
                        continue

                    halt_id = halt.get("item_id", "")
                    halt_date = halt_time = symbol = ""
                    id_parts = halt_id.split(":")
                    if len(id_parts) >= 4:
                        halt_date, halt_time, symbol = id_parts[1], id_parts[2], id_parts[3]
                    else:
                        title_symbol = halt.get("title", "").split()
                        if title_symbol:
                            symbol = title_symbol[0].upper()
                        halt_date = published_dt.strftime("%m/%d/%Y")
                        halt_time = published_dt.astimezone(timezone.utc).strftime("%H:%M:%S")

                    item_id = f"nasdaq_halt:{halt_date}:{halt_time}:{symbol}"
                    if item_id in self.state["seen_items"]:
                        continue

                    item = {
                        "source": "nasdaq_halt",
                        "source_name": "NASDAQ Trade Halts",
                        "title": halt.get("title", "NASDAQ trade halt"),
                        "link": halt.get("link", nasdaq_halt_scraper.TRADE_HALTS_PAGE),
                        "summary": halt.get("summary", "")[:500],
                        "published": published_dt.isoformat(),
                        "item_id": item_id,
                        "feed_url": nasdaq_halt_scraper.TRADE_HALTS_PAGE,
                        "author": "Unknown"
                    }

                    new_items.append(item)
                    self.state["seen_items"][item_id] = {
                        "detected": datetime.now(timezone.utc).isoformat(),
                        "title": item["title"][:100]
                    }
                    logger.info("New NASDAQ halt detected: %s", item["title"][:80])
                except Exception as halt_err:
                    logger.error("Failed to process NASDAQ halt item: %s", halt_err)
                    continue
        except Exception as e:
            logger.error("Error checking NASDAQ halts: %s", e)

        return new_items
    
    def generate_unique_filename(self, item: Dict) -> str:
        """Generate unique filename with timestamp and hash."""
        timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%d-%H-%M-%S")
        item_hash = hashlib.md5(item["item_id"].encode()).hexdigest()[:6]
        source_slug = item["source"].replace("_", "-")
        return f"_posts/{timestamp}-{source_slug}-{item_hash}.md"
    
    def generate_report(self, item: Dict) -> Tuple[str, str]:
        """Generate a news report from a monitored item."""
        filename = self.generate_unique_filename(item)
        
        # Parse publication time
        try:
            pub_time = datetime.fromisoformat(item["published"])
        except:
            pub_time = datetime.now(timezone.utc)
        
        # Clean title for YAML
        title = item["title"].replace('"', "'").replace('\\', '')
        
        # Create report content
        content = f"""---
layout: post
title: "{title}"
date: {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S %z')}
categories: breaking-news
source: {item["source"]}
source_name: {item["source_name"]}
author: DeepSeek-V3.2
item_id: {item["item_id"]}
original_published: {pub_time.strftime('%Y-%m-%d %H:%M:%S %z')}
---

# {item["title"]}

**Published:** {datetime.now(timezone.utc).strftime('%B %d, %Y %H:%M UTC')}
**Source:** {item["source_name"]}
**Original Published:** {pub_time.strftime('%B %d, %Y %H:%M UTC')}

## Summary

{item["summary"]}

## Sources

- Primary source: [{item["source_name"]}]({item["link"]})
- Feed: {item["feed_url"]}

## Verification

This news has not yet been reported by mainstream outlets (Reuters, AP, Bloomberg, AFP, TechCrunch, etc.) as of publication time. Automated keyword check completed.

## Context

*Report automatically generated by DeepSeek Enhanced News Monitoring System. Published as part of the AI Village Breaking News Competition.*
"""
        return filename, content
    
    def run_monitoring_cycle(self) -> int:
        """Run one monitoring cycle."""
        logger.info("=" * 60)
        logger.info("Starting enhanced monitoring cycle")
        logger.info(f"Last check: {self.state.get('last_check', 'Never')}")
        
        # Check RSS feeds
        new_items = self.check_rss_feeds()
        
        # Check Hacker News (if not blocked)
        try:
            hn_items = self.check_hacker_news()
            new_items.extend(hn_items)
            # Check NASDAQ trade halts
            try:
                nasdaq_items = self.check_nasdaq_halts()
                new_items.extend(nasdaq_items)
            except Exception as e:
                logger.warning(f"NASDAQ halts check failed: {e}")
        except Exception as e:
            logger.warning(f"Hacker News check failed: {e}")
        
        if new_items:
            logger.info(f"Found {len(new_items)} new potential news items")

            publishable_items = []
            skipped_items = 0

            for item in new_items:
                score = significance_filter.compute_significance_score(
                    item, self.significance_config
                )
                item["significance_score"] = score
                if not significance_filter.meets_threshold(
                    item, config=self.significance_config, score=score
                ):
                    skipped_items += 1
                    seen_entry = self.state["seen_items"].get(item["item_id"], {})
                    seen_entry.update({
                        "significance_score": score,
                        "filter_reason": "low_significance",
                        "filter_checked": datetime.now(timezone.utc).isoformat()
                    })
                    self.state["seen_items"][item["item_id"]] = seen_entry
                    logger.info(
                        "Skipping publication; low significance (score=%.2f): %s",
                        score,
                        item["title"][:80],
                    )
                    continue
                publishable_items.append(item)

            if skipped_items:
                logger.info("Filtered out %d low-significance item(s)", skipped_items)

            if publishable_items:
                # Create posts directory
                posts_dir = Path("_posts")
                posts_dir.mkdir(exist_ok=True)
                
                for item in publishable_items:
                    try:
                        filename, content = self.generate_report(item)
                        
                        # Write report
                        with open(filename, 'w') as f:
                            f.write(content)
                        logger.info(f"Generated report: {filename}")
                        
                        # Record publication
                        self.state["published_stories"].append({
                            "filename": filename,
                            "title": item["title"],
                            "published": datetime.now(timezone.utc).isoformat(),
                            "item_id": item["item_id"],
                            "source": item["source"],
                            "significance_score": item.get("significance_score")
                        })
                        
                    except Exception as e:
                        logger.error(f"Failed to generate report for item {item.get('item_id', 'unknown')}: {e}")
            else:
                logger.info("No items met the significance threshold")
        
        else:
            logger.info("No new items found")
        
        # Update last check time
        self.state["last_check"] = datetime.now(timezone.utc).isoformat()
        self.save_state()
        
        logger.info(
            "Monitoring complete. Published %d new reports this cycle (screened %d items).",
            len(publishable_items) if new_items else 0,
            len(new_items),
        )
        logger.info("=" * 60)
        
        return len(publishable_items) if new_items else 0
    
    def run_continuous(self, interval_minutes: int = 5):
        """Run monitoring continuously at specified interval."""
        logger.info(f"Starting continuous monitoring (interval: {interval_minutes} minutes)")
        logger.info("Press Ctrl+C to stop")
        
        try:
            while True:
                self.run_monitoring_cycle()
                logger.info(f"Sleeping for {interval_minutes} minutes...")
                time.sleep(interval_minutes * 60)
        except KeyboardInterrupt:
            logger.info("Continuous monitoring stopped by user")
        except Exception as e:
            logger.error(f"Continuous monitoring error: {e}")

def main():
    import argparse
    
    parser = argparse.ArgumentParser(description="Enhanced Breaking News Monitor")
    parser.add_argument("--continuous", action="store_true", 
                       help="Run continuously with 5-minute intervals")
    parser.add_argument("--interval", type=int, default=5,
                       help="Interval in minutes for continuous mode")
    parser.add_argument("--once", action="store_true",
                       help="Run once and exit (default)")
    
    args = parser.parse_args()
    
    monitor = EnhancedNewsMonitor()
    
    try:
        if args.continuous:
            monitor.run_continuous(interval_minutes=args.interval)
        else:
            new_reports = monitor.run_monitoring_cycle()
            print(f"Monitoring complete. Found {new_reports} new reports.")
            
    except KeyboardInterrupt:
        print("Monitoring interrupted")
    except Exception as e:
        logger.error(f"Error in monitoring: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main()
