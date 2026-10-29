import time

from conftest import g
from dolaby_engine.config import EngineConfig
from dolaby_engine.outfit_generator import generate_outfits
from dolaby_engine.schemas import OutfitRequest


def req(**kw):
    return OutfitRequest.from_dict(kw)


def test_empty_wardrobe_returns_no_outfits_and_a_warning():
    r = generate_outfits([], req())
    assert r.outfits == [] and r.warnings


def test_returns_three_outfits_when_wardrobe_allows(wardrobe):
    r = generate_outfits(wardrobe, req(occasion="casual"))
    assert len(r.outfits) == 3
    assert r.outfits[0].score >= r.outfits[1].score >= r.outfits[2].score


def test_only_owned_items_are_used(wardrobe):
    owned = {i.id for i in wardrobe}
    for o in generate_outfits(wardrobe, req()).outfits:
        assert {i.id for i in o.items} <= owned


def test_unavailable_and_excluded_items_never_appear(wardrobe):
    wardrobe = [g(i.id, i.category, i.primary_hex, style=i.style, season=i.season,
                  availability_status="laundry" if i.id == 10 else "available") for i in wardrobe]
    r = generate_outfits(wardrobe, req(excluded_item_ids=[20]))
    used = {x.id for o in r.outfits for x in o.items}
    assert 10 not in used and 20 not in used and r.outfits


def test_incomplete_wardrobe_only_tops(wardrobe):
    tops = [i for i in wardrobe if i.category in ("t-shirts", "shirts")]
    r = generate_outfits(tops, req())
    assert r.outfits == [] and any("no valid top" in w for w in r.warnings)


def test_no_footwear_relaxes_with_warning(wardrobe):
    clothes = [i for i in wardrobe if i.category in ("t-shirts", "jeans")]
    r = generate_outfits(clothes, req())
    assert r.outfits and any("footwear" in w for w in r.warnings)
    assert all(x.role != "footwear" for o in r.outfits for x in o.items)


def test_fewer_than_three_when_wardrobe_is_small():
    w = [g(1, "t-shirts", "#FFFFFF"), g(2, "jeans", "#2B3F66"), g(3, "sneakers", "#FFFFFF")]
    r = generate_outfits(w, req())
    assert len(r.outfits) == 1 and any("Only 1" in x for x in r.warnings)


def test_winter_request_excludes_summer_items_and_adds_outerwear(wardrobe):
    r = generate_outfits(wardrobe, req(season="winter", occasion="casual"))
    used = {x.id for o in r.outfits for x in o.items}
    assert 13 not in used  # summer shorts
    for o in r.outfits:
        assert any(x.role == "outerwear" for x in o.items)


def test_summer_request_has_no_outerwear(wardrobe):
    r = generate_outfits(wardrobe, req(season="summer"))
    assert r.outfits
    assert all(x.role != "outerwear" for o in r.outfits for x in o.items)


def test_dress_outfit_generated():
    w = [g(1, "dresses", "#1F3A5F", style="smart_casual"), g(2, "shoes", "#222222", style="smart_casual")]
    r = generate_outfits(w, req(occasion="work"))
    assert [i.role for i in r.outfits[0].items] == ["one_piece", "footwear"]


def test_near_duplicates_removed(wardrobe):
    r = generate_outfits(wardrobe, req())
    cores = [frozenset(x.id for x in o.items if x.role in ("top", "bottom", "one_piece")) for o in r.outfits]
    assert len(set(cores)) == len(cores)


def test_accessory_is_optional_and_single(wardrobe):
    for o in generate_outfits(wardrobe, req()).outfits:
        assert sum(x.role == "accessory" for x in o.items) <= 1


def test_every_outfit_is_explained(wardrobe):
    for o in generate_outfits(wardrobe, req()).outfits:
        assert "Color:" in o.explanation and 0 <= o.score <= 1


def test_large_wardrobe_stays_bounded():
    w, n = [], 1
    for cat, hx in [("t-shirts", "#FFFFFF"), ("jeans", "#2B3F66"), ("sneakers", "#FFFFFF"), ("jackets", "#222222")]:
        for k in range(40):
            w.append(g(n, cat, f"#{(k * 5) % 256:02X}{(k * 9) % 256:02X}{(k * 13) % 256:02X}", season="autumn"))
            n += 1
    t = time.time()
    r = generate_outfits(w, req(season="autumn"), EngineConfig(max_candidates=500))
    assert r.stats["candidates_evaluated"] <= 500
    assert time.time() - t < 10


def test_preferred_color_influences_ranking(wardrobe):
    plain = generate_outfits(wardrobe, req())
    blue = generate_outfits(wardrobe, req(preferred_colors=["blue"]))
    assert blue.outfits[0].components["preferences"] >= plain.outfits[0].components["preferences"]
