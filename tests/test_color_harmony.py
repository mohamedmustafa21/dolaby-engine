from dolaby_engine.color_harmony import HarmonyConfig, score_palette


def test_all_neutral_scores_well():
    r = score_palette(["#FFFFFF", "#222222", "#808080"])
    assert r.label == "neutral" and r.score >= 0.8


def test_neutral_with_single_accent_is_best_tier():
    r = score_palette(["#FFFFFF", "#D62828"])
    assert r.label == "neutral + accent" and r.score >= 0.9


def test_monochromatic():
    r = score_palette(["#1E6FD9", "#8DB8F0"])
    assert r.label == "monochromatic"


def test_analogous():
    assert score_palette(["#D62828", "#F2A900"]).label in ("analogous", "clashing hues")  # red-orange-ish
    assert score_palette(["#2E8B57", "#2A9DB5"]).label == "analogous"


def test_complementary():
    r = score_palette(["#2060C0", "#E08A10"])
    assert r.label == "complementary"


def test_triadic():
    r = score_palette(["#D62828", "#28A828", "#2828D6"])
    assert r.label == "triadic"


def test_clashing_hues_score_low():
    r = score_palette(["#D62828", "#7B3FA0"])  # red + purple, ~60 deg apart? not analogous
    assert r.score < 0.6


def test_too_many_accent_hues():
    r = score_palette(["#D62828", "#28A828", "#F2C500", "#7B3FA0"])
    assert r.label == "too many accents" and r.score <= 0.3


def test_pair_cap_red_and_pink_is_discouraged():
    assert score_palette(["#D62828", "#FFC0CB"]).score <= 0.45


def test_low_lightness_contrast_penalized():
    flat = score_palette(["#7A7A7A", "#808080"]).score
    contrast = score_palette(["#FFFFFF", "#222222"]).score
    assert contrast > flat


def test_score_bounds_and_empty():
    assert score_palette([]).score == 0.0
    for pal in (["#000000"], ["#D62828", "#28A828", "#2828D6", "#F2C500"]):
        assert 0.0 <= score_palette(pal).score <= 1.0


def test_config_is_respected():
    cfg = HarmonyConfig(score_neutral_only=0.5)
    assert score_palette(["#FFFFFF", "#222222"], cfg).score < score_palette(["#FFFFFF", "#222222"]).score


def test_config_from_dict_rejects_unknown_option():
    import pytest
    with pytest.raises(ValueError):
        HarmonyConfig.from_dict({"nonsense": 1})


def test_explanation_present():
    assert len(score_palette(["#FFFFFF", "#D62828"]).explanation) > 10
