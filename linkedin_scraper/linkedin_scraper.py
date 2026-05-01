import json
import os
from urllib.parse import urlparse

from apify_client import ApifyClient
from apify_client.errors import ApifyApiError

ACTOR_ID = "VhxlqQXRwhW8H5hNV"
OUTPUT_FILE = os.path.join(os.path.dirname(__file__), "linkedin_profiles.json")

TARGET_PROFILE_URLS = [
    "https://www.linkedin.com/in/aborys/",
    "https://www.linkedin.com/in/patrick-crespo-006b75335/",
]


def linkedin_username_from_url(profile_url: str) -> str:
    """
    Extracts the LinkedIn public profile username from a URL like:
    https://www.linkedin.com/in/<username>/
    """
    parsed = urlparse(profile_url)
    path = parsed.path.strip("/")
    parts = path.split("/")
    if len(parts) >= 2 and parts[0] == "in" and parts[1]:
        return parts[1]
    raise ValueError(f"Unsupported LinkedIn profile URL format: {profile_url}")


# Optional: load APIFY_TOKEN from a local .env file (same folder as this script)
try:
    from dotenv import load_dotenv  # type: ignore

    load_dotenv(
        dotenv_path=os.path.join(os.path.dirname(__file__), ".env"),
        override=True,
    )
except Exception:
    pass


apify_token = os.getenv("APIFY_TOKEN", "").strip()
if not apify_token:
    raise SystemExit(
        "Missing APIFY_TOKEN env var. Set it like:\n"
        "  export APIFY_TOKEN='apify_api_...'\n"
        "or create a local .env file containing:\n"
        "  APIFY_TOKEN=apify_api_...\n"
        "and rerun."
    )

if apify_token == "apify_api_...":
    raise SystemExit(
        "APIFY_TOKEN is still set to the placeholder value 'apify_api_...'.\n"
        "Open `linkedin_scraper/.env` and paste your real Apify token, then rerun."
    )

client = ApifyClient(apify_token)

all_results: dict[str, list[dict]] = {}
failed: dict[str, str] = {}

for profile_url in TARGET_PROFILE_URLS:
    username = linkedin_username_from_url(profile_url)
    run_input = {
        "username": username,
        "includeEmail": False,
    }

    print(f"Scraping LinkedIn profile: {profile_url} (username={username})")
    try:
        run = client.actor(ACTOR_ID).call(run_input=run_input)
    except ApifyApiError as exc:
        msg = str(exc)
        failed[profile_url] = msg
        print(f"Failed for {profile_url}: {msg}")
        all_results[profile_url] = []
        continue
    dataset_id = run["defaultDatasetId"]
    print(f"Run finished. Dataset ID: {dataset_id}")

    results = list(client.dataset(dataset_id).iterate_items())
    all_results[profile_url] = results

    if not results:
        print("No data returned for this profile.")
    else:
        print(f"Returned {len(results)} item(s) for this profile.")

# Overwrite output file on every run
with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
    json.dump(all_results, f, ensure_ascii=False, indent=2)

print(f"\nSaved results for {len(TARGET_PROFILE_URLS)} profile(s) to: {OUTPUT_FILE}")

if failed:
    print("\nSome profiles failed:")
    for url, err in failed.items():
        print(f"- {url}: {err}")

