import asyncio
import math
import os
import re
import time
from datetime import datetime, timezone
from typing import Optional

import httpx
from fastapi import APIRouter, BackgroundTasks
from upstash_redis import Redis

from database import get_supabase
from models import TrendSnapshotIn, IngestResult

router = APIRouter(prefix="/api/ingest", tags=["ingest"])

def get_redis() -> Optional[Redis]:
    url = os.environ.get("UPSTASH_REDIS_REST_URL")
    token = os.environ.get("UPSTASH_REDIS_REST_TOKEN")
    if url and token:
        return Redis(url=url, token=token)
    return None

def compute_heat(score: int, comments: int, posted_at: Optional[datetime]) -> float:
    base = math.log10(max(score, 0) + 1) * 10
    if posted_at:
        now = datetime.now(timezone.utc)
        if posted_at.tzinfo is None:
            posted_at = posted_at.replace(tzinfo=timezone.utc)
        hours_old = max((now - posted_at).total_seconds() / 3600, 0.5)
        velocity = comments / hours_old
    else:
        velocity = 0
    return round(base + velocity * 2, 3)

STOP_WORDS = {
    "the","a","an","and","or","but","in","on","at","to","for","of","with","by",
    "from","is","are","was","were","be","been","has","have","had","do","does",
    "did","will","would","could","should","may","might","this","that","it","its",
    "how","why","what","when","who","i","my","your","their","our","we","he","she",
    "they","you","not","no","so","if","as","up","out","new","use","get","can",
    "now","just","vs","via","ask","show","about","into","than","more","also",
    "after","over","any","all",
}

def extract_tags(title: str, subreddit: Optional[str] = None) -> list[str]:
    words = re.findall(r"[a-zA-Z][a-zA-Z0-9+#\-\.]{1,}", title.lower())
    tags = [w for w in words if w not in STOP_WORDS and len(w) > 2][:8]
    if subreddit and subreddit.lower() not in STOP_WORDS:
        tags = [subreddit.lower()] + tags
    return list(dict.fromkeys(tags))

REDDIT_SUBREDDITS = [
    "technology","programming","MachineLearning",
    "artificial","webdev","opensource","SoftwareEngineering"
]
SOURCE_IDS = {"reddit": 1, "hackernews": 2, "github": 3}

async def fetch_reddit(client: httpx.AsyncClient) -> list[TrendSnapshotIn]:
    snapshots = []
    headers = {"User-Agent": "PulseBoard/1.0 (trend intelligence dashboard)"}
    for sub in REDDIT_SUBREDDITS:
        try:
            resp = await client.get(
                f"https://www.reddit.com/r/{sub}/hot.json?limit=15",
                headers=headers, timeout=10.0,
            )
            resp.raise_for_status()
            posts = resp.json().get("data", {}).get("children", [])
            for post in posts:
                p = post.get("data", {})
                if p.get("stickied"):
                    continue
                posted_at = datetime.fromtimestamp(
                    p.get("created_utc", time.time()), tz=timezone.utc
                )
                title = p.get("title", "").strip()
                if not title:
                    continue
                url = p.get("url") or f"https://reddit.com{p.get('permalink', '')}"
                snapshots.append(TrendSnapshotIn(
                    source_id=SOURCE_IDS["reddit"],
                    external_id=p["id"],
                    title=title,
                    url=url,
                    author=p.get("author"),
                    score=p.get("score", 0),
                    comment_count=p.get("num_comments", 0),
                    heat_score=compute_heat(p.get("score", 0), p.get("num_comments", 0), posted_at),
                    posted_at=posted_at,
                    tags=extract_tags(title, subreddit=sub),
                    raw_payload={"subreddit": sub, "permalink": p.get("permalink")},
                ))
        except Exception as e:
            print(f"[ingest] Reddit r/{sub} error: {e}")
    return snapshots

HN_BASE = "https://hacker-news.firebaseio.com/v0"

async def fetch_hn_story(client: httpx.AsyncClient, story_id: int) -> Optional[TrendSnapshotIn]:
    try:
        resp = await client.get(f"{HN_BASE}/item/{story_id}.json", timeout=8.0)
        resp.raise_for_status()
        item = resp.json()
        if not item or item.get("type") != "story" or item.get("deleted"):
            return None
        title = item.get("title", "").strip()
        if not title:
            return None
        posted_at = datetime.fromtimestamp(item.get("time", time.time()), tz=timezone.utc)
        score = item.get("score", 0)
        comments = item.get("descendants", 0)
        url = item.get("url") or f"https://news.ycombinator.com/item?id={story_id}"
        return TrendSnapshotIn(
            source_id=SOURCE_IDS["hackernews"],
            external_id=str(story_id),
            title=title,
            url=url,
            author=item.get("by"),
            score=score,
            comment_count=comments,
            heat_score=compute_heat(score, comments, posted_at),
            posted_at=posted_at,
            tags=extract_tags(title),
            raw_payload={"hn_id": story_id},
        )
    except Exception as e:
        print(f"[ingest] HN story {story_id} error: {e}")
        return None

async def fetch_hackernews(client: httpx.AsyncClient) -> list[TrendSnapshotIn]:
    try:
        resp = await client.get(f"{HN_BASE}/topstories.json", timeout=10.0)
        resp.raise_for_status()
        story_ids = resp.json()[:40]
    except Exception as e:
        print(f"[ingest] HN topstories error: {e}")
        return []
    snapshots = []
    for i in range(0, len(story_ids), 10):
        batch = story_ids[i:i+10]
        results = await asyncio.gather(*[fetch_hn_story(client, sid) for sid in batch])
        snapshots.extend([r for r in results if r is not None])
        if i + 10 < len(story_ids):
            await asyncio.sleep(0.3)
    return snapshots

def write_snapshots(snapshots: list[TrendSnapshotIn]) -> tuple[int, int]:
    if not snapshots:
        return 0, 0
    db = get_supabase()
    inserted = 0
    skipped = 0
    for i in range(0, len(snapshots), 50):
        batch = snapshots[i:i+50]
        rows = []
        for s in batch:
            row = s.model_dump()
            if row.get("posted_at"):
                row["posted_at"] = row["posted_at"].isoformat()
            rows.append(row)
        try:
            db.table("trend_snapshots").upsert(
                rows, ignore_duplicates=True, on_conflict="source_id,external_id"
            ).execute()
            inserted += len(batch)
        except Exception as e:
            print(f"[ingest] Supabase write error: {e}")
            skipped += len(batch)
    return inserted, skipped

def aggregate_topics() -> list[dict]:
    """Returns topic rows for AI enrichment."""
    db = get_supabase()
    try:
        from datetime import timedelta
        from collections import defaultdict
        window_start = datetime.now(timezone.utc) - timedelta(hours=2)
        window_end = datetime.now(timezone.utc)

        result = db.table("trend_snapshots") \
            .select("id,title,url,score,comment_count,heat_score,tags,source_id,fetched_at") \
            .gte("fetched_at", window_start.isoformat()) \
            .execute()
        snapshots = result.data or []
        if not snapshots:
            return []

        source_map = {1: "reddit", 2: "hackernews", 3: "github"}
        topic_groups: dict[str, list[dict]] = defaultdict(list)
        for snap in snapshots:
            for tag in (snap.get("tags") or [])[:4]:
                topic_groups[tag].append(snap)

        topic_groups = {t: s for t, s in topic_groups.items() if len(s) >= 2}

        prev_result = db.table("trending_topics") \
            .select("topic,avg_heat") \
            .gte("window_start", (window_start - timedelta(hours=2)).isoformat()) \
            .execute()
        prev_heats = {r["topic"]: r["avg_heat"] for r in (prev_result.data or [])}

        topic_rows = []
        for topic, snaps in topic_groups.items():
            heats = [s["heat_score"] for s in snaps]
            avg_heat = sum(heats) / len(heats)
            peak_heat = max(heats)
            breakdown: dict[str, int] = defaultdict(int)
            for s in snaps:
                breakdown[source_map.get(s["source_id"], "unknown")] += 1
            sorted_snaps = sorted(snaps, key=lambda x: x["heat_score"], reverse=True)[:5]
            top_urls = [
                {"title": s["title"], "url": s.get("url"),
                 "source": source_map.get(s["source_id"], "unknown"),
                 "heat": s["heat_score"]}
                for s in sorted_snaps
            ]
            momentum = round(avg_heat - prev_heats.get(topic, avg_heat), 3)
            topic_rows.append({
                "topic": topic,
                "mention_count": len(snaps),
                "avg_heat": round(avg_heat, 3),
                "peak_heat": round(peak_heat, 3),
                "momentum": momentum,
                "source_breakdown": dict(breakdown),
                "top_urls": top_urls,
                "window_start": window_start.isoformat(),
                "window_end": window_end.isoformat(),
                "ai_insight": None,
                "sentiment": "neutral",
                "category": "other",
            })

        topic_rows.sort(key=lambda x: x["avg_heat"], reverse=True)
        return topic_rows[:50]

    except Exception as e:
        print(f"[aggregate] Error: {e}")
        return []


async def run_ingest() -> IngestResult:
    result = IngestResult()

    # Fetch Reddit + HN + GitHub concurrently
    from routers.github import fetch_github_trending
    async with httpx.AsyncClient() as client:
        reddit_snaps, hn_snaps = await asyncio.gather(
            fetch_reddit(client), fetch_hackernews(client)
        )
    github_snaps = await fetch_github_trending()

    result.reddit_fetched = len(reddit_snaps)
    result.hn_fetched = len(hn_snaps)

    all_snaps = reddit_snaps + hn_snaps + github_snaps
    result.inserted, result.skipped_duplicates = write_snapshots(all_snaps)

    # Aggregate topics
    topic_rows = aggregate_topics()
    print(f"[ingest] Aggregated {len(topic_rows)} topics — enriching with Groq AI...")

    # Enrich with Groq AI insights
    from groq_insights import enrich_topics_with_insights
    enriched_rows = await enrich_topics_with_insights(topic_rows)

    # Write enriched topics to Supabase
    if enriched_rows:
        db = get_supabase()
        try:
            db.table("trending_topics").insert(enriched_rows).execute()
            print(f"[ingest] Wrote {len(enriched_rows)} enriched topics to Supabase")
        except Exception as e:
            print(f"[ingest] Topic write error: {e}")

    # Cache result in Redis
    redis = get_redis()
    if redis:
        import json
        redis.setex("pulseboard:last_ingest", 3600, json.dumps({
            **result.model_dump(),
            "topics_aggregated": len(enriched_rows),
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }))

    return result

@router.post("/", summary="Trigger ingest in background")
async def trigger_ingest(background_tasks: BackgroundTasks):
    background_tasks.add_task(run_ingest)
    return {"status": "ingest_started"}

@router.post("/sync", summary="Synchronous ingest")
async def trigger_ingest_sync() -> IngestResult:
    return await run_ingest()

@router.get("/status", summary="Last ingest stats")
async def ingest_status():
    redis = get_redis()
    if not redis:
        return {"error": "Redis not configured"}
    import json
    cached = redis.get("pulseboard:last_ingest")
    if not cached:
        return {"status": "no_data"}
    return json.loads(cached)