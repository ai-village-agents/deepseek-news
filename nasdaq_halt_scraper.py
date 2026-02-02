#!/usr/bin/env python3
"""Scrape NASDAQ trade halts into feed-like items."""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Dict, List
from zoneinfo import ZoneInfo

import requests
from bs4 import BeautifulSoup

RPC_URL = "https://www.nasdaqtrader.com/RPCHandler.axd"
TRADE_HALTS_PAGE = "https://www.nasdaqtrader.com/trader.aspx?id=TradeHalts"

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36"
    ),
    "Referer": TRADE_HALTS_PAGE,
}

logger = logging.getLogger("nasdaq_halt_scraper")


def fetch_trade_halt_table_html() -> str:
    """Call the RPC endpoint used by the NASDAQ page to fetch the halt table HTML."""
    payload = {
        "id": 1,
        "method": "BL_TradeHalt.GetTradeHalts",
        "params": "[]",
        "version": "1.1",
    }
    resp = requests.post(RPC_URL, json=payload, headers=HEADERS, timeout=15)
    resp.raise_for_status()
    data = resp.json()
    html = data.get("result", "")
    if not html:
        raise ValueError("Empty response while fetching trade halts")
    return html


def parse_trade_halts(table_html: str) -> List[Dict[str, str]]:
    """Parse the trade halt HTML table into structured dicts."""
    soup = BeautifulSoup(table_html, "html.parser")
    table = soup.find("table")
    if not table:
        logger.warning("No table found in trade halt HTML")
        return []

    rows = table.find_all("tr")
    if not rows:
        logger.warning("No rows found in trade halt table")
        return []

    headers = [th.get_text(strip=True) for th in rows[0].find_all("th")]
    halts: List[Dict[str, str]] = []
    for row in rows[1:]:
        cells = [td.get_text(strip=True) for td in row.find_all("td")]
        if not cells or len(cells) != len(headers):
            continue
        halts.append(dict(zip(headers, cells)))
    return halts


def _parse_datetime_et(date_str: str, time_str: str) -> str:
    """Convert NASDAQ ET date/time strings to an ISO UTC timestamp."""
    try:
        dt_naive = datetime.strptime(f"{date_str} {time_str}", "%m/%d/%Y %H:%M:%S")
        dt_et = dt_naive.replace(tzinfo=ZoneInfo("America/New_York"))
        return dt_et.astimezone(timezone.utc).isoformat()
    except Exception:
        logger.exception("Failed to parse halt datetime: %s %s", date_str, time_str)
        return datetime.now(timezone.utc).isoformat()


def halts_to_feed_items(halts: List[Dict[str, str]]) -> List[Dict[str, str]]:
    """Convert parsed halt rows into monitoring feed items."""
    feed_items: List[Dict[str, str]] = []
    for halt in halts:
        symbol = halt.get("Issue Symbol", "").upper()
        halt_date = halt.get("Halt Date", "")
        halt_time = halt.get("Halt Time", "")
        reason = halt.get("Reason Codes", "") or "Unknown"
        issue_name = halt.get("Issue Name", "Unknown issue")
        market = halt.get("Market", "")
        pause_price = halt.get("Pause Threshold Price", "")
        resumption = halt.get("Resumption Trade Time", "") or halt.get(
            "Resumption Quote Time", ""
        )

        published = _parse_datetime_et(halt_date, halt_time)
        item_id = f"nasdaq_trade_halt:{halt_date}:{halt_time}:{symbol}:{reason}"

        title = f"{symbol} halted at {halt_time} ET ({reason})"
        summary_parts = [
            f"Issue: {issue_name}",
            f"Market: {market}" if market else "",
            f"Pause threshold: {pause_price}" if pause_price else "",
            f"Resumption: {resumption} ET" if resumption else "Resumption: pending",
        ]
        summary = " | ".join(part for part in summary_parts if part)

        feed_items.append(
            {
                "source": "nasdaq_trade_halt",
                "title": title,
                "link": TRADE_HALTS_PAGE,
                "summary": summary,
                "published": published,
                "item_id": item_id,
            }
        )
    return feed_items


def scrape_trade_halts() -> List[Dict[str, str]]:
    """Fetch, parse, and convert NASDAQ trade halts into feed items."""
    try:
        table_html = fetch_trade_halt_table_html()
        halts = parse_trade_halts(table_html)
        return halts_to_feed_items(halts)
    except Exception as exc:
        logger.error("Failed to scrape trade halts: %s", exc)
        return []


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    items = scrape_trade_halts()
    print(f"Fetched {len(items)} halt items")
    for item in items[:5]:
        print(item)
