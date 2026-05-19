import json
import os
from datetime import datetime, timezone, timedelta
from typing import Optional

from fastapi import APIRouter, Query
from upstash_redis import Redis

from database import get_supabase

router = APIRouter(prefix="/api/trends", tags=["trends"])
CACHE_TTL = 60

def get_redis() -> Optional[Redis]:
    url = os.environ.get("UPSTASH_REDIS_REST_URL")
    token = os.environ.get("UPSTASH_REDIS_REST_TOKEN")
    if url and token:
        return Redis(url=url, token=token)
    return None

@router.get("/", summary="Top trending topics")
async def get_trends(
    limit: int = Query(default=20, ge=1, le=50),
    source: Optional[str] = Query(default=None),
    min_heat: float = Query(default=0.0),
):
    cache_key = f"pulseboard:trends:{limit}:{source}:{min_heat}"
    redis = get_redis()
    if redis:
        cached = redis.get(cache_key)
        if cached:
            return json.loads(cached)
    db = get_supabase()
    try:
        since = (datetime.now(timezone.utc) - timedelta(hours=3)).isoformat()
        result = db.table("trending_topics") \
            .select("*").order("avg_heat", desc=True) \
            .gte("computed_at", since).limit(limit * 3).execute()
        rows = result.data or []
        seen: dict[str, dict] = {}
        for row in rows:
            topic = row["topic"]
            if topic not in seen or row.get("computed_at", "") > seen[topic].get("computed_at", ""):
                seen[topic] = row
        topics = list(seen.values())
        if source:
            topics = [t for t in topics if source in (t.get("source_breakdown") or {})]
        if min_heat > 0:
            topics = [t for t in topics if (t.get("avg_heat") or 0) >= min_heat]
        topics.sort(key=lambda x: x.get("avg_heat", 0), reverse=True)
        topics = topics[:limit]
        for t in topics:
            if isinstance(t.get("top_urls"), str):
                try: t["top_urls"] = json.loads(t["top_urls"])
                except: t["top_urls"] = []
            if isinstance(t.get("source_breakdown"), str):
                try: t["source_breakdown"] = json.loads(t["source_breakdown"])
                except: t["source_breakdown"] = {}
        response = {"topics": topics, "count": len(topics),
                    "generated_at": datetime.now(timezone.utc).isoformat()}
        if redis:
            redis.setex(cache_key, CACHE_TTL, json.dumps(response, default=str))
        return response
    except Exception as e:
        return {"topics": [], "count": 0, "error": str(e),
                "generated_at": datetime.now(timezone.utc).isoformat()}

@router.get("/feed", summary="Live snapshot feed")
async def get_feed(
    limit: int = Query(default=30, ge=1, le=100),
    source: Optional[str] = Query(default=None),
):
    redis = get_redis()
    cache_key = f"pulseboard:feed:{limit}:{source}"
    if redis:
        cached = redis.get(cache_key)
        if cached:
            return json.loads(cached)
    db = get_supabase()
    try:
        query = db.from_("recent_snapshots").select("*").limit(limit)
        if source:
            query = query.eq("source", source)
        result = query.execute()
        response = {"items": result.data or [], "count": len(result.data or []),
                    "generated_at": datetime.now(timezone.utc).isoformat()}
        if redis:
            redis.setex(cache_key, 30, json.dumps(response, default=str))
        return response
    except Exception as e:
        return {"items": [], "count": 0, "error": str(e)}

@router.get("/stats", summary="Dashboard stats")
async def get_stats():
    redis = get_redis()
    if redis:
        cached = redis.get("pulseboard:stats")
        if cached:
            return json.loads(cached)
    db = get_supabase()
    try:
        since_24h = (datetime.now(timezone.utc) - timedelta(hours=24)).isoformat()
        since_1h = (datetime.now(timezone.utc) - timedelta(hours=1)).isoformat()
        total = db.table("trend_snapshots").select("id", count="exact").gte("fetched_at", since_24h).execute()
        recent = db.table("trend_snapshots").select("id", count="exact").gte("fetched_at", since_1h).execute()
        sources = db.table("trend_snapshots").select("source_id").gte("fetched_at", since_24h).execute()
        source_counts = {"reddit": 0, "hackernews": 0, "github": 0}
        for row in (sources.data or []):
            slug = {1: "reddit", 2: "hackernews", 3: "github"}.get(row["source_id"])
            if slug:
                source_counts[slug] += 1
        heat = db.table("trend_snapshots").select("heat_score").gte("fetched_at", since_1h) \
            .order("heat_score", desc=True).limit(1).execute()
        peak_heat = heat.data[0]["heat_score"] if heat.data else 0
        response = {
            "total_24h": total.count or 0,
            "ingested_1h": recent.count or 0,
            "peak_heat_1h": peak_heat,
            "source_counts_24h": source_counts,
            "generated_at": datetime.now(timezone.utc).isoformat(),
        }
        if redis:
            redis.setex("pulseboard:stats", 120, json.dumps(response, default=str))
        return response
    except Exception as e:
        return {"total_24h": 0, "ingested_1h": 0, "peak_heat_1h": 0,
                "source_counts_24h": {"reddit": 0, "hackernews": 0, "github": 0}, "error": str(e)}