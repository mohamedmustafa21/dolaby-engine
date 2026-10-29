import numpy as np
import pytest
from PIL import Image

from dolaby_engine.color_analysis import extract_dominant_colors
from dolaby_engine.color_utils import classify, normalize_hex, rgb_to_lab


def shirt_on_background(bg=(240, 240, 240), fg=(200, 30, 40), size=120):
    img = np.zeros((size, size, 3), np.uint8)
    img[:] = bg
    img[25:100, 30:90] = fg
    return img


def test_normalize_hex():
    assert normalize_hex("#abc") == "#AABBCC"
    assert normalize_hex("ff0000") == "#FF0000"
    with pytest.raises(ValueError):
        normalize_hex("not-a-color")


@pytest.mark.parametrize("hex_color,family", [
    ("#000000", "black"), ("#FFFFFF", "white"), ("#808080", "gray"), ("#F5F5DC", "beige"),
    ("#5C3A21", "brown"), ("#1F2A44", "navy"), ("#D62828", "red"), ("#2E8B57", "green"),
    ("#4A90D9", "blue"), ("#FFC0CB", "pink"), ("#F2C500", "yellow"), ("#7B3FA0", "purple"),
])
def test_color_family_mapping(hex_color, family):
    assert classify(hex_color).family == family


def test_neutral_flags():
    assert classify("#222222").is_neutral and classify("#F5F5DC").is_neutral
    assert not classify("#D62828").is_neutral


def test_lab_of_white_and_black():
    assert rgb_to_lab((255, 255, 255))[0] == pytest.approx(100, abs=0.5)
    assert rgb_to_lab((0, 0, 0))[0] == pytest.approx(0, abs=0.5)


def test_background_is_not_reported_as_garment_color():
    res = extract_dominant_colors(shirt_on_background())
    assert res.method == "background_removal"
    assert res.primary_family == "red"
    assert res.confidence > 0.6


def test_dark_garment_on_white_background():
    res = extract_dominant_colors(shirt_on_background(fg=(25, 40, 80)))
    assert res.primary_family == "navy"


def test_two_tone_garment_reports_secondary():
    img = shirt_on_background()
    img[25:60, 30:90] = (240, 200, 0)
    res = extract_dominant_colors(img)
    assert {res.primary_family, res.secondary_family} == {"yellow", "red"}


def test_transparent_png_uses_alpha(tmp_path):
    rgba = np.zeros((100, 100, 4), np.uint8)
    rgba[20:80, 20:80] = (30, 120, 60, 255)
    path = tmp_path / "cutout.png"
    Image.fromarray(rgba, "RGBA").save(path)
    res = extract_dominant_colors(str(path))
    assert res.method == "alpha_mask" and res.primary_family == "green"


def test_busy_background_falls_back_with_low_confidence():
    rng = np.random.default_rng(0)
    noisy = rng.integers(0, 255, (120, 120, 3), dtype=np.uint8)
    res = extract_dominant_colors(noisy)
    assert res.method == "center_crop"
    assert res.confidence < 0.45


def test_analysis_is_deterministic():
    a = extract_dominant_colors(shirt_on_background()).to_dict()
    b = extract_dominant_colors(shirt_on_background()).to_dict()
    assert a == b


def test_result_documents_limitations():
    assert extract_dominant_colors(shirt_on_background()).to_dict()["limitations"]
