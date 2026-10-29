"""Central, overridable engine configuration. Weights are initial heuristics, not validated values."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, FrozenSet, Optional, Tuple

from .color_harmony import HarmonyConfig

DEFAULT_WEIGHTS = {"harmony": 0.35, "compatibility": 0.30, "occasion_season": 0.20, "preferences": 0.15}


@dataclass
class EngineConfig:
    weights: Dict[str, float] = field(default_factory=lambda: dict(DEFAULT_WEIGHTS))
    harmony: HarmonyConfig = field(default_factory=HarmonyConfig)
    max_per_role: int = 8           # pruning: best N items per role enter the search
    max_candidates: int = 3000      # hard cap on evaluated combinations
    max_accessories: int = 4
    accessory_top_n: int = 10       # try accessories only on the best N base outfits
    max_formality_gap: int = 2      # larger gap between two items = invalid
    min_style_pair_score: float = 0.25
    dedupe_jaccard: float = 0.6
    min_outfit_score: float = 0.45  # weaker outfits are dropped rather than shown
    require_footwear: bool = True   # auto-relaxed (with a warning) if wardrobe has none
    hard_incompatible_pairs: FrozenSet[FrozenSet[str]] = frozenset({
        frozenset({"shorts", "coats"}),
        frozenset({"shorts", "boots"}),
    })

    def normalized_weights(self) -> Dict[str, float]:
        total = sum(self.weights.values())
        if total <= 0 or any(w < 0 for w in self.weights.values()):
            raise ValueError("weights must be non-negative and sum to > 0")
        return {k: v / total for k, v in self.weights.items()}

    @classmethod
    def from_dict(cls, data: Optional[dict]) -> "EngineConfig":
        cfg = cls()
        for k, v in (data or {}).items():
            if k == "weights":
                unknown = set(v) - set(DEFAULT_WEIGHTS)
                if unknown:
                    raise ValueError(f"unknown weight keys: {sorted(unknown)}")
                cfg.weights = {**DEFAULT_WEIGHTS, **v}
            elif k == "harmony":
                cfg.harmony = HarmonyConfig.from_dict(v)
            elif k == "hard_incompatible_pairs":
                cfg.hard_incompatible_pairs = frozenset(frozenset(p) for p in v)
            elif hasattr(cfg, k):
                setattr(cfg, k, v)
            else:
                raise ValueError(f"unknown config option '{k}'")
        cfg.normalized_weights()
        return cfg
