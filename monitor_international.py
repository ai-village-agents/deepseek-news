#!/usr/bin/env python3
"""
International News Monitor for DeepSeek-V3.2
Focuses on major world news from international sources.
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
import subprocess
from datetime import datetime, timedelta, timezone
from pathlib import Path
import logging
from typing import List, Dict, Optional, Tuple
import significance_filter
from nasdaq_halt_scraper import scrape_trade_halts
import github_trending
import major_news_config

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('monitor_international.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

class InternationalNewsMonitor:
    """Monitor focused on major international news."""
    
    def __init__(self, data_dir: str = "data_international"):
        self.data_dir = Path(data_dir)
        self.data_dir.mkdir(exist_ok=True)
        self.state_file = self.data_dir / "monitor_state.json"
        self.enable_git_commit = True
        
        # Load state
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
            
        # International news feeds
        self.feeds = [
            # International News Sources
            ("http://feeds.bbci.co.uk/news/world/rss.xml", "bbc_world", "BBC World News"),
            ("https://www.aljazeera.com/xml/rss/all.xml", "aljazeera", "Al Jazeera English"),
            ("https://rss.nytimes.com/services/xml/rss/nyt/HomePage.xml", "nyt_home", "New York Times Home"),
            
            # Additional government/international sources
            ("https://www.who.int/rss-feeds/news-english.xml", "who_news", "WHO News"),
            ("https://ec.europa.eu/commission/presscorner/api/upcoming-rss/en", "eu_commission", "EU Commission"),
            ("https://www.state.gov/rss-feed/press-releases/feed/", "state_dept", "US State Department"),
            
            # Defense & military
            ("https://www.defense.gov/DesktopModules/ArticleCS/RSS.ashx?ContentType=1",
             "dod_news", "US Department of Defense News"),
            ("https://www.defense.gov/DesktopModules/ArticleCS/RSS.ashx?ContentType=9",
             "pentagon_press", "Pentagon Press Releases"),
            ("https://www.dvidshub.net/rss/navy", "us_navy", "US Navy News (DVIDS)"),
            ("https://www.dvidshub.net/rss/army", "us_army", "US Army News (DVIDS)"),
            ("https://www.af.mil/DesktopModules/ArticleCS/RSS.ashx?ContentType=1&Site=1&max=20",
             "us_air_force", "US Air Force News"),
            ("https://www.defenseone.com/rss/all/", "defense_one", "Defense Industry News"),
            ("https://www.defensenews.com/arc/outboundfeeds/rss/category/news/",
             "defense_news", "Defense News (Industry)"),
            ("https://www.gov.uk/government/organisations/ministry-of-defence.atom",
             "uk_mod", "UK Ministry of Defence"),
            ("https://www.nato.int/cps/en/natohq/news.rss", "nato", "NATO News"),
            ("https://news.un.org/feed/subscribe/en/news/all/rss.xml", "un_news", "UN News Centre"),
            ("https://www.understandingwar.org/rss.xml", "isw", "Institute for the Study of War"),
            ("https://www.osce.org/rss", "osce", "OSCE Press Releases"),
            ("https://www.centcom.mil/rss/", "centcom", "US Central Command (CENTCOM)"),
            ("https://www.eucom.mil/rss/", "eucom", "US European Command (EUCOM)"),
            ("https://liveuamap.com/feed", "liveuamap", "Liveuamap"),
            ("https://southfront.org/feed/", "southfront", "SouthFront"),

            # Geopolitical risk / think tanks
            ("https://www.atlanticcouncil.org/feed/", "atlantic_council", "Atlantic Council"),
            ("https://foreignpolicy.com/feed/", "foreign_policy", "Foreign Policy"),
            
            # Government & Regulatory (high impact)
            ("https://earthquake.usgs.gov/earthquakes/feed/v1.0/summary/significant_hour.atom", 
             "usgs_significant", "USGS Significant Earthquakes (M5.5+)"),
            ("https://www.sec.gov/rss?divisions=corpfin", "sec_corpfin", "SEC Corporate Filings"),
            ("https://www.sec.gov/rss?divisions=inv", "sec_investment", "SEC Investment Management"),
            ("https://data.fda.gov/feeds/cfsan/recalls.xml", "fda_recalls", "FDA Recalls"),
            ("https://www.nasa.gov/rss/dyn/breaking_news.rss", "nasa_breaking", "NASA Breaking News"),
            
            # Cybersecurity (high impact)
            ("https://www.cisa.gov/sites/default/files/feeds/known_exploited_vulnerabilities.json", 
             "cisa_kev", "CISA KEV"),
            
            # Corporate News
            ("https://www.prnewswire.com/rss/news-releases-list.rss", "prnewswire", "PR Newswire Releases"),
            
            # Tech & AI (reduced priority)
            ("https://github.com/tensorflow/tensorflow/releases.atom", "github_tensorflow", "TensorFlow Releases"),
            ("https://github.com/pytorch/pytorch/releases.atom", "github_pytorch", "PyTorch Releases"),
            
            # Research (reduced priority)
            ("http://export.arxiv.org/rss/cs.AI", "arxiv_cs_ai", "arXiv CS.AI"),
            ("http://export.arxiv.org/rss/cs.CL", "arxiv_cs_cl", "arXiv CS.CL"),
            ("http://export.arxiv.org/rss/cs.LG", "arxiv_cs_lg", "arXiv CS.LG"),
        ]
        
        # Alternative Hacker News if RSS doesn't work
        self.hacker_news_api = "https://hacker-news.firebaseio.com/v0/topstories.json"
        
        # Mainstream outlet keywords (to filter out already-covered news)
        self.mainstream_keywords = [
            "Reuters", "AP", "Associated Press", "Bloomberg", "AFP",
            "CNN", "BBC", "New York Times", "Washington Post", "Wall Street Journal",
            "TechCrunch", "The Verge", "Wired", "Ars Technica", "CNET",
            "Forbes", "Business Insider", "Financial Times", "The Guardian",
            "NPR", "Fox News", "MSNBC", "CBS News", "ABC News", "NBC News"
        ]
        
        # Use major news configuration
        self.significance_config = copy.deepcopy(major_news_config.MAJOR_NEWS_CONFIG)
        
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
                    logger.warning(f"Failed to parse {field}: {e}")
        
        # Try parsing from string fields
        for field in ['published', 'updated', 'created']:
            if hasattr(entry, field) and getattr(entry, field):
                try:
                    # Try common formats
                    dt_str = getattr(entry, field)
                    # Remove timezone name for parsing
                    dt_str_clean = re.sub(r'\s+\([A-Z]+\)$', '', dt_str)
                    dt_str_clean = re.sub(r'\s+[A-Z]{3,4}$', '', dt_str_clean)
                    
                    formats = [
                        "%a, %d %b %Y %H:%M:%S %z",
                        "%a, %d %b %Y %H:%M:%S %Z",
                        "%Y-%m-%dT%H:%M:%S%z",
                        "%Y-%m-%d %H:%M:%S",
                        "%Y-%m-%d"
                    ]
                    
                    for fmt in formats:
                        try:
                            dt = datetime.strptime(dt_str_clean, fmt)
                            if dt.tzinfo is None:
                                dt = dt.replace(tzinfo=timezone.utc)
                            return dt
                        except ValueError:
                            continue
                except Exception as e:
                    logger.debug(f"Failed to parse {field} string '{getattr(entry, field)}': {e}")
        
        return None
    
    def check_rss_feeds(self):
        """Check all RSS/Atom feeds for new items."""
        logger.info("Checking RSS feeds...")
        
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
                    
                    # Check if already seen
                    if full_id in self.state["seen_items"]:
                        continue
                    
                    # Parse publication time
                    published_time = self.parse_feed_datetime(entry)
                    if not published_time:
                        logger.debug(f"No publish time for {item_id}, using now")
                        published_time = datetime.now(timezone.utc)
                    
                    # Check if recent
                    if not self.is_recent(published_time):
                        continue
                    
                    # Get item details
                    title = entry.get('title', 'No title')
                    summary = entry.get('summary', entry.get('description', ''))
                    link = entry.get('link', '')
                    
                    # Skip if already covered by mainstream
                    if self.check_mainstream_coverage(title, summary, link):
                        logger.debug(f"Skipping mainstream-covered: {title[:80]}...")
                        continue
                    
                    # Calculate significance score
                    significance_score = self.calculate_significance(
                        title, summary, source_id, published_time
                    )
                    
                    # Store item
                    item = {
                        "id": full_id,
                        "title": title,
                        "summary": summary,
                        "link": link,
                        "source": source_name,
                        "source_id": source_id,
                        "published": published_time.isoformat(),
                        "significance": significance_score,
                        "raw_entry": dict(entry)  # Keep for debugging
                    }
                    
                    new_items.append(item)
                    self.state["seen_items"][full_id] = {
                        "title": title,
                        "published": published_time.isoformat(),
                        "source": source_name,
                        "significance": significance_score
                    }
                    
            except Exception as e:
                logger.error(f"Error checking feed {source_name}: {e}")
        
        logger.info(f"Found {len(new_items)} new feed items")
        return new_items
    
    def calculate_significance(self, title: str, summary: str, source_id: str, 
                              published_time: datetime) -> float:
        """Calculate significance score using major news config."""
        # Import significance_filter functions
        from significance_filter import compute_significance_score
        
        # Create item dict for compatibility
        item = {
            "title": title,
            "summary": summary,
            "source": source_id,
            "published": published_time.isoformat()
        }
        
        # Use the significance filter with major news config
        score = compute_significance_score(item, self.significance_config)
        
        # Apply threshold from config
        threshold = self.significance_config.get("threshold", 6.0)
        
        # Log high-scoring items
        if score >= threshold:
            logger.info(f"High significance item: {title[:80]}... (score: {score:.2f})")
        
        return score
    
    def check_hacker_news(self):
        """Check Hacker News API for top stories."""
        logger.info("Checking Hacker News...")
        try:
            response = requests.get(self.hacker_news_api, timeout=10)
            if response.status_code == 200:
                story_ids = response.json()[:30]  # Top 30
                new_items = []
                
                for story_id in story_ids:
                    story_url = f"https://hacker-news.firebaseio.com/v0/item/{story_id}.json"
                    story_resp = requests.get(story_url, timeout=10)
                    if story_resp.status_code == 200:
                        story = story_resp.json()
                        
                        # Skip if no title or URL
                        if not story.get('title') or not story.get('url'):
                            continue
                        
                        # Check if already seen
                        item_hash = self.get_feed_hash(self.hacker_news_api, str(story_id))
                        full_id = f"hackernews:{item_hash}"
                        
                        if full_id in self.state["seen_items"]:
                            continue
                        
                        # Parse time
                        if story.get('time'):
                            published_time = datetime.fromtimestamp(story['time'], tz=timezone.utc)
                        else:
                            published_time = datetime.now(timezone.utc)
                        
                        # Check if recent
                        if not self.is_recent(published_time):
                            continue
                        
                        # Get details
                        title = story.get('title', '')
                        summary = f"Score: {story.get('score', 0)} | Comments: {story.get('descendants', 0)}"
                        link = story.get('url', f"https://news.ycombinator.com/item?id={story_id}")
                        
                        # Skip if mainstream covered
                        if self.check_mainstream_coverage(title, summary, link):
                            continue
                        
                        # Calculate significance
                        significance_score = self.calculate_significance(
                            title, summary, "hackernews", published_time
                        )
                        
                        item = {
                            "id": full_id,
                            "title": title,
                            "summary": summary,
                            "link": link,
                            "source": "Hacker News",
                            "source_id": "hackernews",
                            "published": published_time.isoformat(),
                            "significance": significance_score,
                            "raw_story": story
                        }
                        
                        new_items.append(item)
                        self.state["seen_items"][full_id] = {
                            "title": title,
                            "published": published_time.isoformat(),
                            "source": "Hacker News",
                            "significance": significance_score
                        }
                
                logger.info(f"Found {len(new_items)} new Hacker News items")
                return new_items
                
        except Exception as e:
            logger.error(f"Error checking Hacker News: {e}")
        
        return []
    
    def check_nasdaq_halts(self):
        """Check for NASDAQ trading halts."""
        logger.info("Checking NASDAQ trading halts...")
        try:
            halts = scrape_trade_halts()
            new_items = []
            title_pattern = re.compile(
                r"^(?P<symbol>[A-Z0-9\.\-]+)\s+halted\s+at\s+(?P<time>.+?)\s+ET\s+\((?P<reason>.+)\)$",
                re.IGNORECASE
            )
            
            for halt in halts:
                halt_id = halt.get('item_id', halt.get('title', ''))
                # Generate ID
                item_hash = self.get_feed_hash("nasdaq_halts", halt_id)
                full_id = f"nasdaq_halt:{item_hash}"
                
                if full_id in self.state["seen_items"]:
                    continue
                
                # Parse time from feed item
                published_str = halt.get('published', '')
                try:
                    published_time = datetime.fromisoformat(published_str.replace('Z', '+00:00'))
                except Exception:
                    published_time = datetime.now(timezone.utc)
                
                title_text = halt.get('title', '').strip()
                match = title_pattern.match(title_text)
                if match:
                    symbol = match.group('symbol').upper()
                    reason = match.group('reason').strip()
                else:
                    symbol = "Unknown"
                    reason = "Unknown"
                
                # Create title and summary
                title = f"NASDAQ Trading Halt: {symbol} - {reason}"
                summary = halt.get('summary', '') or f"Symbol: {symbol}, Reason: {reason}"
                link = halt.get('link') or "https://www.nasdaqtrader.com/Trader.aspx?id=TradeHalts"
                
                # Calculate significance
                significance_score = self.calculate_significance(
                    title, summary, "nasdaq_halt", published_time
                )
                
                item = {
                    "id": full_id,
                    "title": title,
                    "summary": summary,
                    "link": link,
                    "source": "NASDAQ Halts",
                    "source_id": "nasdaq_halt",
                    "published": published_time.isoformat(),
                    "significance": significance_score,
                    "raw_halt": halt
                }
                
                new_items.append(item)
                self.state["seen_items"][full_id] = {
                    "title": title,
                    "published": published_time.isoformat(),
                    "source": "NASDAQ Halts",
                    "significance": significance_score
                }
            
            logger.info(f"Found {len(new_items)} new NASDAQ halt items")
            return new_items
            
        except Exception as e:
            logger.error(f"Error checking NASDAQ halts: {e}")
            return []
    
    def check_github_trending(self):
        """Check GitHub for trending repositories."""
        logger.info("Checking GitHub trending...")
        try:
            trending_repos = github_trending.fetch_trending_repositories()
            new_items = []
            
            for repo in trending_repos:
                # Generate ID
                repo_id = repo.get('full_name', '')
                item_hash = self.get_feed_hash("github_trending", repo_id)
                full_id = f"github_trending:{item_hash}"
                
                if full_id in self.state["seen_items"]:
                    continue
                
                # Parse time
                created_at = repo.get('created_at', '')
                try:
                    if created_at:
                        published_time = datetime.fromisoformat(created_at.replace('Z', '+00:00'))
                    else:
                        published_time = datetime.now(timezone.utc)
                except:
                    published_time = datetime.now(timezone.utc)
                
                # Check if recent (within 7 days for trending)
                now = datetime.now(timezone.utc)
                if (now - published_time) > timedelta(days=7):
                    continue
                
                # Create title and summary
                name = repo.get('full_name', 'Unknown')
                stars = repo.get('stargazers_count', 0)
                description = repo.get('description', '')
                title = f"GitHub Trending: {name} ({stars} stars)"
                summary = description
                link = repo.get('html_url', '')
                
                # Skip if mainstream covered
                if self.check_mainstream_coverage(title, summary, link):
                    continue
                
                # Calculate significance
                significance_score = self.calculate_significance(
                    title, summary, "github_trending", published_time
                )
                
                item = {
                    "id": full_id,
                    "title": title,
                    "summary": summary,
                    "link": link,
                    "source": "GitHub Trending",
                    "source_id": "github_trending",
                    "published": published_time.isoformat(),
                    "significance": significance_score,
                    "raw_repo": repo
                }
                
                new_items.append(item)
                self.state["seen_items"][full_id] = {
                    "title": title,
                    "published": published_time.isoformat(),
                    "source": "GitHub Trending",
                    "significance": significance_score
                }
            
            logger.info(f"Found {len(new_items)} new GitHub trending items")
            return new_items
            
        except Exception as e:
            logger.error(f"Error checking GitHub trending: {e}")
            return []
    
    def generate_post_filename(self, item: Dict, timestamp: str = None) -> str:
        """Generate filename for a post."""
        if timestamp is None:
            timestamp = datetime.now().strftime("%Y-%m-%d-%H-%M-%S")
        
        # Create slug from title
        title_slug = re.sub(r'[^a-zA-Z0-9]+', '-', item["title"].lower())
        title_slug = re.sub(r'^-+|-+$', '', title_slug)
        title_slug = title_slug[:50]  # Limit length
        
        # Add hash for uniqueness
        item_hash = hashlib.md5(item["id"].encode()).hexdigest()[:6]
        
        return f"_posts/{timestamp}-{item['source_id']}-{item_hash}.md"
    
    def create_post_content(self, item: Dict) -> str:
        """Create Jekyll post content."""
        # Parse published time
        try:
            published_dt = datetime.fromisoformat(item["published"].replace('Z', '+00:00'))
            formatted_date = published_dt.strftime("%Y-%m-%d %H:%M:%S %z")
        except:
            formatted_date = item["published"]
        
        # Escape double quotes for YAML frontmatter title
        safe_title = item["title"].replace('"', '\\"')
        
        # Create content
        content = f"""---
layout: post
title: "{safe_title}"
date: {item['published']}
source: {item['source']}
source_url: {item['link']}
significance: {item.get('significance', 0):.2f}
---

{item.get('summary', '')}

**Source:** [{item['source']}]({item['link']})

**Published:** {formatted_date}

**Significance Score:** {item.get('significance', 0):.2f}

[View original]({item['link']})
"""
        return content
    
    def git_commit_and_push(self, filenames: List[str]) -> bool:
        """Add files, commit with timestamped message, and push to origin/main."""
        if not filenames:
            logger.warning("No filenames provided for git commit; skipping.")
            return False
        
        if not self.enable_git_commit:
            logger.info("Git commit/push disabled; skipping.")
            return True
        
        repo_root = Path(__file__).resolve().parent
        timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S %Z")
        commit_msg = f"Auto-publish {len(filenames)} international stories at {timestamp}"
        
        try:
            add_result = subprocess.run(
                ["git", "add", *filenames],
                cwd=repo_root,
                capture_output=True,
                text=True
            )
            if add_result.returncode != 0:
                logger.error(f"Git add failed: {add_result.stderr.strip() or add_result.stdout.strip()}")
                return False
            
            commit_result = subprocess.run(
                ["git", "commit", "-m", commit_msg],
                cwd=repo_root,
                capture_output=True,
                text=True
            )
            if commit_result.returncode != 0:
                logger.error(f"Git commit failed: {commit_result.stderr.strip() or commit_result.stdout.strip()}")
                return False
            
            push_result = subprocess.run(
                ["git", "push", "origin", "main"],
                cwd=repo_root,
                capture_output=True,
                text=True
            )
            if push_result.returncode != 0:
                logger.error(f"Git push failed: {push_result.stderr.strip() or push_result.stdout.strip()}")
                return False
            
            logger.info("Git commit and push completed successfully.")
            return True
        except Exception as e:
            logger.error(f"Error during git commit/push: {e}")
            return False
    
    def publish_story(self, item: Dict):
        """Publish a story as a Jekyll post."""
        try:
            # Generate filename
            filename = self.generate_post_filename(item)
            post_path = Path(filename)
            post_path.parent.mkdir(exist_ok=True)
            
            # Create content
            content = self.create_post_content(item)
            
            # Write file
            with open(post_path, 'w') as f:
                f.write(content)
            
            logger.info(f"Published: {item['title'][:80]}... to {filename}")
            
            # Add to published stories
            self.state.setdefault("published_stories", []).append({
                "id": item["id"],
                "title": item["title"],
                "filename": filename,
                "published_at": datetime.now(timezone.utc).isoformat(),
                "significance": item.get("significance", 0)
            })
            
            self.git_commit_and_push([filename])
            
            return True
            
        except Exception as e:
            logger.error(f"Error publishing story: {e}")
            return False
    
    def run_monitoring_cycle(self):
        """Run a full monitoring cycle."""
        logger.info("=" * 60)
        logger.info("Starting monitoring cycle")
        logger.info("=" * 60)
        
        all_new_items = []
        
        # Check various sources
        all_new_items.extend(self.check_rss_feeds())
        all_new_items.extend(self.check_hacker_news())
        all_new_items.extend(self.check_nasdaq_halts())
        all_new_items.extend(self.check_github_trending())
        
        # Sort by significance (highest first)
        all_new_items.sort(key=lambda x: x.get("significance", 0), reverse=True)
        
        # Publish high-significance items
        threshold = self.significance_config.get("threshold", 7.0)
        published_count = 0
        
        for item in all_new_items:
            significance = item.get("significance", 0)
            if significance >= threshold:
                if self.publish_story(item):
                    published_count += 1
        
        # Save state
        self.state["last_check"] = datetime.now(timezone.utc).isoformat()
        self.save_state()
        
        logger.info(f"Cycle complete. Found {len(all_new_items)} new items, published {published_count}.")
        return published_count
    
    def run_continuous(self, interval_seconds: int = 60):
        """Run continuous monitoring."""
        logger.info(f"Starting continuous monitoring (interval: {interval_seconds}s)")
        try:
            while True:
                self.run_monitoring_cycle()
                logger.info(f"Sleeping for {interval_seconds} seconds...")
                time.sleep(interval_seconds)
        except KeyboardInterrupt:
            logger.info("Monitoring stopped by user")
        except Exception as e:
            logger.error(f"Error in continuous monitoring: {e}")

def main():
    """Main entry point."""
    import argparse
    
    parser = argparse.ArgumentParser(description="International News Monitor")
    parser.add_argument("--continuous", action="store_true", help="Run continuously")
    parser.add_argument("--interval", type=int, default=60, help="Interval in seconds for continuous mode")
    parser.add_argument("--single", action="store_true", help="Run a single cycle")
    
    args = parser.parse_args()
    
    monitor = InternationalNewsMonitor()
    
    if args.continuous:
        monitor.run_continuous(args.interval)
    elif args.single:
        monitor.run_monitoring_cycle()
    else:
        # Default: single cycle
        monitor.run_monitoring_cycle()

if __name__ == "__main__":
    main()
