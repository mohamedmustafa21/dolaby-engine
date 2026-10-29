"""Candidate generation with pruning. Uses ONLY the garments passed in; never invents items."""
from __future__ import annotations

from itertools import product
from typing import Dict, List, Optional, Sequence

from .compatibility import item_rejection, occasion_fit, role_of, season_fit, validate_outfit
from .config import EngineConfig
from .ranking import ScoredCandidate, rank, score_outfit, select_diverse, to_outfit
from .schemas import Garment, GenerationResult, OutfitRequest


def _prior(g: Garment, request: OutfitRequest) -> float:
    return occasion_fit(g, request.occasion) * season_fit(g.season, request.season)


def _prune(items: List[Garment], request: OutfitRequest, limit: int) -> List[Garment]:
    return sorted(items, key=lambda g: (-_prior(g, request), g.id))[:limit]


def _outerwear_options(owned: List[Garment], request: OutfitRequest):
    if not owned:
        return [None]
    if request.season == "winter" or "cold" in request.conditions:
        return list(owned)          # required when available
    if request.season == "summer" or "hot" in request.conditions:
        return [None]
    return [None] + list(owned)     # optional


def generate_outfits(wardrobe: Sequence[Garment], request: Optional[OutfitRequest] = None,
                     config: Optional[EngineConfig] = None) -> GenerationResult:
    request = request or OutfitRequest()
    config = config or EngineConfig()
    result = GenerationResult()
    stats = {"wardrobe_items": len(wardrobe), "usable_items": 0, "candidates_evaluated": 0,
             "rejected_invalid": 0, "below_min_score": 0, "returned": 0}

    usable: List[Garment] = []
    for g in sorted(wardrobe, key=lambda g: g.id):
        if not g.available or g.id in request.excluded_item_ids:
            continue
        if role_of(g) is None:
            result.warnings.append(f"Item {g.id}: unknown category '{g.category}' was ignored.")
            continue
        if item_rejection(g, request):
            continue
        usable.append(g)
    stats["usable_items"] = len(usable)

    by_role: Dict[str, List[Garment]] = {}
    for g in usable:
        by_role.setdefault(role_of(g), []).append(g)

    structures = []
    if by_role.get("top") and by_role.get("bottom"):
        structures.append(("two_piece", by_role["top"], by_role["bottom"]))
    if by_role.get("one_piece"):
        structures.append(("one_piece", by_role["one_piece"], [None]))
    if not structures:
        result.warnings.append("The available wardrobe has no valid top + bottom or dress for this request.")
        result.stats = stats
        return result

    footwear = by_role.get("footwear", [])
    require_footwear = config.require_footwear
    if require_footwear and not footwear:
        require_footwear = False
        result.warnings.append("No suitable footwear in the wardrobe; outfits are shown without shoes.")

    limit = config.max_per_role
    while True:
        pools = []
        for _, mains, bottoms in structures:
            pools.append((_prune(mains, request, limit), _prune([b for b in bottoms if b], request, limit) or [None]))
        fw = _prune(footwear, request, limit) if footwear else []
        ow = _outerwear_options(_prune(by_role.get("outerwear", []), request, limit), request)
        size = sum(len(m) * len(b) for m, b in pools) * max(1, len(fw)) * len(ow)
        if size <= config.max_candidates or limit <= 1:
            break
        limit -= 1

    base: List[ScoredCandidate] = []
    for mains, bottoms in pools:
        for main, bottom, shoe, outer in product(mains, bottoms, fw or [None], ow):
            items = [x for x in (main, bottom, shoe, outer) if x is not None]
            if require_footwear and shoe is None:
                continue
            stats["candidates_evaluated"] += 1
            if validate_outfit(items, config):
                stats["rejected_invalid"] += 1
                continue
            base.append(score_outfit(items, request, config))

    ranked = rank(base)
    accessories = _prune(by_role.get("accessory", []), request, config.max_accessories)
    if accessories:  # accessories are optional extras; keep one only if it does not hurt the score
        upgraded = []
        for c in ranked[:config.accessory_top_n]:
            best = c
            for acc in accessories:
                items = list(c.items) + [acc]
                if validate_outfit(items, config):
                    continue
                cand = score_outfit(items, request, config)
                if cand.score > best.score:
                    best = cand
            upgraded.append(best)
        ranked = rank(upgraded + ranked[config.accessory_top_n:])

    good = [c for c in ranked if c.score >= config.min_outfit_score]
    stats["below_min_score"] = len(ranked) - len(good)
    chosen = select_diverse(good, request.max_outfits, config)
    result.outfits = [to_outfit(c) for c in chosen]
    stats["returned"] = len(chosen)
    if len(chosen) < request.max_outfits:
        result.warnings.append(
            f"Only {len(chosen)} good outfit(s) could be built from the available wardrobe.")
    result.stats = stats
    return result
