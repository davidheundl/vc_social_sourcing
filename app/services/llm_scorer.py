"""
LLM-based bio scorer using Google Gemini 2.5 Flash.

Analyzes a Twitter bio and returns structured scores for:
- role_score (0-20): founder / CEO / builder / engineer etc.
- early_stage_score (0-15): MVP, stealth, building in public etc.
- fundraising_score (0-25): actively raising, looking for investors etc.

Results are cached on the Score object so Gemini is only called once per
new profile (or again if the bio changes).
"""

import json
import logging
import time
from typing import Optional

logger = logging.getLogger("llm_scorer")

_client = None

GEMINI_MODEL = "gemini-2.5-flash"

PROMPT_TEMPLATE = """You are a senior VC analyst at a top-tier venture capital firm specializing in early-stage investments.

Your task: analyze a Twitter/X bio and score this person's potential as someone a VC would want to meet.

You are looking for three types of profiles:
1. **Potential founders** — people who might start or are already building a company. Strong signals: technical depth, domain expertise, prior startup experience, "building", "launching", side projects, ex-FAANG/big tech who left to build something.
2. **Early-stage talent** — hidden gems not yet on VC radar. Strong signals: niche expertise in hot areas (AI, biotech, climate, fintech, b2b SaaS), exceptional technical background, research-to-startup trajectory, indie hackers with traction.
3. **Fundraising-ready** — people actively seeking or close to seeking investment. Strong signals: explicit fundraising language, talking to investors, seed/pre-seed context, accelerator mentions (YC, Antler, etc.).

Return ONLY valid JSON (no markdown, no explanation):
{{
  "role_score": <int 0-20>,
  "role_reason": "<one short phrase or empty string>",
  "early_stage_score": <int 0-15>,
  "early_stage_reason": "<one short phrase or empty string>",
  "fundraising_score": <int 0-25>,
  "fundraising_reason": "<one short phrase or empty string>"
}}

Scoring guide:
- role_score:
  20 = founder / co-founder (active or explicit)
  17 = CEO / CTO / CPO / C-suite at startup
  15 = ex-FAANG/top-tier company, now building independently
  12 = "building X", "creating X", "launching X", indie maker, solo builder
  10 = startup employee with domain expertise in AI/biotech/fintech/climate
  6  = engineer / designer / PM at any company
  0  = investor, VC, journalist, no clear signal

- early_stage_score:
  15 = shipped MVP / beta / launched product, has users or traction
  12 = stealth mode / just started / day-one builder
  10 = building in public, hiring first team, open-source project
  8  = side project with clear scope, research being commercialized
  6  = working on something new, vague but promising
  0  = no early-stage signal

- fundraising_score:
  25 = explicitly raising seed / pre-seed round right now
  20 = fundraising language, seeking investment, open to VC
  18 = looking for co-founder or first investors
  15 = mentions YC / Antler / accelerator (applied or accepted)
  12 = talking to VCs or angels
  8  = bootstrapped with revenue (potential future raise)
  0  = no fundraising signal

Important nuances:
- Investors, VCs, and journalists should score 0 for role unless they are also building something.
- "Ex-Google/Meta/OpenAI building X" is a very strong signal (role_score 15+).
- Vague bios with no startup context should score low across the board.
- A researcher moving into industry or commercializing research is a strong signal.

Bio: {bio}"""


def _get_client():
    global _client
    if _client is None:
        try:
            from google import genai
            from config import config
            if not getattr(config, "GEMINI_API_KEY", None):
                return None
            _client = genai.Client(api_key=config.GEMINI_API_KEY)
        except Exception as exc:
            logger.warning("Could not initialise Gemini client: %s", exc)
            return None
    return _client


def score_bio(bio: str) -> Optional[dict]:
    """
    Call Gemini Flash to score a Twitter bio.
    Returns dict with role_score, early_stage_score, fundraising_score + reasons,
    or None if the API call fails or no API key is configured.
    """
    client = _get_client()
    if not client or not bio or not bio.strip():
        return None

    from google.genai import types
    system_instruction = PROMPT_TEMPLATE.split("Bio: {bio}")[0].strip()
    user_message = f"Bio: {bio[:500]}"
    config = types.GenerateContentConfig(
        system_instruction=system_instruction,
        temperature=0.1,
        max_output_tokens=1024,
        response_mime_type="application/json",
    )

    for attempt in range(3):
        try:
            response = client.models.generate_content(
                model=GEMINI_MODEL,
                contents=user_message,
                config=config,
            )
            return json.loads(response.text.strip())
        except Exception as exc:
            err = str(exc)
            if "429" in err or "RESOURCE_EXHAUSTED" in err:
                wait = 15 * (attempt + 1)
                logger.info("Gemini rate limit — retrying in %ds", wait)
                time.sleep(wait)
            else:
                logger.warning("Gemini bio scoring failed: %s", exc)
                return None

    logger.warning("Gemini bio scoring: all retries exhausted")
    return None
