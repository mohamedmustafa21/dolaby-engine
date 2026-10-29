import json

import pytest

from conftest import g
from dolaby_engine.config import EngineConfig
from dolaby_engine.outfit_generator import generate_outfits
from dolaby_engine.ranking import is_near_duplicate, score_outfit
from dolaby_engine.schemas import OutfitRequest


def test_weights_are_normalized():
    cfg = EngineConfig(weights={"harmony": 7, "compatibility": 6, "occasion_season": 4, "preferences": 3})
    w = cfg.normalized_weights()
    assert sum(w.values()) == pytest.approx(1.0)
    assert w["harmony"] == pytest.approx(0.35)


def test_default_weights_match_spec():
    w = EngineConfig().normalized_weights()
    assert (w["harmony"], w["compatibility"], w["occasion_season"], w["preferences"]) == pytest.approx((0.35, 0.30, 0.20, 0.15))


def test_bad_config_rejected():
    with pytest.raises(ValueError):
        EngineConfig.from_dict({"weights": {"unknown": 1}})
    with pytest.raises(ValueError):
        EngineConfig.from_dict({"bogus": 1})


def test_ranking_is_deterministic_for_fixed_input(wardrobe):
    req = OutfitRequest.from_dict({"occasion": "casual", "season": "autumn"})
    runs = [json.dumps(generate_outfits(wardrobe, req).to_dict(), sort_keys=True) for _ in range(3)]
    assert len(set(runs)) == 1


def test_input_order_does_not_change_result(wardrobe):
    req = OutfitRequest.from_dict({})
    a = generate_outfits(wardrobe, req).to_dict()
    b = generate_outfits(list(reversed(wardrobe)), req).to_dict()
    assert a == b


def test_clashing_colors_score_lower_than_matching():
    req = OutfitRequest.from_dict({})
    cfg = EngineConfig()
    good = score_outfit([g(1, "t-shirts", "#FFFFFF"), g(2, "jeans", "#2B3F66"), g(3, "sneakers", "#FFFFFF")], req, cfg)
    bad = score_outfit([g(1, "t-shirts", "#D62828"), g(2, "jeans", "#28A828"), g(3, "sneakers", "#7B3FA0")], req, cfg)
    assert good.score > bad.score


def test_color_alone_does_not_decide_compatibility():
    req = OutfitRequest.from_dict({})
    cfg = EngineConfig()
    same = [g(1, "t-shirts", "#FFFFFF"), g(2, "jeans", "#2B3F66"), g(3, "sneakers", "#FFFFFF")]
    mixed = [g(1, "shirts", "#FFFFFF", style="formal"), g(2, "jeans", "#2B3F66", style="casual"),
             g(3, "sneakers", "#FFFFFF", style="casual")]
    assert score_outfit(same, req, cfg).components["compatibility"] > score_outfit(mixed, req, cfg).components["compatibility"]


def test_near_duplicate_detection():
    req, cfg = OutfitRequest.from_dict({}), EngineConfig()
    a = score_outfit([g(1, "t-shirts", "#FFF"), g(2, "jeans", "#2B3F66"), g(3, "sneakers", "#FFF")], req, cfg)
    b = score_outfit([g(1, "t-shirts", "#FFF"), g(2, "jeans", "#2B3F66"), g(4, "shoes", "#222", style="smart_casual")], req, cfg)
    c = score_outfit([g(5, "t-shirts", "#FFF"), g(6, "jeans", "#2B3F66"), g(3, "sneakers", "#FFF")], req, cfg)
    assert is_near_duplicate(a, b, cfg.dedupe_jaccard)      # same top+bottom
    assert not is_near_duplicate(a, c, cfg.dedupe_jaccard)  # different top+bottom


def test_changing_weights_changes_scores(wardrobe):
    req = OutfitRequest.from_dict({})
    a = generate_outfits(wardrobe, req).outfits[0].score
    b = generate_outfits(wardrobe, req, EngineConfig.from_dict({"weights": {"harmony": 1, "compatibility": 0, "occasion_season": 0, "preferences": 0}})).outfits[0].score
    assert a != b
