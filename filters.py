#!/usr/bin/env python3
"""
Filtering and significance scoring module for DeepSeek News Monitoring.
Provides scoring and filtering for news items to prioritize significant events.
"""

import re
import logging
from pathlib import Path
from typing import Dict, Any, List, Optional

logger = logging.getLogger(__name__)

class NewsFilter:
    def __init__(self):
        # Source type weights (0-10)
        self.source_weights = {
            # Government & Regulatory (highest weight)
            "sec_corpfin": 9.0,
            "sec_investment": 9.0,
            "nasa_breaking": 8.5,
            "fda_recalls": 8.0,
            "noaa_weather": 7.5,
            "usgs_earthquake": 7.0,
            
            # Tech releases (medium weight)
            "github_tensorflow": 6.5,
            "github_pytorch": 6.5,
            "github_huggingface": 6.5,
            "github_openai": 6.5,
            "github_langchain": 6.5,
            
            # Research (medium)
            "arxiv_cs_ai": 6.0,
            "arxiv_cs_cl": 6.0,
            "arxiv_cs_lg": 6.0,
            
            # Standards & Security
            "ietf_rfc": 7.0,
            "ietf_doc": 6.0,
            "cve_all": 7.5,
            
            # News aggregators (lower weight, often already covered)
            "hackernews": 5.0,
        }
        
        # Keywords that boost score
        self.important_keywords = {
            "breaking": 1.5,
            "alert": 1.3,
            "warning": 1.3,
            "emergency": 1.5,
            "critical": 1.4,
            "major": 1.4,
            "update": 1.1,
            "release": 1.2,
            "security": 1.4,
            "vulnerability": 1.4,
            "earthquake": 1.2,
            "hurricane": 1.5,
            "tornado": 1.5,
            "recall": 1.4,
            "filing": 1.2,
            "8-k": 1.5,  # SEC Form 8-K (current report)
            "10-k": 1.4,  # SEC Form 10-K (annual report)
            "10-q": 1.3,  # SEC Form 10-Q (quarterly report)
        }
        
        # Thresholds for specific source types
        self.thresholds = {
            "usgs_earthquake": 3.0,  # Minimum magnitude
            "hackernews": 100,  # Minimum points
            "github_*": "version_release",  # Only version releases, not commits
        }
        
        # Regex patterns
        self.patterns = {
            "earthquake_magnitude": r"M\s*([\d\.]+)\s*-",
            "version_number": r'\b(v?\d+\.\d+\.\d+|[vV]\d+\.\d+|release|version)\b',
            "github_commit": r'\b(trunk/|viable/|commit|Revert|\[)\b',
            "hackernews_points": r'Score:\s*(\d+)',
        }
    
    def extract_magnitude(self, title: str) -> Optional[float]:
        """Extract earthquake magnitude from title."""
        match = re.search(self.patterns["earthquake_magnitude"], title)
        if match:
            try:
                return float(match.group(1))
            except ValueError:
                return None
        return None
    
    def is_version_release(self, title: str) -> bool:
        """Check if GitHub title is a version release (not a commit)."""
        # Check for version number patterns
        if re.search(self.patterns["version_number"], title, re.IGNORECASE):
            return True
        
        # Check for commit-like patterns (lowercase if it's a commit)
        if re.search(self.patterns["github_commit"], title):
            return False
        
        # Default: assume it's a release if title is short and has version-like structure
        return len(title.split()) < 10 and any(char.isdigit() for char in title)
    
    def extract_hackernews_points(self, summary: str) -> Optional[int]:
        """Extract points from Hacker News summary."""
        match = re.search(self.patterns["hackernews_points"], summary)
        if match:
            try:
                return int(match.group(1))
            except ValueError:
                return None
        return None
    
    def score_item(self, item: Dict[str, Any]) -> float:
        """Score an item from 0-10 based on significance."""
        source = item.get("source", "")
        title = item.get("title", "").lower()
        summary = item.get("summary", "").lower()
        
        # Start with source weight
        base_score = self.source_weights.get(source, 5.0)
        
        # Apply source-specific scoring
        if source.startswith("usgs_earthquake"):
            magnitude = self.extract_magnitude(item.get("title", ""))
            if magnitude is not None:
                # Scale magnitude: M3.0 = 5.0, M4.0 = 6.0, M5.0 = 7.0, etc.
                mag_score = max(0, (magnitude - 2.0) * 2.0)
                base_score += mag_score
                logger.debug(f"Earthquake magnitude {magnitude}: +{mag_score:.1f}")
        
        elif source.startswith("github_"):
            if self.is_version_release(title):
                base_score += 2.0  # Bonus for actual releases
                logger.debug(f"GitHub version release: +2.0")
            else:
                base_score -= 1.5  # Penalty for commits/trivial updates
                logger.debug(f"GitHub commit/trivial: -1.5")
        
        elif source == "hackernews":
            points = self.extract_hackernews_points(item.get("summary", ""))
            if points is not None:
                # Scale points: 100 points = +1.0, 200 points = +2.0, etc.
                points_score = min(3.0, points / 100.0)
                base_score += points_score
                logger.debug(f"Hacker News points {points}: +{points_score:.1f}")
        
        # Apply keyword bonuses
        keyword_bonus = 0
        for keyword, boost in self.important_keywords.items():
            if keyword in title or keyword in summary:
                keyword_bonus += boost - 1.0  # Add the boost amount above 1.0
        
        # Cap keyword bonus at 2.0
        keyword_bonus = min(2.0, keyword_bonus)
        base_score += keyword_bonus
        
        # Normalize to 0-10 range
        final_score = max(0.0, min(10.0, base_score))
        
        logger.debug(f"Scored item '{title[:50]}...' from {source}: {final_score:.1f}/10")
        return final_score
    
    def should_publish(self, item: Dict[str, Any], threshold: float = 5.0) -> bool:
        """Determine if an item should be published based on score and source-specific thresholds."""
        score = self.score_item(item)
        
        # Check source-specific thresholds
        source = item.get("source", "")
        
        if source.startswith("usgs_earthquake"):
            magnitude = self.extract_magnitude(item.get("title", ""))
            if magnitude is not None and magnitude < self.thresholds["usgs_earthquake"]:
                logger.debug(f"Earthquake magnitude {magnitude} below threshold {self.thresholds['usgs_earthquake']}")
                return False
        
        elif source == "hackernews":
            points = self.extract_hackernews_points(item.get("summary", ""))
            if points is not None and points < self.thresholds["hackernews"]:
                logger.debug(f"Hacker News points {points} below threshold {self.thresholds['hackernews']}")
                return False
        
        elif source.startswith("github_"):
            if not self.is_version_release(item.get("title", "")):
                logger.debug(f"GitHub item is not a version release, skipping")
                return False
        
        # Final score threshold
        if score < threshold:
            logger.debug(f"Score {score:.1f} below threshold {threshold}")
            return False
        
        return True
    
    def filter_existing_posts(self, posts_dir: str = "_posts", threshold: float = 5.0):
        """Filter existing posts and move low-scoring ones to _trash directory."""
        posts_path = Path(posts_dir)
        trash_path = Path("_trash")
        trash_path.mkdir(exist_ok=True)
        
        moved_count = 0
        for post_file in posts_path.glob("*.md"):
            try:
                with open(post_file, 'r') as f:
                    content = f.read()
                
                # Extract metadata (simplified)
                title_match = re.search(r'title:\s*"([^"]+)"', content)
                source_match = re.search(r'source:\s*(\S+)', content)
                
                if title_match and source_match:
                    item = {
                        "title": title_match.group(1),
                        "source": source_match.group(1),
                        "summary": "",  # Would need to extract from content
                    }
                    
                    if not self.should_publish(item, threshold):
                        # Move to trash
                        trash_file = trash_path / post_file.name
                        post_file.rename(trash_file)
                        moved_count += 1
                        logger.info(f"Moved low-scoring post: {post_file.name}")
            
            except Exception as e:
                logger.error(f"Error processing {post_file}: {e}")
        
        logger.info(f"Filtered {moved_count} posts to _trash")
        return moved_count

# Convenience functions
def score_item(item: Dict[str, Any]) -> float:
    """Convenience function to score an item."""
    filter_obj = NewsFilter()
    return filter_obj.score_item(item)

def should_publish(item: Dict[str, Any], threshold: float = 5.0) -> bool:
    """Convenience function to check if item should be published."""
    filter_obj = NewsFilter()
    return filter_obj.should_publish(item, threshold)

if __name__ == "__main__":
    # Test the filter with sample items
    import json
    
    filter_obj = NewsFilter()
    
    test_items = [
        {
            "source": "usgs_earthquake",
            "title": "M 4.5 - 10 km NE of Some City",
            "summary": "Earthquake alert"
        },
        {
            "source": "usgs_earthquake",
            "title": "M 2.5 - 5 km NW of Small Town",
            "summary": "Minor earthquake"
        },
        {
            "source": "github_pytorch",
            "title": "Release v2.0.0: Major update",
            "summary": "PyTorch major release"
        },
        {
            "source": "github_pytorch",
            "title": "trunk/abc123: Fix typo",
            "summary": "Minor fix"
        },
        {
            "source": "hackernews",
            "title": "Interesting Tech Story",
            "summary": "Score: 250 | Comments: 45"
        },
    ]
    
    print("Testing filter scoring:")
    for item in test_items:
        score = filter_obj.score_item(item)
        should_pub = filter_obj.should_publish(item)
        print(f"  {item['source']}: '{item['title'][:30]}...' -> Score: {score:.1f}, Publish: {should_pub}")
