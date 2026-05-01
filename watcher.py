import time
import requests
from rich.console import Console

from config import MAX_PAGES_PER_ACCOUNT, RAPIDAPI_PROVIDERS
from storage import get_known_following, save_following, save_signals

console = Console()


def fetch_following(api_key: str, provider_cfg: dict, watcher_id: str) -> list[dict]:
    """Fetch following list via RapidAPI. Returns list of user dicts."""
    results = []
    cursor = None
    pages_fetched = 0
    headers = {
        "x-rapidapi-key": api_key,
        "x-rapidapi-host": provider_cfg["host"],
    }

    while pages_fetched < MAX_PAGES_PER_ACCOUNT:
        params = provider_cfg["params"](watcher_id, cursor)

        try:
            resp = requests.get(
                provider_cfg["following_url"],
                headers=headers,
                params=params,
                timeout=15,
            )
        except requests.RequestException as e:
            console.print(f"[red]Request error: {e}[/red]")
            break

        if resp.status_code == 429:
            console.print("[yellow]Rate limit hit — sleeping 60s...[/yellow]")
            time.sleep(60)
            continue

        if resp.status_code != 200:
            console.print(f"[red]API error {resp.status_code}: {resp.text[:200]}[/red]")
            break

        data = resp.json()
        users, next_cursor = provider_cfg["parse"](data)

        if not users:
            break

        results.extend(users)
        pages_fetched += 1

        # Stop if no next page or cursor is 0 (Twitter's "end of list" sentinel)
        if not next_cursor or str(next_cursor) in ("0", "-1"):
            break

        cursor = next_cursor
        time.sleep(1.5)  # be polite

    return results


def check_account(api_key: str, provider_cfg: dict, watcher: dict) -> list[dict]:
    """
    Check one VC account for new follows.
    Returns list of newly followed user dicts.
    """
    watcher_id = watcher["id"]
    watcher_name = watcher["name"]

    console.print(f"  Checking [bold cyan]{watcher_name}[/bold cyan]...", end=" ")

    known = get_known_following(watcher_id)
    current = fetch_following(api_key, provider_cfg, watcher_id)

    if not current:
        console.print("[yellow]no data returned[/yellow]")
        return []

    if not known:
        save_following(watcher_id, current)
        console.print(f"[dim]seeded {len(current)} accounts (first run)[/dim]")
        return []

    new_users = [u for u in current if u["id"] not in known]

    save_following(watcher_id, current)

    if new_users:
        save_signals(watcher_id, watcher_name, new_users)
        console.print(f"[green]{len(new_users)} new follow(s) detected![/green]")
    else:
        console.print(f"[dim]no new follows ({len(current)} total)[/dim]")

    return new_users
