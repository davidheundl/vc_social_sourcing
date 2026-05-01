"""
Followers Watcher — fetches the most recent followers of each watched VC.

Only fetches MAX_FOLLOWER_PAGES pages per VC (default: 1 = ~200 newest followers).
Twitter returns followers in reverse-chronological order, so page 1 = the freshest.

This keeps API usage minimal: 1 request per VC per scan cycle.
"""

import time
import requests
from rich.console import Console

from config import MAX_FOLLOWER_PAGES, FOLLOWER_ENDPOINT, WATCHED_ACCOUNTS
from storage import save_vc_followers

console = Console()


def fetch_recent_followers(api_key: str, provider_name: str, watcher_id: str) -> list[dict]:
    """Fetch up to MAX_FOLLOWER_PAGES pages of recent followers for a VC account."""
    cfg = FOLLOWER_ENDPOINT.get(provider_name)
    if not cfg:
        return []

    headers = {
        "x-rapidapi-key": api_key,
        "x-rapidapi-host": cfg["host"],
    }

    results = []
    cursor = None
    pages_fetched = 0

    while pages_fetched < MAX_FOLLOWER_PAGES:
        params = cfg["params"](watcher_id, cursor)
        try:
            resp = requests.get(cfg["url"], headers=headers, params=params, timeout=15)
        except requests.RequestException as e:
            console.print(f"[red]Follower fetch error: {e}[/red]")
            break

        if resp.status_code == 429:
            console.print("[yellow]Rate limit — sleeping 60s...[/yellow]")
            time.sleep(60)
            continue

        if resp.status_code != 200:
            console.print(f"[red]API error {resp.status_code}: {resp.text[:200]}[/red]")
            break

        users, next_cursor = cfg["parse"](resp.json())
        if not users:
            break

        results.extend(users)
        pages_fetched += 1

        if not next_cursor or str(next_cursor) in ("0", "-1"):
            break

        cursor = next_cursor
        time.sleep(1.5)

    return results


def scan_followers(api_key: str, provider_name: str = "twitter135"):
    """Scan recent followers of all watched VCs and persist them."""
    console.print("  [dim]Scanning recent VC followers...[/dim]")
    total = 0

    for watcher in WATCHED_ACCOUNTS:
        users = fetch_recent_followers(api_key, provider_name, watcher["id"])
        if users:
            save_vc_followers(watcher["id"], users)
            total += len(users)
            console.print(
                f"  [dim]  {watcher['name']}: {len(users)} recent followers stored[/dim]"
            )
        else:
            console.print(f"  [dim]  {watcher['name']}: no follower data[/dim]")
        time.sleep(1.5)

    return total
