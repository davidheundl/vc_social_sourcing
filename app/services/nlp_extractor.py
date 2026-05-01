import re
from dataclasses import dataclass, field
from typing import List


@dataclass
class ExtractedSignals:
    is_founder: bool = False
    fundraising_intent: bool = False
    early_stage: bool = False
    sectors: List[str] = field(default_factory=list)
    matched_keywords: List[str] = field(default_factory=list)


_FOUNDER_KEYWORDS = [
    r"\bfounder\b", r"\bco-founder\b", r"\bcofounder\b",
    r"\bceo\b", r"\bbuilding\b", r"\bstarting\b",
]

_FUNDRAISING_KEYWORDS = [
    r"\braising\b", r"\bpre-seed\b", r"\bpreseed\b", r"\bseed round\b",
    r"\blooking for investors\b", r"\btalking to vcs\b", r"\bopen to investment\b",
    r"\bfundraising\b", r"\binvestment round\b",
]

_EARLY_STAGE_KEYWORDS = [
    r"\bmvp\b", r"\bbeta\b", r"\blaunching soon\b", r"\bjust launched\b",
    r"\bjust started\b", r"\bnew startup\b", r"\bstealth\b",
    r"\bhiring founding team\b", r"\bbuilding in public\b",
]

_SECTORS = {
    "AI": [r"\bai\b", r"\bartificial intelligence\b", r"\bllm\b", r"\bmachine learning\b", r"\bml\b"],
    "Fintech": [r"\bfintech\b", r"\bpayments\b", r"\bneobank\b", r"\bcrypto\b", r"\bdefi\b"],
    "SaaS": [r"\bsaas\b", r"\bb2b\b", r"\bsoftware\b"],
    "Healthtech": [r"\bhealthtech\b", r"\bmedtech\b", r"\bhealth\b", r"\bclinical\b"],
    "Climate": [r"\bclimatetech\b", r"\bcleantech\b", r"\bsustainability\b", r"\bgreen\b"],
    "Deeptech": [r"\bdeeptech\b", r"\bdeep tech\b", r"\bquantum\b", r"\bbiotech\b"],
}


def _match_any(text: str, patterns: List[str]) -> List[str]:
    text = text.lower()
    return [p for p in patterns if re.search(p, text)]


def extract_signals(text: str) -> ExtractedSignals:
    if not text:
        return ExtractedSignals()

    signals = ExtractedSignals()
    combined = text.lower()

    founder_hits = _match_any(combined, _FOUNDER_KEYWORDS)
    if founder_hits:
        signals.is_founder = True
        signals.matched_keywords.extend(founder_hits)

    fundraising_hits = _match_any(combined, _FUNDRAISING_KEYWORDS)
    if fundraising_hits:
        signals.fundraising_intent = True
        signals.matched_keywords.extend(fundraising_hits)

    early_hits = _match_any(combined, _EARLY_STAGE_KEYWORDS)
    if early_hits:
        signals.early_stage = True
        signals.matched_keywords.extend(early_hits)

    for sector, patterns in _SECTORS.items():
        if _match_any(combined, patterns):
            signals.sectors.append(sector)

    return signals
