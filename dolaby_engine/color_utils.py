"""Pure-Python color math and naming (no OpenCV needed). Deterministic."""
from __future__ import annotations

import colorsys
import math
import re
from dataclasses import dataclass
from typing import Tuple

_HEX_RE = re.compile(r"^#?([0-9a-fA-F]{6}|[0-9a-fA-F]{3})$")

NEUTRAL_FAMILIES = frozenset({"black", "white", "gray", "beige", "brown", "navy"})
FAMILIES = ("black", "white", "gray", "beige", "brown", "navy", "red", "orange",
            "yellow", "green", "teal", "blue", "purple", "pink")


def normalize_hex(value) -> str:
    if not isinstance(value, str) or not _HEX_RE.match(value.strip()):
        raise ValueError(f"not a valid hex color: {value!r}")
    h = value.strip().lstrip("#")
    if len(h) == 3:
        h = "".join(c * 2 for c in h)
    return "#" + h.upper()


def hex_to_rgb(value: str) -> Tuple[int, int, int]:
    h = normalize_hex(value)[1:]
    return int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)


def rgb_to_hex(rgb) -> str:
    r, g, b = (max(0, min(255, int(round(c)))) for c in rgb)
    return f"#{r:02X}{g:02X}{b:02X}"


def rgb_to_lab(rgb) -> Tuple[float, float, float]:
    """sRGB (0-255) -> CIELAB (D65)."""
    def lin(c: float) -> float:
        c /= 255.0
        return c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4

    r, g, b = (lin(c) for c in rgb)
    x = (0.4124564 * r + 0.3575761 * g + 0.1804375 * b) / 0.95047
    y = 0.2126729 * r + 0.7151522 * g + 0.0721750 * b
    z = (0.0193339 * r + 0.1191920 * g + 0.9503041 * b) / 1.08883

    def f(t: float) -> float:
        return t ** (1 / 3) if t > 216 / 24389 else (24389 / 27 * t + 16) / 116

    fx, fy, fz = f(x), f(y), f(z)
    return 116 * fy - 16, 500 * (fx - fy), 200 * (fy - fz)


def delta_e(lab1, lab2) -> float:
    """CIE76 color difference. Simple and adequate for coarse grouping."""
    return math.dist(lab1, lab2)


def circular_hue_distance(a: float, b: float) -> float:
    d = abs(a - b) % 360.0
    return min(d, 360.0 - d)


@dataclass(frozen=True)
class ColorInfo:
    hex: str
    family: str
    hue: float
    saturation: float
    value: float
    lightness: float  # CIELAB L*
    chroma: float  # CIELAB C*

    @property
    def is_neutral(self) -> bool:
        return self.family in NEUTRAL_FAMILIES


def classify(value: str) -> ColorInfo:
    """Map a hex color to a human-understandable family using HSV + CIELAB chroma."""
    hx = normalize_hex(value)
    rgb = hex_to_rgb(hx)
    h, s, v = colorsys.rgb_to_hsv(*(c / 255.0 for c in rgb))
    hue = h * 360.0
    L, a, b = rgb_to_lab(rgb)
    chroma = math.hypot(a, b)

    if v < 0.20:
        family = "black"
    elif s < 0.10 or chroma < 9:
        family = "white" if v >= 0.88 else ("black" if v < 0.30 else "gray")
    elif 20 <= hue < 65 and v >= 0.62 and s < (0.45 if hue < 45 else 0.30):
        family = "beige"
    elif 8 <= hue < 50 and v < 0.62:
        family = "brown"
    elif 195 <= hue <= 260 and v < 0.45 and s >= 0.35:
        family = "navy"
    elif (hue < 15 or hue >= 295) and s < 0.5 and v >= 0.75:
        family = "pink"
    elif hue < 15 or hue >= 345:
        family = "red"
    elif hue < 40:
        family = "orange"
    elif hue < 75:
        family = "green" if v < 0.62 else "yellow"  # dark yellow-green = olive
    elif hue < 165:
        family = "green"
    elif hue < 200:
        family = "teal"
    elif hue < 255:
        family = "blue"
    elif hue < 295:
        family = "purple"
    else:
        family = "pink"
    return ColorInfo(hx, family, hue, s, v, L, chroma)
