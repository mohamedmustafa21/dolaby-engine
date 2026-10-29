"""Scoring, deterministic ranking and near-duplicate removal."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List, Optional, Sequence

from .color_harmony import score_palette
from .color_utils import classify
from .compatibility import (occasion_fit, outfit_compatibility, role_of, season_fit, style_score)
from .config import EngineConfig
from .schemas import Garment, Outfit, OutfitItem, OutfitRequest

ROLE_ORDER = {"top": 0, "one_piece": 0, "bottom": 1, "outerwear": 2, "footwear": 3, "accessory": 4}


@dataclass
class ScoredCandidate:
    items: Sequence[Garment]
    score: float
    components: Dict[str, float]
    harmony_label: str
    explanation: str

    def key(self):
        return (-self.score, tuple(sorted(i.id for i in self.items)))

    def ids(self) -> frozenset:
        return frozenset(i.id for i in self.items)

    def core_ids(self) -> frozenset:
        return frozenset(i.id for i in self.items if role_of(i) in ("top", "bottom", "one_piece"))


def _palette(items: Sequence[Garment]) -> List[str]:
    colors = []
    for i in items:
        colors.append(i.primary_hex)
        if i.secondary_hex and i.pattern not in ("solid", "none", ""):
            colors.append(i.secondary_hex)
    return colors


def _preference_score(items, request: OutfitRequest):
    signals, notes = [], []
    wanted = request.style or request.user_preferred_style
    if wanted:
        core = [i for i in items if role_of(i) != "accessory"]
        s = sum(style_score(i.style, wanted) for i in core) / len(core)
        signals.append(s)
        notes.append(f"matches your {wanted.replace('_', ' ')} preference ({s:.0%})")
    if request.preferred_colors:
        fams = {classify(i.primary_hex).family for i in items}
        hexes = {i.primary_hex for i in items}
        hit = [c for c in request.preferred_colors if c in fams or c.upper() in hexes]
        signals.append(len(hit) / len(request.preferred_colors))
        notes.append(f"includes preferred color(s): {', '.join(hit)}" if hit
                     else "does not include your preferred colors")
    if not signals:
        return 0.5, "No explicit style or color preferences were set."
    return sum(signals) / len(signals), "Outfit " + " and ".join(notes) + "."


def score_outfit(items: Sequence[Garment], request: OutfitRequest, config: EngineConfig) -> ScoredCandidate:
    items = sorted(items, key=lambda i: (ROLE_ORDER.get(role_of(i), 9), i.id))
    harmony = score_palette(_palette(items), config.harmony)
    compat, compat_note = outfit_compatibility(items, config)
    occ = sum(occasion_fit(i, request.occasion) for i in items) / len(items)
    sea = sum(season_fit(i.season, request.season) for i in items) / len(items)
    cold_note = ""
    if "cold" in request.conditions and not any(role_of(i) == "outerwear" for i in items):
        sea = max(0.0, sea - 0.15)
        cold_note = " No outerwear was included although cold conditions were selected."
    occ_season = 0.5 * occ + 0.5 * sea
    pref, pref_note = _preference_score(items, request)

    comps = {"harmony": harmony.score, "compatibility": compat,
             "occasion_season": round(occ_season, 4), "preferences": round(pref, 4)}
    w = config.normalized_weights()
    total = round(sum(w[k] * comps[k] for k in w), 4)
    season_txt = f" and the {request.season} season" if request.season else ""
    explanation = (f"Color: {harmony.explanation} Garments: {compat_note} "
                   f"Occasion: suits '{request.occasion}'{season_txt} ({occ_season:.0%}).{cold_note} "
                   f"Preferences: {pref_note}")
    return ScoredCandidate(items, total, comps, harmony.label, explanation)


def rank(candidates: Sequence[ScoredCandidate]) -> List[ScoredCandidate]:
    """Deterministic: score desc, ties broken by sorted item ids."""
    return sorted(candidates, key=lambda c: c.key())


def is_near_duplicate(a: ScoredCandidate, b: ScoredCandidate, jaccard: float) -> bool:
    if a.core_ids() == b.core_ids():
        return True  # same top+bottom (or dress) with other shoes/layers is not a new outfit idea
    union = a.ids() | b.ids()
    return len(a.ids() & b.ids()) / len(union) >= jaccard


def select_diverse(ranked: Sequence[ScoredCandidate], limit: int, config: EngineConfig) -> List[ScoredCandidate]:
    chosen: List[ScoredCandidate] = []
    for c in ranked:
        if all(not is_near_duplicate(c, o, config.dedupe_jaccard) for o in chosen):
            chosen.append(c)
        if len(chosen) >= limit:
            break
    return chosen


def to_outfit(c: ScoredCandidate) -> Outfit:
    return Outfit(items=[OutfitItem(i.id, role_of(i)) for i in c.items], score=c.score,
                  components=c.components, harmony_label=c.harmony_label, explanation=c.explanation)
