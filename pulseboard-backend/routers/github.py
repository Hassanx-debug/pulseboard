"""
PulseBoard — GitHub Trending Scraper
Scrapes github.com/trending (no API key needed).
Uses stars/day as heat signal.
"""

import math
import re
import time
from datetime import datetime, timezone
from typing import Optional

import httpx
from fastapi import APIRouter

from database import get_supabase
from models import TrendSnapshotIn

router = APIRouter(prefix="/api/github", tags=["github"])

SOURCE_ID = 3  # github source_id in sources table

STOP_WORDS = {
    "the","a","an","and","or","but","in","on","at","to","for","of","with",
    "by","from","is","are","was","were","be","been","has","have","had",
}

def extract_tags(text: str) -> list[str]:
    words = re.findall(r"[a-zA-Z][a-zA-Z0-9+#\-\.]{1,}", text.lower())
    tags = [w for w in words if w not in STOP_WORDS and len(w) > 2][:6]
    return list(dict.fromkeys(tags))

def compute_heat(stars_today: int, total_stars: int) -> float:
    base = math.log10(max(total_stars, 0) + 1) * 8
    daily_boost = math.log10(max(stars_today, 0) + 1) * 15
    return round(base + daily_boost, 3)


async def fetch_github_trending() -> list[TrendSnapshotIn]:
    """Scrape GitHub trending page using their internal API."""
    snapshots = []

    try:
        async with httpx.AsyncClient() as client:
            # GitHub has an undocumented explore API
            resp = await client.get(
                "https://github.com/trending",
                headers={
                    "User-Agent": "Mozilla/5.0 (compatible; PulseBoard/1.0)",
                    "Accept": "text/html",
                },
                timeout=15.0,
                follow_redirects=True,
            )
            resp.raise_for_status()
            html = resp.text

        # Parse repo entries from HTML
        # Pattern: /owner/repo in article tags
        repo_pattern = re.findall(
            r'href="/([a-zA-Z0-9_.-]+/[a-zA-Z0-9_.-]+)"[^>]*>\s*\n?\s*(?:<[^>]+>\s*)*([^<\n]{3,80})',
            html
        )

        # Better: extract from the structured article blocks
        articles = re.findall(
            r'<article[^>]*class="[^"]*Box-row[^"]*"[^>]*>(.*?)</article>',
            html, re.DOTALL
        )

        seen = set()
        for article in articles[:25]:
            # Extract repo name
            repo_match = re.search(r'href="/([a-zA-Z0-9_.-]+/[a-zA-Z0-9_.-]+)"', article)
            if not repo_match:
                continue
            repo_path = repo_match.group(1)
            if repo_path in seen:
                continue
            seen.add(repo_path)

            # Extract description
            desc_match = re.search(r'<p[^>]*>\s*(.*?)\s*</p>', article, re.DOTALL)
            description = ""
            if desc_match:
                description = re.sub(r'<[^>]+>', '', desc_match.group(1)).strip()

            # Extract stars today
            stars_today = 0
            today_match = re.search(r'([\d,]+)\s*stars?\s*today', article, re.IGNORECASE)
            if today_match:
                stars_today = int(today_match.group(1).replace(",", ""))

            # Extract total stars
            total_stars = 0
            star_matches = re.findall(r'([\d,]+)\s*(?:stargazers|stars)', article, re.IGNORECASE)
            if star_matches:
                total_stars = int(star_matches[0].replace(",", ""))

            title = f"{repo_path}" + (f" — {description[:80]}" if description else "")
            tags = extract_tags(f"{repo_path} {description}")

            snapshots.append(TrendSnapshotIn(
                source_id=SOURCE_ID,
                external_id=repo_path,
                title=title,
                url=f"https://github.com/{repo_path}",
                author=repo_path.split("/")[0],
                score=total_stars,
                comment_count=stars_today,  # stars_today as proxy for velocity
                heat_score=compute_heat(stars_today, total_stars),
                posted_at=datetime.now(timezone.utc),
                tags=tags,
                raw_payload={
                    "repo_path": repo_path,
                    "stars_today": stars_today,
                    "total_stars": total_stars,
                    "description": description,
                },
            ))

    except Exception as e:
        print(f"[github] Scrape error: {e}")

    print(f"[github] Fetched {len(snapshots)} trending repos")
    return snapshots


@router.post("/ingest", summary="Ingest GitHub trending repos")
async def ingest_github():
    snapshots = await fetch_github_trending()
    if not snapshots:
        return {"inserted": 0, "error": "No repos scraped"}

    db = get_supabase()
    rows = []
    for s in snapshots:
        row = s.model_dump()
        if row.get("posted_at"):
            row["posted_at"] = row["posted_at"].isoformat()
        rows.append(row)

    try:
        db.table("trend_snapshots").upsert(
            rows, ignore_duplicates=True, on_conflict="source_id,external_id"
        ).execute()
        return {"inserted": len(rows), "repos": [s.external_id for s in snapshots[:5]]}
    except Exception as e:
        return {"inserted": 0, "error": str(e)}