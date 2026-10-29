import json
import subprocess
import sys
from pathlib import Path

import numpy as np
from PIL import Image

ROOT = Path(__file__).resolve().parents[1]


def run(args, stdin=""):
    p = subprocess.run([sys.executable, "-m", "dolaby_engine", *args], input=stdin, capture_output=True,
                       text=True, cwd=ROOT)
    return p.returncode, json.loads(p.stdout)


def test_generate_roundtrip():
    payload = {"wardrobe": [
        {"id": 1, "category": "t-shirts", "hex_color": "#FFFFFF", "style": "casual", "season": "all"},
        {"id": 2, "category": "jeans", "hex_color": "#2B3F66", "style": "casual", "season": "all"},
        {"id": 3, "category": "sneakers", "hex_color": "#FFFFFF", "style": "casual", "season": "all"}],
        "request": {"occasion": "casual"}}
    code, out = run(["generate"], json.dumps(payload))
    assert code == 0 and len(out["outfits"]) == 1 and "rules-based" in out["method"]


def test_invalid_input_returns_error_json():
    code, out = run(["generate"], json.dumps({"wardrobe": [{"id": 1, "category": "jeans", "hex_color": "zzz"}]}))
    assert code == 2 and "error" in out


def test_analyze_command(tmp_path):
    img = np.full((100, 100, 3), 240, np.uint8)
    img[20:80, 20:80] = (30, 60, 160)
    path = tmp_path / "shirt.png"
    Image.fromarray(img).save(path)
    code, out = run(["analyze", "--image", str(path)])
    assert code == 0 and out["primary_family"] == "blue" and out["limitations"]
