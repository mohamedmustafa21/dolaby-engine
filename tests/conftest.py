import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import pytest

from dolaby_engine.schemas import Garment


def g(id, category, hex_color, **kw):
    return Garment.from_dict({"id": id, "category": category, "hex_color": hex_color, **kw})


@pytest.fixture
def wardrobe():
    return [
        g(1, "t-shirts", "#FFFFFF"), g(2, "shirts", "#9CC3E6", style="smart_casual"),
        g(3, "t-shirts", "#1F3A5F", style="casual"), g(4, "shirts", "#F5F5DC", style="smart_casual"),
        g(10, "jeans", "#2B3F66"), g(11, "trousers", "#C8B79A", style="smart_casual"),
        g(12, "trousers", "#222222", style="smart_casual"), g(13, "shorts", "#C8B79A", season="summer"),
        g(20, "sneakers", "#FFFFFF"), g(21, "shoes", "#3B2A20", style="smart_casual"),
        g(22, "boots", "#222222", season="winter", style="casual"),
        g(30, "jackets", "#222222", season="autumn", style="smart_casual"),
        g(31, "coats", "#7A5C3E", season="winter", style="smart_casual"),
        g(40, "bags", "#7A5C3E", style="casual"),
    ]
