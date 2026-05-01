import logging
import logging.config
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from app.database import Base, SessionLocal
from app.routers import profiles, scoring, graph, ingest, sourcing
from app.routers import vc_signals
from app.routers import founders

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
    # Create all tables (idempotent — safe to run on every startup for SQLite dev)
    from app.database import engine
    import app.models  # noqa — registers all models with Base.metadata
    Base.metadata.create_all(bind=engine)

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
app.include_router(vc_signals.router)
app.include_router(founders.router)

# Serve the React frontend at /new (SPA — all sub-routes return index.html)
_frontend_react = Path(__file__).parent.parent / "frontend_react" / "dist"
if _frontend_react.exists():
    app.mount("/new/assets", StaticFiles(directory=str(_frontend_react / "assets")), name="new-assets")

    @app.get("/new", include_in_schema=False)
    @app.get("/new/{path:path}", include_in_schema=False)
    async def new_frontend(path: str = ""):
        return FileResponse(str(_frontend_react / "index.html"))

# Serve the frontend dashboard
_frontend = Path(__file__).parent.parent / "frontend"
if _frontend.exists():
    app.mount("/static", StaticFiles(directory=str(_frontend)), name="static")

@app.get("/dashboard", include_in_schema=False)
async def dashboard():
    return FileResponse(str(_frontend / "index.html"))


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
    return RedirectResponse(url="/dashboard")
