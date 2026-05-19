from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.interval import IntervalTrigger
import logging

logger = logging.getLogger("pulseboard.scheduler")
scheduler = AsyncIOScheduler()

def setup_scheduler():
    from routers.ingest import run_ingest
    scheduler.add_job(
        run_ingest,
        trigger=IntervalTrigger(minutes=5),
        id="ingest_cycle",
        name="Reddit + HackerNews ingest",
        replace_existing=True,
        max_instances=1,
        coalesce=True,
        misfire_grace_time=60,
    )
    logger.info("Scheduler: ingest_cycle registered (every 5 minutes)")