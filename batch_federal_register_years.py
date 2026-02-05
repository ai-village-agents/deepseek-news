#!/usr/bin/env python3
"""
Orchestrate multi-year mining of Federal Register documents.

This script coordinates the existing FederalRegisterBatchMiner across a year
range, adds retry-aware HTTP handling, optional skipping of previously
processed dates from the shared state file, and progress logging suited for
large historical backfills.
"""

import argparse
import logging
import sys
import time
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Iterable, List, Set, Tuple

from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

from batch_federal_register import (
    DEFAULT_STATE,
    DEFAULT_THRESHOLD,
    FederalRegisterBatchMiner,
)

logger = logging.getLogger(__name__)


def _daterange(start: date, end: date) -> Iterable[date]:
    """Yield every date in the inclusive range."""
    cursor = start
    while cursor <= end:
        yield cursor
        cursor += timedelta(days=1)


def _build_retry_adapter(max_retries: int, backoff_factor: float) -> HTTPAdapter:
    """Create an HTTPAdapter with backoff for 429/5xx handling."""
    retry = Retry(
        total=max_retries,
        backoff_factor=backoff_factor,
        status_forcelist=[429, 500, 502, 503, 504],
        allowed_methods=["HEAD", "GET", "OPTIONS"],
        raise_on_status=False,
    )
    return HTTPAdapter(max_retries=retry)


def _load_processed_dates(state: dict) -> Set[str]:
    """Read processed_dates from the shared state structure."""
    dates = state.get("processed_dates", [])
    if isinstance(dates, list):
        return {str(d) for d in dates}
    return set()


def _persist_state(miner: FederalRegisterBatchMiner, processed_dates: Set[str]) -> None:
    """Write state with updated processed_dates and last_run markers."""
    miner.state["processed_dates"] = sorted(processed_dates)
    miner.state["last_run"] = datetime.utcnow().isoformat() + "Z"
    miner._save_state()


def _prepare_miner(
    *,
    start: date,
    end: date,
    threshold: float,
    state_file: Path,
    rate_limit: float,
    enable_git: bool,
    max_retries: int,
    retry_backoff: float,
) -> FederalRegisterBatchMiner:
    """Instantiate and configure a miner with retry-aware HTTP handling."""
    miner = FederalRegisterBatchMiner(
        start=start,
        end=end,
        threshold=threshold,
        state_file=state_file,
        rate_limit=rate_limit,
        enable_git=enable_git,
    )
    adapter = _build_retry_adapter(max_retries=max_retries, backoff_factor=retry_backoff)
    miner.session.mount("https://", adapter)
    miner.session.mount("http://", adapter)
    return miner


def _process_dates(
    miner: FederalRegisterBatchMiner,
    dates: List[date],
    *,
    skip_existing: bool,
    sleep_between_days: float,
) -> Tuple[int, int, List[str]]:
    """
    Process a list of dates using the provided miner.

    Returns:
        created_count: Total published posts.
        processed_days: Number of days traversed.
        created_files: List of created filenames for git handling.
    """
    processed_dates = _load_processed_dates(miner.state)

    if skip_existing and processed_dates:
        pending_dates = [d for d in dates if d.isoformat() not in processed_dates]
    else:
        pending_dates = list(dates)

    skipped = len(dates) - len(pending_dates)
    if skipped:
        logger.info("Skipping %s dates already marked processed via state file.", skipped)

    total_created = 0
    created_files: List[str] = []
    total_dates = len(pending_dates)

    for idx, target_date in enumerate(pending_dates, start=1):
        logger.info("Processing %s (%s/%s)", target_date.isoformat(), idx, total_dates)
        try:
            docs = miner.fetch_documents_for_date(target_date)
        except Exception:
            logger.exception("Unexpected error fetching documents for %s", target_date.isoformat())
            continue

        for doc in docs:
            try:
                created = miner._maybe_publish(doc)
            except Exception:
                logger.exception("Error handling document on %s", target_date.isoformat())
                continue
            if created:
                created_files.append(created)
                total_created += 1

        processed_dates.add(target_date.isoformat())
        _persist_state(miner, processed_dates)

        if sleep_between_days > 0:
            time.sleep(sleep_between_days)

    processed_days = len(pending_dates)
    return total_created, processed_days, created_files


def main() -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Run the Federal Register miner across a range of years, "
            "with optional skipping of already processed dates."
        )
    )
    current_year = date.today().year

    parser.add_argument("--start-year", type=int, default=current_year, help="First year to process (inclusive).")
    parser.add_argument("--end-year", type=int, default=current_year, help="Last year to process (inclusive).")
    parser.add_argument(
        "--threshold",
        type=float,
        default=DEFAULT_THRESHOLD,
        help=f"Significance threshold; defaults to {DEFAULT_THRESHOLD}.",
    )
    parser.add_argument(
        "--state-file",
        type=Path,
        default=DEFAULT_STATE,
        help="State JSON path tracking processed IDs/dates.",
    )
    parser.add_argument(
        "--rate-limit",
        type=float,
        default=0.5,
        help="Delay (seconds) between paginated API calls.",
    )
    parser.add_argument(
        "--sleep-between-days",
        type=float,
        default=0.0,
        help="Optional pause between day boundaries to reduce API pressure.",
    )
    parser.add_argument(
        "--max-retries",
        type=int,
        default=3,
        help="Max retries for 429/5xx API responses.",
    )
    parser.add_argument(
        "--retry-backoff",
        type=float,
        default=2.0,
        help="Backoff factor for retry handling (seconds base).",
    )
    parser.add_argument(
        "--log-level",
        default="INFO",
        choices=["DEBUG", "INFO", "WARNING", "ERROR"],
        help="Logging verbosity.",
    )
    parser.add_argument(
        "--no-git",
        action="store_true",
        help="Disable git add/commit/push for generated posts.",
    )
    parser.add_argument(
        "--no-skip-existing",
        dest="skip_existing",
        action="store_false",
        help="Process all dates even if state file marks them complete.",
    )
    parser.set_defaults(skip_existing=True)

    args = parser.parse_args()

    logging.basicConfig(
        level=getattr(logging, args.log_level),
        format="%(asctime)s - %(levelname)s - %(message)s",
    )

    if args.start_year > args.end_year:
        parser.error("start-year must be less than or equal to end-year")

    start_date = date(args.start_year, 1, 1)
    end_date = date(args.end_year, 12, 31)

    miner = _prepare_miner(
        start=start_date,
        end=end_date,
        threshold=args.threshold,
        state_file=args.state_file,
        rate_limit=args.rate_limit,
        enable_git=not args.no_git,
        max_retries=args.max_retries,
        retry_backoff=args.retry_backoff,
    )

    all_dates = list(_daterange(start_date, end_date))
    total_created, processed_days, created_files = _process_dates(
        miner,
        all_dates,
        skip_existing=args.skip_existing,
        sleep_between_days=args.sleep_between_days,
    )

    miner._git_commit_and_push(created_files)

    logger.info(
        "Finished Federal Register year batch %s-%s: %s new posts across %s days.",
        args.start_year,
        args.end_year,
        total_created,
        processed_days,
    )
    logger.info("Dates requested: %s, skipped: %s", len(all_dates), len(all_dates) - processed_days)
    return 0


if __name__ == "__main__":
    sys.exit(main())
