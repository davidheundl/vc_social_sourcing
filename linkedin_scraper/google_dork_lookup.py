"""
Runs targeted Google dork queries for two people across
GitHub, Crunchbase, and AngelList.
Saves all results to google_dork_results.json.
"""

import json
import os
import time

import requests
from dotenv import load_dotenv

load_dotenv(dotenv_path=os.path.join(os.path.dirname(__file__), ".env"), override=True)

SERPAPI_KEY = os.getenv("SERPAPI_KEY", "").strip()
if not SERPAPI_KEY:
    raise SystemExit("Missing SERPAPI_KEY in .env")

OUTPUT_FILE = os.path.join(os.path.dirname(__file__), "google_dork_results.json")
SERPAPI_URL = "https://serpapi.com/search"

TARGETS = [
    {"name": "Antoni Borys"},
    {"name": "Patrick Crespo"},
]

QUERY_TEMPLATES = [
    'site:github.com "{name}"',
    'site:crunchbase.com "{name}"',
    'site:angel.co "{name}"',
]


def build_queries(target: dict) -> list[tuple[str, str]]:
    return [
        (template, template.format(name=target["name"]))
        for template in QUERY_TEMPLATES
    ]


def search(query: str) -> list[dict]:
    params = {
        "engine": "google",
        "q": query,
        "api_key": SERPAPI_KEY,
        "num": 10,
        "hl": "en",
        "gl": "us",
    }
    try:
        resp = requests.get(SERPAPI_URL, params=params, timeout=30)
        if resp.status_code == 429:
            print("  [!] Rate limit hit — waiting 60s…")
            time.sleep(60)
            resp = requests.get(SERPAPI_URL, params=params, timeout=30)
        resp.raise_for_status()
        return resp.json().get("organic_results", [])
    except Exception as exc:
        print(f"  [!] Search failed: {exc}")
        return []


results = {}

for target in TARGETS:
    name = target["name"]
    print(f"\n=== {name} ===")
    target_results = []

    for template, query in build_queries(target):
        print(f"  Query: {query}")
        hits = search(query)
        print(f"  → {len(hits)} result(s)")
        target_results.append({
            "template": template,
            "query": query,
            "hits": [
                {
                    "title": h.get("title"),
                    "link": h.get("link"),
                    "snippet": h.get("snippet"),
                }
                for h in hits
            ],
        })
        time.sleep(1.5)

    results[name] = target_results

with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
    json.dump(results, f, ensure_ascii=False, indent=2)

print(f"\nSaved Google Dork results to: {OUTPUT_FILE}")
