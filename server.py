"""
🦁 Mufasa Real Assistant API — Unified Server
----------------------------------------------
This FastAPI app powers:
✅ AI Chat (Mufasa Brain)
✅ Swahili & Yoruba Learning APIs
✅ Web Frontend (index.html + assets)
✅ Browser-based TTS/STT passthrough (optional)
"""

import json
import os
from datetime import date
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.responses import FileResponse, JSONResponse
from fastapi.middleware.cors import CORSMiddleware
import openai

# ============================================
# 🔧 CONFIGURATION
# ============================================

app = FastAPI(title="Mufasa Real Assistant", version="2.0")

# Allow all origins for now (you can restrict later)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

BASE_DIR = Path(__file__).resolve().parent
RESOURCES = BASE_DIR / "resources"
ASSETS = BASE_DIR / "assets"

# Files for language lessons
DATA_SWAHILI = RESOURCES / "swahili_30days.json"
DATA_YORUBA = RESOURCES / "yoruba_30days.json"

# Connect OpenAI (Mufasa brain)
openai.api_key = os.getenv("OPENAI_API_KEY")

# ============================================
# 🌍 FRONTEND ROUTES
# ============================================

@app.get("/")
def home():
    """Serve the main Mufasa portal."""
    index_path = BASE_DIR / "index.html"
    if index_path.exists():
        return FileResponse(index_path)
    return JSONResponse({"error": "index.html not found"}, status_code=404)

@app.get("/swahili")
def swahili_page():
    """Serve Swahili learning page."""
    page = BASE_DIR / "swahili.html"
    if page.exists():
        return FileResponse(page)
    return JSONResponse({"error": "swahili.html not found"}, status_code=404)

@app.get("/yoruba")
def yoruba_page():
    """Serve Yoruba learning page."""
    page = BASE_DIR / "yoruba.html"
    if page.exists():
        return FileResponse(page)
    return JSONResponse({"error": "yoruba.html not found"}, status_code=404)

# ============================================
# 📘 DAILY LESSON ROUTES
# ============================================

@app.get("/api/swahili/today")
def swahili_today():
    """Return today's Swahili lesson (rotating 30-day)."""
    if not DATA_SWAHILI.exists():
        return JSONResponse({"error": "Missing resources/swahili_30days.json"}, status_code=404)

    lessons = json.loads(DATA_SWAHILI.read_text(encoding="utf-8"))
    idx = (date.today().timetuple().tm_yday - 1) % len(lessons)
    return lessons[idx]

@app.get("/api/yoruba/today")
def yoruba_today():
    """Return today's Yoruba lesson (rotating 30-day)."""
    if not DATA_YORUBA.exists():
        return JSONResponse({"error": "Missing resources/yoruba_30days.json"}, status_code=404)

    lessons = json.loads(DATA_YORUBA.read_text(encoding="utf-8"))
    idx = (date.today().timetuple().tm_yday - 1) % len(lessons)
    return lessons[idx]

# ============================================
# 🤖 MUFASA CHAT ENDPOINT
# ============================================

@app.post("/api/chat")
async def chat(request: Request):
    """
    Accepts a JSON body:
      { "message": "your question here" }

    Returns:
      { "reply": "Mufasa's response" }
    """
    data = await request.json()
    user_message = data.get("message", "").strip()

    if not user_message:
        return {"reply": "I didn’t catch that, young one. Speak again with clarity."}

    try:
        completion = openai.ChatCompletion.create(
            model="gpt-4o-mini",
            messages=[
                {
                    "role": "system",
                    "content": (
                        "You are Mufasa — a Pan-African teacher, "
                        "guiding with wisdom, love, and strength. "
                        "Speak clearly and motivate learning. "
                        "If the user asks about culture or languages, "
                        "answer in an inspiring but factual tone."
                    ),
                },
                {"role": "user", "content": user_message},
            ],
            max_tokens=300,
            temperature=0.7,
        )

        reply = completion["choices"][0]["message"]["content"].strip()
        return {"reply": reply}

    except Exception as e:
        print("⚠️ OpenAI Error:", e)
        return {"reply": "Mufasa is silent for a moment — connection issue. Try again soon."}

# ============================================
# 🔊 BROWSER TTS/STT PLACEHOLDERS
# ============================================

@app.post("/api/voice/tts")
async def tts_placeholder():
    """
    Placeholder route — TTS happens client-side in browser.
    This endpoint only exists for compatibility; returns 503.
    """
    return JSONResponse(
        {"error": "TTS handled in browser using Web Speech API. No server TTS active."},
        status_code=503,
    )

@app.post("/api/voice/stt")
async def stt_placeholder():
    """
    Placeholder route — STT happens client-side in browser.
    This endpoint only exists for compatibility; returns 503.
    """
    return JSONResponse(
        {"error": "STT handled in browser using Web Speech API. No server STT active."},
        status_code=503,
    )

# ============================================
# 🖼️ ASSETS (video, css, js, etc.)
# ============================================

@app.get("/assets/{filename}")
def get_asset(filename: str):
    """Serve static assets like fire-lion.mp4."""
    path = ASSETS / filename
    if path.exists():
        return FileResponse(path)
    return JSONResponse({"error": "Asset not found"}, status_code=404)

@app.get("/{filename}")
def get_static(filename: str):
    """Serve CSS/JS files from root directory."""
    path = BASE_DIR / filename
    if path.exists():
        return FileResponse(path)
    return JSONResponse({"error": f"{filename} not found"}, status_code=404)

# ============================================
# 🚀 RUN LOCALLY
# ============================================

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=5000)
