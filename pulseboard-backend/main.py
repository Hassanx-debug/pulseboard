import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from routers import ingest, trends
from scheduler import scheduler, setup_scheduler

logging.basicConfig(level=logging.INFO,
    format="%(asctime)s [%(name)s] %(levelname)s: %(message)s")
logger = logging.getLogger("pulseboard")

@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("PulseBoard API starting up...")
    setup_scheduler()
    scheduler.start()
    logger.info("Scheduler started")
    try:
        from routers.ingest import run_ingest
        logger.info("Running initial ingest...")
        result = await run_ingest()
        logger.info(f"Ingest complete: {result.reddit_fetched} Reddit, {result.hn_fetched} HN, {result.inserted} inserted")
    except Exception as e:
        logger.warning(f"Initial ingest failed (non-fatal): {e}")
    yield
    logger.info("Shutting down...")
    scheduler.shutdown(wait=False)

app = FastAPI(title="PulseBoard API", version="2.0.0", lifespan=lifespan)

@app.middleware("http")
async def update_scheme_middleware(request: Request, call_next):
    proto = request.headers.get("x-forwarded-proto")
    if proto:
        request.scope["scheme"] = proto
    response = await call_next(request)
    return response

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",
        "https://localhost:3000",
        "https://pulseboard-teal-ten.vercel.app",
        "https://pulseboard-psi-dusky.vercel.app",
        "https://*.vercel.app",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

from routers.ingest import router as ingest_router
from routers.trends import router as trends_router
from routers.github import router as github_router

app.include_router(ingest_router)
app.include_router(trends_router)
app.include_router(github_router)

@app.get("/health")
async def health():
    import os
    return {
        "status": "ok",
        "version": "2.0.0",
        "supabase": "configured" if os.environ.get("SUPABASE_URL") else "missing",
        "redis": "configured" if os.environ.get("UPSTASH_REDIS_REST_URL") else "missing",
        "scheduler": scheduler.running,
    }

@app.get("/")
async def root():
    return {"name": "PulseBoard API", "version": "2.0.0", "docs": "/docs"}
