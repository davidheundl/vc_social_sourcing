"""
VC Social Sourcing Tool — FastAPI application entry point.

Start with:
    uvicorn main:app --reload
"""

import logging
import logging.config
from contextlib import asynccontextmanager
from datetime import datetime, timezone

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware

from config import config
from database import get_db, init_db, log_error
from models.founder import (
    FounderDetail,
    FounderOut,
    FounderPatch,
    FounderStatus,
    HealthOut,
    JobStatus,
    ManualSearchRequest,
    PaginatedFounders,
    SignalOut,
    StatsOut,
)
from scheduler import shutdown_scheduler, start_scheduler

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------

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
        "console": {
            "class": "logging.StreamHandler",
            "formatter": "standard",
        }
    },
    "root": {"level": "INFO", "handlers": ["console"]},
}

logging.config.dictConfig(LOGGING_CONFIG)
logger = logging.getLogger("main")

# ---------------------------------------------------------------------------
# App lifecycle
# ---------------------------------------------------------------------------


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Starting VC Sourcing Tool backend …")
    init_db()
    start_scheduler()
    logger.info("All systems running. API ready.")
    yield
    logger.info("Shutting down …")
    shutdown_scheduler()


app = FastAPI(
    title="VC Social Sourcing Tool",
    description="Finds early-stage stealth founders across Twitter, LinkedIn & ProductHunt",
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ---------------------------------------------------------------------------
# GET /founders
# ---------------------------------------------------------------------------


@app.get("/founders", response_model=PaginatedFounders, tags=["Founders"])
async def list_founders(
    min_score: int = Query(default=40, ge=0, le=100),
    status: FounderStatus | None = Query(default=None),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
):
    """List founders sorted by score descending, optionally filtered by status."""
    with get_db() as conn:
        conditions = ["score >= ?"]
        params: list = [min_score]

        if status:
            conditions.append("status = ?")
            params.append(status.value)

        where = " AND ".join(conditions)
        total = conn.execute(
            f"SELECT COUNT(*) FROM founders WHERE {where}", params
        ).fetchone()[0]

        rows = conn.execute(
            f"SELECT * FROM founders WHERE {where} ORDER BY score DESC LIMIT ? OFFSET ?",
            [*params, limit, offset],
        ).fetchall()

    return PaginatedFounders(
        total=total,
        limit=limit,
        offset=offset,
        items=[FounderOut.from_row(r) for r in rows],
    )


# ---------------------------------------------------------------------------
# GET /founders/{id}
# ---------------------------------------------------------------------------


@app.get("/founders/{founder_id}", response_model=FounderDetail, tags=["Founders"])
async def get_founder(founder_id: int):
    """Return full founder profile with all associated signals."""
    with get_db() as conn:
        row = conn.execute(
            "SELECT * FROM founders WHERE id = ?", (founder_id,)
        ).fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="Founder not found")

        signals = conn.execute(
            "SELECT * FROM signals WHERE founder_id = ? ORDER BY created_at DESC",
            (founder_id,),
        ).fetchall()

    detail = FounderDetail.from_row(row)
    detail.signal_records = [SignalOut.from_row(s) for s in signals]
    return detail


# ---------------------------------------------------------------------------
# PATCH /founders/{id}
# ---------------------------------------------------------------------------


@app.patch("/founders/{founder_id}", response_model=FounderOut, tags=["Founders"])
async def update_founder(founder_id: int, body: FounderPatch):
    """Update a founder's status or notes (e.g. mark as reviewed/contacted)."""
    updates: list[str] = []
    params: list = []

    if body.status is not None:
        updates.append("status = ?")
        params.append(body.status.value)
    if body.notes is not None:
        updates.append("notes = ?")
        params.append(body.notes)

    if not updates:
        raise HTTPException(status_code=400, detail="No fields to update")

    updates.append("last_updated = ?")
    params.append(datetime.now(timezone.utc).isoformat())
    params.append(founder_id)

    with get_db() as conn:
        result = conn.execute(
            f"UPDATE founders SET {', '.join(updates)} WHERE id = ?", params
        )
        if result.rowcount == 0:
            raise HTTPException(status_code=404, detail="Founder not found")
        row = conn.execute(
            "SELECT * FROM founders WHERE id = ?", (founder_id,)
        ).fetchone()

    return FounderOut.from_row(row)


# ---------------------------------------------------------------------------
# GET /signals/recent
# ---------------------------------------------------------------------------


@app.get("/signals/recent", response_model=list[SignalOut], tags=["Signals"])
async def recent_signals(limit: int = Query(default=100, ge=1, le=500)):
    """Return the most recent raw signals across all data sources."""
    with get_db() as conn:
        rows = conn.execute(
            "SELECT * FROM signals ORDER BY created_at DESC LIMIT ?", (limit,)
        ).fetchall()
    return [SignalOut.from_row(r) for r in rows]


# ---------------------------------------------------------------------------
# POST /workers/google-dorker/enable  |  /disable
# ---------------------------------------------------------------------------


@app.post("/workers/google-dorker/enable", tags=["Workers"])
async def enable_google_dorker():
    """Enable the Google Dorker for this session (uses SerpAPI quota)."""
    config.GOOGLE_DORKER_ENABLED = True
    logger.warning("Google Dorker ENABLED via API — SerpAPI quota will be consumed")
    return {"google_dorker_enabled": True}


@app.post("/workers/google-dorker/disable", tags=["Workers"])
async def disable_google_dorker():
    """Disable the Google Dorker to protect SerpAPI quota."""
    config.GOOGLE_DORKER_ENABLED = False
    logger.info("Google Dorker disabled via API")
    return {"google_dorker_enabled": False}


@app.post("/workers/google-dorker/run-once", tags=["Workers"])
async def run_google_dorker_once():
    """Trigger a single Google Dorker run right now, regardless of the enabled flag."""
    import asyncio
    from workers.google_dorker import run as dorker_run
    logger.warning("Google Dorker triggered manually — SerpAPI quota will be consumed")
    loop = asyncio.get_event_loop()
    count = await loop.run_in_executor(None, lambda: dorker_run(force=True))
    return {"new_signals": count}


# ---------------------------------------------------------------------------
# GET /stats
# ---------------------------------------------------------------------------


@app.get("/stats", response_model=StatsOut, tags=["Analytics"])
async def get_stats():
    """Aggregate statistics: totals, source breakdown, average score."""
    with get_db() as conn:
        total = conn.execute("SELECT COUNT(*) FROM founders").fetchone()[0]

        today_str = datetime.now(timezone.utc).date().isoformat()
        today_count = conn.execute(
            "SELECT COUNT(*) FROM founders WHERE first_seen >= ?", (today_str,)
        ).fetchone()[0]

        avg_score_row = conn.execute(
            "SELECT AVG(score) FROM founders"
        ).fetchone()[0]
        avg_score = round(float(avg_score_row or 0), 1)

        source_rows = conn.execute(
            "SELECT source, COUNT(*) as cnt FROM signals GROUP BY source"
        ).fetchall()
        by_source = {r["source"]: r["cnt"] for r in source_rows}

    return StatsOut(
        total_founders=total,
        founders_today=today_count,
        average_score=avg_score,
        by_source=by_source,
    )


# ---------------------------------------------------------------------------
# POST /search/manual
# ---------------------------------------------------------------------------


@app.post("/search/manual", response_model=FounderDetail, tags=["Actions"])
async def manual_search(body: ManualSearchRequest):
    """
    Trigger immediate Proxycurl enrichment for a LinkedIn URL.
    Returns the enriched founder profile.
    """
    from workers.proxycurl_enricher import enrich_url

    if not config.PROXYCURL_API_KEY:
        raise HTTPException(
            status_code=503,
            detail="Proxycurl API key not configured",
        )

    result = enrich_url(body.linkedin_url)
    if result is None:
        raise HTTPException(
            status_code=502,
            detail="Proxycurl enrichment failed or returned no data",
        )

    with get_db() as conn:
        row = conn.execute(
            "SELECT * FROM founders WHERE linkedin_url = ?", (body.linkedin_url,)
        ).fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="Founder not saved — check URL")

        signals = conn.execute(
            "SELECT * FROM signals WHERE founder_id = ? ORDER BY created_at DESC",
            (row["id"],),
        ).fetchall()

    # Trigger scoring immediately
    from scoring import score_founder
    score_founder(row["id"])

    with get_db() as conn:
        row = conn.execute(
            "SELECT * FROM founders WHERE id = ?", (row["id"],)
        ).fetchone()

    detail = FounderDetail.from_row(row)
    detail.signal_records = [SignalOut.from_row(s) for s in signals]
    return detail


# ---------------------------------------------------------------------------
# GET /health
# ---------------------------------------------------------------------------


@app.get("/health", response_model=HealthOut, tags=["System"])
async def health():
    """Return scheduler status, last run times, and database row counts."""
    from scheduler import get_scheduler

    scheduler = get_scheduler()
    scheduler_status = "running" if (scheduler and scheduler.running) else "stopped"

    with get_db() as conn:
        job_rows = conn.execute("SELECT * FROM jobs_log").fetchall()
        db_counts = {
            "founders": conn.execute("SELECT COUNT(*) FROM founders").fetchone()[0],
            "signals": conn.execute("SELECT COUNT(*) FROM signals").fetchone()[0],
            "investors": conn.execute("SELECT COUNT(*) FROM investor_db").fetchone()[0],
            "errors": conn.execute("SELECT COUNT(*) FROM errors").fetchone()[0],
        }

    jobs = [
        JobStatus(
            job_name=r["job_name"],
            last_run=r["last_run"],
            last_count=r["last_count"] or 0,
            consecutive_failures=r["consecutive_failures"] or 0,
            paused_until=r["paused_until"],
        )
        for r in job_rows
    ]

    return HealthOut(
        status=scheduler_status,
        db_counts=db_counts,
        jobs=jobs,
    )


# ---------------------------------------------------------------------------
# Root redirect to docs
# ---------------------------------------------------------------------------


@app.get("/", include_in_schema=False)
async def root():
    from fastapi.responses import RedirectResponse
    return RedirectResponse(url="/dashboard")


@app.get("/dashboard", include_in_schema=False)
async def dashboard():
    from fastapi.responses import HTMLResponse

    with get_db() as conn:
        rows = conn.execute(
            "SELECT * FROM founders ORDER BY score DESC LIMIT 200"
        ).fetchall()
        stats = {
            "total": conn.execute("SELECT COUNT(*) FROM founders").fetchone()[0],
            "signals": conn.execute("SELECT COUNT(*) FROM signals").fetchone()[0],
        }

    source_colors = {
        "twitter": "#1DA1F2",
        "linkedin": "#0A66C2",
        "producthunt": "#DA552F",
        "google": "#34A853",
        "hackernews": "#FF6600",
    }

    def badge(source: str) -> str:
        color = source_colors.get(source, "#888")
        return f'<span style="background:{color};color:#fff;padding:2px 7px;border-radius:10px;font-size:11px;margin:1px;display:inline-block">{source}</span>'

    def score_color(score: int) -> str:
        if score >= 70:
            return "#16a34a"
        if score >= 40:
            return "#d97706"
        return "#dc2626"

    rows_html = ""
    for r in rows:
        import json
        try:
            signals = json.loads(r["signals"]) if isinstance(r["signals"], str) else (r["signals"] or [])
        except Exception:
            signals = []
        badges = "".join(badge(s) for s in signals)
        sc = r["score"] or 0
        twitter = f'<a href="https://twitter.com/{r["twitter_handle"]}" target="_blank">@{r["twitter_handle"]}</a>' if r["twitter_handle"] else "—"
        linkedin = f'<a href="{r["linkedin_url"]}" target="_blank">LinkedIn</a>' if r["linkedin_url"] else "—"
        rows_html += f"""
        <tr>
            <td style="font-weight:600">{r["name"] or "Unknown"}</td>
            <td>{twitter}</td>
            <td>{linkedin}</td>
            <td style="text-align:center">
                <span style="font-weight:700;color:{score_color(sc)};font-size:16px">{sc}</span>
            </td>
            <td>{badges or "—"}</td>
            <td style="font-size:12px;color:#555;max-width:260px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap" title="{(r['bio'] or '').replace(chr(34), '')}">{r["bio"] or "—"}</td>
            <td style="font-size:12px;color:#888">{(r["first_seen"] or "")[:10]}</td>
        </tr>"""

    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>VC Founder Sourcing</title>
<style>
  * {{ box-sizing: border-box; margin: 0; padding: 0; }}
  body {{ font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif; background: #f8fafc; color: #1e293b; }}
  header {{ background: #0f172a; color: #fff; padding: 20px 32px; display: flex; align-items: center; gap: 16px; }}
  header h1 {{ font-size: 20px; font-weight: 700; }}
  header p {{ font-size: 13px; color: #94a3b8; margin-top: 2px; }}
  .stats {{ display: flex; gap: 16px; padding: 20px 32px; }}
  .stat {{ background: #fff; border: 1px solid #e2e8f0; border-radius: 8px; padding: 14px 20px; min-width: 130px; }}
  .stat .n {{ font-size: 28px; font-weight: 700; color: #0f172a; }}
  .stat .l {{ font-size: 12px; color: #64748b; margin-top: 2px; }}
  .table-wrap {{ padding: 0 32px 40px; overflow-x: auto; }}
  table {{ width: 100%; border-collapse: collapse; background: #fff; border: 1px solid #e2e8f0; border-radius: 8px; overflow: hidden; }}
  th {{ background: #f1f5f9; font-size: 11px; text-transform: uppercase; letter-spacing: .05em; color: #64748b; padding: 10px 14px; text-align: left; border-bottom: 1px solid #e2e8f0; }}
  td {{ padding: 10px 14px; border-bottom: 1px solid #f1f5f9; font-size: 13px; vertical-align: middle; }}
  tr:last-child td {{ border-bottom: none; }}
  tr:hover td {{ background: #f8fafc; }}
  a {{ color: #3b82f6; text-decoration: none; }}
  a:hover {{ text-decoration: underline; }}
  .empty {{ text-align: center; padding: 60px; color: #94a3b8; font-size: 15px; }}
</style>
</head>
<body>
<header>
  <div>
    <h1>VC Founder Sourcing</h1>
    <p>Early-stage stealth founders — sorted by signal score</p>
  </div>
  <div style="margin-left:auto;font-size:12px;color:#64748b">
    <a href="/docs" style="color:#7dd3fc">API docs</a>
  </div>
</header>
<div class="stats">
  <div class="stat"><div class="n">{stats["total"]}</div><div class="l">Founders found</div></div>
  <div class="stat"><div class="n">{stats["signals"]}</div><div class="l">Signals collected</div></div>
</div>
<div class="table-wrap">
{"<p class='empty'>No founders yet — crawlers are running, check back in a moment.</p>" if not rows else f"""
  <table>
    <thead>
      <tr>
        <th>Name</th><th>Twitter</th><th>LinkedIn</th><th style="text-align:center">Score</th><th>Sources</th><th>Bio</th><th>First seen</th>
      </tr>
    </thead>
    <tbody>{rows_html}</tbody>
  </table>"""}
</div>
</body>
</html>"""
    return HTMLResponse(html)
