#!/usr/bin/env python3
"""
Breaking news monitoring system for DeepSeek-V3.2
Monitors various upstream sources for news before mainstream outlets pick it up.

Enhancements:
- Broader source coverage (SEC, USGS, NOAA, GitHub releases, Hacker News, arXiv, IETF, CVE/NASA).
- Stronger duplicate protection via timestamp + item hash filenames.
- Mainstream detection over title + summary.
- Lightweight verification against expected domains and reachability.
- Optional manual review flag; supports one-off or daemon mode.
"""

import argparse
import hashlib
import json
import logging
import time
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Optional

import feedparser
import requests

logger = logging.getLogger("deepseek.monitor")


class NewsMonitor:
    def __init__(
        self,
        data_dir: str = "data",
        manual_review: bool = False,
        entry_limit: int = 10,
        timeout: int = 10,
    ):
        self.data_dir = Path(data_dir)
        self.data_dir.mkdir(exist_ok=True)
        self.posts_dir = Path("_posts")
        self.posts_dir.mkdir(exist_ok=True)
        self.manual_review = manual_review
        self.entry_limit = entry_limit
        self.timeout = timeout
        self.state_file = self.data_dir / "monitor_state.json"
        self.feeds = self._build_feed_catalog()
        self.load_state()

    @staticmethod
    def _build_feed_catalog() -> List[Dict[str, object]]:
        """Catalog of feeds with expected domains for light verification."""
        return [
            # Regulatory / official
            {
                "url": "https://www.sec.gov/rss?divisions=corpfin",
                "source": "sec",
                "domains": ["sec.gov"],
            },
            {
                "url": "https://earthquake.usgs.gov/earthquakes/feed/v1.0/summary/all_hour.atom",
                "source": "usgs",
                "domains": ["earthquake.usgs.gov"],
            },
            {
                "url": "https://alerts.weather.gov/cap/us.php?x=0",
                "source": "noaa",
                "domains": ["weather.gov", "noaa.gov"],
            },
            {
                "url": "https://nvd.nist.gov/feeds/xml/cve/misc/nvd-rss.xml",
                "source": "cve",
                "domains": ["nvd.nist.gov"],
            },
            {
                "url": "https://www.nasa.gov/rss/dyn/breaking_news.rss",
                "source": "nasa",
                "domains": ["nasa.gov"],
            },
            # Open research / drafts
            {
                "url": "https://export.arxiv.org/rss/cs.AI",
                "source": "arxiv_cs_ai",
                "domains": ["arxiv.org"],
            },
            {
                "url": "https://export.arxiv.org/rss/cs.CL",
                "source": "arxiv_cs_cl",
                "domains": ["arxiv.org"],
            },
            {
                "url": "https://export.arxiv.org/rss/cs.LG",
                "source": "arxiv_cs_lg",
                "domains": ["arxiv.org"],
            },
            {
                "url": "https://datatracker.ietf.org/doc/feed/",
                "source": "ietf_drafts",
                "domains": ["datatracker.ietf.org"],
            },
            # Developer ecosystems
            {
                "url": "https://github.com/tensorflow/tensorflow/releases.atom",
                "source": "github_tensorflow",
                "domains": ["github.com"],
            },
            {
                "url": "https://github.com/pytorch/pytorch/releases.atom",
                "source": "github_pytorch",
                "domains": ["github.com"],
            },
            {
                "url": "https://github.com/huggingface/transformers/releases.atom",
                "source": "github_hf_transformers",
                "domains": ["github.com"],
            },
            {
                "url": "https://github.com/openai/openai-python/releases.atom",
                "source": "github_openai_sdk",
                "domains": ["github.com"],
            },
            # Community / security / misc
            {
                "url": "https://hnrss.org/frontpage",
                "source": "hacker_news",
                "domains": ["news.ycombinator.com"],
            },
        ]

    def load_state(self) -> None:
        if self.state_file.exists():
            with open(self.state_file, "r") as f:
                self.state = json.load(f)
        else:
            self.state = {"last_check": None, "seen_items": {}, "published_stories": []}

    def save_state(self) -> None:
        with open(self.state_file, "w") as f:
            json.dump(self.state, f, indent=2)

    def check_rss_feeds(self) -> List[Dict[str, str]]:
        """Check RSS feeds from upstream sources with verification and dedupe."""
        new_items: List[Dict[str, str]] = []
        for feed in self.feeds:
            url = feed["url"]
            source = feed["source"]
            logger.info("Checking feed: %s", url)
            try:
                parsed = feedparser.parse(url)
            except Exception as exc:  # feedparser can throw
                logger.error("Error parsing feed %s: %s", url, exc)
                continue

            for entry in parsed.entries[: self.entry_limit]:
                item_id = f"{source}:{entry.get('id', entry.get('link', ''))}"
                if item_id in self.state["seen_items"]:
                    continue

                pub_time = self._extract_pub_time(entry)
                if datetime.utcnow() - pub_time > timedelta(hours=24):
                    continue

                summary = entry.get("summary", "")
                title = entry.get("title", "").strip() or "Untitled"
                link = entry.get("link", "")

                if self.check_mainstream_coverage(title, summary, link):
                    logger.debug("Skipping mainstream-covered item: %s", title)
                    self.state["seen_items"][item_id] = True
                    continue

                if not self.verify_item(link, feed.get("domains")):
                    logger.debug("Skipping unverifiable item: %s", link)
                    self.state["seen_items"][item_id] = True
                    continue

                new_items.append(
                    {
                        "source": source,
                        "title": title,
                        "link": link,
                        "summary": summary,
                        "published": pub_time.isoformat(),
                        "item_id": item_id,
                    }
                )
                self.state["seen_items"][item_id] = True

        return new_items

    @staticmethod
    def _extract_pub_time(entry) -> datetime:
        published = entry.get("published_parsed") or entry.get("updated_parsed")
        if published:
            return datetime.utcfromtimestamp(time.mktime(published))
        return datetime.utcnow()

    def check_mainstream_coverage(self, title: str, summary: str, link: str) -> bool:
        """Check if news has already been covered by mainstream outlets."""
        mainstream_keywords = [
            "Reuters",
            "AP",
            "Associated Press",
            "Bloomberg",
            "AFP",
            "CNN",
            "BBC",
            "New York Times",
            "Washington Post",
            "Wall Street Journal",
            "WSJ",
            "Financial Times",
            "The Guardian",
            "Fox News",
            "NPR",
        ]

        haystack = " ".join([title, summary, link]).lower()
        return any(keyword.lower() in haystack for keyword in mainstream_keywords)

    def verify_item(self, link: str, expected_domains: Optional[List[str]]) -> bool:
        """Lightweight verification that the item originates from the expected source."""
        if not link:
            return False

        if expected_domains:
            if not any(domain in link for domain in expected_domains):
                return False

        headers = {"User-Agent": "DeepSeekNewsMonitor/1.0 (+https://deepseek.news)"}
        try:
            response = requests.head(
                link, timeout=self.timeout, allow_redirects=True, headers=headers
            )
            if response.status_code >= 400:
                return False
        except requests.RequestException as exc:
            logger.warning("HEAD check failed for %s: %s", link, exc)
            return False

        return True

    def _slugify(self, value: str) -> str:
        return (
            "".join(ch if ch.isalnum() else "-" for ch in value.lower())
            .strip("-")
            .strip()
            or "item"
        )

    def _build_filename(self, item: Dict[str, str]) -> Path:
        timestamp = datetime.utcnow().strftime("%Y-%m-%d-%H-%M-%S")
        item_hash = hashlib.sha1(item["item_id"].encode("utf-8")).hexdigest()[:8]
        slug = self._slugify(item["source"])
        return self.posts_dir / f"{timestamp}-{slug}-{item_hash}.md"

    def generate_report(self, item: Dict[str, str]) -> Path:
        """Generate a news report from a monitored item."""
        filename = self._build_filename(item)
        title = f"{item['title']} - Breaking Report"

        content = f"""---
layout: post
title: "{title}"
date: {datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S %z')}
categories: breaking-news
source: {item['source']}
author: DeepSeek-V3.2
manual_review: {str(self.manual_review).lower()}
---

# {item['title']}

**Published:** {datetime.utcnow().strftime('%B %d, %Y %H:%M UTC')}

## Summary

{item['summary'] or 'No summary provided.'}

## Sources

- Primary source: [{item['source']}]({item['link']})

## Verification

- Source domain verified: {item['link']}
- Mainstream coverage detected: False (title/summary keyword scan)

## Context

*Report automatically generated by DeepSeek News Monitoring System*
"""

        filename.write_text(content)
        return filename

    def run_monitoring_cycle(self) -> int:
        """Run one monitoring cycle."""
        logger.info("Starting monitoring cycle")
        new_items = self.check_rss_feeds()

        if new_items:
            logger.info("Found %s new potential news items", len(new_items))
            for item in new_items:
                report_path = self.generate_report(item)
                logger.info("Generated report: %s", report_path)
                self.state["published_stories"].append(
                    {
                        "filename": str(report_path),
                        "title": item["title"],
                        "published": datetime.utcnow().isoformat(),
                        "item_id": item["item_id"],
                    }
                )
        else:
            logger.info("No new items this cycle")

        self.state["last_check"] = datetime.utcnow().isoformat()
        self.save_state()
        return len(new_items)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="DeepSeek News Monitor")
    parser.add_argument(
        "--interval",
        type=int,
        default=0,
        help="If set (>0), run continuously every N seconds.",
    )
    parser.add_argument(
        "--manual-review",
        action="store_true",
        help="Flag generated posts for manual review instead of auto-publish.",
    )
    parser.add_argument(
        "--entry-limit",
        type=int,
        default=10,
        help="Max items to scan per feed per cycle.",
    )
    parser.add_argument(
        "--timeout",
        type=int,
        default=10,
        help="Network timeout (seconds) for verification requests.",
    )
    parser.add_argument(
        "--log-level",
        default="INFO",
        help="Logging level (DEBUG, INFO, WARNING, ERROR).",
    )
    return parser.parse_args()


def setup_logging(level: str) -> None:
    logging.basicConfig(
        level=getattr(logging, level.upper(), logging.INFO),
        format="%(asctime)s [%(levelname)s] %(message)s",
    )


def run_daemon(monitor: NewsMonitor, interval: int) -> None:
    """Run monitoring in a loop with delay."""
    logger.info("Running in continuous mode every %s seconds", interval)
    try:
        while True:
            monitor.run_monitoring_cycle()
            time.sleep(interval)
    except KeyboardInterrupt:
        logger.info("Monitoring interrupted by user")
    except Exception as exc:
        logger.exception("Unexpected error in daemon mode: %s", exc)


def main() -> None:
    args = parse_args()
    setup_logging(args.log_level)

    monitor = NewsMonitor(
        manual_review=args.manual_review,
        entry_limit=args.entry_limit,
        timeout=args.timeout,
    )

    if args.interval and args.interval > 0:
        run_daemon(monitor, args.interval)
    else:
        try:
            new_reports = monitor.run_monitoring_cycle()
            logger.info("Monitoring complete. Found %s new reports.", new_reports)
        except Exception as exc:
            logger.exception("Error in monitoring: %s", exc)


if __name__ == "__main__":
    main()
