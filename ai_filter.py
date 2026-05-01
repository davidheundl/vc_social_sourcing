#!/usr/bin/env python3
"""
AI Founder Filter (Ollama)
==========================
Uses a local Ollama model to score founder potential. Free, no API key needed.

Setup (once):
    brew install ollama
    ollama pull llama3.2
    ollama serve          ← keep running in a separate terminal

Usage:
    python ai_filter.py             # Score all unscored profiles
    python ai_filter.py --rescore   # Re-score everything
    python ai_filter.py --model mistral  # Use a different model
"""

import argparse
import json
import re
import sqlite3
import sys
import time

import requests
from rich.console import Console
from rich.progress import track

console = Console()

OLLAMA_URL = "http://localhost:11434/api/generate"

PROMPT = """You analyze Twitter/X profiles to assess startup founder potential.

Profile:
Name: {name}
Username: @{username}
Bio: {bio}

Score founder potential 0-10:
- 8-10: Strong — engineer/PM at top tech company, mentions "building", "ex-FAANG", side projects
- 5-7:  Medium — tech background, investor, researcher, entrepreneur-adjacent
- 2-4:  Weak — general tech, media, academic, no founding intent
- 0-1:  Not relevant — politician, celebrity, brand, sports, news

Reply with ONLY this JSON (no explanation, no markdown):
{{"score": 7, "reason": "one sentence", "tags": ["tag1", "tag2"]}}

Valid tags: engineer, founder, investor, researcher, ex-faang, building, side-project, open-to-work, pm, designer, operator, academic, media, brand, irrelevant"""


def check_ollama(model: str) -> bool:
    """Check if Ollama is running and the model is available."""
    try:
        resp = requests.get("http://localhost:11434/api/tags", timeout=3)
        if resp.status_code != 200:
            return False
        models = [m["name"].split(":")[0] for m in resp.json().get("models", [])]
        return model in models
    except requests.ConnectionError:
        return False


def score_profile(model: str, username: str, name: str, bio: str) -> dict:
    prompt = PROMPT.format(
        name=name or username,
        username=username,
        bio=bio or "(no bio)",
    )
    try:
        resp = requests.post(
            OLLAMA_URL,
            json={"model": model, "prompt": prompt, "stream": False, "format": "json"},
            timeout=30,
        )
        raw = resp.json().get("response", "").strip()
        # Extract JSON even if model adds extra text
        match = re.search(r'\{.*\}', raw, re.DOTALL)
        if match:
            return json.loads(match.group())
    except Exception as e:
        console.print(f"[red]Error @{username}: {e}[/red]")
    return {"score": -1, "reason": "error", "tags": []}


def run(rescore: bool = False, model: str = "llama3.2"):
    if not check_ollama(model):
        console.print(f"[red]Ollama nicht erreichbar oder Modell '{model}' nicht gefunden.[/red]")
        console.print("\nSetup:")
        console.print("  [cyan]brew install ollama[/cyan]")
        console.print(f"  [cyan]ollama pull {model}[/cyan]")
        console.print("  [cyan]ollama serve[/cyan]  ← in separatem Terminal lassen")
        sys.exit(1)

    conn = sqlite3.connect("state.db")
    conn.row_factory = sqlite3.Row

    if rescore:
        rows = conn.execute(
            "SELECT DISTINCT followed_id, username, display_name, description FROM following"
        ).fetchall()
    else:
        rows = conn.execute(
            "SELECT DISTINCT followed_id, username, display_name, description FROM following WHERE ai_score IS NULL"
        ).fetchall()

    if not rows:
        console.print("[green]Alle Profile bereits bewertet. --rescore zum Wiederholen.[/green]")
        return

    console.print(f"[bold]Scoring {len(rows)} Profile mit Ollama ({model})...[/bold]")
    console.print("[dim]Ca. 20-30 Sek pro Profil auf CPU — läuft im Hintergrund.[/dim]\n")

    scored = 0
    for row in track(rows, description="Scoring..."):
        result = score_profile(
            model,
            username=row["username"] or "",
            name=row["display_name"] or "",
            bio=row["description"] or "",
        )

        if result["score"] >= 0:
            conn.execute(
                """
                UPDATE following
                SET ai_score = ?, ai_reason = ?, ai_tags = ?
                WHERE followed_id = ?
                """,
                (
                    result["score"],
                    result["reason"],
                    ",".join(result.get("tags", [])),
                    row["followed_id"],
                ),
            )
            conn.commit()
            scored += 1

    conn.close()
    console.print(f"\n[bold green]Fertig! {scored}/{len(rows)} Profile bewertet.[/bold green]")
    console.print("Browser neu laden um die Scores zu sehen.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--rescore", action="store_true")
    parser.add_argument("--model", default="llama3.2", help="Ollama model (default: llama3.2)")
    args = parser.parse_args()
    run(rescore=args.rescore, model=args.model)
