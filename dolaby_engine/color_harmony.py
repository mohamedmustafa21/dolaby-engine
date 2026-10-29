"""Explainable, configurable color-harmony rules. Score in [0, 1] plus a short explanation.

Hue relations use HSV hue angles (a simplification of a real color wheel); lightness and
chroma balance use CIELAB. All thresholds live in HarmonyConfig. These are heuristics,
not scientifically established values.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, FrozenSet, List, Sequence

from .color_utils import NEUTRAL_FAMILIES, ColorInfo, circular_hue_distance, classify


def _pair(a: str, b: str) -> FrozenSet[str]:
    return frozenset((a, b))


@dataclass
class HarmonyConfig:
    neutral_families: FrozenSet[str] = NEUTRAL_FAMILIES
    mono_deg: float = 15.0
    analogous_deg: float = 45.0
    complementary_tol: float = 25.0
    triadic_tol: float = 20.0
    score_neutral_only: float = 0.85
    score_neutral_accent: float = 0.92
    score_monochromatic: float = 0.90
    score_analogous: float = 0.85
    score_complementary: float = 0.85
    score_triadic: float = 0.70
    score_clash: float = 0.30
    score_too_many: float = 0.20
    max_accent_hues: int = 2
    min_lightness_contrast: float = 12.0
    ideal_lightness_contrast: tuple = (25.0, 70.0)
    low_contrast_penalty: float = 0.10
    ideal_contrast_bonus: float = 0.03
    high_chroma: float = 60.0
    competing_chroma_penalty: float = 0.15
    # Pairs of families that are capped to a lower score regardless of hue relations.
    pair_caps: Dict[FrozenSet[str], float] = field(default_factory=lambda: {
        _pair("red", "pink"): 0.45,
        _pair("navy", "black"): 0.55,
        _pair("brown", "black"): 0.55,
        _pair("green", "blue"): 0.60,
        _pair("red", "orange"): 0.50,
        _pair("red", "green"): 0.40,
    })

    @classmethod
    def from_dict(cls, data: dict) -> "HarmonyConfig":
        cfg = cls()
        for k, v in (data or {}).items():
            if k == "pair_caps":
                cfg.pair_caps = {frozenset(p.split("+")): float(s) for p, s in v.items()}
            elif k == "neutral_families":
                cfg.neutral_families = frozenset(v)
            elif hasattr(cfg, k):
                setattr(cfg, k, v)
            else:
                raise ValueError(f"unknown harmony option '{k}'")
        return cfg


@dataclass
class HarmonyResult:
    score: float
    label: str
    explanation: str


def _clusters(hues: Sequence[float], tol: float) -> List[float]:
    reps: List[float] = []
    for h in hues:
        if all(circular_hue_distance(h, r) > tol for r in reps):
            reps.append(h)
    return reps


def score_palette(colors: Sequence[str], config: HarmonyConfig = None) -> HarmonyResult:
    cfg = config or HarmonyConfig()
    infos: List[ColorInfo] = [classify(c) for c in colors]
    if not infos:
        return HarmonyResult(0.0, "empty", "No colors to evaluate.")
    chromatic = [i for i in infos if i.family not in cfg.neutral_families]
    neutrals = [i for i in infos if i.family in cfg.neutral_families]
    fams = ", ".join(sorted({i.family for i in infos}))
    reps = _clusters([i.hue for i in chromatic], cfg.mono_deg)
    n = len(reps)

    if n == 0:
        score, label = cfg.score_neutral_only, "neutral"
        text = f"All-neutral palette ({fams}) is easy to wear."
    elif n == 1:
        if neutrals:
            score, label = cfg.score_neutral_accent, "neutral + accent"
            text = f"Neutrals ({fams}) let a single {chromatic[0].family} accent stand out."
        else:
            score, label = cfg.score_monochromatic, "monochromatic"
            text = f"Shades of {chromatic[0].family} give a monochromatic look."
    elif n == 2:
        d = circular_hue_distance(reps[0], reps[1])
        if d <= cfg.analogous_deg:
            score, label = cfg.score_analogous, "analogous"
            text = f"Neighboring hues ({fams}) form an analogous palette."
        elif abs(d - 180) <= cfg.complementary_tol:
            score, label = cfg.score_complementary, "complementary"
            text = f"Opposite hues ({fams}) are complementary."
        else:
            score, label = cfg.score_clash, "clashing hues"
            text = f"Hues ({fams}) are neither neighboring nor complementary, so they may compete."
    elif n == 3 and all(
        abs(circular_hue_distance(a, b) - 120) <= cfg.triadic_tol
        for i, a in enumerate(reps) for b in reps[i + 1:]
    ):
        score, label = cfg.score_triadic, "triadic"
        text = f"Three evenly spaced hues ({fams}) form a triadic palette; keep it playful."
    elif n == 3:
        score, label = cfg.score_clash, "too many accents"
        text = f"Three unrelated hues ({fams}) compete for attention."
    else:
        score, label = cfg.score_too_many, "too many accents"
        text = f"{n} different hues ({fams}) compete for attention."
    notes = [text]

    lights = [i.lightness for i in infos]
    spread = max(lights) - min(lights)
    if len(infos) >= 2 and label not in ("monochromatic",):
        if spread < cfg.min_lightness_contrast:
            score -= cfg.low_contrast_penalty
            notes.append("Items have very similar lightness, so the look may feel flat.")
        elif cfg.ideal_lightness_contrast[0] <= spread <= cfg.ideal_lightness_contrast[1]:
            score += cfg.ideal_contrast_bonus
            notes.append("Light/dark contrast is well balanced.")

    loud = _clusters([i.hue for i in chromatic if i.chroma >= cfg.high_chroma], cfg.mono_deg)
    if len(loud) >= 2 and label != "complementary":
        score -= cfg.competing_chroma_penalty
        notes.append("Several strongly saturated colors compete.")

    fam_set = {i.family for i in infos}
    caps = [c for p, c in cfg.pair_caps.items() if p <= fam_set]
    if caps:
        score = min(score, min(caps))
        notes.append("A combination in this palette is generally considered hard to pair.")

    return HarmonyResult(round(max(0.0, min(1.0, score)), 4), label, " ".join(notes))
