import json
from datetime import date
from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import FileResponse, JSONResponse

app = FastAPI()

DATA_PATH = Path("resources") / "swahili_30days.json"

@app.get("/")
def home():
    return FileResponse("index.html")

@app.get("/swahili")
def swahili_page():
    return FileResponse("swahili.html")

@app.get("/api/swahili/today")
def swahili_today():
    if not DATA_PATH.exists():
        return JSONResponse(
            {"error": "Missing resources/swahili_30days.json"},
            status_code=404
        )

    lessons = json.loads(DATA_PATH.read_text(encoding="utf-8"))

    # pick day-of-year mod 30 -> stable “lesson of the day”
    idx = (date.today().timetuple().tm_yday - 1) % len(lessons)
    lesson = lessons[idx]
    return lesson
