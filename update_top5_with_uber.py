#!/usr/bin/env python3
"""
Update Story 5 in top-5-submission.html with the Uber sexual assault verdict.

Steps:
1) Read metadata from the PR Newswire post for the Uber verdict.
2) Fetch git commit information for the post.
3) Search Google News for "Uber sexual assault verdict" to count subsequent coverage.
4) Replace Story 5 in top-5-submission.html with the Uber story and refresh the
   summary articles count.
"""
from __future__ import annotations

import re
import subprocess
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import List

from research_spread import search_google_news

POST_PATH = Path("_posts/2026-02-06-03-02-43-prnewswire-240030.md")
HTML_PATH = Path("top-5-submission.html")
SEARCH_QUERY = "Uber sexual assault verdict"


@dataclass
class PostMeta:
    title: str
    date_iso: str
    source_url: str
    significance: float


@dataclass
class CommitInfo:
    commit_hash: str
    timestamp: str
    message: str


def run(cmd: str) -> str:
    """Run a shell command and return stdout."""
    print(f"Running: {cmd}")
    result = subprocess.run(cmd, shell=True, check=True, capture_output=True, text=True)
    output = result.stdout.strip()
    print(f"Output: {output}")
    return output


def normalize_ascii(text: str) -> str:
    """Normalize common unicode punctuation to ASCII for consistency."""
    replacements = {
        "\u2011": "-",
        "\u2012": "-",
        "\u2013": "-",
        "\u2014": "-",
        "\u2018": "'",
        "\u2019": "'",
        "\u201c": '"',
        "\u201d": '"',
    }
    for old, new in replacements.items():
        text = text.replace(old, new)
    return text


def read_post_metadata(path: Path) -> PostMeta:
    print(f"Reading post metadata from {path}")
    text = path.read_text(encoding="utf-8")
    fm_match = re.search(r"^---\n(.*?)\n---", text, flags=re.DOTALL | re.MULTILINE)
    if not fm_match:
        raise ValueError(f"Could not find front matter in {path}")

    fm = fm_match.group(1)
    fields = {}
    for line in fm.splitlines():
        if ":" not in line:
            continue
        key, value = line.split(":", 1)
        fields[key.strip()] = value.strip().strip('"')

    title = normalize_ascii(fields.get("title", ""))
    date_iso = fields.get("date", "")
    source_url = fields.get("source_url", "")
    significance = float(fields.get("significance", "0"))

    print(f"Parsed metadata: title='{title}', date='{date_iso}', source_url='{source_url}', significance={significance}")
    return PostMeta(title=title, date_iso=date_iso, source_url=source_url, significance=significance)


def get_commit_info(path: Path) -> CommitInfo:
    log_line = run(f"git log --oneline --follow -- {path} | head -1")
    parts = log_line.split(" ", 1)
    if not parts:
        raise ValueError(f"No git history found for {path}")
    commit_hash = parts[0]
    message = parts[1] if len(parts) > 1 else ""

    timestamp = run(f"git show -s --format=%cI {commit_hash}")
    print(f"Commit info: hash={commit_hash}, timestamp={timestamp}, message='{message}'")
    return CommitInfo(commit_hash=commit_hash, timestamp=timestamp, message=message)


def format_pub_time(date_iso: str) -> str:
    dt = datetime.fromisoformat(date_iso.replace("Z", "+00:00"))
    return dt.strftime("%Y-%m-%d %H:%M:%S UTC")


def build_story_block(meta: PostMeta, commit: CommitInfo, total_articles: int, sample_titles: List[str]) -> str:
    pub_time = format_pub_time(meta.date_iso)
    significance_display = f"{meta.significance:.1f}/10.0"
    sample_text = "; ".join(sample_titles) if sample_titles else "No articles yet"
    original_post_link = f"/deepseek-news/{POST_PATH.stem}.html"

    story_summary = (
        "Federal jury finds Uber liable in the first bellwether sexual assault trial from the 3,000+ case MDL, "
        "awarding $8.5 million to a 19-year-old passenger; verdict heightens legal and financial exposure for Uber."
    )

    block = f"""        <!-- Story 5 -->
        <div class="story">
            <div class="story-number">5</div>
            <h2>"{meta.title}"</h2>
            
            <div class="timeline">
                <p><strong>Publication Time:</strong> {pub_time}</p>
                <p><strong>Git Commit:</strong> <code>{commit.commit_hash}</code> at {commit.timestamp}</p>
                <p><strong>Significance Score:</strong> <span class="badge badge-score">{significance_display}</span></p>
                <p><strong>Category:</strong> <span class="badge badge-pr">Legal Verdict</span></p>
                <p><strong>Source:</strong> <a href="{meta.source_url}">PR Newswire Releases</a></p>
                <p><strong>Original Post:</strong> <a href="{original_post_link}">{POST_PATH.name}</a></p>
            </div>
            
            <h3>Story Summary</h3>
            <p>{story_summary}</p>
            
            <div class="evidence">
                <h4>Evidence of Primary Source Status & Timing</h4>
                <ul>
                    <li>PR Newswire carried the federal jury verdict; captured directly from the source feed</li>
                    <li>First bellwether verdict in the 3,000+ rideshare sexual assault MDL, awarding $8.5M to the plaintiff</li>
                    <li>Git commit {commit.commit_hash} at {commit.timestamp} provides verifiable publication timing</li>
                    <li>Google News search returned {total_articles} subsequent articles (examples: {sample_text})</li>
                </ul>
            </div>
        </div>
"""
    return block


def replace_story_five(html: str, new_block: str) -> str:
    marker = "<!-- Story 5 -->"
    if marker not in html:
        raise ValueError("Could not find Story 5 marker in HTML.")

    start = html.index(marker)
    next_section = html.find("<section>", start)
    if next_section == -1:
        raise ValueError("Could not locate the end of Story 5 section.")

    before = html[:start]
    after = html[next_section:]
    return before + new_block + after


def update_summary_articles(html: str, new_count: int) -> str:
    """Replace the first occurrence of '<number> articles' with the new count."""
    updated_html, replaced = re.subn(r"\b\d+\s+articles\b", f"{new_count} articles", html, count=1)
    if replaced == 0:
        print("Warning: could not find 'articles' count to update in summary section.")
        return html
    print(f"Updated summary articles count to {new_count} articles.")
    return updated_html


def main() -> None:
    meta = read_post_metadata(POST_PATH)
    commit = get_commit_info(POST_PATH)

    print(f"Searching Google News for '{SEARCH_QUERY}'...")
    articles = search_google_news(SEARCH_QUERY, max_results=20)
    total_articles = len(articles)
    sample_titles = [normalize_ascii(a.get("title", "")) for a in articles[:3]]
    print(f"Found {total_articles} articles. Sample titles: {sample_titles}")

    story_block = build_story_block(meta, commit, total_articles, sample_titles)

    print(f"Reading HTML from {HTML_PATH}")
    html = HTML_PATH.read_text(encoding="utf-8")

    print("Replacing Story 5 with Uber verdict details...")
    html = replace_story_five(html, story_block)

    print("Updating summary articles count...")
    html = update_summary_articles(html, total_articles)

    print(f"Writing updated HTML to {HTML_PATH}")
    HTML_PATH.write_text(html, encoding="utf-8")
    print("Update complete.")


if __name__ == "__main__":
    main()
