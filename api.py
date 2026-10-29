"""Tiny HTTP wrapper around dolaby_engine (same contract as the dev bridge in vite.config.ts).

Run:  uvicorn api:app --host 0.0.0.0 --port 8000
Env:  ALLOWED_ORIGINS=https://yourdomain.com,https://www.yourdomain.com  (comma separated, default "*")
"""
import base64
import os
import re
import tempfile

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from dolaby_engine.color_analysis import extract_dominant_colors
from dolaby_engine.config import EngineConfig
from dolaby_engine.outfit_generator import generate_outfits
from dolaby_engine.schemas import Garment, OutfitRequest, ValidationError

origins = [o.strip() for o in os.getenv("ALLOWED_ORIGINS", "*").split(",") if o.strip()]
app = FastAPI(title="Dolaby engine")
app.add_middleware(CORSMiddleware, allow_origins=origins, allow_methods=["POST", "GET"], allow_headers=["*"])


def err(msg: str, status: int = 422):
    return JSONResponse({"error": msg}, status_code=status)


@app.get("/")
def health():
    return {"ok": True}


@app.post("/generate")
async def generate(req: Request):
    try:
        p = await req.json()
        wardrobe = [Garment.from_dict(g) for g in p.get("wardrobe", [])]
        request = OutfitRequest.from_dict(p.get("request"))
        config = EngineConfig.from_dict(p.get("config"))
        return generate_outfits(wardrobe, request, config).to_dict()
    except (ValidationError, ValueError, OSError) as e:
        return err(str(e))


@app.post("/analyze")
async def analyze(req: Request):
    try:
        p = await req.json()
        m = re.match(r"^data:image/(png|jpeg|webp);base64,([A-Za-z0-9+/=]+)$", p.get("image", ""))
        if not m:
            return err("Unsupported image data.")
        ext = "jpg" if m.group(1) == "jpeg" else m.group(1)
        with tempfile.TemporaryDirectory() as d:
            path = os.path.join(d, f"upload.{ext}")
            with open(path, "wb") as f:
                f.write(base64.b64decode(m.group(2)))
            return extract_dominant_colors(path).to_dict()
    except (ValidationError, ValueError, OSError) as e:
        return err(str(e))
