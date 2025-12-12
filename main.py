import os
import io
import json
import time
import uuid
import statistics
from typing import List, Dict, Any, Optional
from datetime import date, timedelta

import httpx
from fastapi import FastAPI, HTTPException, UploadFile, File, Form, Request
from fastapi.responses import StreamingResponse, JSONResponse, HTMLResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from dotenv import load_dotenv

from api.auth import mint_jwt, require_role
from api.rate_limit import allow  # kept for future
from api.api_metrics import metrics, log_middleware
from openai import OpenAI

# ─────────────────────────────────────────────────────────────
# Optional local Phi-3 integration
# ─────────────────────────────────────────────────────────────
try:
    from phi.model import Phi3Mini
    phi3 = Phi3Mini()
    HAS_LOCAL_PHI3 = True
except Exception:
    phi3 = None
    HAS_LOCAL_PHI3 = False

load_dotenv()

API_HOST = os.getenv("API_HOST", "0.0.0.0")
API_PORT = int(os.getenv("API_PORT", "7720"))
DATA_DIR = os.getenv("DATA_DIR", "/data")

TELEMETRY_DIR = os.path.join(DATA_DIR, "telemetry")
RULES_DIR = os.path.join(DATA_DIR, "rules")
EXPER_DIR = os.path.join(DATA_DIR, "experiments")
TESTS_DIR = os.path.join(DATA_DIR, "tests")
KNOWLEDGE_DIR = os.path.join(DATA_DIR, "knowledge")
USER_DIR = os.path.join(DATA_DIR, "users")
PROGRAM_DIR = os.path.join(DATA_DIR, "programs")
STORYBOARD_DIR = os.path.join(DATA_DIR, "storyboards")
VIDEO_DIR = os.path.join(DATA_DIR, "video_jobs")

for d in [
    TELEMETRY_DIR, RULES_DIR, EXPER_DIR, TESTS_DIR,
    KNOWLEDGE_DIR, USER_DIR, PROGRAM_DIR, STORYBOARD_DIR, VIDEO_DIR
]:
    os.makedirs(d, exist_ok=True)

# Optional helper service URLs
STT_URL = os.getenv("STT_URL", "http://localhost:8765")
TTS_URL = os.getenv("TTS_URL", "http://localhost:8766")
ADVISOR_URL = os.getenv("ADVISOR_URL", "http://localhost:8764")
ADVISOR_MODE = os.getenv("ADVISOR_MODE", "off")

# OpenAI
OPENAI_MODEL = os.getenv("OPENAI_MODEL", "gpt-4.1-mini")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
openai_client: Optional[OpenAI] = OpenAI(api_key=OPENAI_API_KEY) if OPENAI_API_KEY else None

# ─────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────

def write_json(path: str, obj: Any):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w") as f:
        json.dump(obj, f, indent=2)

def read_json(path: str) -> Any:
    with open(path) as f:
        return json.load(f)

def user_profile_path(user_id: str) -> str:
    return os.path.join(USER_DIR, f"{user_id}.json")

def load_user_profile(user_id: Optional[str]) -> Dict[str, Any]:
    if not user_id:
        return {}
    path = user_profile_path(user_id)
    if not os.path.exists(path):
        profile = {
            "user_id": user_id,
            "created_at": int(time.time()),
            "last_updated": int(time.time()),
            "demographics": {},
            "goals": [],
            "injuries": [],
            "training_history": [],
            "last_briefing": "",
        }
        write_json(path, profile)
        return profile
    return read_json(path)

def save_user_profile(profile: Dict[str, Any]):
    user_id = profile.get("user_id")
    if not user_id:
        return
    profile["last_updated"] = int(time.time())
    write_json(user_profile_path(user_id), profile)

def save_program(user_id: str, program: Dict[str, Any]) -> str:
    ts = int(time.time())
    program_id = program.get("id") or f"prog_{user_id}_{ts}"
    program["id"] = program_id
    program["user_id"] = user_id
    program["created_at"] = ts
    path = os.path.join(PROGRAM_DIR, f"{program_id}.json")
    write_json(path, program)
    return program_id

def list_programs_for_user(user_id: str) -> List[Dict[str, Any]]:
    programs = []
    for fname in os.listdir(PROGRAM_DIR):
        if not fname.endswith(".json"):
            continue
        path = os.path.join(PROGRAM_DIR, fname)
        try:
            data = read_json(path)
        except Exception:
            continue
        if data.get("user_id") == user_id:
            programs.append(data)
    programs.sort(key=lambda p: p.get("created_at", 0), reverse=True)
    return programs

def attach_calendar_to_program(program: Dict[str, Any], start_date: Optional[str]) -> None:
    try:
        base_date = date.fromisoformat(start_date) if start_date else date.today()
    except Exception:
        base_date = date.today()

    calendar: List[Dict[str, Any]] = []
    current = base_date

    for week_block in program.get("plan", []):
        week_idx = week_block.get("week")
        for day in week_block.get("days", []):
            label = day.get("label") or f"Day {day.get('day_index')}"
            calendar.append({
                "date": current.isoformat(),
                "week": week_idx,
                "day_index": day.get("day_index"),
                "label": label,
            })
            current += timedelta(days=1)

    program["calendar"] = calendar

def llm_chat(system_prompt: str, user_prompt: str, temperature: float = 0.6) -> str:
    if openai_client is not None:
        resp = openai_client.chat.completions.create(
            model=OPENAI_MODEL,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            temperature=temperature,
        )
        return resp.choices[0].message.content

    if HAS_LOCAL_PHI3 and phi3 is not None:
        # Phi3Mini example: generate from concatenated prompt
        return phi3.generate(system_prompt + "\n\n" + user_prompt)

    raise HTTPException(
        status_code=503,
        detail="No LLM configured (OPENAI_API_KEY missing and Phi-3 not available).",
    )

# ─────────────────────────────────────────────────────────────
# Models
# ─────────────────────────────────────────────────────────────

class Telemetry(BaseModel):
    source: str
    session_id: str
    metrics: Dict[str, float]
    experiment: Optional[str] = None
    variant: Optional[str] = None

class AutoTuneReq(BaseModel):
    move: str
    window: int = 50
    policy: Dict[str, float] = {}

class RuleVersion(BaseModel):
    label: str

class ABStart(BaseModel):
    name: str
    metric: str
    variant_a: Dict[str, float]
    variant_b: Dict[str, float]
    duration_sessions: int = 20

class RegressGate(BaseModel):
    name: str
    min_depth: Optional[float] = None
    max_wobble: Optional[float] = None

class RegressReq(BaseModel):
    gates: List[RegressGate]

class AskPayload(BaseModel):
    question: str
    user_id: Optional[str] = None
    session_id: Optional[str] = None
    context: Optional[str] = None  # JSON string from front-end
    telemetry: Optional[Dict[str, Any]] = None
    mode: Optional[str] = "chat"   # "chat" | "briefing_update" | "program_help"

class ProfileUpsert(BaseModel):
    user_id: str
    age: Optional[int] = None
    height_cm: Optional[float] = None
    weight_kg: Optional[float] = None
    goals: Optional[List[str]] = None
    injuries: Optional[List[str]] = None
    notes: Optional[str] = None

class ProgramRequest(BaseModel):
    user_id: str
    goal: str
    weeks: int = 12
    days_per_week: int = 4
    home_only: bool = True
    yoga_heavy: bool = True
    assessment_summary: Optional[str] = None
    extra_context: Optional[str] = None
    start_date: Optional[str] = None
    created_by: Optional[str] = None

class StoryboardReq(BaseModel):
    prompt: str
    user_id: Optional[str] = None
    max_slides: int = 8
    style: Optional[str] = "cinematic"  # or "museum", "minimal"
    voiceover: bool = True

class VideoJobReq(BaseModel):
    storyboard_id: str
    fps: int = 30
    seconds_per_slide: int = 5
    # Later you can add: music_url, voice_id, etc.

# ─────────────────────────────────────────────────────────────
# App
# ─────────────────────────────────────────────────────────────

app = FastAPI(title="Maat / Mufasa API", version="2.2.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.middleware("http")(log_middleware)
app.add_api_route("/metrics", metrics, methods=["GET"])

@app.get("/health")
def health():
    return {
        "ok": True,
        "label": "Maat/Mufasa API",
        "has_openai": bool(openai_client),
        "openai_model": OPENAI_MODEL,
        "has_local_phi3": HAS_LOCAL_PHI3,
        "stt_url": STT_URL,
        "tts_url": TTS_URL,
        "advisor_mode": ADVISOR_MODE,
        "time": int(time.time()),
    }

# IMPORTANT: API root should NOT serve index.html
@app.get("/")
def root():
    return {"ok": True, "service": "mufasa-api", "hint": "Use /health, /ask, /storyboard, /slideshow.html"}

# ─────────────────────────────────────────────────────────────
# Telemetry / tuning / tests (kept)
# ─────────────────────────────────────────────────────────────

@app.post("/telemetry/ingest")
def telemetry_ingest(t: Telemetry):
    rec = t.model_dump() | {"ts": int(time.time())}
    path = os.path.join(TELEMETRY_DIR, f"t_{rec['ts']}_{t.session_id}.json")
    write_json(path, rec)
    agg_path = os.path.join(TELEMETRY_DIR, "rolling.jsonl")
    with open(agg_path, "a") as f:
        f.write(json.dumps(rec) + "\n")
    return {"ok": True}

def list_recent_telemetry(n: int = 200) -> List[Dict[str, Any]]:
    items = []
    for fname in sorted(os.listdir(TELEMETRY_DIR))[-n:]:
        if fname.endswith(".json") and fname.startswith("t_"):
            items.append(read_json(os.path.join(TELEMETRY_DIR, fname)))
    return items

@app.post("/tuning/auto")
def tuning_auto(req: AutoTuneReq):
    data = list_recent_telemetry(req.window)
    if not data:
        raise HTTPException(status_code=400, detail="No telemetry")

    depths = [d["metrics"].get("depth", 0.0) for d in data if "depth" in d["metrics"]]
    wobbles = [d["metrics"].get("knee_wobble_deg", 0.0) for d in data if "knee_wobble_deg" in d["metrics"]]
    avg_depth = statistics.mean(depths) if depths else 0.0
    avg_wobble = statistics.mean(wobbles) if wobbles else 999.0

    adjust_pct = float(req.policy.get("adjust_pct", 0.1))
    recommended: Dict[str, Any] = {}
    notes: List[str] = []

    if avg_depth < req.policy.get("depth_min", 0.8):
        recommended["hips_drop"] = {"op": "scale_up", "by": adjust_pct, "reason": "avg_depth low"}
        notes.append(f"Depth {avg_depth:.2f} < min {req.policy.get('depth_min', 0.8)}")

    if avg_wobble > req.policy.get("wobble_max", 3.0):
        recommended["tempo_slowdown"] = {"op": "scale_up", "by": adjust_pct, "reason": "knee wobble high"}
        notes.append(f"Wobble {avg_wobble:.2f} > max {req.policy.get('wobble_max', 3.0)}")

    proposal = {
        "move": req.move,
        "timestamp": int(time.time()),
        "stats": {"avg_depth": avg_depth, "avg_wobble": avg_wobble},
        "recommended": recommended,
        "notes": notes,
    }
    path = os.path.join(RULES_DIR, f"tune_{proposal['timestamp']}.json")
    write_json(path, proposal)
    return {"ok": True, "proposal": proposal}

# ─────────────────────────────────────────────────────────────
# Voice passthrough (optional)
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
# Profiles
# ─────────────────────────────────────────────────────────────

@app.post("/users/profile/upsert")
def profile_upsert(p: ProfileUpsert):
    profile = load_user_profile(p.user_id)

    demo = profile.get("demographics", {})
    if p.age is not None: demo["age"] = p.age
    if p.height_cm is not None: demo["height_cm"] = p.height_cm
    if p.weight_kg is not None: demo["weight_kg"] = p.weight_kg
    profile["demographics"] = demo

    if p.goals is not None: profile["goals"] = p.goals
    if p.injuries is not None: profile["injuries"] = p.injuries

    if p.notes:
        prev = profile.get("last_briefing", "")
        profile["last_briefing"] = (prev + "\n\n" + p.notes).strip()

    save_user_profile(profile)
    return {"ok": True, "profile": profile}

@app.get("/users/profile/get")
def profile_get(user_id: str):
    return {"ok": True, "profile": load_user_profile(user_id)}

# ─────────────────────────────────────────────────────────────
# Program generation (kept)
# ─────────────────────────────────────────────────────────────

@app.post("/coach/program/generate")
async def coach_program_generate(req: ProgramRequest):
    profile = load_user_profile(req.user_id)

    system_prompt = (
        "You are Ma'at 2.0, a NASM-informed Pan-African virtual coach.\n"
        "Return ONLY valid JSON in the specified schema.\n"
    )

    user_prompt = (
        f"User profile:\n{json.dumps(profile, indent=2)}\n\n"
        f"Goal: {req.goal}\nWeeks: {req.weeks}\nDays/week: {req.days_per_week}\n"
        f"Home only: {req.home_only}\nYoga heavy: {req.yoga_heavy}\n\n"
        f"Assessment summary:\n{req.assessment_summary or 'None'}\n\n"
        f"Extra context:\n{req.extra_context or ''}\n\n"
        "Output JSON schema:\n"
        "{"
        "\"title\":str,\"goal\":str,\"weeks\":int,\"days_per_week\":int,"
        "\"notes\":str,"
        "\"plan\":[{\"week\":int,\"days\":[{\"day_index\":int,\"label\":str,\"focus\":str,"
        "\"blocks\":[{\"type\":\"warmup\"|\"activation\"|\"strength\"|\"yoga\"|\"core\"|\"recovery\","
        "\"description\":str,\"items\":[str]}]}]}]"
        "}"
    )

    raw = llm_chat(system_prompt, user_prompt, temperature=0.6)
    try:
        program = json.loads(raw)
    except Exception:
        program = {"title":"Program (unparsed)","goal":req.goal,"weeks":req.weeks,"days_per_week":req.days_per_week,"notes":"Model returned non-JSON.","plan":[],"raw":raw}

    attach_calendar_to_program(program, req.start_date)
    if req.created_by:
        program["created_by"] = req.created_by

    program_id = save_program(req.user_id, program)
    return {"ok": True, "program_id": program_id, "program": program}

@app.get("/coach/program/list")
def coach_program_list(user_id: str):
    programs = list_programs_for_user(user_id)
    items = [{"id":p.get("id"),"title":p.get("title"),"goal":p.get("goal"),"created_at":p.get("created_at")} for p in programs]
    return {"ok": True, "programs": items}

@app.get("/coach/program/get")
def coach_program_get(program_id: str):
    path = os.path.join(PROGRAM_DIR, f"{program_id}.json")
    if not os.path.exists(path):
        raise HTTPException(status_code=404, detail="Program not found")
    return {"ok": True, "program": read_json(path)}

@app.get("/coach/calendar")
def coach_calendar(user_id: str, program_id: Optional[str] = None):
    programs = list_programs_for_user(user_id)
    if not programs:
        return {"ok": True, "events": [], "program_id": None}

    chosen = None
    if program_id:
        chosen = next((p for p in programs if p.get("id") == program_id), None)

    if chosen is None:
        chosen = next((p for p in programs if "calendar" in p), programs[0])

    return {"ok": True, "events": chosen.get("calendar") or [], "program_id": chosen.get("id")}

# ─────────────────────────────────────────────────────────────
# ASK
# ─────────────────────────────────────────────────────────────

@app.post("/ask")
async def ask(payload: AskPayload):
    question = payload.question
    user_id = payload.user_id or "anonymous"
    mode = payload.mode or "chat"

    profile = load_user_profile(user_id)

    telemetry_text = ""
    if payload.telemetry:
        t = payload.telemetry
        telemetry_text = (
            "\n\nWorkout telemetry:\n"
            f"- Exercise: {t.get('exercise_id')}\n"
            f"- Reps so far: {t.get('reps')}\n"
            f"- Last depth score (0–1): {t.get('depth_score')}\n"
            f"- Last form judged good?: {t.get('good_form')}\n"
        )

    context_text = ""
    if payload.context:
        try:
            ctx_obj = json.loads(payload.context)
        except Exception:
            ctx_obj = {"raw_context": payload.context}
        context_text = "\n\nFront-end context:\n" + json.dumps(ctx_obj, indent=2)

    system_prompt = (
        "You are Ma'at 2.0, Rashad's Pan-African AI coach.\n"
        "Be short, direct, and safe.\n"
        "Use telemetry if present.\n"
        "User profile:\n"
        f"{json.dumps(profile, indent=2)}"
        f"{telemetry_text}"
        f"{context_text}"
    )

    if mode == "briefing_update":
        system_prompt += (
            "\nUpdate the user briefing in 3–6 sentences, second-person.\n"
        )

    answer = llm_chat(system_prompt, question, temperature=0.6)

    if mode == "briefing_update":
        profile["last_briefing"] = answer
        save_user_profile(profile)

    ts = int(time.time())
    record = {
        "ts": ts,
        "question": question,
        "answer": answer,
        "session_id": payload.session_id,
        "user_id": user_id,
        "mode": mode,
        "telemetry": payload.telemetry,
    }
    write_json(os.path.join(KNOWLEDGE_DIR, f"qa_{ts}.json"), record)
    return record

# ─────────────────────────────────────────────────────────────
# STORYBOARD + SLIDESHOW
# ─────────────────────────────────────────────────────────────

@app.post("/storyboard")
def storyboard(req: StoryboardReq):
    """
    Returns a slide plan you can render into HTML / video later.
    """
    sb_id = f"sb_{int(time.time())}_{uuid.uuid4().hex[:8]}"

    system_prompt = (
        "You create storyboards for short educational videos.\n"
        "Return ONLY valid JSON:\n"
        "{"
        "\"title\":str,"
        "\"slides\":[{\"title\":str,\"bullets\":[str],\"narration\":str,\"on_screen\":str}],"
        "\"cta\":str"
        "}"
    )

    user_prompt = (
        f"Topic/prompt: {req.prompt}\n"
        f"Max slides: {req.max_slides}\n"
        f"Style: {req.style}\n"
        "Make it clear, punchy, and suitable for a slideshow video."
    )

    raw = llm_chat(system_prompt, user_prompt, temperature=0.7)
    try:
        sb = json.loads(raw)
    except Exception:
        sb = {"title":"Storyboard (unparsed)","slides":[],"cta":"","raw":raw}

    payload = {
        "id": sb_id,
        "user_id": req.user_id,
        "created_at": int(time.time()),
        "request": req.model_dump(),
        "storyboard": sb,
    }
    write_json(os.path.join(STORYBOARD_DIR, f"{sb_id}.json"), payload)
    return {"ok": True, "storyboard_id": sb_id, "data": payload}

@app.get("/storyboard/get")
def storyboard_get(storyboard_id: str):
    path = os.path.join(STORYBOARD_DIR, f"{storyboard_id}.json")
    if not os.path.exists(path):
        raise HTTPException(status_code=404, detail="Storyboard not found")
    return {"ok": True, "data": read_json(path)}

@app.get("/slideshow.html")
def slideshow_html(storyboard_id: str):
    """
    Lightweight HTML slideshow renderer for a storyboard.
    Your STATIC SITE should link to this endpoint (API domain) in a new tab
    OR you can copy this HTML into your static site if you want it local.
    """
    path = os.path.join(STORYBOARD_DIR, f"{storyboard_id}.json")
    if not os.path.exists(path):
        raise HTTPException(status_code=404, detail="Storyboard not found")

    data = read_json(path)
    sb = data.get("storyboard", {})
    slides = sb.get("slides", [])
    title = sb.get("title", "Slideshow")

    # Simple no-framework slideshow
    html = f"""
<!doctype html>
<html>
<head>
  <meta charset="utf-8"/>
  <meta name="viewport" content="width=device-width,initial-scale=1"/>
  <title>{title}</title>
  <style>
    body {{ margin:0; font-family: system-ui, -apple-system, Segoe UI, Roboto, Arial; background:#0b0b0b; color:#f5f5f5; }}
    .wrap {{ max-width: 980px; margin: 0 auto; padding: 20px; }}
    .card {{ border: 1px solid #2a2a2a; border-radius: 16px; padding: 18px; background: rgba(255,255,255,0.03); }}
    .row {{ display:flex; gap:12px; align-items:center; justify-content:space-between; margin: 12px 0; }}
    button {{ padding: 10px 14px; border-radius: 12px; border: 1px solid #444; background:#141414; color:#fff; }}
    button:active {{ transform: scale(0.99); }}
    .muted {{ color:#bdbdbd; font-size: 13px; }}
    ul {{ line-height: 1.45; }}
    .big {{ font-size: 28px; font-weight: 800; margin: 4px 0 10px; }}
    .small {{ font-size: 14px; color:#d6d6d6; }}
    .progress {{ height: 6px; background:#1a1a1a; border-radius: 999px; overflow:hidden; }}
    .bar {{ height: 100%; width: 0%; background: #caa24a; }}
  </style>
</head>
<body>
  <div class="wrap">
    <div class="row">
      <div>
        <div class="muted">Storyboard</div>
        <div class="big">{title}</div>
      </div>
      <div class="row">
        <button id="prevBtn">Prev</button>
        <button id="speakBtn">Speak</button>
        <button id="nextBtn">Next</button>
      </div>
    </div>

    <div class="progress"><div class="bar" id="bar"></div></div>

    <div class="card" style="margin-top:14px;">
      <div class="muted" id="slideCount"></div>
      <div class="big" id="slideTitle"></div>
      <div class="small" id="slideOnScreen"></div>
      <ul id="slideBullets"></ul>
      <div class="muted" style="margin-top:10px;">Narration</div>
      <div id="slideNarration" class="small"></div>
    </div>

    <div class="muted" style="margin-top:14px;">Tip: Use “Speak” to hear narration (browser TTS).</div>
  </div>

<script>
  const slides = {json.dumps(slides)};
  let i = 0;

  const titleEl = document.getElementById("slideTitle");
  const onScreenEl = document.getElementById("slideOnScreen");
  const bulletsEl = document.getElementById("slideBullets");
  const narrationEl = document.getElementById("slideNarration");
  const countEl = document.getElementById("slideCount");
  const barEl = document.getElementById("bar");

  function render() {{
    const s = slides[i] || {{}};
    titleEl.textContent = s.title || ("Slide " + (i+1));
    onScreenEl.textContent = s.on_screen || "";
    narrationEl.textContent = s.narration || "";
    bulletsEl.innerHTML = "";
    (s.bullets || []).forEach(b => {{
      const li = document.createElement("li");
      li.textContent = b;
      bulletsEl.appendChild(li);
    }});
    countEl.textContent = `Slide ${'{'}i+1{'}'} / ${'{'}slides.length{'}'}`;
    const pct = slides.length ? ((i+1)/slides.length)*100 : 0;
    barEl.style.width = pct + "%";
  }}

  function speakCurrent() {{
    const s = slides[i] || {{}};
    const text = (s.narration || s.on_screen || s.title || "");
    if (!text) return;
    if (!("speechSynthesis" in window)) return alert("TTS not supported in this browser.");
    window.speechSynthesis.cancel();
    const u = new SpeechSynthesisUtterance(text);
    window.speechSynthesis.speak(u);
  }}

  document.getElementById("prevBtn").onclick = () => {{ i = Math.max(0, i-1); render(); }};
  document.getElementById("nextBtn").onclick = () => {{ i = Math.min(slides.length-1, i+1); render(); }};
  document.getElementById("speakBtn").onclick = () => speakCurrent();

  render();
</script>
</body>
</html>
"""
    return HTMLResponse(html)

# ─────────────────────────────────────────────────────────────
# VIDEO JOB REQUEST (stub)
# ─────────────────────────────────────────────────────────────

@app.post("/video/request")
def video_request(req: VideoJobReq):
    """
    This creates a 'job' record. Actual MP4 generation should be done by a worker
    (or a separate service) because Render free instances + ffmpeg setup can be tricky.
    """
    sb_path = os.path.join(STORYBOARD_DIR, f"{req.storyboard_id}.json")
    if not os.path.exists(sb_path):
        raise HTTPException(status_code=404, detail="Storyboard not found")

    job_id = f"vid_{int(time.time())}_{uuid.uuid4().hex[:8]}"
    job = {
        "id": job_id,
        "created_at": int(time.time()),
        "status": "queued",
        "request": req.model_dump(),
        "storyboard_path": sb_path,
        "output": None,
        "notes": "Video rendering not implemented in this API yet. Connect a worker (ffmpeg) or external renderer."
    }
    write_json(os.path.join(VIDEO_DIR, f"{job_id}.json"), job)
    return {"ok": True, "job": job}

@app.get("/video/job")
def video_job(job_id: str):
    path = os.path.join(VIDEO_DIR, f"{job_id}.json")
    if not os.path.exists(path):
        raise HTTPException(status_code=404, detail="Job not found")
    return {"ok": True, "job": read_json(path)}

# ─────────────────────────────────────────────────────────────
# Auth helpers
# ─────────────────────────────────────────────────────────────

@app.post("/auth/login")
def login(role: str = "coach", tenant: str = "default", user_id: str = "u1"):
    token = mint_jwt({"role": role, "tenant": tenant, "sub": user_id})
    return {"token": token}

@app.get("/auth/me")
def me(request: Request):
    payload = require_role(request, roles=("viewer", "coach", "owner"))
    return {"you": payload}
