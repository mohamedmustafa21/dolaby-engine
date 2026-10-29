"""Input/output data structures. Strict validation: bad input fails loudly."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from .color_utils import normalize_hex

STYLES = ("casual", "smart_casual", "formal", "sporty", "streetwear", "minimal")
OCCASIONS = ("casual", "work", "formal", "party", "sport")
SEASONS = ("spring", "summer", "autumn", "winter")
CONDITIONS = ("cold", "hot")  # user-selected; the engine never checks live weather
ROLES = ("top", "bottom", "one_piece", "footwear", "outerwear", "accessory")


class ValidationError(ValueError):
    """Raised when engine input is malformed."""


def _norm_token(value: Any) -> str:
    return str(value).strip().lower().replace("-", "_").replace(" ", "_")


def _norm_slug(value: Any) -> str:
    return str(value).strip().lower().replace("_", "-").replace(" ", "-")


@dataclass(frozen=True)
class Garment:
    id: int
    category: str  # category slug, e.g. "t-shirts"
    primary_hex: str
    style: str = "casual"
    season: str = "all"
    pattern: str = "solid"
    formality: Optional[int] = None  # 1 (very casual) .. 5 (very formal)
    secondary_hex: Optional[str] = None
    available: bool = True
    name: Optional[str] = None

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Garment":
        try:
            gid = int(data["id"])
            category = _norm_slug(data["category"])
        except (KeyError, TypeError, ValueError) as exc:
            raise ValidationError(f"garment needs integer 'id' and 'category': {exc}") from exc
        color = data.get("hex_color") or data.get("primary_hex")
        try:
            primary = normalize_hex(color)
            sec = data.get("secondary_hex")
            secondary = normalize_hex(sec) if sec else None
        except (ValueError, TypeError) as exc:
            raise ValidationError(f"garment {gid}: invalid color: {exc}") from exc
        style = _norm_token(data.get("style") or "casual")
        if style not in STYLES:
            raise ValidationError(f"garment {gid}: unknown style '{style}'")
        season = _norm_token(data.get("season") or "all")
        if season not in SEASONS + ("all",):
            raise ValidationError(f"garment {gid}: unknown season '{season}'")
        formality = data.get("formality_level", data.get("formality"))
        if formality is not None:
            formality = int(formality)
            if not 1 <= formality <= 5:
                raise ValidationError(f"garment {gid}: formality must be 1..5")
        status = data.get("availability_status", "available")
        available = bool(data.get("available", True)) and _norm_token(status) == "available"
        return cls(
            id=gid, category=category, primary_hex=primary, style=style, season=season,
            pattern=_norm_token(data.get("pattern") or "solid"), formality=formality,
            secondary_hex=secondary, available=available, name=data.get("name"),
        )


@dataclass(frozen=True)
class OutfitRequest:
    occasion: str = "casual"
    season: Optional[str] = None
    style: Optional[str] = None
    user_preferred_style: Optional[str] = None
    preferred_colors: tuple = ()  # color family names or hex codes
    excluded_item_ids: frozenset = frozenset()
    conditions: tuple = ()
    max_outfits: int = 3

    @classmethod
    def from_dict(cls, data: Optional[Dict[str, Any]]) -> "OutfitRequest":
        data = data or {}
        occasion = _norm_token(data.get("occasion") or "casual")
        if occasion not in OCCASIONS:
            raise ValidationError(f"unknown occasion '{occasion}'")
        season = data.get("season")
        season = _norm_token(season) if season else None
        if season is not None and season not in SEASONS:
            raise ValidationError(f"unknown season '{season}'")
        styles = []
        for key in ("style", "user_preferred_style"):
            v = data.get(key)
            v = _norm_token(v) if v else None
            if v is not None and v not in STYLES:
                raise ValidationError(f"unknown {key} '{v}'")
            styles.append(v)
        conditions = tuple(_norm_token(c) for c in data.get("conditions") or ())
        for c in conditions:
            if c not in CONDITIONS:
                raise ValidationError(f"unknown condition '{c}'")
        max_outfits = int(data.get("max_outfits", 3))
        if not 1 <= max_outfits <= 10:
            raise ValidationError("max_outfits must be 1..10")
        return cls(
            occasion=occasion, season=season, style=styles[0], user_preferred_style=styles[1],
            preferred_colors=tuple(str(c).strip().lower() for c in data.get("preferred_colors") or ()),
            excluded_item_ids=frozenset(int(i) for i in data.get("excluded_item_ids") or ()),
            conditions=conditions, max_outfits=max_outfits,
        )


@dataclass
class OutfitItem:
    id: int
    role: str


@dataclass
class Outfit:
    items: List[OutfitItem]
    score: float
    components: Dict[str, float]
    harmony_label: str
    explanation: str

    def item_ids(self) -> frozenset:
        return frozenset(i.id for i in self.items)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "items": [{"id": i.id, "role": i.role} for i in self.items],
            "score": self.score,
            "components": self.components,
            "harmony_label": self.harmony_label,
            "explanation": self.explanation,
        }


@dataclass
class GenerationResult:
    outfits: List[Outfit] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)
    stats: Dict[str, int] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        from . import __version__
        return {
            "engine_version": __version__,
            "method": "rules-based (deterministic); not a trained ML model",
            "outfits": [o.to_dict() for o in self.outfits],
            "warnings": self.warnings,
            "stats": self.stats,
        }
