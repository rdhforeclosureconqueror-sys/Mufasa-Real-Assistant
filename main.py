import os
import io
import json
import time
from typing import Any, Dict, Optional, List

import httpx
from fastapi import FastAPI, HTTPException, UploadFile, File, Form, Request
from fastapi.responses import JSONResponse, StreamingResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from dotenv import load_dotenv

# OpenAI (new SDK)
from openai import OpenAI

# ─────────────────────────────────────────────────────────────
# Env + Paths
# ─────────────────────────────────────────────────────────────
load_dotenv()

DATA_DIR = os.getenv("DATA_DIR", "/data")
STORYBOARD_DIR = os.path.join(DATA_DIR, "storyboards")
KNOWLEDGE_DIR = os.path.join(DATA_DIR, "knowledge")

os.makedirs(STORYBOARD_DIR, exist_ok=True)
os.makedirs(KNOWLEDGE_DIR, exist_ok=True)

# Optional sidecar URLs (only used if you run them)
STT_URL = os.getenv("STT_URL", "").strip()  # e.g. https://your-stt.onrender.com
TTS_URL = os.getenv("TTS_URL", "").strip()  # e.g. https://your-tts.onrender.com

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "").strip()
OPENAI_MODEL = os.getenv("OPENAI_MODEL", "gpt-4.1-mini").strip()

openai_client: Optional[OpenAI] = OpenAI(api_key=OPENAI_API_KEY) if OPENAI_API_KEY else None


# ─────────────────────────────────────────────────────────────
# App
# ─────────────────────────────────────────────────────────────
app = FastAPI(title="Mufasa Real Assistant API", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # you can tighten later
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/")
def root():
    return {
        "ok": True,
        "service": "Mufasa-Real-Assistant-API",
        "hint": "Try /health or POST /ask",
    }


@app.get("/health")
def health():
    return {
        "ok": True,
        "has_openai": bool(openai_client),
        "openai_model": OPENAI_MODEL,
        "data_dir": DATA_DIR,
        "storyboard_dir": STORYBOARD_DIR,
        "tts_passthrough": bool(TTS_URL),
        "stt_passthrough": bool(STT_URL),
    }


# ─────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────
def _write_json(path: str, obj: Any) -> None:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(obj, f, ensure_ascii=False, indent=2)


def _read_json(path: str) -> Any:
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def _sb_path(sb_id: str) -> str:
    return os.path.join(STORYBOARD_DIR, f"{sb_id}.json")


def _log_qa(record: Dict[str, Any]) -> None:
    ts = int(time.time())
    _write_json(os.path.join(KNOWLEDGE_DIR, f"qa_{ts}.json"), record)


# ─────────────────────────────────────────────────────────────
# Models
# ─────────────────────────────────────────────────────────────
class AskPayload(BaseModel):
    question: str
    user_id: Optional[str] = None
    session_id: Optional[str] = None
    mode: Optional[str] = "chat"
    context: Optional[Dict[str, Any]] = None


class StoryboardReq(BaseModel):
    question: str
    user_id: Optional[str] = None
    max_slides: int = 8


# ─────────────────────────────────────────────────────────────
# ASK
# ─────────────────────────────────────────────────────────────
@app.post("/ask")
async def ask(payload: AskPayload):
    q = (payload.question or "").strip()
    if not q:
        raise HTTPException(status_code=400, detail="Missing question")

    if openai_client is None:
        raise HTTPException(status_code=503, detail="OPENAI_API_KEY not set")

    user_id = payload.user_id or "public"
    system_prompt = (
        "You are Mufasa Real Assistant — a Pan-African cultural educator.\n"
        "Be accurate, clear, and structured.\n"
        "If the user asks for a lesson: use a short outline.\n"
        "Do not invent sources; if unsure, say so.\n"
    )

    # Include lightweight context if provided
    ctx = payload.context or {}
    if ctx:
        system_prompt += "\nContext JSON:\n" + json.dumps(ctx, ensure_ascii=False)

    try:
        resp = openai_client.chat.completions.create(
            model=OPENAI_MODEL,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": q},
            ],
            temperature=0.6,
        )
        answer = resp.choices[0].message.content or ""
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"OpenAI error: {str(e)}")

    rec = {
        "ts": int(time.time()),
        "user_id": user_id,
        "session_id": payload.session_id,
        "mode": payload.mode,
        "question": q,
        "answer": answer,
    }
    _log_qa(rec)
    return rec


# ─────────────────────────────────────────────────────────────
# TTS / STT
# ─────────────────────────────────────────────────────────────
@app.post("/voice/tts")
async def voice_tts(text: str = Form(...)):
    text = (text or "").strip()
    if not text:
        raise HTTPException(status_code=400, detail="Missing text")

    # Option A: passthrough to your own TTS service (recommended if you have it)
    if TTS_URL:
        async with httpx.AsyncClient(timeout=120) as client:
            r = await client.post(f"{TTS_URL.rstrip('/')}/tts", data={"text": text})
            if r.status_code != 200:
                raise HTTPException(status_code=r.status_code, detail=r.text)
            return StreamingResponse(io.BytesIO(r.content), media_type="audio/wav")

    # Option B: fallback “no TTS configured”
    raise HTTPException(
        status_code=503,
        detail="No TTS configured. Set TTS_URL to a service that exposes POST /tts returning audio/wav.",
    )


@app.post("/voice/stt")
async def voice_stt(file: UploadFile = File(...)):
    if not STT_URL:
        raise HTTPException(
            status_code=503,
            detail="No STT configured. Set STT_URL to a service that exposes POST /stt.",
        )

    async with httpx.AsyncClient(timeout=120) as client:
        files = {
            "file": (file.filename, await file.read(), file.content_type or "application/octet-stream")
        }
        r = await client.post(f"{STT_URL.rstrip('/')}/stt", files=files)
        if r.status_code != 200:
            raise HTTPException(status_code=r.status_code, detail=r.text)
        return JSONResponse(r.json())


# ─────────────────────────────────────────────────────────────
# STORYBOARD (for slideshow.html)
# ─────────────────────────────────────────────────────────────
@app.post("/storyboard/generate")
async def storyboard_generate(req: StoryboardReq):
    if openai_client is None:
        raise HTTPException(status_code=503, detail="OPENAI_API_KEY not set")

    user_id = req.user_id or "public"
    max_slides = max(3, min(int(req.max_slides or 8), 12))
    prompt = (req.question or "").strip()
    if not prompt:
        raise HTTPException(status_code=400, detail="Missing question")

    system_prompt = (
        "You are Mufasa's Slideshow Director.\n"
        "Return ONLY valid JSON.\n"
        "Create a micro-lesson deck.\n"
        "JSON shape:\n"
        "{\n"
        '  "deck_title": string,\n'
        '  "topic": string,\n'
        '  "audience": "general",\n'
        '  "slides": [\n'
        '     {"title": string, "bullets": [string], "narration": string}\n'
        "  ]\n"
        "}\n"
        f"Max slides: {max_slides}\n"
        "No markdown.\n"
    )

    try:
        resp = openai_client.chat.completions.create(
            model=OPENAI_MODEL,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": prompt},
            ],
            temperature=0.5,
        )
        raw = resp.choices[0].message.content or ""
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"OpenAI error: {str(e)}")

    try:
        deck = json.loads(raw)
    except Exception:
        deck = {
            "deck_title": "Slideshow (unparsed)",
            "topic": prompt[:80],
            "audience": "general",
            "slides": [
                {
                    "title": "Error",
                    "bullets": ["Model returned non-JSON output."],
                    "narration": raw[:1500],
                }
            ],
        }

    sb_id = f"sb_{int(time.time())}"
    story = {
        "id": sb_id,
        "created_at": int(time.time()),
        "user_id": user_id,
        "question": prompt,
        "deck": deck,
    }

    _write_json(_sb_path(sb_id), story)
    return {"ok": True, "id": sb_id, "storyboard": story}


@app.get("/storyboard/get")
def storyboard_get(id: str):
    if not id:
        raise HTTPException(status_code=400, detail="Missing id")

    p = _sb_path(id)
    if not os.path.exists(p):
        raise HTTPException(status_code=404, detail="Storyboard not found")

    story = _read_json(p)
    return {"ok": True, "storyboard": story}
