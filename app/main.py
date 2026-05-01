import logging
import logging.config
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.database import Base, SessionLocal
from app.routers import profiles, scoring, graph, ingest
from app.routers import sourcing

LOGGING_CONFIG = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
        "standard": {
            "format": "[%(asctime)s] [%(name)s] [%(levelname)s] %(message)s",
            "datefmt": "%Y-%m-%dT%H:%M:%SZ",
        }
    },
    "handlers": {
        "console": {"class": "logging.StreamHandler", "formatter": "standard"}
    },
    "root": {"level": "INFO", "handlers": ["console"]},
}

logging.config.dictConfig(LOGGING_CONFIG)
logger = logging.getLogger("main")


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Starting VC Lead Intelligence API …")
    # Schema is managed by Alembic — run `alembic upgrade head` before starting.

    with SessionLocal() as db:
        from app.services.worker_db import seed_investors, seed_job_logs
        seed_investors(db)
        seed_job_logs(db)

    from scheduler import start_scheduler
    start_scheduler()

    logger.info("All systems running. API ready.")
    yield

    from scheduler import shutdown_scheduler
    shutdown_scheduler()
    logger.info("Shutdown complete.")


app = FastAPI(
    title="VC Lead Intelligence API",
    description="Score and rank early-stage founders for VC sourcing",
    version="0.2.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(profiles.router)
app.include_router(scoring.router)
app.include_router(graph.router)
app.include_router(ingest.router)
app.include_router(sourcing.router)


@app.get("/health", tags=["meta"])
def health():
    from scheduler import get_scheduler
    from app.models.job_log import JobLog, ErrorLog
    from app.models.profile import Profile
    from app.models.signal import Signal
    from app.models.investor import InvestorProfile

    scheduler = get_scheduler()
    scheduler_status = "running" if (scheduler and scheduler.running) else "stopped"

    with SessionLocal() as db:
        jobs = [
            {
                "job_name": j.job_name,
                "last_run": j.last_run.isoformat() if j.last_run else None,
                "last_count": j.last_count or 0,
                "consecutive_failures": j.consecutive_failures or 0,
                "paused_until": j.paused_until.isoformat() if j.paused_until else None,
            }
            for j in db.query(JobLog).all()
        ]
        db_counts = {
            "profiles": db.query(Profile).count(),
            "signals": db.query(Signal).count(),
            "investors": db.query(InvestorProfile).count(),
            "errors": db.query(ErrorLog).count(),
        }

    return {"status": scheduler_status, "db_counts": db_counts, "jobs": jobs}


@app.get("/", include_in_schema=False)
async def root():
    from fastapi.responses import RedirectResponse
    return RedirectResponse(url="/docs")
