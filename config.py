"""
VC/Angel accounts to monitor.
To find a user's numeric ID: https://tweeterid.com
"""


def _parse_twitter135(data: dict) -> tuple[list[dict], str | None]:
    """Parse twitter135 GraphQL response into a flat user list + next cursor."""
    try:
        instructions = (
            data["data"]["user"]["result"]["timeline"]["timeline"]["instructions"]
        )
    except (KeyError, TypeError):
        return [], None

    entries = next((i["entries"] for i in instructions if "entries" in i), [])
    users = []
    cursor_next = None

    for entry in entries:
        content = entry.get("content", {})
        item = content.get("itemContent", {})

        if item.get("itemType") == "TimelineUser":
            result = item.get("user_results", {}).get("result", {})
            legacy = result.get("legacy", {})
            uid = result.get("rest_id", "")
            if uid:
                users.append({
                    "id": uid,
                    "name": legacy.get("name", ""),
                    "username": legacy.get("screen_name", ""),
                    "description": legacy.get("description", ""),
                })

        if (
            content.get("entryType") == "TimelineTimelineCursor"
            and content.get("cursorType") == "Bottom"
        ):
            cursor_next = content.get("value")

    return users, cursor_next

WATCHED_ACCOUNTS = [
    # Format: {"name": "Display Name", "id": "numeric_twitter_id", "username": "handle"}
    {"name": "Paul Graham",           "id": "183749519",  "username": "paulg"},
    {"name": "Garry Tan",             "id": "11768582",   "username": "garrytan"},
    {"name": "Christoph Janz",        "id": "273383",     "username": "chrija"},
    {"name": "Reshma Sohoni",         "id": "26743889",   "username": "reshmacs"},
    {"name": "Klaus Hommels",         "id": "21870345",   "username": "hommels"},
    {"name": "Balderton Capital",     "id": "16650886",   "username": "balderton"},
    {"name": "Atomico",               "id": "44579473",   "username": "atomico"},
    {"name": "NirkDowztski (test)",   "id": "1467509644260225028", "username": "NirkDowztski"},
    # Add more here...
]

# RapidAPI provider configs
# Sign up at rapidapi.com, search "Twitter" and subscribe to one of these (all have free tiers)
RAPIDAPI_PROVIDERS = {
    "twitter135": {
        "host": "twitter135.p.rapidapi.com",
        "following_url": "https://twitter135.p.rapidapi.com/v2/Following/",
        # Query params: id (numeric), count (max 200 per page)
        "params": lambda user_id, cursor: {
            "id": user_id,
            "count": "200",
            **({"cursor": cursor} if cursor else {}),
        },
        # How to extract users and next cursor from response (GraphQL structure)
        "parse": _parse_twitter135,
    },
    "twttrapi": {
        "host": "twttrapi.p.rapidapi.com",
        "following_url": "https://twttrapi.p.rapidapi.com/get-user-followings",
        "params": lambda user_id, cursor: {
            "user_id": user_id,
            **({"next_cursor": cursor} if cursor else {}),
        },
        "parse": lambda data: (
            [
                {
                    "id": str(u.get("id_str") or u.get("id", "")),
                    "name": u.get("name", ""),
                    "username": u.get("screen_name", ""),
                    "description": u.get("description", ""),
                }
                for u in (data.get("users") or [])
                if isinstance(u, dict)
            ],
            data.get("next_cursor_str"),
        ),
    },
}

# Follower endpoint config (twitter135 only — same GraphQL parse function)
FOLLOWER_ENDPOINT = {
    "twitter135": {
        "host": "twitter135.p.rapidapi.com",
        "url": "https://twitter135.p.rapidapi.com/v2/Followers/",
        "params": lambda user_id, cursor: {
            "id": user_id,
            "count": "200",
            **({"cursor": cursor} if cursor else {}),
        },
        "parse": _parse_twitter135,
    },
}

# Max pages to fetch per account (200 users/page for most providers)
# Basic tier: ~10,000 req/month — 50 pages × 7 accounts = 350 req/full scan
MAX_PAGES_PER_ACCOUNT = 50

# Follower scan: only fetch the 1 most recent page (~200 newest followers) per VC
# This keeps API usage low while catching fresh follows
MAX_FOLLOWER_PAGES = 1

# How many VCs someone must have followed recently to be flagged as a signal
MIN_VC_OVERLAP = 3

# Time window in hours for the overlap check
FOLLOWER_WINDOW_HOURS = 48

# SQLite file to persist state between runs
DB_PATH = "state.db"
