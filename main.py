#!/usr/bin/env python3
"""
X Talent Radar
==============
Watches VC/angel Twitter accounts and surfaces new follows as talent signals.
Uses RapidAPI Twitter scrapers (no official X API key needed).

Usage:
    python main.py                        # Run one scan
    python main.py --watch                # Loop forever, scan every 6 hours
    python main.py --watch --interval 12  # Loop every 12 hours
    python main.py --signals              # Show recent signals from DB
    python main.py --provider twttrapi    # Use a different RapidAPI provider
"""

import argparse
import os
import sys
import time

from dotenv import load_dotenv
from rich.console import Console
from rich.table import Table

from config import WATCHED_ACCOUNTS, RAPIDAPI_PROVIDERS, MIN_VC_OVERLAP, FOLLOWER_WINDOW_HOURS
from storage import get_recent_signals, get_multi_vc_followers, init_db
from watcher import check_account
from followers_watcher import scan_followers

console = Console()


def load_config(provider_name: str) -> tuple[str, dict]:
    load_dotenv()
    api_key = os.getenv("RAPIDAPI_KEY")
    if not api_key:
        console.print("[red]RAPIDAPI_KEY not set. Copy .env.example to .env and fill it in.[/red]")
        sys.exit(1)

    provider_cfg = RAPIDAPI_PROVIDERS.get(provider_name)
    if not provider_cfg:
        console.print(f"[red]Unknown provider '{provider_name}'. Choose from: {list(RAPIDAPI_PROVIDERS.keys())}[/red]")
        sys.exit(1)

    return api_key, provider_cfg


def run_scan(api_key: str, provider_cfg: dict, provider_name: str = "twitter135"):
    console.rule("[bold]X Talent Radar — Scan")
    all_signals: list[dict] = []

    for watcher in WATCHED_ACCOUNTS:
        new = check_account(api_key, provider_cfg, watcher)
        all_signals.extend(new)
        time.sleep(2)

    # Follower overlap scan (1 page per VC = minimal API usage)
    scan_followers(api_key, provider_name)
    overlaps = get_multi_vc_followers(MIN_VC_OVERLAP, FOLLOWER_WINDOW_HOURS)

    console.rule()
    if all_signals:
        console.print(f"\n[bold green]New following signals: {len(all_signals)}[/bold green]\n")
        _print_table(all_signals, include_watcher=False)
    else:
        console.print("\n[dim]No new following signals this run.[/dim]")

    if overlaps:
        console.print(f"\n[bold yellow]Multi-VC followers ({FOLLOWER_WINDOW_HOURS}h window, ≥{MIN_VC_OVERLAP} VCs): {len(overlaps)}[/bold yellow]")
    else:
        console.print(f"[dim]No multi-VC followers detected yet.[/dim]")


def _print_table(rows, include_watcher: bool = True):
    table = Table(show_header=True, header_style="bold magenta", expand=True)

    if include_watcher:
        table.add_column("Spotted by", style="cyan", no_wrap=True)
    table.add_column("@username", style="bold", no_wrap=True)
    table.add_column("Display name", no_wrap=True)
    table.add_column("Bio", overflow="fold")
    if include_watcher:
        table.add_column("Detected", style="dim", no_wrap=True)

    for r in rows:
        if include_watcher:
            table.add_row(
                r["watcher_name"],
                f"@{r['username']}",
                r["display_name"] or "",
                r["description"] or "",
                r["detected_at"],
            )
        else:
            table.add_row(
                f"@{r['username']}",
                r["name"],
                r.get("description", ""),
            )

    console.print(table)


def show_signals(limit: int = 50):
    console.rule("[bold]Recent Signals")
    rows = get_recent_signals(limit)
    if not rows:
        console.print("[dim]No signals recorded yet. Run a scan first.[/dim]")
        return
    _print_table(rows, include_watcher=True)


def main():
    parser = argparse.ArgumentParser(description="X Talent Radar via RapidAPI")
    parser.add_argument("--signals", action="store_true", help="Show recent signals from DB")
    parser.add_argument("--limit", type=int, default=50, help="Number of signals to show (default 50)")
    parser.add_argument("--watch", action="store_true", help="Loop forever, re-scanning at a fixed interval")
    parser.add_argument("--interval", type=float, default=0.0833, help="Hours between scans in --watch mode (default 5 min)")
    parser.add_argument(
        "--provider",
        default=os.getenv("RAPIDAPI_PROVIDER", "twitter135"),
        choices=list(RAPIDAPI_PROVIDERS.keys()),
        help="RapidAPI provider to use",
    )
    args = parser.parse_args()

    init_db()

    if args.signals:
        show_signals(args.limit)
        return

    api_key, provider_cfg = load_config(args.provider)

    if args.watch:
        interval_sec = int(args.interval * 3600)
        console.print(f"[bold cyan]Watch mode — scanning every {args.interval * 60:.0f}min. Ctrl-C to stop.[/bold cyan]")
        while True:
            run_scan(api_key, provider_cfg, args.provider)
            console.print(f"\n[dim]Next scan in {args.interval * 60:.0f}min — sleeping...[/dim]")
            try:
                time.sleep(interval_sec)
            except KeyboardInterrupt:
                console.print("\n[yellow]Stopped.[/yellow]")
                break
    else:
        run_scan(api_key, provider_cfg, args.provider)


if __name__ == "__main__":
    main()
