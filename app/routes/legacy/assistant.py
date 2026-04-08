import io
import json
import os
import time
from pathlib import Path
from typing import Any, Dict, Optional

import httpx
from fastapi import APIRouter, File, Form, HTTPException, UploadFile
from fastapi.responses import JSONResponse, StreamingResponse
from openai import OpenAI
from pydantic import BaseModel

from app.core.config import get_settings

settings = get_settings()
router = APIRouter(prefix="/legacy", tags=["legacy-assistant"])

BASE_DIR = Path(__file__).resolve().parents[3]
DATA_DIR = os.getenv("DATA_DIR", "/data")
STORYBOARD_DIR = os.path.join(DATA_DIR, "storyboards")
KNOWLEDGE_DIR = os.path.join(DATA_DIR, "knowledge")
os.makedirs(STORYBOARD_DIR, exist_ok=True)
os.makedirs(KNOWLEDGE_DIR, exist_ok=True)

openai_client: Optional[OpenAI] = OpenAI(api_key=settings.openai_api_key) if settings.openai_api_key else None


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


@router.post("/ask")
async def ask(payload: AskPayload):
    q = (payload.question or "").strip()
    if not q:
        raise HTTPException(status_code=400, detail="Missing question")
    if openai_client is None:
        raise HTTPException(status_code=503, detail="OPENAI_API_KEY not set")

    resp = openai_client.chat.completions.create(
        model=settings.openai_model,
        messages=[
            {"role": "system", "content": "Legacy assistant mode."},
            {"role": "user", "content": q},
        ],
        temperature=0.6,
    )
    answer = resp.choices[0].message.content or ""
    rec = {"ts": int(time.time()), "user_id": payload.user_id or "public", "question": q, "answer": answer}
    _log_qa(rec)
    return rec


@router.post("/api/chat")
async def chat(payload: AskPayload):
    return await ask(payload)


@router.post("/voice/tts")
async def voice_tts(text: str = Form(...)):
    if not settings.tts_url:
        raise HTTPException(status_code=503, detail="No TTS configured")
    async with httpx.AsyncClient(timeout=120) as client:
        r = await client.post(f"{settings.tts_url.rstrip('/')}/tts", data={"text": text})
        if r.status_code != 200:
            raise HTTPException(status_code=r.status_code, detail=r.text)
        return StreamingResponse(io.BytesIO(r.content), media_type="audio/wav")


@router.post("/voice/stt")
async def voice_stt(file: UploadFile = File(...)):
    if not settings.stt_url:
        raise HTTPException(status_code=503, detail="No STT configured")
    async with httpx.AsyncClient(timeout=120) as client:
        files = {"file": (file.filename, await file.read(), file.content_type or "application/octet-stream")}
        r = await client.post(f"{settings.stt_url.rstrip('/')}/stt", files=files)
        if r.status_code != 200:
            raise HTTPException(status_code=r.status_code, detail=r.text)
        return JSONResponse(r.json())


@router.post("/storyboard/generate")
async def storyboard_generate(req: StoryboardReq):
    if openai_client is None:
        raise HTTPException(status_code=503, detail="OPENAI_API_KEY not set")
    resp = openai_client.chat.completions.create(
        model=settings.openai_model,
        messages=[{"role": "user", "content": req.question}],
        temperature=0.5,
    )
    deck = {"deck_title": "Legacy", "slides": [{"title": "Slide", "bullets": [resp.choices[0].message.content or ""]}]}
    sb_id = f"sb_{int(time.time())}"
    story = {"id": sb_id, "created_at": int(time.time()), "user_id": req.user_id or "public", "deck": deck}
    _write_json(_sb_path(sb_id), story)
    return {"ok": True, "id": sb_id, "storyboard": story}


@router.get("/storyboard/get")
def storyboard_get(id: str):
    p = _sb_path(id)
    if not os.path.exists(p):
        raise HTTPException(status_code=404, detail="Storyboard not found")
    return {"ok": True, "storyboard": _read_json(p)}
