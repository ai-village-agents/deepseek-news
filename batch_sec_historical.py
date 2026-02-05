#!/usr/bin/env python3
"""
Batch miner for historical SEC EDGAR filings (8-K, 10-Q, 10-K, 6-K, 20-F).
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
from sec_batch_fetcher import SECBatchFetcher, DEFAULT_COMPANY_LIMIT, DEFAULT_FORMS
from edgar_api import EdgarAPI, normalize_cik

logger = logging.getLogger(__name__)

DEFAULT_START = date(2024, 1, 1)
DEFAULT_END = date(2025, 12, 31)
DEFAULT_THRESHOLD = 7.0
DEFAULT_STATE = Path("data/sec_state.json")

def parse_date_arg(value: Optional[str], fallback: date) -> date:
    """Parse YYYY-MM-DD strings into date objects with a safe fallback."""
    if not value:
        return fallback
    try:
        return datetime.strptime(value, "%Y-%m-%d").date()
    except Exception:
        logger.warning("Invalid date '%s', using fallback %s", value, fallback.isoformat())
        return fallback

class SECHistoricalBatchMiner:
    """Batch miner for SEC historical filings."""
    
    def __init__(
        self,
        start: date,
        end: date,
        threshold: float = DEFAULT_THRESHOLD,
        state_file: Path = DEFAULT_STATE,
        company_limit: int = 100,
        enable_git: bool = True,
    ):
        self.start_date = start
        self.end_date = end
        self.threshold = threshold
        self.company_limit = company_limit
        self.enable_git = enable_git
        
        self.state_file = state_file
        self.state_file.parent.mkdir(parents=True, exist_ok=True)
        self.state = self._load_state()
        
        # Use default user agent from monitor_international
        self.user_agent = "DeepSeek-V3.2 News Monitor (contact: deepseek-v3.2@agentvillage.org)"
        self.fetcher = SECBatchFetcher(
            user_agent=self.user_agent,
            cache_dir="data",
            max_calls_per_second=4.0,
            inter_company_delay=0.5
        )
        self.edgar = EdgarAPI(user_agent=self.user_agent, max_calls_per_second=4.0)
        
        self.significance_config = copy.deepcopy(major_news_config.MAJOR_NEWS_CONFIG)
        self.significance_config["threshold"] = threshold
    
    def _load_state(self) -> Dict:
        """Load processed filing IDs from disk."""
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
    
    def _build_filename(self, accession: str, filing_date: date, process_time: datetime, title: str) -> str:
        """Build a Jekyll-friendly filename."""
        slug = re.sub(r"[^a-zA-Z0-9]+", "-", title.lower()).strip("-")[:60] or "sec-filing"
        timestamp = datetime.combine(filing_date, process_time.time(), tzinfo=timezone.utc)
        digest = hashlib.md5(accession.encode()).hexdigest()[:6]
        return f"_posts/{timestamp.strftime('%Y-%m-%d-%H-%M-%S')}-{slug}-{digest}.md"
    def _render_post(
        self,
        *,
        title: str,
        summary: str,
        link: str,
        accession: str,
        company_name: str,
        form_type: str,
        filing_date: date,
        post_dt: datetime,
        score: float,
    ) -> str:
        """Render markdown content for a SEC filing."""
        safe_title = title.replace('"', "'").replace("\\", "")
        formatted_post_dt = post_dt.strftime("%Y-%m-%d %H:%M:%S %z")
        formatted_filing_dt = datetime.combine(filing_date, datetime.min.time(), tzinfo=timezone.utc).strftime("%Y-%m-%d %H:%M:%S %z")
        
        content = f"""---
layout: post
title: "{safe_title}"
date: {formatted_post_dt}
categories: breaking-news
source: sec_edgar
source_name: SEC EDGAR
author: DeepSeek-V3.2
item_id: sec:{accession}
original_published: {formatted_filing_dt}
significance: {score:.2f}
---

# {title}

**Published:** {post_dt.strftime('%B %d, %Y %H:%M UTC')}
**Source:** SEC EDGAR
**Original Published:** {filing_date.isoformat()}

## Summary

{summary or 'No summary provided.'}

## Sources

- Primary source: [SEC EDGAR Filing]({link})
- Company: {company_name}
- Form type: {form_type}
- Accession number: {accession}

## Significance

- Automated score: {score:.2f} (threshold {self.threshold:.2f})

## Context

*Batch-mined by DeepSeek SEC historical script for corporate filings monitoring.*
"""
        return content
    
    def _maybe_publish(self, filing, company_name: str) -> Optional[str]:
        """Score and publish a single SEC filing if it meets the threshold."""
        from edgar_api import Filing
        
        # Convert to Filing object if needed
        if isinstance(filing, Filing):
            f = filing
        else:
            # Assume dict with fields
            f = filing
        
        accession = f.accession_number
        if accession in self.state.get("processed_ids", []):
            logger.debug("Skipping already processed filing %s", accession)
            return None
        
        # Check filing date range
        if f.filing_date < self.start_date or f.filing_date > self.end_date:
            logger.debug("Filing date %s outside range %s to %s", 
                         f.filing_date, self.start_date, self.end_date)
            return None
        
        title = f"{company_name or f.cik} - {f.form_type}"
        if f.description:
            title += f" - {f.description[:50]}"
        summary = f"{f.form_type} filing for {company_name or f.cik}"
        if f.report_date:
            summary += f" (report date {f.report_date.isoformat()})"
        if f.description:
            summary += f": {f.description}"
        
        item = {
            "title": title,
            "summary": summary,
            "source": "sec_edgar",
            "source_name": "SEC EDGAR",
            "published": f.filing_date.isoformat(),
        }
        
        score = significance_filter.compute_significance_score(item, self.significance_config)
        if not significance_filter.meets_threshold(
            item, config=self.significance_config, threshold=self.threshold, score=score
        ):
            logger.debug("Below threshold (%.2f < %.2f): %s", score, self.threshold, title[:80])
            return None
        
        post_time = datetime.now(timezone.utc)
        filename = self._build_filename(accession, f.filing_date, post_time, title)
        content = self._render_post(
            title=title,
            summary=summary,
            link=f.url,
            accession=accession,
            company_name=company_name or f.cik,
            form_type=f.form_type,
            filing_date=f.filing_date,
            post_dt=post_time,
            score=score,
        )
        
        Path(filename).parent.mkdir(parents=True, exist_ok=True)
        with open(filename, "w") as fh:
            fh.write(content)
        logger.info("Published %s (score %.2f) -> %s", title[:80], score, filename)
        
        self.state.setdefault("processed_ids", []).append(accession)
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
            f"Add SEC EDGAR historical batch: "
            f"{self.start_date.isoformat()} to {self.end_date.isoformat()} ({len(files)} filings)"
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
        """Process companies and publish qualifying filings."""
        all_files: List[str] = []
        
        # Get company list
        try:
            companies = self.fetcher.download_company_tickers()
            logger.info("Loaded %s companies", len(companies))
        except Exception as exc:
            logger.error("Failed to load company tickers: %s", exc)
            return 0, []
        
        # Limit companies
        selected_companies = companies[:self.company_limit]
        logger.info("Processing %s companies", len(selected_companies))
        
        for i, company in enumerate(selected_companies, 1):
            cik = str(company.get("cik", ""))
            ticker = company.get("ticker", "")
            name = company.get("title", "")
            
            if not cik:
                logger.debug("Skipping company without CIK")
                continue
            
            logger.info("[%s/%s] Processing %s (%s)", i, len(selected_companies), name or ticker, cik)
            
            try:
                # Fetch submissions to get recent filings
                submissions = self.edgar.get_company_submissions(cik)
                recent_data = submissions.get("filings", {}).get("recent", {})
                
                if not recent_data:
                    logger.debug("No recent filings for CIK %s", cik)
                    continue
                
                # Parse filings from recent data
                forms = recent_data.get("form", [])
                filing_dates = recent_data.get("filingDate", [])
                accession_nums = recent_data.get("accessionNumber", [])
                primary_docs = recent_data.get("primaryDocument", [])
                descriptions = recent_data.get("primaryDocDescription", [])
                report_dates = recent_data.get("reportDate", [])
                file_numbers = recent_data.get("fileNumber", [])
                items = recent_data.get("items", [])
                
                for idx in range(len(forms)):
                    form_type = forms[idx]
                    if not form_type or form_type.upper() not in DEFAULT_FORMS:
                        continue
                    
                    # Parse filing date
                    try:
                        filing_date = datetime.strptime(filing_dates[idx], "%Y-%m-%d").date()
                    except Exception:
                        continue
                    
                    # Check date range
                    if filing_date < self.start_date or filing_date > self.end_date:
                        continue
                    
                    # Create Filing object
                    from edgar_api import Filing
                    filing = Filing(
                        cik=cik,
                        company_name=name,
                        form_type=form_type,
                        accession_number=accession_nums[idx],
                        filing_date=filing_date,
                        report_date=self._parse_date_safe(report_dates[idx] if idx < len(report_dates) else None),
                        primary_document=primary_docs[idx] if idx < len(primary_docs) else None,
                        file_number=file_numbers[idx] if idx < len(file_numbers) else None,
                        description=descriptions[idx] if idx < len(descriptions) else None,
                        url=self._build_filing_url(cik, accession_nums[idx], primary_docs[idx] if idx < len(primary_docs) else None),
                        items=items[idx] if idx < len(items) else None,
                    )
                    
                    created = self._maybe_publish(filing, name)
                    if created:
                        all_files.append(created)
                
                # Rate limiting between companies
                time.sleep(0.5)
                
            except Exception as exc:
                logger.error("Error processing CIK %s: %s", cik, exc)
                continue
        
        self.state["last_run"] = datetime.now(timezone.utc).isoformat()
        self._save_state()
        
        self._git_commit_and_push(all_files)
        return len(all_files), all_files
    
    def _parse_date_safe(self, date_str: Optional[str]) -> Optional[date]:
        if not date_str:
            return None
        try:
            return datetime.strptime(date_str, "%Y-%m-%d").date()
        except Exception:
            return None
    
    def _build_filing_url(self, cik: str, accession: str, primary_doc: Optional[str]) -> str:
        """Build SEC EDGAR filing URL."""
        cik_norm = normalize_cik(cik)
        accession_compact = accession.replace("-", "")
        base_path = f"https://www.sec.gov/Archives/edgar/data/{int(cik_norm)}/{accession_compact}"
        if primary_doc:
            return f"{base_path}/{primary_doc}"
        return base_path
def main():
    parser = argparse.ArgumentParser(description="Batch mine historical SEC EDGAR filings (8-K, 10-Q, 10-K, 6-K, 20-F).")
    parser.add_argument("--start-date", help="Start date (YYYY-MM-DD). Defaults to 2024-01-01.")
    parser.add_argument("--end-date", help="End date (YYYY-MM-DD). Defaults to 2025-12-31.")
    parser.add_argument(
        "--threshold",
        type=float,
        default=DEFAULT_THRESHOLD,
        help="Significance threshold to publish (default 7.0).",
    )
    parser.add_argument(
        "--company-limit",
        type=int,
        default=100,
        help="Number of companies to process (default 100).",
    )
    parser.add_argument(
        "--state-file",
        type=Path,
        default=DEFAULT_STATE,
        help="Path to JSON state tracking processed filing IDs.",
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
    
    miner = SECHistoricalBatchMiner(
        start=start,
        end=end,
        threshold=args.threshold,
        state_file=args.state_file,
        company_limit=args.company_limit,
        enable_git=not args.no_git,
    )
    
    created_count, files = miner.run()
    logger.info(
        "Completed SEC EDGAR batch: %s new posts between %s and %s",
        created_count,
        start.isoformat(),
        end.isoformat(),
    )
    if files:
        logger.debug("Created files: %s", ", ".join(files))

if __name__ == "__main__":
    main()
