#!/usr/bin/env python3
"""
Lightweight SEC EDGAR API helper.
Supports fetching recent filings (8-K, 10-Q, and other material forms),
pulling companyfacts/submissions data, and formatting filings for RSS usage.
"""

from __future__ import annotations

import logging
import threading
import time
from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone
from typing import Dict, List, Optional

import requests

try:  # Optional dependency used elsewhere in the repo
    from feedparser.util import FeedParserDict
except Exception:  # pragma: no cover - fallback when feedparser isn't installed

    class FeedParserDict(dict):
        """Minimal shim used when feedparser is unavailable."""

        pass


logger = logging.getLogger(__name__)

SUBMISSIONS_URL = "https://data.sec.gov/submissions/CIK{cik}.json"
COMPANYFACTS_URL = "https://data.sec.gov/api/xbrl/companyfacts/CIK{cik}.json"


def normalize_cik(cik: str) -> str:
    """Return zero-padded 10-digit CIK."""
    digits = "".join(ch for ch in str(cik) if ch.isdigit())
    if not digits:
        raise ValueError(f"Invalid CIK: {cik!r}")
    return digits.zfill(10)


class RateLimiter:
    """Simple thread-safe rate limiter using a minimum interval between calls."""

    def __init__(self, max_calls_per_second: float = 4.0) -> None:
        if max_calls_per_second <= 0:
            raise ValueError("max_calls_per_second must be positive")
        self.min_interval = 1.0 / max_calls_per_second
        self._lock = threading.Lock()
        self._last_call = 0.0

    def wait(self) -> None:
        with self._lock:
            now = time.monotonic()
            elapsed = now - self._last_call
            if elapsed < self.min_interval:
                time.sleep(self.min_interval - elapsed)
            self._last_call = time.monotonic()


@dataclass
class Filing:
    cik: str
    company_name: Optional[str]
    form_type: str
    accession_number: str
    filing_date: date
    report_date: Optional[date]
    primary_document: Optional[str]
    file_number: Optional[str]
    description: Optional[str]
    url: str
    items: Optional[str]


class EdgarAPI:
    """
    Minimal wrapper around SEC's submissions/companyfacts endpoints with
    respectful rate limiting and RSS-friendly parsing utilities.
    """

    def __init__(
        self,
        user_agent: str,
        max_calls_per_second: float = 4.0,
        session: Optional[requests.Session] = None,
    ) -> None:
        if not user_agent or "example.com" in user_agent.lower():
            raise ValueError("Provide a real contact email in the User-Agent per SEC guidance.")

        self.session = session or requests.Session()
        self.session.headers.update(
            {
                "User-Agent": user_agent,
                "Accept": "application/json",
                "Accept-Encoding": "gzip, deflate",
            }
        )
        self.rate_limiter = RateLimiter(max_calls_per_second)

    def _get_json(self, url: str) -> Dict:
        self.rate_limiter.wait()
        resp = self.session.get(url, timeout=20)
        resp.raise_for_status()
        return resp.json()

    def get_company_submissions(self, cik: str) -> Dict:
        """Fetch the submissions payload for a company."""
        cik_norm = normalize_cik(cik)
        url = SUBMISSIONS_URL.format(cik=cik_norm)
        logger.debug("Fetching submissions for CIK %s", cik_norm)
        return self._get_json(url)

    def get_company_facts(self, cik: str) -> Dict:
        """Fetch the companyfacts payload (includes tickers, entity data, facts)."""
        cik_norm = normalize_cik(cik)
        url = COMPANYFACTS_URL.format(cik=cik_norm)
        logger.debug("Fetching companyfacts for CIK %s", cik_norm)
        return self._get_json(url)

    def get_recent_filings(
        self,
        cik: str,
        days: int = 3,
        forms: Optional[List[str]] = None,
        start_date: Optional[date] = None,
        end_date: Optional[date] = None,
    ) -> List[Filing]:
        """
        Return filings within a date window for a company.

        If ``start_date``/``end_date`` are provided, the window is inclusive of those
        dates. Otherwise, it falls back to the last ``days`` ending today (UTC).
        """
        cik_norm = normalize_cik(cik)
        submissions = self.get_company_submissions(cik_norm)
        company_name = submissions.get("name")
        recent = submissions.get("filings", {}).get("recent", {})

        if not recent:
            logger.warning("No recent filings found for %s", cik_norm)
            return []

        default_forms = ["8-K", "10-Q", "10-K", "6-K", "20-F"]
        form_filter = [f.strip().upper() for f in (forms or default_forms)]
        today = datetime.now(timezone.utc).date()
        window_end = end_date or today
        window_start = start_date or (window_end - timedelta(days=days))

        if window_start > window_end:
            raise ValueError(
                f"start_date {window_start} is after end_date {window_end} for CIK {cik_norm}"
            )

        filings: List[Filing] = []
        for idx, form_type in enumerate(recent.get("form", [])):
            if form_type is None:
                continue

            form_type = form_type.upper()
            if form_filter and form_type not in form_filter:
                continue

            filing_date_str = recent.get("filingDate", [])[idx]
            try:
                filing_dt = datetime.strptime(filing_date_str, "%Y-%m-%d").date()
            except Exception:
                logger.debug("Skipping filing with unparseable date: %s", filing_date_str)
                continue

            if filing_dt < window_start or filing_dt > window_end:
                continue

            accession = recent.get("accessionNumber", [])[idx]
            accession_compact = accession.replace("-", "")
            primary_doc = self._safe_get(recent, "primaryDocument", idx)
            description = self._safe_get(recent, "primaryDocDescription", idx)
            report_dt = self._parse_date_safe(self._safe_get(recent, "reportDate", idx))
            file_number = self._safe_get(recent, "fileNumber", idx)
            items = self._safe_get(recent, "items", idx)

            base_path = f"https://www.sec.gov/Archives/edgar/data/{int(cik_norm)}/{accession_compact}"
            url = f"{base_path}/{primary_doc}" if primary_doc else base_path

            filings.append(
                Filing(
                    cik=cik_norm,
                    company_name=company_name,
                    form_type=form_type,
                    accession_number=accession,
                    filing_date=filing_dt,
                    report_date=report_dt,
                    primary_document=primary_doc,
                    file_number=file_number,
                    description=description,
                    url=url,
                    items=items,
                )
            )

        return filings

    def filing_to_rss_entry(
        self,
        filing: Filing,
        source_id: str = "sec_edgar",
        source_name: str = "SEC EDGAR Filings",
    ) -> FeedParserDict:
        """Convert a Filing into the feedparser-like structure used by our RSS monitors."""
        published_dt = datetime.combine(filing.filing_date, datetime.min.time(), tzinfo=timezone.utc)
        summary_parts = [f"{filing.form_type} filing"]
        if filing.company_name:
            summary_parts.append(f"for {filing.company_name}")
        if filing.report_date:
            summary_parts.append(f"(report date {filing.report_date.isoformat()})")
        if filing.description:
            summary_parts.append(filing.description)
        summary = " ".join(summary_parts)

        entry = FeedParserDict(
            {
                "id": filing.accession_number,
                "title": f"{filing.company_name or filing.cik} - {filing.form_type}",
                "link": filing.url,
                "summary": summary.strip(),
                "source": source_name,
                "source_id": source_id,
                "published": filing.filing_date.isoformat(),
            }
        )
        entry["published_parsed"] = published_dt.timetuple()
        return entry

    @staticmethod
    def _parse_date_safe(date_str: Optional[str]) -> Optional[date]:
        if not date_str:
            return None
        try:
            return datetime.strptime(date_str, "%Y-%m-%d").date()
        except Exception:
            return None

    @staticmethod
    def _safe_get(data: Dict, key: str, index: int) -> Optional[str]:
        try:
            value = data.get(key, [])[index]
            return value if value not in ("", None) else None
        except Exception:
            return None


__all__ = [
    "EdgarAPI",
    "Filing",
    "normalize_cik",
]
