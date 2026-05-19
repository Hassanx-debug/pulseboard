"""
PulseBoard — Groq AI Insight Generator
Generates one-line intelligence summaries for trending topics.
Uses LLaMA 3.1 8B on Groq (free tier: 14,400 req/day).
"""

import os
import json
import asyncio
from typing import Optional
import httpx
from dotenv import load_dotenv

load_dotenv()

GROQ_API_URL = "https://api.groq.com/openai/v1/chat/completions"
GROQ_MODEL = "llama-3.1-8b-instant"  # fastest, free


async def generate_insight(
    topic: str,
    mention_count: int,
    avg_heat: float,
    source_breakdown: dict,
    top_urls: list,
) -> dict:
    """
    Generate AI insight for a single trending topic.
    Returns dict with: insight, sentiment, category
    """
    api_key = os.environ.get("GROQ_API_KEY")
    if not api_key:
        return {"insight": None, "sentiment": "neutral", "category": "other"}

    # Build context from top URLs
    url_context = ""
    for item in top_urls[:3]:
        url_context += f'- "{item.get("title", "")}" ({item.get("source", "")})\n'

    sources_str = ", ".join(
        f"{src}: {count}" for src, count in source_breakdown.items()
    )

    prompt = f"""You are a tech trend analyst. Analyze this trending topic and respond ONLY with a JSON object.

Topic: #{topic}
Mentions: {mention_count} posts across {sources_str}
Heat score: {avg_heat:.1f}
Sample headlines:
{url_context}

Respond with ONLY this JSON, no other text:
{{
  "insight": "one sharp sentence explaining why this is trending and what it means for developers (max 120 chars)",
  "sentiment": "bullish|bearish|neutral|controversial",
  "category": "ai|dev_tools|security|web|infra|language|hardware|business|other"
}}"""

    try:
        async with httpx.AsyncClient() as client:
            resp = await client.post(
                GROQ_API_URL,
                headers={
                    "Authorization": f"Bearer {api_key}",
                    "Content-Type": "application/json",
                },
                json={
                    "model": GROQ_MODEL,
                    "messages": [{"role": "user", "content": prompt}],
                    "max_tokens": 150,
                    "temperature": 0.3,
                },
                timeout=15.0,
            )
            resp.raise_for_status()
            data = resp.json()
            text = data["choices"][0]["message"]["content"].strip()

            # Strip markdown fences if present
            text = text.replace("```json", "").replace("```", "").strip()
            parsed = json.loads(text)

            return {
                "insight": parsed.get("insight", "")[:200],
                "sentiment": parsed.get("sentiment", "neutral"),
                "category": parsed.get("category", "other"),
            }

    except Exception as e:
        print(f"[groq] Error for topic '{topic}': {e}")
        return {"insight": None, "sentiment": "neutral", "category": "other"}


async def enrich_topics_with_insights(topics: list[dict]) -> list[dict]:
    """
    Takes a list of topic rows, enriches them with AI insights in batches.
    Rate limit: Groq free tier allows ~30 req/min, so we batch with delays.
    """
    if not os.environ.get("GROQ_API_KEY"):
        print("[groq] No API key set — skipping AI insights")
        return topics

    enriched = []
    batch_size = 5  # process 5 topics at a time

    for i in range(0, len(topics), batch_size):
        batch = topics[i:i + batch_size]

        tasks = [
            generate_insight(
                topic=t["topic"],
                mention_count=t["mention_count"],
                avg_heat=t["avg_heat"],
                source_breakdown=t.get("source_breakdown", {}),
                top_urls=t.get("top_urls", []),
            )
            for t in batch
        ]

        results = await asyncio.gather(*tasks)

        for topic, result in zip(batch, results):
            topic["ai_insight"] = result["insight"]
            topic["sentiment"] = result["sentiment"]
            topic["category"] = result["category"]
            enriched.append(topic)

        # Respect Groq rate limits — wait between batches
        if i + batch_size < len(topics):
            await asyncio.sleep(4)

    print(f"[groq] Enriched {len(enriched)} topics with AI insights")
    return enriched