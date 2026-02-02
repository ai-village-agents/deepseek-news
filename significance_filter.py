"""
Significance scoring utilities for news items.

This module assigns a 0-10 score to incoming items based on source authority
and content cues (earthquake magnitude, Hacker News points, GitHub release
tags, etc.). It also exposes helpers to evaluate items against a threshold and
to archive previously generated posts that fall below a significance cutoff.
"""

import logging
import re
import time
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Union

logger = logging.getLogger(__name__)


# Regex patterns
EARTHQUAKE_MAGNITUDE_RE = re.compile(
    r"\b(?:M|mag|magnitude)[^\d]{0,3}(\d+(?:\.\d+)?)", re.IGNORECASE
)
GITHUB_VERSION_RE = re.compile(
    r"\b[vV]?(\d+(?:\.\d+){1,2}(?:[-+][0-9A-Za-z.-]+)?)\b"
)
HN_SCORE_RE = re.compile(r"\bScore:\s*(\d+)", re.IGNORECASE)


DEFAULT_CONFIG: Dict = {
    "threshold": 6.0,
    "archive_threshold": 5.0,
    "base_score": 1.0,
    "weights": {
        "government": 3.0,
        "regulatory": 3.0,
        "sec": 3.2,
        "nasa": 3.2,
        "earthquake": 2.5,
        "github_release": 1.8,
        "arxiv": 1.5,
        "hackernews": 1.0,
    },
    "earthquake": {
        "min_magnitude": 3.0,
        "major_magnitude": 6.0,
        "magnitude_scale": 0.9,
        "major_bonus": 1.5,
    },
    "github": {"require_version": True},
    "hackernews": {
        "score_threshold": 100,
        "increment": 50,
        "bonus_per_increment": 0.4,
    },
    "arxiv": {
        "priority_keywords": [
            "gpt",
            "large language model",
            "llm",
            "foundation model",
            "multimodal",
            "alignment",
            "safety",
            "quantization",
            "distillation",
            "rlhf",
        ],
        "keyword_bonus": 0.8,
    },
    "caps": {"min_score": 0.0, "max_score": 10.0},
}


def extract_earthquake_magnitude(text: str) -> Optional[float]:
    """Extract magnitude from an earthquake headline."""
    if not text:
        return None
    for match in EARTHQUAKE_MAGNITUDE_RE.finditer(text):
        try:
            return float(match.group(1))
        except (TypeError, ValueError):
            continue
    return None


def extract_github_version(text: str) -> Optional[str]:
    """Extract a semantic-ish version tag from a GitHub release title."""
    if not text:
        return None
    match = GITHUB_VERSION_RE.search(text)
    return match.group(1) if match else None


def extract_hn_score(text: str) -> Optional[int]:
    """Extract Hacker News score from a summary string."""
    if not text:
        return None
    match = HN_SCORE_RE.search(text)
    if not match:
        return None
    try:
        return int(match.group(1))
    except ValueError:
        return None


def detect_category(item: Dict) -> str:
    """Best-effort categorization of an item based on source metadata."""
    source = item.get("source", "") or ""
    source_name = item.get("source_name", "") or ""
    combined = f"{source} {source_name}".lower()

    if "earthquake" in combined or "usgs" in combined:
        return "earthquake"
    if "hackernews" in combined or combined.strip() == "hn":
        return "hackernews"
    if "github" in combined:
        return "github_release"
    if "arxiv" in combined:
        return "arxiv"
    if "nasa" in combined:
        return "nasa"
    if "sec" in combined:
        return "sec"
    if any(token in combined for token in ["fda", "noaa", "gov", "government"]):
        return "government"
    if any(token in combined for token in ["rfc", "ietf", "regulatory"]):
        return "regulatory"
    return "general"


def _apply_caps(score: float, config: Dict) -> float:
    """Clamp score to configured caps."""
    caps = config.get("caps", {})
    min_score = caps.get("min_score", 0.0)
    max_score = caps.get("max_score", 10.0)
    return max(min(score, max_score), min_score)


def compute_significance_score(item: Dict, config: Dict = DEFAULT_CONFIG) -> float:
    """
    Compute a 0-10 significance score for a news item.

    Factors include source authority, earthquake magnitude, Hacker News points,
    and whether GitHub titles look like actual versioned releases.
    """
    score = float(config.get("base_score", 1.0))

    title = (item.get("title") or "").strip()
    summary = (item.get("summary") or "").strip()
    category = detect_category(item)

    # Source weight
    score += config.get("weights", {}).get(category, 0)

    # Category-specific boosts/filters
    if category == "earthquake":
        magnitude = extract_earthquake_magnitude(f"{title} {summary}")
        mag_cfg = config.get("earthquake", {})
        if magnitude is None:
            score -= 0.5  # weak signal if magnitude missing
        elif magnitude < mag_cfg.get("min_magnitude", 0):
            score -= 1.5  # below threshold, de-prioritize heavily
        else:
            score += (magnitude - mag_cfg.get("min_magnitude", 0)) * mag_cfg.get(
                "magnitude_scale", 1.0
            )
            if magnitude >= mag_cfg.get("major_magnitude", 10.0):
                score += mag_cfg.get("major_bonus", 0)

    elif category == "github_release":
        version = extract_github_version(title)
        if not version and config.get("github", {}).get("require_version", True):
            logger.debug("GitHub item missing version tag; lowering significance")
            return _apply_caps(0.5, config)
        if version:
            score += 0.8
        if "release" in title.lower():
            score += 0.5

    elif category == "arxiv":
        keywords = config.get("arxiv", {}).get("priority_keywords", [])
        keyword_bonus = config.get("arxiv", {}).get("keyword_bonus", 0)
        lower_title = title.lower()
        if any(k in lower_title for k in keywords):
            score += keyword_bonus

    elif category == "hackernews":
        hn_cfg = config.get("hackernews", {})
        hn_score = item.get("score")
        if hn_score is None:
            hn_score = extract_hn_score(summary)
        if hn_score is not None and hn_score >= 0:
            if hn_score >= hn_cfg.get("score_threshold", 0):
                score += 1.0
            increments = max(
                0, (hn_score - hn_cfg.get("score_threshold", 0))
            ) // max(1, hn_cfg.get("increment", 1))
            score += increments * hn_cfg.get("bonus_per_increment", 0)
        else:
            score -= 0.3  # weak confidence without score

    if category == "nasa":
        score += 1.2
    if category == "sec":
        if "8-k" in title.lower():
            score += 1.0

    return _apply_caps(score, config)


def meets_threshold(
    item: Dict,
    config: Dict = DEFAULT_CONFIG,
    threshold: Optional[float] = None,
    score: Optional[float] = None,
) -> bool:
    """Return True if the item meets or exceeds the configured threshold."""
    threshold = threshold if threshold is not None else config.get("threshold", 0)
    computed_score = score if score is not None else compute_significance_score(
        item, config
    )
    return computed_score >= threshold


def _parse_front_matter(text: str) -> Dict[str, str]:
    """Parse minimal YAML-style front matter without dependencies."""
    lines = text.splitlines()
    if len(lines) < 3 or not lines[0].strip().startswith("---"):
        return {}
    try:
        end_idx = lines[1:].index("---") + 1
    except ValueError:
        return {}

    front_matter_lines = lines[1:end_idx]
    metadata: Dict[str, str] = {}
    for line in front_matter_lines:
        if ":" not in line:
            continue
        key, _, value = line.partition(":")
        metadata[key.strip()] = value.strip().strip('"')
    return metadata


def _extract_summary_section(text: str) -> str:
    """Extract summary section from a generated markdown post."""
    summary = []
    capture = False
    for line in text.splitlines():
        if line.strip().lower().startswith("## summary"):
            capture = True
            continue
        if capture and line.startswith("## "):
            break
        if capture:
            summary.append(line)
    return "\n".join(summary).strip()


def move_low_significance_posts(
    posts_dir: Union[Path, str] = "_posts",
    archive_dir: Union[Path, str] = "archive",
    config: Dict = DEFAULT_CONFIG,
    threshold: Optional[float] = None,
) -> List[Tuple[Path, Path]]:
    """
    Scan posts and move any that fall below the archive threshold.

    Returns a list of (source_path, archived_path) tuples for moved files.
    """
    posts_path = Path(posts_dir)
    archive_path = Path(archive_dir)
    archive_path.mkdir(parents=True, exist_ok=True)

    cutoff = threshold if threshold is not None else config.get(
        "archive_threshold", config.get("threshold", 0)
    )
    moved: List[Tuple[Path, Path]] = []

    for post_file in posts_path.glob("*.md"):
        try:
            text = post_file.read_text(encoding="utf-8")
        except FileNotFoundError:
            continue

        metadata = _parse_front_matter(text)
        summary = _extract_summary_section(text)
        item = {
            "title": metadata.get("title", post_file.name),
            "source": metadata.get("source", ""),
            "source_name": metadata.get("source_name", metadata.get("source", "")),
            "summary": summary,
        }
        score = compute_significance_score(item, config)
        if score >= cutoff:
            continue

        target = archive_path / post_file.name
        if target.exists():
            target = archive_path / f"{post_file.stem}-{int(time.time())}{post_file.suffix}"
        post_file.rename(target)
        moved.append((post_file, target))
        logger.info(
            "Archived low-significance post %s (score=%.2f -> %s)", post_file, score, target
        )

    return moved
