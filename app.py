from flask import Flask, render_template_string, request
import sqlite3
from config import MIN_VC_OVERLAP, FOLLOWER_WINDOW_HOURS

app = Flask(__name__)
DB = "state.db"

HTML = """
<!DOCTYPE html>
<html lang="de">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>X Talent Radar</title>
<style>
  * { box-sizing: border-box; margin: 0; padding: 0; }
  body { font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif; background: #0f1117; color: #e1e4e8; min-height: 100vh; }

  header { padding: 24px 32px; border-bottom: 1px solid #21262d; display: flex; align-items: center; gap: 16px; }
  header h1 { font-size: 20px; font-weight: 600; }
  header span { color: #8b949e; font-size: 14px; }

  .controls { padding: 16px 32px; display: flex; gap: 10px; flex-wrap: wrap; align-items: center; border-bottom: 1px solid #21262d; }
  input[type=search] {
    background: #161b22; border: 1px solid #30363d; color: #e1e4e8;
    padding: 8px 14px; border-radius: 6px; font-size: 14px; width: 260px;
  }
  input[type=search]:focus { outline: none; border-color: #58a6ff; }
  select {
    background: #161b22; border: 1px solid #30363d; color: #e1e4e8;
    padding: 8px 12px; border-radius: 6px; font-size: 14px;
  }
  .count { margin-left: auto; color: #8b949e; font-size: 13px; }

  .grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(320px, 1fr)); gap: 16px; padding: 24px 32px; }

  .card {
    background: #161b22; border: 1px solid #21262d; border-radius: 10px;
    padding: 18px; transition: border-color 0.15s; display: flex; flex-direction: column; gap: 8px;
  }
  .card:hover { border-color: #58a6ff44; }
  .card.score-high { border-left: 3px solid #3fb950; }
  .card.score-mid  { border-left: 3px solid #d29922; }
  .card.score-low  { border-left: 3px solid #21262d; }

  .card-top { display: flex; justify-content: space-between; align-items: flex-start; }
  .username { font-weight: 600; color: #58a6ff; font-size: 15px; }
  .username a { color: inherit; text-decoration: none; }
  .username a:hover { text-decoration: underline; }

  .badges { display: flex; gap: 6px; flex-wrap: wrap; align-items: center; }
  .watcher-badge {
    font-size: 11px; padding: 2px 8px; border-radius: 20px;
    background: #21262d; color: #8b949e; white-space: nowrap;
  }
  .score-badge {
    font-size: 12px; font-weight: 700; padding: 2px 8px; border-radius: 20px; white-space: nowrap;
  }
  .score-high-badge { background: #1a4a1f; color: #3fb950; }
  .score-mid-badge  { background: #3d2e05; color: #d29922; }
  .score-low-badge  { background: #21262d; color: #6e7681; }
  .new-badge { font-size: 11px; padding: 2px 8px; border-radius: 20px; background: #1f6feb33; color: #58a6ff; border: 1px solid #1f6feb; }

  .display-name { font-size: 13px; color: #8b949e; }
  .bio { font-size: 13px; color: #c9d1d9; line-height: 1.5; }
  .ai-reason { font-size: 12px; color: #6e7681; font-style: italic; }
  .tags { display: flex; flex-wrap: wrap; gap: 4px; }
  .tag { font-size: 11px; padding: 1px 7px; border-radius: 20px; background: #21262d; color: #8b949e; }

  .tabs { display: flex; padding: 0 32px; border-bottom: 1px solid #21262d; }
  .tab { padding: 12px 20px; font-size: 14px; color: #8b949e; border-bottom: 2px solid transparent; text-decoration: none; }
  .tab.active { color: #e1e4e8; border-bottom-color: #f78166; }

  .empty { text-align: center; padding: 80px; color: #8b949e; grid-column: 1/-1; }
  .pending-note { padding: 12px 32px; background: #1f2937; color: #8b949e; font-size: 13px; }
</style>
</head>
<body>

<header>
  <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="#58a6ff" stroke-width="2"><circle cx="11" cy="11" r="8"/><path d="m21 21-4.35-4.35"/></svg>
  <h1>X Talent Radar</h1>
  <span>{{ watcher_count }} VC accounts · {{ total_count }} profiles</span>
</header>

<div class="tabs">
  <a href="/?tab=all" class="tab {{ 'active' if tab == 'all' }}">Alle ({{ total_count }})</a>
  <a href="/?tab=founders" class="tab {{ 'active' if tab == 'founders' }}">Founder-Potenzial ({{ founder_count }})</a>
  <a href="/?tab=signals" class="tab {{ 'active' if tab == 'signals' }}">Neue Signals ({{ signal_count }})</a>
  <a href="/?tab=multivc" class="tab {{ 'active' if tab == 'multivc' }}">🔥 Multi-VC Follower ({{ multivc_count }})</a>
</div>

{% if unscored_count > 0 %}
<div class="pending-note">
  ⚡ {{ unscored_count }} Profile noch nicht bewertet —
  führe <code>python ai_filter.py</code> aus um den AI-Score zu berechnen.
</div>
{% endif %}

{% if tab == 'multivc' %}
<div class="pending-note" style="color:#f0a500;">
  🔥 Personen, die innerhalb der letzten {{ window_hours }}h mindestens {{ min_overlap }} VCs gefolgt sind — hohes Funding-Signal.
</div>
{% endif %}

<div class="controls">
  <form method="get" style="display:contents">
    <input type="hidden" name="tab" value="{{ tab }}">
    <input type="search" name="q" value="{{ q }}" placeholder="Name, @handle, Bio…" autocomplete="off">
    <select name="watcher" onchange="this.form.submit()">
      <option value="">Alle VCs</option>
      {% for w in watchers %}
      <option value="{{ w }}" {{ 'selected' if watcher == w }}>{{ w }}</option>
      {% endfor %}
    </select>
    {% if tab != 'signals' %}
    <select name="min_score" onchange="this.form.submit()">
      <option value="0"  {{ 'selected' if min_score == 0  }}>Alle Scores</option>
      <option value="5"  {{ 'selected' if min_score == 5  }}>Score ≥ 5</option>
      <option value="7"  {{ 'selected' if min_score == 7  }}>Score ≥ 7 (stark)</option>
      <option value="9"  {{ 'selected' if min_score == 9  }}>Score ≥ 9 (top)</option>
    </select>
    {% endif %}
    <button type="submit" style="display:none"></button>
  </form>
  <span class="count">{{ results|length }} Ergebnisse</span>
</div>

<div class="grid">
  {% for r in results %}
  {% set score = r.ai_score if r.ai_score is not none else -1 %}
  {% set card_class = 'score-high' if score >= 7 else ('score-mid' if score >= 4 else 'score-low') %}
  <div class="card {{ card_class }}">
    <div class="card-top">
      <div class="username"><a href="https://x.com/{{ r.username }}" target="_blank">@{{ r.username }}</a></div>
      <div class="badges">
        {% if tab == 'multivc' %}
          <span class="score-badge score-high-badge">{{ r.vc_count }} VCs</span>
        {% elif score >= 0 %}
          {% set badge_class = 'score-high-badge' if score >= 7 else ('score-mid-badge' if score >= 4 else 'score-low-badge') %}
          <span class="score-badge {{ badge_class }}">{{ score }}/10</span>
        {% endif %}
        {% if r.is_new %}<span class="new-badge">✦ Neu</span>{% endif %}
      </div>
    </div>

    <div class="display-name">{{ r.display_name or '' }}</div>
    {% if r.description %}<div class="bio">{{ r.description }}</div>{% endif %}
    {% if r.ai_reason %}<div class="ai-reason">{{ r.ai_reason }}</div>{% endif %}

    {% if r.ai_tags %}
    <div class="tags">
      {% for tag in r.ai_tags.split(',') %}
        {% if tag.strip() %}<span class="tag">{{ tag.strip() }}</span>{% endif %}
      {% endfor %}
    </div>
    {% endif %}

    <div style="margin-top:2px">
      <span class="watcher-badge">via {{ r.watcher_name }}</span>
    </div>
  </div>
  {% else %}
  <div class="empty">Keine Ergebnisse.</div>
  {% endfor %}
</div>

<script>
  const input = document.querySelector('input[type=search]');
  let timer;
  input.addEventListener('input', () => {
    clearTimeout(timer);
    timer = setTimeout(() => input.form.submit(), 400);
  });
</script>
</body>
</html>
"""

WATCHER_NAMES = {
    "183749519": "Paul Graham",
    "11768582":  "Garry Tan",
    "273383":    "Christoph Janz",
    "26743889":  "Reshma Sohoni",
    "21870345":  "Klaus Hommels",
    "16650886":  "Balderton Capital",
    "44579473":  "Atomico",
    "1467509644260225028": "NirkDowztski (test)",
}


def get_conn():
    conn = sqlite3.connect(DB)
    conn.row_factory = sqlite3.Row
    return conn


@app.route("/")
def index():
    tab       = request.args.get("tab", "all")
    q         = request.args.get("q", "").strip()
    watcher   = request.args.get("watcher", "")
    min_score = int(request.args.get("min_score", 0))

    conn = get_conn()

    if tab == "multivc":
        rows = conn.execute(
            """
            SELECT
                follower_id,
                username,
                display_name,
                description,
                COUNT(DISTINCT watcher_id)        AS vc_count,
                GROUP_CONCAT(DISTINCT watcher_id) AS watcher_ids,
                MIN(first_seen)                   AS first_seen
            FROM vc_followers
            WHERE first_seen >= datetime('now', ? || ' hours')
            GROUP BY follower_id
            HAVING vc_count >= ?
            ORDER BY vc_count DESC, first_seen DESC
            LIMIT 200
            """,
            (f"-{FOLLOWER_WINDOW_HOURS}", MIN_VC_OVERLAP),
        ).fetchall()
        results = []
        for r in rows:
            d = dict(r)
            if q:
                haystack = f"{d.get('username','')} {d.get('display_name','')} {d.get('description','')}".lower()
                if q.lower() not in haystack:
                    continue
            wids = (d.get("watcher_ids") or "").split(",")
            d["watcher_name"] = ", ".join(WATCHER_NAMES.get(w.strip(), w.strip()) for w in wids if w.strip())
            d["is_new"] = False
            d["ai_score"] = None
            d["ai_reason"] = None
            d["ai_tags"] = None
            results.append(d)
        params = []

    elif tab == "signals":
        query = "SELECT s.followed_id as user_id, s.username, s.display_name, s.description, s.watcher_name, 1 as is_new, NULL as ai_score, NULL as ai_reason, NULL as ai_tags, NULL as watcher_id FROM new_signals s"
        conditions, params = [], []
        if q:
            conditions.append("(s.username LIKE ? OR s.display_name LIKE ? OR s.description LIKE ?)")
            params += [f"%{q}%", f"%{q}%", f"%{q}%"]
        if conditions:
            query += " WHERE " + " AND ".join(conditions)
        query += " ORDER BY s.detected_at DESC LIMIT 200"

    elif tab == "founders":
        query = "SELECT f.followed_id as user_id, f.username, f.display_name, f.description, f.watcher_id, f.ai_score, f.ai_reason, f.ai_tags, 0 as is_new FROM following f"
        conditions = ["f.ai_score >= 7"]
        params = []
        if q:
            conditions.append("(f.username LIKE ? OR f.display_name LIKE ? OR f.description LIKE ?)")
            params += [f"%{q}%", f"%{q}%", f"%{q}%"]
        if watcher:
            wid = next((k for k, v in WATCHER_NAMES.items() if v == watcher), None)
            if wid:
                conditions.append("f.watcher_id = ?")
                params.append(wid)
        query += " WHERE " + " AND ".join(conditions)
        query += " ORDER BY f.ai_score DESC LIMIT 500"

    else:  # all
        query = "SELECT f.followed_id as user_id, f.username, f.display_name, f.description, f.watcher_id, f.ai_score, f.ai_reason, f.ai_tags, 0 as is_new FROM following f"
        conditions, params = [], []
        if q:
            conditions.append("(f.username LIKE ? OR f.display_name LIKE ? OR f.description LIKE ?)")
            params += [f"%{q}%", f"%{q}%", f"%{q}%"]
        if watcher:
            wid = next((k for k, v in WATCHER_NAMES.items() if v == watcher), None)
            if wid:
                conditions.append("f.watcher_id = ?")
                params.append(wid)
        if min_score:
            conditions.append("f.ai_score >= ?")
            params.append(min_score)
        if conditions:
            query += " WHERE " + " AND ".join(conditions)
        query += " ORDER BY COALESCE(f.ai_score, -1) DESC LIMIT 500"

    if tab != "multivc":
        rows = conn.execute(query, params).fetchall()
        results = []
        for r in rows:
            d = dict(r)
            if tab != "signals":
                d["watcher_name"] = WATCHER_NAMES.get(str(d.get("watcher_id", "")), "—")
            results.append(d)

    total_count    = conn.execute("SELECT COUNT(*) FROM following").fetchone()[0]
    signal_count   = conn.execute("SELECT COUNT(*) FROM new_signals").fetchone()[0]
    founder_count  = conn.execute("SELECT COUNT(*) FROM following WHERE ai_score >= 7").fetchone()[0]
    unscored_count = conn.execute("SELECT COUNT(*) FROM following WHERE ai_score IS NULL").fetchone()[0]
    watcher_count  = conn.execute("SELECT COUNT(DISTINCT watcher_id) FROM following").fetchone()[0]
    multivc_count  = conn.execute(
        """
        SELECT COUNT(*) FROM (
            SELECT follower_id FROM vc_followers
            WHERE first_seen >= datetime('now', ? || ' hours')
            GROUP BY follower_id
            HAVING COUNT(DISTINCT watcher_id) >= ?
        )
        """,
        (f"-{FOLLOWER_WINDOW_HOURS}", MIN_VC_OVERLAP),
    ).fetchone()[0]
    watchers = list(WATCHER_NAMES.values())

    conn.close()

    return render_template_string(HTML,
        results=results, tab=tab, q=q, watcher=watcher,
        min_score=min_score, watchers=watchers,
        total_count=total_count, signal_count=signal_count,
        founder_count=founder_count, unscored_count=unscored_count,
        watcher_count=watcher_count, multivc_count=multivc_count,
        window_hours=FOLLOWER_WINDOW_HOURS, min_overlap=MIN_VC_OVERLAP,
    )


if __name__ == "__main__":
    print("→ http://localhost:8080")
    app.run(debug=True, port=8080)
