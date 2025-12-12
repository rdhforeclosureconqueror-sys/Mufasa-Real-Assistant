import os
import io
import json
import time
import statistics
from typing import List, Dict, Any, Optional
from datetime import date, timedelta

import httpx
from fastapi import FastAPI, HTTPException, UploadFile, File, Form, Request
from fastapi.responses import StreamingResponse, JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from dotenv import load_dotenv

from api.auth import mint_jwt, require_role
from api.rate_limit import allow  # (not used yet, but kept for future)
from api.api_metrics import metrics, log_middleware
from openai import OpenAI

# ───────────────────────────────────────────────────────────────────────────────
# Optional local Phi-3 integration
# ───────────────────────────────────────────────────────────────────────────────
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

for d in [TELEMETRY_DIR, RULES_DIR, EXPER_DIR, TESTS_DIR, KNOWLEDGE_DIR, USER_DIR, PROGRAM_DIR, STORYBOARD_DIR]:
    os.makedirs(d, exist_ok=True)

# Helper service URLs (optional sidecars)
STT_URL = os.getenv("STT_URL", "http://localhost:8765")
TTS_URL = os.getenv("TTS_URL", "http://localhost:8766")
ADVISOR_URL = os.getenv("ADVISOR_URL", "http://localhost:8764")
ADVISOR_MODE = os.getenv("ADVISOR_MODE", "off")

# OpenAI client
OPENAI_MODEL = os.getenv("OPENAI_MODEL", "gpt-4.1-mini")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
openai_client: Optional[OpenAI] = OpenAI(api_key=OPENAI_API_KEY) if OPENAI_API_KEY else None


# ───────────────────────────────────────────────────────────────────────────────
# Helpers
# ───────────────────────────────────────────────────────────────────────────────
def write_json(path: str, obj: Any):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(obj, f, indent=2, ensure_ascii=False)

def read_json(path: str) -> Any:
    with open(path, encoding="utf-8") as f:
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

def save_storyboard(story: Dict[str, Any]) -> str:
    ts = int(time.time())
    sid = story.get("id") or f"sb_{ts}"
    story["id"] = sid
    story["created_at"] = ts
    path = os.path.join(STORYBOARD_DIR, f"{sid}.json")
    write_json(path, story)
    return sid

def load_storyboard(sb_id: str) -> Dict[str, Any]:
    path = os.path.join(STORYBOARD_DIR, f"{sb_id}.json")
    if not os.path.exists(path):
        raise HTTPException(status_code=404, detail="Storyboard not found")
    return read_json(path)


# ───────────────────────────────────────────────────────────────────────────────
# Pydantic models
# ───────────────────────────────────────────────────────────────────────────────
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
    context: Optional[str] = None
    telemetry: Optional[Dict[str, Any]] = None
    mode: Optional[str] = "chat"  # "chat", "briefing_update", "program_help"

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
    question: str
    user_id: Optional[str] = None
    max_slides: int = 8


# ───────────────────────────────────────────────────────────────────────────────
# FastAPI app
# ───────────────────────────────────────────────────────────────────────────────
app = FastAPI(title="Maat 2.0 Brain", version="2.2.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.middleware("http")(log_middleware)
app.add_api_route("/metrics", metrics, methods=["GET"])


@app.get("/")
def root():
    # fixes the 405 HEAD/GET confusion when you open the API in browser
    return {"ok": True, "service": "Maat2.0 API", "hint": "Use /health or POST /ask"}


@app.get("/health")
def health():
    return {
        "ok": True,
        "label": "Maat2.0",
        "phase": 7,
        "stt_url": STT_URL,
        "tts_url": TTS_URL,
        "advisor_mode": ADVISOR_MODE,
        "has_local_phi3": HAS_LOCAL_PHI3,
        "has_openai": bool(openai_client),
        "openai_model": OPENAI_MODEL,
    }


# ───────────────────────────────────────────────────────────────────────────────
# Telemetry, tuning, experiments, regression tests (unchanged)
# ───────────────────────────────────────────────────────────────────────────────
@app.post("/telemetry/ingest")
def telemetry_ingest(t: Telemetry):
    rec = t.model_dump() | {"ts": int(time.time())}
    path = os.path.join(TELEMETRY_DIR, f"t_{rec['ts']}_{t.session_id}.json")
    write_json(path, rec)
    agg_path = os.path.join(TELEMETRY_DIR, "rolling.jsonl")
    with open(agg_path, "a", encoding="utf-8") as f:
        f.write(json.dumps(rec, ensure_ascii=False) + "\n")
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

@app.post("/rules/version/promote")
def rules_version_promote(ver: RuleVersion):
    snapshots = []
    for fname in os.listdir(RULES_DIR):
        if fname.startswith("tune_") and fname.endswith(".json"):
            snapshots.append(read_json(os.path.join(RULES_DIR, fname)))
    if not snapshots:
        raise HTTPException(status_code=400, detail="No tuning proposals to version")
    path = os.path.join(RULES_DIR, f"version_{int(time.time())}_{ver.label}.json")
    write_json(path, {"label": ver.label, "proposals": snapshots})
    return {"ok": True, "version_file": path}

@app.post("/rules/version/rollback")
def rules_version_rollback(ver: RuleVersion):
    with open(os.path.join(RULES_DIR, "rollback.log"), "a", encoding="utf-8") as f:
        f.write(f"{int(time.time())}\tROLLBACK\t{ver.label}\n")
    return {"ok": True}

@app.post("/experiments/ab/start")
def experiments_ab_start(cfg: ABStart):
    exp_id = f"exp_{int(time.time())}_{cfg.name}"
    state = {
        "id": exp_id,
        "cfg": cfg.model_dump(),
        "a": {"n": 0, "sum": 0.0},
        "b": {"n": 0, "sum": 0.0},
    }
    path = os.path.join(EXPER_DIR, f"{exp_id}.json")
    write_json(path, state)
    return {"ok": True, "exp_id": exp_id}

@app.get("/experiments/ab/status")
def experiments_ab_status(exp_id: str):
    path = os.path.join(EXPER_DIR, f"{exp_id}.json")
    if not os.path.exists(path):
        raise HTTPException(status_code=404, detail="Experiment not found")
    state = read_json(path)
    a = state["a"]
    b = state["b"]
    winner = None
    if a["n"] > 0 and b["n"] > 0:
        mean_a = a["sum"] / a["n"]
        mean_b = b["sum"] / b["n"]
        if abs(mean_a - mean_b) > 0.05:
            winner = "A" if mean_a > mean_b else "B"
        state["means"] = {"A": mean_a, "B": mean_b}
        state["winner"] = winner
    return state

@app.post("/tests/regress/run")
def tests_regress_run(req: RegressReq):
    data = list_recent_telemetry(100)
    depths = [d["metrics"].get("depth", 0.0) for d in data if "depth" in d["metrics"]]
    wobbles = [d["metrics"].get("knee_wobble_deg", 0.0) for d in data if "knee_wobble_deg" in d["metrics"]]

    results = []
    for g in req.gates:
        gate_res = {"name": g.name, "pass": True, "notes": []}
        if g.min_depth is not None:
            avg_depth = (sum(depths) / len(depths)) if depths else 0.0
            if avg_depth < g.min_depth:
                gate_res["pass"] = False
                gate_res["notes"].append(f"avg_depth {avg_depth:.2f} < {g.min_depth}")
        if g.max_wobble is not None:
            avg_wobble = (sum(wobbles) / len(wobbles)) if wobbles else 999.0
            if avg_wobble > g.max_wobble:
                gate_res["pass"] = False
                gate_res["notes"].append(f"avg_wobble {avg_wobble:.2f} > {g.max_wobble}")
        results.append(gate_res)

    overall = all(r["pass"] for r in results)
    path = os.path.join(TESTS_DIR, f"regress_{int(time.time())}.json")
    write_json(path, {"overall": overall, "results": results})
    return {"overall": overall, "results": results}


# ───────────────────────────────────────────────────────────────────────────────
# Voice: STT / TTS passthrough
# ───────────────────────────────────────────────────────────────────────────────
@app.post("/voice/stt")
async def voice_stt(file: UploadFile = File(...)):
    async with httpx.AsyncClient(timeout=120) as client:
        files = {
            "file": (file.filename, await file.read(), file.content_type or "application/octet-stream")
        }
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


# ───────────────────────────────────────────────────────────────────────────────
# User Profile APIs
# ───────────────────────────────────────────────────────────────────────────────
@app.post("/users/profile/upsert")
def profile_upsert(p: ProfileUpsert):
    profile = load_user_profile(p.user_id)

    demo = profile.get("demographics", {})
    if p.age is not None:
        demo["age"] = p.age
    if p.height_cm is not None:
        demo["height_cm"] = p.height_cm
    if p.weight_kg is not None:
        demo["weight_kg"] = p.weight_kg
    profile["demographics"] = demo

    if p.goals is not None:
        profile["goals"] = p.goals
    if p.injuries is not None:
        profile["injuries"] = p.injuries

    if p.notes:
        prev = profile.get("last_briefing", "")
        profile["last_briefing"] = (prev + "\n\n" + p.notes).strip()

    save_user_profile(profile)
    return {"ok": True, "profile": profile}

@app.get("/users/profile/get")
def profile_get(user_id: str):
    return {"ok": True, "profile": load_user_profile(user_id)}


# ───────────────────────────────────────────────────────────────────────────────
# Program generation APIs (unchanged)
# ───────────────────────────────────────────────────────────────────────────────
@app.post("/coach/program/generate")
async def coach_program_generate(req: ProgramRequest):
    if openai_client is None and not HAS_LOCAL_PHI3:
        raise HTTPException(status_code=503, detail="No LLM is configured for program generation.")

    profile = load_user_profile(req.user_id)

    system_prompt = (
        "You are Ma'at 2.0, a NASM-informed Pan-African virtual coach.\n"
        "Return ONLY valid JSON.\n"
    )

    user_prompt = (
        f"User profile:\n{json.dumps(profile, indent=2)}\n\n"
        f"Goal: {req.goal}\nWeeks: {req.weeks}\nDays per week: {req.days_per_week}\n"
        f"Home only: {req.home_only}\nYoga heavy: {req.yoga_heavy}\n\n"
        f"Assessment:\n{req.assessment_summary or 'None'}\n\n"
        f"Extra:\n{req.extra_context or ''}\n\n"
        "Output JSON with keys: title, goal, weeks, days_per_week, notes, plan[].\n"
    )

    raw = None
    if openai_client is not None:
        resp = openai_client.chat.completions.create(
            model=OPENAI_MODEL,
            messages=[{"role": "system", "content": system_prompt},
                      {"role": "user", "content": user_prompt}],
            temperature=0.6,
        )
        raw = resp.choices[0].message.content
    else:
        raw = phi3.generate(user_prompt)

    try:
        program = json.loads(raw)
    except Exception:
        program = {"title": "Program (unparsed)", "goal": req.goal, "weeks": req.weeks,
                   "days_per_week": req.days_per_week, "notes": "Non-JSON output.", "plan": [], "raw": raw}

    attach_calendar_to_program(program, req.start_date)
    if req.created_by:
        program["created_by"] = req.created_by

    pid = save_program(req.user_id, program)
    return {"ok": True, "program_id": pid, "program": program}

@app.get("/coach/program/list")
def coach_program_list(user_id: str):
    programs = list_programs_for_user(user_id)
    return {"ok": True, "programs": [{
        "id": p.get("id"), "title": p.get("title"), "goal": p.get("goal"), "created_at": p.get("created_at")
    } for p in programs]}

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


# ───────────────────────────────────────────────────────────────────────────────
# ASK
# ───────────────────────────────────────────────────────────────────────────────
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
        "You are Ma'at 2.0, Rashad's Pan-African AI assistant.\n"
        "Be clear, safe, and helpful.\n"
        "Default to 2–8 sentences unless asked to go long.\n\n"
        "User profile:\n"
        f"{json.dumps(profile, indent=2)}\n"
        f"{telemetry_text}"
        f"{context_text}\n"
    )

    if mode == "briefing_update":
        system_prompt += (
            "\nUpdate your internal briefing about this user in 3–6 sentences, second person.\n"
        )

    if openai_client is None and not HAS_LOCAL_PHI3:
        raise HTTPException(status_code=503, detail="No LLM configured (missing OPENAI_API_KEY).")

    if openai_client is not None:
        resp = openai_client.chat.completions.create(
            model=OPENAI_MODEL,
            messages=[{"role": "system", "content": system_prompt},
                      {"role": "user", "content": question}],
            temperature=0.6,
        )
        answer = resp.choices[0].message.content
    else:
        answer = phi3.generate(question)

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


# ───────────────────────────────────────────────────────────────────────────────
# SLIDESHOW / STORYBOARD (NEW)
# ───────────────────────────────────────────────────────────────────────────────
@app.post("/storyboard/generate")
async def storyboard_generate(req: StoryboardReq):
    """
    Generates a slide deck outline (JSON) from a user question.
    This is "the slideshow brain" step.
    """
    if openai_client is None and not HAS_LOCAL_PHI3:
        raise HTTPException(status_code=503, detail="No LLM configured for storyboard generation.")

    user_id = req.user_id or "public"
    profile = load_user_profile(user_id)

    system_prompt = (
        "You are Mufasa's Slideshow Director.\n"
        "Return ONLY valid JSON.\n"
        "Goal: Convert the user's question into an 6-10 slide micro-lesson.\n"
        "Each slide must have:\n"
        "- title (short)\n"
        "- bullets (3-6 bullets)\n"
        "- narration (1 short paragraph)\n"
        "No markdown.\n"
    )

    user_prompt = (
        f"User: {user_id}\nProfile:\n{json.dumps(profile, indent=2)}\n\n"
        f"Question: {req.question}\n"
        f"Max slides: {req.max_slides}\n\n"
        "Output JSON shape:\n"
        "{\n"
        '  "deck_title": string,\n'
        '  "topic": string,\n'
        '  "audience": "general",\n'
        '  "slides": [\n'
        '     {"title": string, "bullets": [string], "narration": string}\n'
        "  ]\n"
        "}\n"
    )

    if openai_client is not None:
        resp = openai_client.chat.completions.create(
            model=OPENAI_MODEL,
            messages=[{"role": "system", "content": system_prompt},
                      {"role": "user", "content": user_prompt}],
            temperature=0.5,
        )
        raw = resp.choices[0].message.content
    else:
        raw = phi3.generate(user_prompt)

    try:
        deck = json.loads(raw)
    except Exception:
        deck = {
            "deck_title": "Slideshow (unparsed)",
            "topic": req.question[:80],
            "audience": "general",
            "slides": [{"title": "Error", "bullets": ["Model returned non-JSON"], "narration": raw}],
        }

    story = {
        "user_id": user_id,
        "question": req.question,
        "deck": deck,
    }
    sb_id = save_storyboard(story)
    return {"ok": True, "id": sb_id, "storyboard": story}


@app.get("/storyboard/get")
def storyboard_get(id: str):
    story = load_storyboard(id)
    return {"ok": True, "storyboard": story}


# ───────────────────────────────────────────────────────────────────────────────
# Auth helpers (unchanged)
# ───────────────────────────────────────────────────────────────────────────────
@app.post("/auth/login")
def login(role: str = "coach", tenant: str = "default", user_id: str = "u1"):
    token = mint_jwt({"role": role, "tenant": tenant, "sub": user_id})
    return {"token": token}

@app.get("/auth/me")
def me(request: Request):
    payload = require_role(request, roles=("viewer", "coach", "owner"))
    return {"you": payload}
