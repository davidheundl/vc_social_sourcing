"""
Looks up two people on Product Hunt by first/last name,
scanning posts and filtering by maker name.
Saves results to producthunt_profiles.json.
"""

import json
import os
import time

import requests
from dotenv import load_dotenv

load_dotenv(dotenv_path=os.path.join(os.path.dirname(__file__), ".env"), override=True)

PH_TOKEN = os.getenv("PRODUCTHUNT_API_TOKEN", "").strip()
if not PH_TOKEN:
    raise SystemExit("Missing PRODUCTHUNT_API_TOKEN in .env")

OUTPUT_FILE = os.path.join(os.path.dirname(__file__), "producthunt_profiles.json")
PH_GRAPHQL_URL = "https://api.producthunt.com/v2/api/graphql"

TARGETS = [
    {"first": "Antoni",  "last": "Borys"},
    {"first": "Patrick", "last": "Crespo"},
]

POSTS_QUERY = """
query RecentPosts($after: String) {
  posts(first: 50, order: NEWEST, after: $after) {
    pageInfo { hasNextPage endCursor }
    edges {
      node {
        id
        name
        tagline
        votesCount
        createdAt
        url
        makers {
          id
          name
          username
          headline
          twitterUsername
          websiteUrl
          profileImage
        }
      }
    }
  }
}
"""


def _graphql(query: str, variables: dict) -> dict:
    headers = {
        "Authorization": f"Bearer {PH_TOKEN}",
        "Content-Type": "application/json",
        "Accept": "application/json",
    }
    resp = requests.post(
        PH_GRAPHQL_URL,
        json={"query": query, "variables": variables},
        headers=headers,
        timeout=30,
    )
    if resp.status_code == 429:
        print("  [!] Rate limit — waiting 60s…")
        time.sleep(60)
        resp = requests.post(PH_GRAPHQL_URL, json={"query": query, "variables": variables}, headers=headers, timeout=30)
    resp.raise_for_status()
    data = resp.json()
    if "errors" in data:
        raise RuntimeError(f"GraphQL errors: {data['errors']}")
    return data.get("data", {})


def name_matches(maker_name: str, first: str, last: str) -> bool:
    n = (maker_name or "").lower()
    return first.lower() in n and last.lower() in n


def scan_posts_for_person(first: str, last: str, max_pages: int = 10) -> dict:
    full_name = f"{first} {last}"
    print(f"  Scanning Product Hunt posts for '{full_name}' (up to {max_pages} pages)…")

    found_profile: dict | None = None
    posts_as_maker: list[dict] = []
    cursor = None
    pages = 0

    while pages < max_pages:
        try:
            data = _graphql(POSTS_QUERY, {"after": cursor})
        except Exception as exc:
            print(f"  [!] Query failed: {exc}")
            break

        posts_data = data.get("posts", {})
        edges = posts_data.get("edges", [])
        page_info = posts_data.get("pageInfo", {})

        for edge in edges:
            post = edge.get("node", {})
            for maker in post.get("makers", []):
                if not name_matches(maker.get("name", ""), first, last):
                    continue

                if found_profile is None:
                    found_profile = {k: v for k, v in maker.items() if k != "id"}
                    found_profile["ph_id"] = maker.get("id")

                posts_as_maker.append({
                    "post_id": post.get("id"),
                    "post_name": post.get("name"),
                    "tagline": post.get("tagline"),
                    "votes": post.get("votesCount"),
                    "created_at": post.get("createdAt"),
                    "url": post.get("url"),
                })

        if not page_info.get("hasNextPage"):
            break
        cursor = page_info.get("endCursor")
        pages += 1
        time.sleep(0.5)

    return {
        "query": full_name,
        "profile": found_profile,
        "posts_as_maker": posts_as_maker,
    }


results = {}

for target in TARGETS:
    full_name = f"{target['first']} {target['last']}"
    print(f"\n=== {full_name} ===")
    result = scan_posts_for_person(target["first"], target["last"])

    if result["profile"]:
        print(f"  Found: {result['profile'].get('name')} — {result['profile'].get('headline')}")
        print(f"  Posts as maker: {len(result['posts_as_maker'])}")
    else:
        print(f"  Not found in recent Product Hunt posts.")

    results[full_name] = result

with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
    json.dump(results, f, ensure_ascii=False, indent=2)

print(f"\nSaved Product Hunt data to: {OUTPUT_FILE}")
