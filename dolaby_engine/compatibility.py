"""Garment roles, hard rejection rules and soft compatibility scores."""
from __future__ import annotations

from typing import Dict, List, Optional, Sequence, Tuple

from .config import EngineConfig
from .schemas import Garment, OutfitRequest

CATEGORY_ROLES: Dict[str, str] = {
    "t-shirts": "top", "shirts": "top", "blouses": "top",
    "trousers": "bottom", "jeans": "bottom", "shorts": "bottom", "skirts": "bottom",
    "dresses": "one_piece",
    "jackets": "outerwear", "coats": "outerwear",
    "sneakers": "footwear", "shoes": "footwear", "boots": "footwear",
    "accessories": "accessory", "bags": "accessory",
}

DEFAULT_FORMALITY: Dict[str, int] = {
    "t-shirts": 1, "shirts": 3, "blouses": 3, "trousers": 3, "jeans": 2, "shorts": 1,
    "skirts": 3, "dresses": 3, "jackets": 3, "coats": 3, "sneakers": 1, "shoes": 4,
    "boots": 3, "accessories": 3, "bags": 3,
}

_STYLE_PAIRS = {
    ("casual", "casual"): 1.0, ("casual", "smart_casual"): 0.8, ("casual", "formal"): 0.3,
    ("casual", "sporty"): 0.7, ("casual", "streetwear"): 0.85, ("casual", "minimal"): 0.85,
    ("smart_casual", "smart_casual"): 1.0, ("smart_casual", "formal"): 0.8,
    ("smart_casual", "sporty"): 0.35, ("smart_casual", "streetwear"): 0.5,
    ("smart_casual", "minimal"): 0.9, ("formal", "formal"): 1.0, ("formal", "sporty"): 0.05,
    ("formal", "streetwear"): 0.15, ("formal", "minimal"): 0.8, ("sporty", "sporty"): 1.0,
    ("sporty", "streetwear"): 0.8, ("sporty", "minimal"): 0.6, ("streetwear", "streetwear"): 1.0,
    ("streetwear", "minimal"): 0.7, ("minimal", "minimal"): 1.0,
}

# occasion -> (min formality, max formality, preferred styles)
OCCASION_PROFILES = {
    "casual": (1, 3, {"casual", "streetwear", "minimal", "smart_casual"}),
    "work": (3, 4, {"smart_casual", "formal", "minimal"}),
    "formal": (4, 5, {"formal"}),
    "party": (3, 5, {"formal", "smart_casual", "streetwear"}),
    "sport": (1, 2, {"sporty"}),
}

# (item season, requested season) -> fit; summer<->winter is rejected outright.
_SEASON_FIT = {"all": 0.85}
_ADJACENT = {("spring", "summer"), ("summer", "autumn"), ("autumn", "winter"), ("winter", "spring")}


def role_of(garment: Garment) -> Optional[str]:
    return CATEGORY_ROLES.get(garment.category)


def formality_of(garment: Garment) -> int:
    return garment.formality if garment.formality is not None else DEFAULT_FORMALITY.get(garment.category, 3)


def style_score(a: str, b: str) -> float:
    return _STYLE_PAIRS.get((a, b), _STYLE_PAIRS.get((b, a), 0.5))


def season_fit(item_season: str, target: Optional[str]) -> Optional[float]:
    """Return fit in [0,1], or None if the item must be rejected for this season."""
    if target is None:
        return 1.0
    if item_season == "all":
        return _SEASON_FIT["all"]
    if item_season == target:
        return 1.0
    if {item_season, target} == {"summer", "winter"}:
        return None
    if (item_season, target) in _ADJACENT or (target, item_season) in _ADJACENT:
        return 0.6
    return 0.5  # spring <-> autumn


def occasion_fit(garment: Garment, occasion: str) -> Optional[float]:
    """Fit in [0,1], or None if the item is unsuitable (formality 2+ outside the range)."""
    lo, hi, styles = OCCASION_PROFILES[occasion]
    f = formality_of(garment)
    gap = max(lo - f, f - hi, 0)
    if gap >= 2:
        return None
    formality_fit = 1.0 - 0.4 * gap
    style_fit = 1.0 if garment.style in styles else 0.4
    return 0.7 * formality_fit + 0.3 * style_fit


def item_rejection(garment: Garment, request: OutfitRequest) -> Optional[str]:
    """Item-level hard rules for this request (used to prune before combining)."""
    if season_fit(garment.season, request.season) is None:
        return f"{garment.category} ({garment.season}) is out of season for {request.season}"
    if occasion_fit(garment, request.occasion) is None:
        return f"{garment.category} is too {'formal' if formality_of(garment) > 3 else 'casual'} for {request.occasion}"
    if "hot" in request.conditions and role_of(garment) == "outerwear":
        return "outerwear skipped for hot conditions"
    return None


def pair_rejection(a: Garment, b: Garment, config: EngineConfig) -> Optional[str]:
    if frozenset({a.category, b.category}) in config.hard_incompatible_pairs:
        return f"{a.category} + {b.category} is excluded by rule"
    if abs(formality_of(a) - formality_of(b)) > config.max_formality_gap:
        return f"formality of {a.category} and {b.category} is too far apart"
    if style_score(a.style, b.style) < config.min_style_pair_score:
        return f"styles {a.style}/{b.style} do not belong together"
    return None


def validate_outfit(items: Sequence[Garment], config: EngineConfig) -> List[str]:
    reasons = []
    roles = [role_of(i) for i in items]
    has_pair = "top" in roles and "bottom" in roles
    has_one = "one_piece" in roles
    if has_one and (("top" in roles) or ("bottom" in roles)):
        reasons.append("a dress cannot be combined with a separate top or bottom")
    if not has_pair and not has_one:
        reasons.append("outfit needs top + bottom or a one-piece")
    for r in ("top", "bottom", "one_piece", "footwear", "outerwear"):
        if roles.count(r) > 1:
            reasons.append(f"more than one {r}")
    if roles.count("accessory") > 1:
        reasons.append("more than one accessory")
    for i, a in enumerate(items):
        for b in items[i + 1:]:
            r = pair_rejection(a, b, config)
            if r:
                reasons.append(r)
    return reasons


def _pattern_score(items: Sequence[Garment]) -> Tuple[float, str]:
    patterned = [i.pattern for i in items if i.pattern not in ("solid", "none", "")]
    if len(patterned) <= 1:
        return 1.0, "at most one patterned piece"
    if len(set(patterned)) == 1:
        return 0.6, "repeated pattern"
    return 0.35, "multiple different patterns compete"


def outfit_compatibility(items: Sequence[Garment], config: EngineConfig) -> Tuple[float, str]:
    """Soft score for a (hard-valid) outfit: style fit, formality coherence, pattern balance."""
    styles, forms = [], []
    for i, a in enumerate(items):
        for b in items[i + 1:]:
            styles.append(style_score(a.style, b.style))
            forms.append(1.0 - abs(formality_of(a) - formality_of(b)) / 4.0)
    style_avg = sum(styles) / len(styles) if styles else 1.0
    form_avg = sum(forms) / len(forms) if forms else 1.0
    pat, pat_note = _pattern_score(items)
    score = 0.45 * style_avg + 0.35 * form_avg + 0.20 * pat
    gap = max(formality_of(x) for x in items) - min(formality_of(x) for x in items)
    note = (f"Styles are {'well matched' if style_avg >= 0.8 else 'somewhat mixed'}, "
            f"formality gap is {gap} level(s), {pat_note}.")
    return round(score, 4), note
