from fastapi import FastAPI
from app.database import engine, Base
from app.routers import profiles, scoring, graph, ingest

# Create all tables on startup (dev convenience — use Alembic in prod)
Base.metadata.create_all(bind=engine)

app = FastAPI(
    title="VC Lead Intelligence API",
    description="Score and rank early-stage founders for VC sourcing",
    version="0.1.0",
)

app.include_router(profiles.router)
app.include_router(scoring.router)
app.include_router(graph.router)
app.include_router(ingest.router)


@app.get("/health", tags=["meta"])
def health():
    return {"status": "ok"}
