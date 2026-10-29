"""Baseline dominant-garment-color estimation with OpenCV + Pillow + NumPy.

This is local image processing, NOT semantic clothing recognition. It does not know
what the garment is; it only estimates which colors dominate the *foreground*.

Method
1. Load (Pillow, EXIF-aware), downscale. If the image has real transparency, use alpha as the mask.
2. Otherwise estimate the background from a border ring (median CIELAB) and mark pixels that
   differ perceptibly (delta E) as foreground; clean up with morphology, keep the largest blob.
3. If the border is not uniform or the mask is implausible, fall back to a central crop and
   lower the confidence.
4. Cluster foreground pixels in CIELAB with a deterministic k-means (farthest-point init).
5. Report palette, primary/secondary color, neutral flag and a confidence value.

Known limitations (documented on purpose): busy backgrounds, shadows on the garment, strong
colored lighting, white garments on white backgrounds, and skin/hands/hangers inside the mask
can all distort results. Users must be able to correct colors manually (the API stores the
corrected value; the analysis is only a suggestion).
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple, Union

import cv2
import numpy as np
from PIL import Image, ImageOps

from .color_utils import classify, delta_e, rgb_to_hex, rgb_to_lab

LIMITATIONS = [
    "Colors are estimated from pixels only; no garment type or style is recognized.",
    "Backgrounds, shadows, skin and lighting can distort the estimate.",
    "Always let the user confirm or correct the suggested colors.",
]


@dataclass
class ColorShare:
    hex: str
    family: str
    share: float
    is_neutral: bool


@dataclass
class ImageColorResult:
    primary_hex: str
    secondary_hex: Optional[str]
    primary_family: str
    secondary_family: Optional[str]
    is_neutral: bool
    palette: List[ColorShare]
    confidence: float
    method: str
    foreground_coverage: float
    limitations: List[str] = field(default_factory=lambda: list(LIMITATIONS))

    def to_dict(self) -> Dict[str, Any]:
        return {
            "primary_hex": self.primary_hex,
            "secondary_hex": self.secondary_hex,
            "primary_family": self.primary_family,
            "secondary_family": self.secondary_family,
            "is_neutral": self.is_neutral,
            "palette": [vars(p) for p in self.palette],
            "analysis_confidence": self.confidence,
            "method": self.method,
            "foreground_coverage": self.foreground_coverage,
            "limitations": self.limitations,
        }


def load_image(source: Union[str, np.ndarray, Image.Image], max_side: int = 256
               ) -> Tuple[np.ndarray, Optional[np.ndarray]]:
    """Return (RGB uint8 array, alpha mask or None) downscaled to max_side."""
    if isinstance(source, np.ndarray):
        img = Image.fromarray(source.astype(np.uint8))
    elif isinstance(source, Image.Image):
        img = source
    else:
        img = Image.open(source)
        img = ImageOps.exif_transpose(img)
    img.thumbnail((max_side, max_side))
    alpha = None
    if img.mode in ("RGBA", "LA") or "transparency" in img.info:
        rgba = img.convert("RGBA")
        a = np.asarray(rgba)[:, :, 3]
        if (a < 250).mean() > 0.02:  # only trust alpha if it really cuts something out
            alpha = a
        img = rgba
    rgb = np.asarray(img.convert("RGB"))
    return rgb, alpha


def _to_lab(rgb: np.ndarray) -> np.ndarray:
    return cv2.cvtColor(rgb.astype(np.float32) / 255.0, cv2.COLOR_RGB2LAB)


def estimate_foreground_mask(rgb: np.ndarray, alpha: Optional[np.ndarray] = None,
                             threshold: float = 15.0) -> Tuple[np.ndarray, str]:
    h, w = rgb.shape[:2]
    if alpha is not None:
        return alpha > 128, "alpha_mask"

    lab = _to_lab(rgb)
    ring = max(2, int(0.05 * min(h, w)))
    border = np.zeros((h, w), bool)
    border[:ring, :] = border[-ring:, :] = border[:, :ring] = border[:, -ring:] = True
    bg = np.median(lab[border], axis=0)
    spread = np.median(np.linalg.norm(lab[border] - bg, axis=1))

    def center_crop() -> Tuple[np.ndarray, str]:
        m = np.zeros((h, w), bool)
        m[h // 4: 3 * h // 4, w // 4: 3 * w // 4] = True
        return m, "center_crop"

    if spread > 12:  # background is not uniform -> border model unreliable
        return center_crop()

    mask = (np.linalg.norm(lab - bg, axis=2) > threshold).astype(np.uint8)
    k = np.ones((5, 5), np.uint8)
    mask = cv2.morphologyEx(mask, cv2.MORPH_OPEN, k)
    mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, k)
    n, labels, stats, _ = cv2.connectedComponentsWithStats(mask, connectivity=8)
    if n > 1:
        largest = 1 + int(np.argmax(stats[1:, cv2.CC_STAT_AREA]))
        mask = labels == largest
    else:
        mask = mask.astype(bool)
    coverage = mask.mean()
    if coverage < 0.04 or coverage > 0.95:
        return center_crop()
    return mask, "background_removal"


def _kmeans_lab(points: np.ndarray, k: int, iters: int = 12) -> Tuple[np.ndarray, np.ndarray]:
    """Deterministic k-means (farthest-point init, no RNG)."""
    k = min(k, len(points))
    first = int(np.argmin(np.linalg.norm(points - np.median(points, axis=0), axis=1)))
    centers = [points[first]]
    for _ in range(1, k):
        d = np.min([np.linalg.norm(points - c, axis=1) for c in centers], axis=0)
        centers.append(points[int(np.argmax(d))])
    centers = np.array(centers, dtype=np.float64)
    labels = np.zeros(len(points), int)
    for _ in range(iters):
        dist = np.linalg.norm(points[:, None, :] - centers[None, :, :], axis=2)
        labels = np.argmin(dist, axis=1)
        for i in range(k):
            sel = points[labels == i]
            if len(sel):
                centers[i] = sel.mean(axis=0)
    return centers, labels


def extract_dominant_colors(source, k: int = 3, merge_delta_e: float = 12.0,
                            min_secondary_share: float = 0.15) -> ImageColorResult:
    rgb, alpha = load_image(source)
    mask, method = estimate_foreground_mask(rgb, alpha)
    pixels_rgb = rgb[mask].astype(np.float64)
    if len(pixels_rgb) == 0:
        raise ValueError("image has no usable pixels")
    step = max(1, len(pixels_rgb) // 6000)  # deterministic subsample
    pixels_rgb = pixels_rgb[::step]
    lab = _to_lab(pixels_rgb.reshape(-1, 1, 3).astype(np.uint8)).reshape(-1, 3).astype(np.float64)

    centers, labels = _kmeans_lab(lab, k)
    clusters = []
    for i in range(len(centers)):
        sel = labels == i
        if sel.any():
            clusters.append({"rgb": pixels_rgb[sel].mean(axis=0), "lab": centers[i], "n": int(sel.sum())})
    clusters.sort(key=lambda c: -c["n"])
    merged: List[dict] = []
    for c in clusters:  # merge perceptually near-identical clusters (shading of one color)
        for m in merged:
            if delta_e(tuple(m["lab"]), tuple(c["lab"])) < merge_delta_e:
                tot = m["n"] + c["n"]
                m["rgb"] = (m["rgb"] * m["n"] + c["rgb"] * c["n"]) / tot
                m["n"] = tot
                break
        else:
            merged.append(dict(c))
    merged.sort(key=lambda c: -c["n"])
    total = sum(c["n"] for c in merged)
    palette = []
    for c in merged:
        hx = rgb_to_hex(c["rgb"])
        info = classify(hx)
        palette.append(ColorShare(hx, info.family, round(c["n"] / total, 4), info.is_neutral))

    primary = palette[0]
    secondary = next((p for p in palette[1:] if p.share >= min_secondary_share), None)
    base = {"alpha_mask": 0.9, "background_removal": 0.8, "center_crop": 0.4}[method]
    confidence = round(max(0.05, min(0.99, base * (0.5 + 0.5 * primary.share))), 3)
    return ImageColorResult(
        primary_hex=primary.hex, secondary_hex=secondary.hex if secondary else None,
        primary_family=primary.family, secondary_family=secondary.family if secondary else None,
        is_neutral=primary.is_neutral, palette=palette, confidence=confidence,
        method=method, foreground_coverage=round(float(mask.mean()), 4),
    )
