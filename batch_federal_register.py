#!/usr/bin/env python3
"""
Batch miner for historical Federal Register documents.

For each date in the configured range, fetches every Federal Register document
via the API, scores significance using the same configuration as
monitor_international.py, and publishes qualifying items as Jekyll posts.
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
from typing import Dict, List, Optional, Tuple

import requests

import major_news_config
import significance_filter

logger = logging.getLogger(__name__)


DEFAULT_START = date(2026, 1, 1)
DEFAULT_END = date(2026, 2, 3)
DEFAULT_THRESHOLD = 6.0
DEFAULT_STATE = Path("data/federal_register_state.json")


def parse_date_arg(value: Optional[str], fallback: date) -> date:
    """Parse YYYY-MM-DD strings into date objects with a safe fallback."""
    if not value:
        return fallback
    try:
        return datetime.strptime(value, "%Y-%m-%d").date()
    except Exception:
        logger.warning("Invalid date '%s', using fallback %s", value, fallback.isoformat())
        return fallback


class FederalRegisterBatchMiner:
    """Batch miner that mirrors Federal Register feed parsing logic."""

    BASE_URL = "https://www.federalregister.gov/api/v1/documents"

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
        # Align the config threshold with the CLI-provided value
        self.significance_config["threshold"] = threshold

    def _load_state(self) -> Dict:
        """Load processed document IDs from disk."""
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

    def _date_range(self) -> List[date]:
        """Inclusive range of dates to process."""
        days = []
        cursor = self.start_date
        while cursor <= self.end_date:
            days.append(cursor)
            cursor += timedelta(days=1)
        return days

    def fetch_documents_for_date(self, target_date: date) -> List[Dict]:
        """Fetch every document for a single publication date."""
        params = {
            "per_page": 100,
            "page": 1,
            "order": "newest",
            "conditions[publication_date][gte]": target_date.isoformat(),
            "conditions[publication_date][lte]": target_date.isoformat(),
        }

        results: List[Dict] = []
        page = 1
        total_pages = 1

        while page <= total_pages:
            params["page"] = page
            try:
                resp = self.session.get(self.BASE_URL, params=params, timeout=30)
                resp.raise_for_status()
                data = resp.json()
            except Exception as exc:
                logger.error("Error fetching %s page %s: %s", target_date, page, exc)
                break

            total_pages = data.get("total_pages", total_pages)
            docs = data.get("results", [])
            results.extend(docs)
            logger.info(
                "Fetched %s docs for %s (page %s/%s)",
                len(docs),
                target_date.isoformat(),
                page,
                total_pages,
            )
            page += 1
            if page <= total_pages:
                time.sleep(self.rate_limit)

        return results

    def _parse_publication_datetime(self, published: Optional[str]) -> datetime:
        """Parse publication_date strings into UTC datetimes."""
        if published:
            try:
                return datetime.strptime(published, "%Y-%m-%d").replace(tzinfo=timezone.utc)
            except Exception:
                logger.debug("Could not parse publication date '%s'", published)
        return datetime.now(timezone.utc)

    def _build_filename(self, doc_id: str, pub_dt: datetime, process_time: datetime, title: str) -> str:
        """
        Build a Jekyll-friendly filename.

        Requirement: use document publication date + current time for the filename.
        """
        slug = re.sub(r"[^a-zA-Z0-9]+", "-", title.lower()).strip("-")[:60] or "federal-register"
        timestamp = datetime.combine(pub_dt.date(), process_time.time(), tzinfo=timezone.utc)
        digest = hashlib.md5(doc_id.encode()).hexdigest()[:6]
        return f"_posts/{timestamp.strftime('%Y-%m-%d-%H-%M-%S')}-{slug}-{digest}.md"

    def _render_post(
        self,
        *,
        title: str,
        summary: str,
        link: str,
        doc_id: str,
        pub_dt: datetime,
        post_dt: datetime,
        score: float,
    ) -> str:
        """Render markdown content for a Federal Register document."""
        safe_title = title.replace('"', "'").replace("\\", "")
        formatted_post_dt = post_dt.strftime("%Y-%m-%d %H:%M:%S %z")
        formatted_pub_dt = pub_dt.strftime("%Y-%m-%d %H:%M:%S %z")

        content = f"""---
layout: post
title: "{safe_title}"
date: {formatted_post_dt}
categories: breaking-news
source: federal_register
source_name: Federal Register
author: DeepSeek-V3.2
item_id: federal_register:{doc_id}
original_published: {formatted_pub_dt}
significance: {score:.2f}
---

# {title}

**Published:** {post_dt.strftime('%B %d, %Y %H:%M UTC')}
**Source:** Federal Register
**Original Published:** {pub_dt.strftime('%B %d, %Y %H:%M UTC')}
**Document Number:** {doc_id}

## Summary

{summary or 'No summary provided.'}

## Sources

- Primary source: [Federal Register]({link or 'https://www.federalregister.gov/'})
- API: https://www.federalregister.gov/api/v1/documents/{doc_id}

## Significance

- Automated score: {score:.2f} (threshold {self.threshold:.2f})

## Context

*Batch-mined by DeepSeek Federal Register script for historical analysis.*
"""
        return content

    def _maybe_publish(self, doc: Dict) -> Optional[str]:
        """Score and publish a single document if it meets the threshold."""
        doc_id = str(doc.get("document_number") or doc.get("id") or doc.get("html_url") or "").strip()
        if not doc_id:
            return None

        if doc_id in self.state.get("processed_ids", []):
            logger.debug("Skipping already processed doc %s", doc_id)
            return None

        title = doc.get("title") or "Federal Register Document"
        summary = (doc.get("abstract") or doc.get("summary") or "").strip()
        link = doc.get("html_url") or doc.get("pdf_url") or ""
        publication_date = doc.get("publication_date") or doc.get("public_inspection_date")

        pub_dt = self._parse_publication_datetime(publication_date)
        post_time = datetime.now(timezone.utc)

        item = {
            "title": title,
            "summary": summary,
            "source": "federal_register",
            "source_id": "federal_register",
            "published": pub_dt.isoformat(),
        }

        score = significance_filter.compute_significance_score(item, self.significance_config)
        if not significance_filter.meets_threshold(
            item, config=self.significance_config, threshold=self.threshold, score=score
        ):
            logger.debug(
                "Below threshold (%.2f < %.2f): %s", score, self.threshold, title[:80]
            )
            return None

        filename = self._build_filename(doc_id, pub_dt, post_time, title)
        content = self._render_post(
            title=title,
            summary=summary,
            link=link,
            doc_id=doc_id,
            pub_dt=pub_dt,
            post_dt=post_time,
            score=score,
        )

        Path(filename).parent.mkdir(parents=True, exist_ok=True)
        with open(filename, "w") as f:
            f.write(content)
        logger.info("Published %s (score %.2f) -> %s", title[:80], score, filename)

        self.state.setdefault("processed_ids", []).append(doc_id)
        return filename

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
            f"Add {len(files)} Federal Register posts "
            f"({self.start_date.isoformat()} to {self.end_date.isoformat()})"
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
        """Process the full date range and publish qualifying documents."""
        all_files: List[str] = []
        for day in self._date_range():
            docs = self.fetch_documents_for_date(day)
            if not docs:
                logger.info("No documents found for %s", day.isoformat())
                continue
            for doc in docs:
                created = self._maybe_publish(doc)
                if created:
                    all_files.append(created)

        self.state["last_run"] = datetime.now(timezone.utc).isoformat()
        self._save_state()

        self._git_commit_and_push(all_files)
        return len(all_files), all_files


def main():
    parser = argparse.ArgumentParser(description="Batch mine historical Federal Register documents.")
    parser.add_argument("--start-date", help="Start date (YYYY-MM-DD). Defaults to 2026-01-01.")
    parser.add_argument("--end-date", help="End date (YYYY-MM-DD). Defaults to 2026-02-03.")
    parser.add_argument(
        "--threshold",
        type=float,
        default=DEFAULT_THRESHOLD,
        help="Significance threshold to publish (default 6.0).",
    )
    parser.add_argument(
        "--state-file",
        type=Path,
        default=DEFAULT_STATE,
        help="Path to JSON state tracking processed document IDs.",
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

    miner = FederalRegisterBatchMiner(
        start=start,
        end=end,
        threshold=args.threshold,
        state_file=args.state_file,
        enable_git=not args.no_git,
    )

    created_count, files = miner.run()
    logger.info("Completed Federal Register batch: %s new posts", created_count)
    if files:
        logger.debug("Created files: %s", ", ".join(files))


if __name__ == "__main__":
    main()
