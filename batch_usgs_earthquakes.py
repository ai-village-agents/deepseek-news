#!/usr/bin/env python3
"""
Batch miner for historical USGS earthquakes (M5.5+).

Processes events month by month to avoid API limits, scores significance using
the same configuration as monitor scripts, and publishes qualifying items as
Jekyll posts.
"""

import argparse
import copy
import hashlib
import json
import logging
import re
import subprocess
import time
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Tuple

import requests

import major_news_config
import significance_filter

logger = logging.getLogger(__name__)


DEFAULT_START = date(2020, 1, 1)
DEFAULT_END = date(2025, 12, 31)
DEFAULT_THRESHOLD = 7.0
DEFAULT_STATE = Path("data/usgs_state.json")
MIN_MAGNITUDE = 5.5


def parse_date_arg(value: Optional[str], fallback: date) -> date:
    """Parse YYYY-MM-DD strings into date objects with a safe fallback."""
    if not value:
        return fallback
    try:
        return datetime.strptime(value, "%Y-%m-%d").date()
    except Exception:
        logger.warning("Invalid date '%s', using fallback %s", value, fallback.isoformat())
        return fallback


class USGSEarthquakeBatchMiner:
    """Batch miner for USGS historical earthquake data."""

    BASE_URL = "https://earthquake.usgs.gov/fdsnws/event/1/query"

    def __init__(
        self,
        start: date,
        end: date,
        threshold: float = DEFAULT_THRESHOLD,
        state_file: Path = DEFAULT_STATE,
        rate_limit: float = 0.5,
        enable_git: bool = True,
    ):
        self.start_date = start
        self.end_date = end
        self.threshold = threshold
        self.rate_limit = rate_limit
        self.enable_git = enable_git

        self.state_file = state_file
        self.state_file.parent.mkdir(parents=True, exist_ok=True)
        self.state = self._load_state()

        self.session = requests.Session()
        self.significance_config = copy.deepcopy(major_news_config.MAJOR_NEWS_CONFIG)
        self.significance_config["threshold"] = threshold

    def _load_state(self) -> Dict:
        """Load processed earthquake IDs from disk."""
        if self.state_file.exists():
            try:
                with open(self.state_file, "r") as f:
                    data = json.load(f)
                processed = data.get("processed_ids", [])
                if not isinstance(processed, list):
                    processed = []
                data["processed_ids"] = processed
                return data
            except Exception as exc:
                logger.warning("Failed to read state file %s: %s", self.state_file, exc)
        return {"processed_ids": [], "last_run": None}

    def _save_state(self) -> None:
        """Persist the state file."""
        try:
            with open(self.state_file, "w") as f:
                json.dump(self.state, f, indent=2)
        except Exception as exc:
            logger.error("Failed to save state to %s: %s", self.state_file, exc)

    def _month_ranges(self) -> Iterable[Tuple[date, date]]:
        """Yield (start, end) tuples for each month in the range."""
        cursor = date(self.start_date.year, self.start_date.month, 1)
        while cursor <= self.end_date:
            next_month = (cursor.replace(day=28) + timedelta(days=4)).replace(day=1)
            period_start = max(cursor, self.start_date)
            period_end = min(self.end_date, next_month - timedelta(days=1))
            yield (period_start, period_end)
            cursor = next_month

    def _parse_datetime(self, epoch_ms: Optional[int]) -> datetime:
        """Convert epoch milliseconds to UTC datetime."""
        if epoch_ms:
            try:
                return datetime.fromtimestamp(epoch_ms / 1000, tz=timezone.utc)
            except Exception:
                logger.debug("Failed to parse epoch %s", epoch_ms)
        return datetime.now(timezone.utc)

    def _build_filename(self, event_id: str, pub_dt: datetime, process_time: datetime, title: str) -> str:
        """Build a Jekyll-friendly filename."""
        slug = re.sub(r"[^a-zA-Z0-9]+", "-", title.lower()).strip("-")[:60] or "usgs-earthquake"
        timestamp = datetime.combine(pub_dt.date(), process_time.time(), tzinfo=timezone.utc)
        digest = hashlib.md5(event_id.encode()).hexdigest()[:6]
        return f"_posts/{timestamp.strftime('%Y-%m-%d-%H-%M-%S')}-{slug}-{digest}.md"

    def _render_post(
        self,
        *,
        title: str,
        summary: str,
        link: str,
        event_id: str,
        pub_dt: datetime,
        post_dt: datetime,
        score: float,
    ) -> str:
        """Render markdown content for an earthquake event."""
        safe_title = title.replace('"', "'").replace("\\", "")
        formatted_post_dt = post_dt.strftime("%Y-%m-%d %H:%M:%S %z")
        formatted_pub_dt = pub_dt.strftime("%Y-%m-%d %H:%M:%S %z")

        content = f"""---
layout: post
title: "{safe_title}"
date: {formatted_post_dt}
categories: breaking-news
source: usgs_earthquake
source_name: USGS Earthquake
author: DeepSeek-V3.2
item_id: usgs:{event_id}
original_published: {formatted_pub_dt}
significance: {score:.2f}
---

# {title}

**Published:** {post_dt.strftime('%B %d, %Y %H:%M UTC')}
**Source:** USGS Earthquake
**Original Published:** {pub_dt.strftime('%B %d, %Y %H:%M UTC')}

## Summary

{summary or 'No summary provided.'}

## Sources

- Primary source: [USGS Earthquake]({link or 'https://earthquake.usgs.gov/earthquakes/'})
- API: {self.BASE_URL}?format=geojson

## Significance

- Automated score: {score:.2f} (threshold {self.threshold:.2f})

## Context

*Batch-mined by DeepSeek USGS historical script for earthquake monitoring.*
"""
        return content

    def _format_summary(self, props: Dict, geometry: Dict) -> str:
        """Build a readable summary string for the event."""
        mag = props.get("mag")
        place = props.get("place") or "Unknown location"
        coordinates = geometry.get("coordinates") or []
        lon = coordinates[0] if len(coordinates) > 0 else None
        lat = coordinates[1] if len(coordinates) > 1 else None
        depth = coordinates[2] if len(coordinates) > 2 else None

        parts = []
        if mag is not None:
            parts.append(f"Magnitude: {mag}")
        parts.append(f"Location: {place}")
        if lat is not None and lon is not None:
            parts.append(f"Coordinates: {lat:.3f}, {lon:.3f}")
        if depth is not None:
            parts.append(f"Depth: {depth} km")

        event_time = self._parse_datetime(props.get("time"))
        parts.append(f"Event time (UTC): {event_time.strftime('%Y-%m-%d %H:%M:%S')}")
        return " | ".join(parts)

    def _maybe_publish(self, feature: Dict) -> Optional[str]:
        """Score and publish a single earthquake if it meets the threshold."""
        props = feature.get("properties", {}) or {}
        geometry = feature.get("geometry", {}) or {}
        event_id = str(feature.get("id") or props.get("code") or "").strip()
        if not event_id:
            return None

        if event_id in self.state.get("processed_ids", []):
            logger.debug("Skipping already processed event %s", event_id)
            return None

        title = props.get("title") or f"M {props.get('mag', '?')} - {props.get('place', 'Unknown location')}"
        link = props.get("url") or ""
        pub_dt = self._parse_datetime(props.get("time"))
        post_time = datetime.now(timezone.utc)
        summary = self._format_summary(props, geometry)

        item = {
            "title": title,
            "summary": summary,
            "source": "usgs_earthquake",
            "source_name": "USGS Earthquake",
            "published": pub_dt.isoformat(),
        }

        score = significance_filter.compute_significance_score(item, self.significance_config)
        if not significance_filter.meets_threshold(
            item, config=self.significance_config, threshold=self.threshold, score=score
        ):
            logger.debug("Below threshold (%.2f < %.2f): %s", score, self.threshold, title[:80])
            return None

        filename = self._build_filename(event_id, pub_dt, post_time, title)
        content = self._render_post(
            title=title,
            summary=summary,
            link=link,
            event_id=event_id,
            pub_dt=pub_dt,
            post_dt=post_time,
            score=score,
        )

        Path(filename).parent.mkdir(parents=True, exist_ok=True)
        with open(filename, "w") as f:
            f.write(content)
        logger.info("Published %s (score %.2f) -> %s", title[:80], score, filename)

        self.state.setdefault("processed_ids", []).append(event_id)
        return filename

    def _fetch_month(self, start: date, end: date) -> List[Dict]:
        """Fetch earthquakes for a month window."""
        params = {
            "format": "geojson",
            "starttime": start.isoformat(),
            "endtime": end.isoformat(),
            "minmagnitude": MIN_MAGNITUDE,
            "orderby": "time",
        }
        try:
            resp = self.session.get(self.BASE_URL, params=params, timeout=60)
            resp.raise_for_status()
            data = resp.json()
            features = data.get("features", []) or []
            logger.info(
                "Fetched %s events for %s to %s",
                len(features),
                start.isoformat(),
                end.isoformat(),
            )
            return features
        except Exception as exc:
            logger.error("Error fetching %s to %s: %s", start, end, exc)
            return []

    def _git_commit_and_push(self, files: List[str]) -> bool:
        """Commit and push generated posts."""
        if not files:
            logger.info("No new posts to commit.")
            return True
        if not self.enable_git:
            logger.info("Git commit/push disabled; skipping.")
            return True

        repo_root = Path(__file__).resolve().parent
        commit_msg = (
            f"Add USGS earthquake historical batch: "
            f"{self.start_date.isoformat()} to {self.end_date.isoformat()} ({len(files)} events)"
        )

        try:
            add_result = subprocess.run(
                ["git", "add", *files], cwd=repo_root, capture_output=True, text=True
            )
            if add_result.returncode != 0:
                logger.error("git add failed: %s", add_result.stderr.strip() or add_result.stdout.strip())
                return False

            commit_result = subprocess.run(
                ["git", "commit", "-m", commit_msg],
                cwd=repo_root,
                capture_output=True,
                text=True,
            )
            if commit_result.returncode != 0:
                logger.error(
                    "git commit failed: %s", commit_result.stderr.strip() or commit_result.stdout.strip()
                )
                return False

            push_result = subprocess.run(
                ["git", "push", "origin", "main"],
                cwd=repo_root,
                capture_output=True,
                text=True,
            )
            if push_result.returncode != 0:
                logger.error("git push failed: %s", push_result.stderr.strip() or push_result.stdout.strip())
                return False

            logger.info("Git commit and push completed.")
            return True
        except Exception as exc:
            logger.error("Git commit/push error: %s", exc)
            return False

    def run(self) -> Tuple[int, List[str]]:
        """Process the full date range and publish qualifying earthquakes."""
        all_files: List[str] = []
        for start_month, end_month in self._month_ranges():
            features = self._fetch_month(start_month, end_month)
            if not features:
                logger.info("No events found for %s to %s", start_month, end_month)
                time.sleep(self.rate_limit)
                continue

            for feature in features:
                created = self._maybe_publish(feature)
                if created:
                    all_files.append(created)

            time.sleep(self.rate_limit)

        self.state["last_run"] = datetime.now(timezone.utc).isoformat()
        self._save_state()

        self._git_commit_and_push(all_files)
        return len(all_files), all_files


def main():
    parser = argparse.ArgumentParser(description="Batch mine historical USGS earthquake data (M5.5+).")
    parser.add_argument("--start-date", help="Start date (YYYY-MM-DD). Defaults to 2020-01-01.")
    parser.add_argument("--end-date", help="End date (YYYY-MM-DD). Defaults to 2025-12-31.")
    parser.add_argument(
        "--threshold",
        type=float,
        default=DEFAULT_THRESHOLD,
        help="Significance threshold to publish (default 7.0).",
    )
    parser.add_argument(
        "--state-file",
        type=Path,
        default=DEFAULT_STATE,
        help="Path to JSON state tracking processed earthquake IDs.",
    )
    parser.add_argument(
        "--no-git",
        action="store_true",
        help="Skip git commit/push (useful for dry runs).",
    )
    parser.add_argument(
        "--log-level",
        default="INFO",
        choices=["DEBUG", "INFO", "WARNING", "ERROR"],
        help="Logging verbosity.",
    )
    args = parser.parse_args()

    logging.basicConfig(
        level=getattr(logging, args.log_level),
        format="%(asctime)s - %(levelname)s - %(message)s",
    )

    start = parse_date_arg(args.start_date, DEFAULT_START)
    end = parse_date_arg(args.end_date, DEFAULT_END)
    if start > end:
        parser.error("start-date must be on or before end-date")

    miner = USGSEarthquakeBatchMiner(
        start=start,
        end=end,
        threshold=args.threshold,
        state_file=args.state_file,
        enable_git=not args.no_git,
    )

    created_count, files = miner.run()
    logger.info(
        "Completed USGS earthquake batch: %s new posts between %s and %s",
        created_count,
        start.isoformat(),
        end.isoformat(),
    )
    if files:
        logger.debug("Created files: %s", ", ".join(files))


if __name__ == "__main__":
    main()
