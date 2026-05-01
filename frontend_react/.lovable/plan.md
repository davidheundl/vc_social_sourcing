## Goal

Simplify the Tracking page so it instantly communicates: "we're on it, scanning your investors every week, and here's what we found this week." Less density, more reassurance, clearer hierarchy.

## Current problems

- Stats bar has 5 separate metric chunks (total / up-to-date / stale / outdated / status pill) — too many numbers, no clear primary signal.
- Each row in the tracking list crams 6 columns (logo, name+meta, last snapshot, next snapshot, snapshot count, connection count, switch, delete) — feels like a database admin panel, not a "we've got this" tool.
- "Stale / outdated" status language sounds like things are broken, even when nothing is wrong. Snapshots run weekly automatically — there's no real user action needed.
- Activity feed is a sidebar that competes with the list instead of reinforcing the "we're working" feeling.
- No clear "this week's progress" hero element.

## New layout

```text
┌──────────────────────────────────────────────────────────────┐
│ Header: Founder Radar  [Radar] [Tracking]      [+ Add]       │
├──────────────────────────────────────────────────────────────┤
│  HERO STATUS BANNER                                          │
│  ● Scanning 24 investors · This week: 18 snapshots taken,    │
│    6 scheduled · 47 new connections discovered               │
│  [progress bar showing weekly cycle ████████░░ 72%]          │
├─────────────────────────────────────────┬────────────────────┤
│  Tracked Investors  [search] [VC|Angel] │  This Week         │
│                                         │                    │
│  ┌─ Sequoia ────────────── ✓ scanned ─┐ │  • Sequoia +3      │
│  │ Logo  Sequoia Capital     VC       │ │  • Benchmark +1    │
│  │       Last scan 2d ago             │ │  • A. Karp +2      │
│  │       Next scan in 5d   [⏸] [···]  │ │  ...               │
│  └────────────────────────────────────┘ │                    │
│  ┌─ Benchmark ─────────── ⏱ scanning ─┐ │                    │
│  │ ...                                │ │                    │
│  └────────────────────────────────────┘ │                    │
└─────────────────────────────────────────┴────────────────────┘
```

## Changes

### 1. Replace the multi-metric stats bar with a single "Hero Status Banner"

One reassuring sentence + a weekly progress bar. Replaces lines 159–204 of `Tracking.tsx`.

Content:
- Pulsing green dot + "Scanning N investors continuously"
- Sub-line: "This week: X of N snapshots complete · Y new connections discovered"
- Thin progress bar showing % of weekly cycle complete (snapshots done / total tracked)
- One small "Next sync window: <day>" hint on the right

No more separate stale/outdated chips up top — those become per-row indicators only.

### 2. Soften status language

Map current 3 states to friendlier language:
- `up_to_date` → "Scanned this week" (green check)
- `stale` → "Scanning soon" (amber clock, not warning)
- `outdated` → "Catching up" (blue spinner-style, not red error)

Rationale: the tool is doing the work automatically. Nothing the user did is "wrong." Red error states should be reserved for real failures (e.g. LinkedIn auth lost) — not a missed weekly cadence.

### 3. Simplify the row

Reduce from 6 columns to 3 zones: identity, status, controls.

Per row:
- Left: logo + name + type badge + firm/sector (one line of meta, not two)
- Middle: status pill ("Scanned 2d ago · Next in 5d") — single line, muted
- Right: pause switch + overflow menu (move delete into the menu, no inline confirm)

Drop from default view: total snapshots count, connection count number. These move to a hover tooltip or a future detail drawer — they're noise in the main list.

### 4. Make the activity feed feel like progress, not just a log

Right sidebar becomes "This Week" — grouped summary instead of an infinite live ticker:
- Heading: "This week's discoveries"
- Each entry: investor logo + name + "+N new connections"
- Sorted by impact (most new connections first), capped at ~10
- Small footer: "Updated continuously · Next full cycle Monday"

Keep one subtle live indicator (pulsing dot) so it still feels alive, but stop the scrolling-log feeling.

### 5. Remove the "All systems operational / N profiles need attention" pill

Folded into the hero banner. One source of truth for overall status.

## Files to edit

- `src/pages/Tracking.tsx` — replace stats bar with hero banner; simplify filter strip; relabel sidebar
- `src/components/TrackingList.tsx` — collapse columns to 3 zones; soften status labels; move delete into overflow menu
- `src/components/SnapshotActivityFeed.tsx` — convert from rolling log to "This Week" grouped summary (still updates live, but aggregates per investor)
- `src/data/mockSubscriptions.ts` — add a small helper to compute "weekly progress" (snapshots done this ISO week / total active) and "this week's discoveries" aggregate

No data model changes required — everything derives from existing fields.

## Out of scope

- No changes to the Radar page
- No changes to scoring logic
- No new routes or pages