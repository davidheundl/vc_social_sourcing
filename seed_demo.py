"""
Seed the database with demo founders and score them.
Usage: python seed_demo.py [--base-url http://localhost:8000]
"""

import json
import sys
import urllib.request
import urllib.error

BASE_URL = sys.argv[2] if len(sys.argv) > 2 else "http://127.0.0.1:8000"
if "--base-url" in sys.argv:
    idx = sys.argv.index("--base-url")
    BASE_URL = sys.argv[idx + 1]


def post(path: str, payload) -> dict:
    data = json.dumps(payload).encode()
    req = urllib.request.Request(
        f"{BASE_URL}{path}",
        data=data,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req) as resp:
            return json.loads(resp.read())
    except urllib.error.HTTPError as e:
        body = e.read().decode()
        print(f"  ERROR {e.code}: {body[:300]}")
        return {}


def get(path: str) -> dict | list:
    req = urllib.request.Request(f"{BASE_URL}{path}")
    with urllib.request.urlopen(req) as resp:
        return json.loads(resp.read())


if __name__ == "__main__":
    print(f"Target: {BASE_URL}\n")

    # 1. Ingest demo profiles
    print("Step 1 — Ingesting 20 demo profiles...")
    with open("demo_data.json", encoding="utf-8") as f:
        profiles = json.load(f)

    result = post("/ingest/", profiles)
    if isinstance(result, list):
        print(f"  OK {len(result)} profiles ingested\n")
    else:
        print(f"  Result: {result}\n")

    # 2. Score all profiles
    print("Step 2 — Scoring all profiles...")
    scored = post("/score/all", None)
    print(f"  OK {scored}\n")

    # 3. Preview ranked leads
    print("Step 3 — Top 10 ranked leads:")
    leads = get("/ranked-leads?limit=10")
    if isinstance(leads, list):
        print(f"  {'Name':<25} {'Score':>6}  {'Priority':<8}  {'Country':<15}  Reasons")
        print(f"  {'-'*25} {'-'*6}  {'-'*8}  {'-'*15}  -------")
        for lead in leads:
            reasons_short = "; ".join(lead.get("reasons", [])[:2])
            print(
                f"  {lead['full_name']:<25} {lead['score']:>6.1f}  {lead['priority']:<8}  "
                f"{(lead.get('country') or ''):<15}  {reasons_short}"
            )

    print("\nDone. Run GET /ranked-leads to explore results.")
