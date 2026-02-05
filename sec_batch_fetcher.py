#!/usr/bin/env python3
"""
Batch SEC EDGAR fetcher that produces feedparser-style entries.

Workflow:
- Download ``company_tickers.json`` from sec.gov (cached to ``data/company_tickers.json``).
- Select companies (top by market cap when available, otherwise sampled/ordered).
- Pull recent filings (8-K, 10-Q, 10-K, 6-K, 20-F, etc.) from the last N days.
- Convert filings to RSS-friendly entries compatible with the existing monitors.
"""

from __future__ import annotations

import json
import logging
import random
import time
from datetime import date
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Sequence

import requests

from edgar_api import EdgarAPI, Filing, normalize_cik

logger = logging.getLogger(__name__)

COMPANY_TICKERS_URL = "https://www.sec.gov/files/company_tickers.json"
DEFAULT_CACHE_DIR = "data"
DEFAULT_COMPANY_LIMIT = 50
DEFAULT_FORMS = ["8-K", "10-Q", "10-K", "6-K", "20-F"]


class SECBatchFetcher:
    """Fetch recent filings for many companies with SEC rate limits respected."""

    def __init__(
        self,
        user_agent: str,
        cache_dir: str = DEFAULT_CACHE_DIR,
        tickers_url: str = COMPANY_TICKERS_URL,
        max_calls_per_second: float = 4.0,
        inter_company_delay: float = 0.0,
    ) -> None:
        if not user_agent:
            raise ValueError("user_agent is required and must include contact info per SEC guidance.")

        self.user_agent = user_agent
        self.tickers_url = tickers_url
        self.cache_dir = Path(cache_dir)
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self.cache_path = self.cache_dir / "company_tickers.json"
        self.inter_company_delay = max(0.0, inter_company_delay)

        self.session = requests.Session()
        self.session.headers.update(
            {
                "User-Agent": user_agent,
                "Accept": "application/json",
            }
        )

        self.edgar = EdgarAPI(user_agent=user_agent, max_calls_per_second=max_calls_per_second)

    # ------------------------------------------------------------------
    # Company universe helpers
    # ------------------------------------------------------------------
    def download_company_tickers(self, force_refresh: bool = False) -> List[Dict[str, Any]]:
        """
        Download and cache the SEC company tickers list.
        Falls back to cached copy if the download fails.
        """
        if self.cache_path.exists() and not force_refresh:
            try:
                return self._normalize_company_payload(json.loads(self.cache_path.read_text()))
            except Exception as exc:
                logger.warning("Failed to read cached company tickers, refetching: %s", exc)

        try:
            resp = self.session.get(self.tickers_url, timeout=30)
            resp.raise_for_status()
            payload = resp.json()
            self.cache_path.write_text(json.dumps(payload, indent=2))
            logger.info("Downloaded company tickers list (%s)", self.cache_path)
            return self._normalize_company_payload(payload)
        except Exception as exc:
            logger.error("Could not download company_tickers.json: %s", exc)
            if self.cache_path.exists():
                logger.info("Using cached company tickers from %s", self.cache_path)
                try:
                    return self._normalize_company_payload(json.loads(self.cache_path.read_text()))
                except Exception as cache_exc:
                    logger.error("Cached company tickers are unreadable: %s", cache_exc)
            raise

    def _normalize_company_payload(self, payload: Any) -> List[Dict[str, Any]]:
        """
        Normalize company_tickers payload into a list of dicts with ticker, cik, title, and market cap.
        The official SEC file is a dict keyed by index -> {cik_str, ticker, title}.
        Some alternative datasets include a ``market_cap`` field; we use it when present.
        """
        entries: List[Dict[str, Any]] = []

        if isinstance(payload, dict):
            candidates: Iterable[Any] = payload.values()
        elif isinstance(payload, list):
            candidates = payload
        else:
            logger.warning("Unexpected company_tickers payload type: %s", type(payload))
            return entries

        for obj in candidates:
            if not isinstance(obj, dict):
                continue

            ticker = (obj.get("ticker") or obj.get("ticker_symbol") or "").strip()
            cik_raw = obj.get("cik_str") or obj.get("cik") or obj.get("cikNumber")
            title = (obj.get("title") or obj.get("name") or obj.get("company") or "").strip()
            market_cap = obj.get("market_cap") or obj.get("marketcap") or obj.get("marketCap")

            if not ticker or not cik_raw:
                continue

            try:
                cik = normalize_cik(cik_raw)
            except Exception:
                logger.debug("Skipping company with invalid CIK: %s (%s)", ticker, cik_raw)
                continue

            try:
                market_cap_val = float(market_cap) if market_cap is not None else None
            except Exception:
                market_cap_val = None

            entries.append(
                {
                    "ticker": ticker,
                    "cik": cik,
                    "title": title or ticker,
                    "market_cap": market_cap_val,
                }
            )

        return entries

    def select_companies(
        self,
        companies: Sequence[Dict[str, Any]],
        limit: Optional[int] = DEFAULT_COMPANY_LIMIT,
        top_by_market_cap: bool = True,
        seed: Optional[int] = None,
    ) -> List[Dict[str, Any]]:
        """
        Choose which companies to query.
        - If ``top_by_market_cap`` and market cap data exists, take the highest caps first.
        - Otherwise sample/shuffle deterministically (when seed is provided).
        """
        if not companies:
            return []

        chosen: List[Dict[str, Any]]
        if top_by_market_cap:
            with_cap = [c for c in companies if c.get("market_cap") is not None]
            without_cap = [c for c in companies if c.get("market_cap") is None]

            if with_cap:
                with_cap_sorted = sorted(with_cap, key=lambda c: c["market_cap"], reverse=True)
                chosen = with_cap_sorted + without_cap
            else:
                logger.debug("Market cap not available; falling back to ticker order.")
                chosen = list(companies)
        else:
            rng = random.Random(seed)
            chosen = list(companies)
            rng.shuffle(chosen)

        if limit and limit > 0:
            chosen = chosen[:limit]

        return chosen

    # ------------------------------------------------------------------
    # Filings helpers
    # ------------------------------------------------------------------
    def fetch_recent_filings_for_companies(
        self,
        days: int = 3,
        forms: Optional[List[str]] = None,
        start_date: Optional[date] = None,
        end_date: Optional[date] = None,
        company_limit: int = DEFAULT_COMPANY_LIMIT,
        top_by_market_cap: bool = True,
        seed: Optional[int] = None,
        force_refresh_tickers: bool = False,
    ) -> List[Filing]:
        """Fetch recent filings for a batch of companies."""
        company_universe = self.download_company_tickers(force_refresh=force_refresh_tickers)
        selected_companies = self.select_companies(
            company_universe, limit=company_limit, top_by_market_cap=top_by_market_cap, seed=seed
        )

        logger.info(
            "Querying recent filings for %s companies (days=%s, start=%s, end=%s, forms=%s)",
            len(selected_companies),
            days,
            start_date.isoformat() if start_date else None,
            end_date.isoformat() if end_date else None,
            forms or DEFAULT_FORMS,
        )

        filings: List[Filing] = []
        for company in selected_companies:
            cik = company["cik"]
            ticker = company.get("ticker")
            try:
                company_filings = self.edgar.get_recent_filings(
                    cik=cik,
                    days=days,
                    forms=forms,
                    start_date=start_date,
                    end_date=end_date,
                )
            except Exception as exc:
                logger.warning("Failed to fetch filings for %s (%s): %s", ticker, cik, exc)
                continue

            for filing in company_filings:
                if not filing.company_name and company.get("title"):
                    filing.company_name = company["title"]
            filings.extend(company_filings)

            if self.inter_company_delay:
                time.sleep(self.inter_company_delay)

        return filings

    def fetch_rss_entries(
        self,
        days: int = 3,
        forms: Optional[List[str]] = None,
        start_date: Optional[date] = None,
        end_date: Optional[date] = None,
        company_limit: int = DEFAULT_COMPANY_LIMIT,
        top_by_market_cap: bool = True,
        seed: Optional[int] = None,
        force_refresh_tickers: bool = False,
        source_id: str = "sec_edgar_batch",
        source_name: str = "SEC EDGAR Filings",
    ) -> List[Dict[str, Any]]:
        """
        Fetch recent filings and return feedparser-style entries that downstream
        monitors can consume directly.
        """
        filings = self.fetch_recent_filings_for_companies(
            days=days,
            forms=forms or DEFAULT_FORMS,
            start_date=start_date,
            end_date=end_date,
            company_limit=company_limit,
            top_by_market_cap=top_by_market_cap,
            seed=seed,
            force_refresh_tickers=force_refresh_tickers,
        )

        entries: List[Dict[str, Any]] = []
        for filing in filings:
            try:
                entry = self.edgar.filing_to_rss_entry(
                    filing, source_id=source_id, source_name=source_name
                )
            except Exception as exc:
                logger.debug("Failed to convert filing to RSS entry (%s): %s", filing, exc)
                continue

            entry["cik"] = filing.cik
            entry["company_name"] = filing.company_name
            entries.append(entry)

        return entries


def fetch_sec_batch_rss_entries(
    user_agent: str,
    days: int = 3,
    forms: Optional[List[str]] = None,
    company_limit: int = DEFAULT_COMPANY_LIMIT,
    top_by_market_cap: bool = True,
    seed: Optional[int] = None,
    force_refresh_tickers: bool = False,
    max_calls_per_second: float = 4.0,
    inter_company_delay: float = 0.0,
    source_id: str = "sec_edgar_batch",
    source_name: str = "SEC EDGAR Filings",
) -> List[Dict[str, Any]]:
    """
    Convenience wrapper for one-off batch pulls.
    Returns feedparser-style entries suitable for existing RSS ingestion.
    """
    fetcher = SECBatchFetcher(
        user_agent=user_agent,
        max_calls_per_second=max_calls_per_second,
        inter_company_delay=inter_company_delay,
    )
    return fetcher.fetch_rss_entries(
        days=days,
        forms=forms or DEFAULT_FORMS,
        company_limit=company_limit,
        top_by_market_cap=top_by_market_cap,
        seed=seed,
        force_refresh_tickers=force_refresh_tickers,
        source_id=source_id,
        source_name=source_name,
    )


__all__ = [
    "SECBatchFetcher",
    "fetch_sec_batch_rss_entries",
    "COMPANY_TICKERS_URL",
    "DEFAULT_FORMS",
]


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    try:
        entries = fetch_sec_batch_rss_entries(
            user_agent="DeepSeekNewsMonitor/1.0 (contact@yourdomain.com)",
            days=2,
            company_limit=10,
        )
        for entry in entries:
            logger.info("%s | %s", entry.get("title"), entry.get("link"))
    except Exception as exc:  # pragma: no cover - runtime helper
        logger.error("SEC batch fetch failed: %s", exc)
