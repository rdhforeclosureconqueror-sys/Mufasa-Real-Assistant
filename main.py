import os, io, json, time, statistics
from typing import List, Dict, Any, Optional
from datetime import date, timedelta

import httpx
from fastapi import FastAPI, HTTPException, UploadFile, File, Form, Request
from fastapi.responses import StreamingResponse, JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from dotenv import load_dotenv
from openai import OpenAI

load_dotenv()

DATA_DIR = os.getenv("DATA_DIR", "/data")
STT_URL = os.getenv("STT_URL", "http://localhost:8765")
TTS_URL = os.getenv("TTS_URL", "http://localhost:8766")

OPENAI_MODEL = os.getenv("OPENAI_MODEL", "gpt-4.1-mini")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
openai_client: Optional[OpenAI] = OpenAI(api_key=OPENAI_API_KEY) if OPENAI_API_KEY else None

STORYBOARD_DIR = os.path.join(DATA_DIR, "storyboards")
os.makedirs(STORYBOARD_DIR, exist_ok=True)

def write_json(path: str, obj: Any):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(obj, f, indent=2, ensure_ascii=False)

def read_json(path: str) -> Any:
    with open(path, encoding="utf-8") as f:
        return json.load(f)

def save_storyboard(data: Dict[str, Any]) -> str:
    ts = int(time.time())
    sid = data.get("id") or f"sb_{ts}"
    data["id"] = sid
    data["created_at"] = ts
    write_json(os.path.join(STORYBOARD_DIR, f"{sid}.json"), data)
    return sid

def load_storyboard(sb_id: str) -> Dict[str, Any]:
    path = os.path.join(STORYBOARD_DIR, f"{sb_id}.json")
    if not os.path.exists(path):
        raise HTTPException(status_code=404, detail="Storyboard not found")
    return read_json(path)

# ─────────────────────────────────────────────────────────────

class AskPayload(BaseModel):
    question: str
    user_id: Optional[str] = None
    session_id: Optional[str] = None
    context: Optional[str] = None
    telemetry: Optional[Dict[str, Any]] = None
    mode: Optional[str] = "chat"

class StoryboardReq(BaseModel):
    text: str
    user_id: Optional[str] = None
    max_slides: int = 8

# ─────────────────────────────────────────────────────────────

app = FastAPI(title="Mufasa Real Assistant API", version="2.2.1")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/")
def root():
    return {
        "ok": True,
        "service": "Mufasa-Real-Assistant-API",
        "hint": "POST /ask, POST /storyboard/generate, GET /storyboard/get?storyboard_id=..."
    }

@app.get("/health")
def health():
    return {
        "ok": True,
        "tts_url": TTS_URL,
        "stt_url": STT_URL,
        "has_openai": bool(openai_client),
        "openai_model": OPENAI_MODEL,
    }

# ─────────────────────────────────────────────────────────────
# Voice passthrough
# ─────────────────────────────────────────────────────────────

@app.post("/voice/stt")
async def voice_stt(file: UploadFile = File(...)):
    async with httpx.AsyncClient(timeout=120) as client:
        files = {"file": (file.filename, await file.read(), file.content_type or "application/octet-stream")}
        r = await client.post(f"{STT_URL}/stt", files=files)
        if r.status_code != 200:
            raise HTTPException(status_code=r.status_code, detail=r.text)
        return JSONResponse(r.json())

@app.post("/voice/tts")
async def voice_tts(text: str = Form(...)):
    async with httpx.AsyncClient(timeout=120) as client:
        r = await client.post(f"{TTS_URL}/tts", data={"text": text})
        if r.status_code != 200:
            raise HTTPException(status_code=r.status_code, detail=r.text)
        return StreamingResponse(io.BytesIO(r.content), media_type="audio/wav")

# ─────────────────────────────────────────────────────────────
# ASK (simple)
# ─────────────────────────────────────────────────────────────

@app.post("/ask")
async def ask(payload: AskPayload):
    if openai_client is None:
        raise HTTPException(status_code=503, detail="Missing OPENAI_API_KEY on API service")

    system_prompt = (
        "You are Mufasa, a Pan-African history assistant.\n"
        "Be structured, clear, and concise.\n"
    )

    resp = openai_client.chat.completions.create(
        model=OPENAI_MODEL,
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": payload.question},
        ],
        temperature=0.6,
    )
    answer = resp.choices[0].message.content
    return {"ok": True, "answer": answer, "ts": int(time.time())}

# ─────────────────────────────────────────────────────────────
# STORYBOARD / SLIDESHOW
# ─────────────────────────────────────────────────────────────

@app.post("/storyboard/generate")
async def storyboard_generate(req: StoryboardReq):
    if openai_client is None:
        raise HTTPException(status_code=503, detail="Missing OPENAI_API_KEY on API service")

    max_slides = max(4, min(int(req.max_slides or 8), 12))

    system_prompt = (
        "You are a slideshow director.\n"
        "Return ONLY valid JSON.\n"
        "Create a micro-lesson deck.\n"
        "JSON shape:\n"
        "{\n"
        '  "title": string,\n'
        '  "slides": [{"title": string, "bullets": [string], "narration": string}]\n'
        "}\n"
    )

    user_prompt = (
        f"Create a {max_slides}-slide deck from this text.\n\n"
        f"TEXT:\n{req.text}\n"
    )

    resp = openai_client.chat.completions.create(
        model=OPENAI_MODEL,
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
        temperature=0.5,
    )
    raw = resp.choices[0].message.content

    try:
        deck = json.loads(raw)
    except Exception:
        deck = {
            "title": "Deck (unparsed)",
            "slides": [
                {"title": "Error", "bullets": ["Model returned non-JSON"], "narration": raw}
            ]
        }

    data = {
        "storyboard": deck,
        "user_id": req.user_id or "public",
        "source_text_preview": (req.text or "")[:4000],
    }
    sid = save_storyboard(data)

    # IMPORTANT: frontend expects ok + data + storyboard nested
    return {"ok": True, "data": {"id": sid, "storyboard": deck}}

@app.get("/storyboard/get")
def storyboard_get(storyboard_id: Optional[str] = None, id: Optional[str] = None):
    sbid = storyboard_id or id
    if not sbid:
        raise HTTPException(status_code=400, detail="Missing storyboard_id")
    obj = load_storyboard(sbid)
    return {"ok": True, "data": {"id": obj["id"], "storyboard": obj["storyboard"]}}
