import pytest

from conftest import g
from dolaby_engine.compatibility import (item_rejection, occasion_fit, role_of, season_fit,
                                         style_score, validate_outfit)
from dolaby_engine.config import EngineConfig
from dolaby_engine.schemas import OutfitRequest, ValidationError

CFG = EngineConfig()


def test_category_roles():
    assert role_of(g(1, "t-shirts", "#FFF")) == "top"
    assert role_of(g(2, "dresses", "#FFF")) == "one_piece"
    assert role_of(g(3, "coats", "#FFF")) == "outerwear"
    assert role_of(g(4, "bags", "#FFF")) == "accessory"
    assert role_of(g(5, "hats", "#FFF")) is None


def test_valid_basic_outfit():
    items = [g(1, "t-shirts", "#FFF"), g(2, "jeans", "#2B3F66"), g(3, "sneakers", "#FFF")]
    assert validate_outfit(items, CFG) == []


def test_missing_bottom_is_invalid():
    assert validate_outfit([g(1, "t-shirts", "#FFF"), g(3, "sneakers", "#FFF")], CFG)


def test_dress_with_separate_top_is_invalid():
    items = [g(1, "dresses", "#112233"), g(2, "shirts", "#FFF"), g(3, "shoes", "#000")]
    assert any("dress" in r for r in validate_outfit(items, CFG))


def test_dress_with_shoes_is_valid():
    assert validate_outfit([g(1, "dresses", "#112233", style="smart_casual"), g(3, "shoes", "#000", style="smart_casual")], CFG) == []


def test_two_tops_is_invalid():
    items = [g(1, "t-shirts", "#FFF"), g(2, "shirts", "#FFF"), g(3, "jeans", "#2B3F66")]
    assert any("more than one top" in r for r in validate_outfit(items, CFG))


def test_shorts_with_coat_and_boots_rejected():
    base = [g(1, "t-shirts", "#FFF"), g(2, "shorts", "#C8B79A")]
    assert validate_outfit(base + [g(3, "coats", "#7A5C3E")], CFG)
    assert validate_outfit(base + [g(4, "boots", "#222")], CFG)


def test_formal_with_sporty_style_rejected():
    items = [g(1, "shirts", "#FFF", style="formal"), g(2, "trousers", "#222", style="formal"),
             g(3, "sneakers", "#FFF", style="sporty")]
    assert validate_outfit(items, CFG)


def test_formality_gap_rejected():
    items = [g(1, "t-shirts", "#FFF", formality_level=1), g(2, "trousers", "#222", formality_level=5)]
    assert any("formality" in r for r in validate_outfit(items, CFG))


def test_summer_item_rejected_in_winter_but_all_season_ok():
    req = OutfitRequest.from_dict({"season": "winter"})
    assert item_rejection(g(1, "shorts", "#FFF", season="summer"), req)
    assert item_rejection(g(2, "jeans", "#FFF", season="all"), req) is None


def test_season_fit_values():
    assert season_fit("summer", "summer") == 1.0
    assert season_fit("all", "winter") == 0.85
    assert season_fit("autumn", "winter") == 0.6
    assert season_fit("summer", "winter") is None
    assert season_fit("winter", None) == 1.0


def test_occasion_rejects_far_formality():
    assert occasion_fit(g(1, "t-shirts", "#FFF"), "formal") is None
    assert occasion_fit(g(2, "shoes", "#000", style="formal"), "formal") == pytest.approx(1.0)


def test_hot_conditions_skip_outerwear():
    req = OutfitRequest.from_dict({"conditions": ["hot"]})
    assert item_rejection(g(1, "jackets", "#222"), req)


def test_style_score_symmetric():
    assert style_score("casual", "formal") == style_score("formal", "casual")


def test_invalid_input_fails_loudly():
    with pytest.raises(ValidationError):
        g(1, "jeans", "#FFF", style="gothic")
    with pytest.raises(ValidationError):
        g(1, "jeans", "banana")
