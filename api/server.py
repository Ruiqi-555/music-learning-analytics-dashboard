import sys
import os
import threading
import uuid
import uvicorn
from pathlib import Path
from typing import List, Optional, Dict

from fastapi import FastAPI, HTTPException, Query, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

# --- 1. Setup Paths ---
ROOT = Path(__file__).resolve().parents[1]
sys.path.append(str(ROOT))

from src.music_app_system import MusicAppSystem
from scripts import init_db as init_db_script
from scripts import simulate_data as simulate_data_script
from scripts import generate_dashboard as generate_dashboard_script

DB_PATH = ROOT / "data" / "music.db"
os.makedirs(DB_PATH.parent, exist_ok=True)

app = FastAPI(title="Music Membership API")
system = MusicAppSystem(str(DB_PATH))
tasks_status: Dict[str, Dict[str, str]] = {}

# --- 2. Mount Static & Outputs ---
outputs_dir = ROOT / "outputs"
os.makedirs(outputs_dir, exist_ok=True)
app.mount("/outputs", StaticFiles(directory=outputs_dir), name="outputs")

static_dir = ROOT / "static"
os.makedirs(static_dir, exist_ok=True)
app.mount("/static", StaticFiles(directory=static_dir, html=True), name="static")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


# --- 3. Global Exception Handler (Fixes 'Unexpected token <') ---
@app.exception_handler(500)
async def internal_exception_handler(request: Request, exc: Exception):
    return JSONResponse(
        status_code=500,
        content={"message": f"Internal Server Error: {str(exc)}"},
    )


# --- 4. Models & API ---
class RegisterRequest(BaseModel):
    email: Optional[str] = None
    phone: Optional[str] = None
    nickname: str
    gender: Optional[str] = None
    birth_year: Optional[int] = None
    region: Optional[str] = None
    register_source: Optional[str] = "web"
    fav_genres: Optional[str] = None
    fav_scenes: Optional[str] = None
    extra_info: Optional[str] = None


@app.post("/api/register")
def register_user(req: RegisterRequest):
    user_id = system.register_user(
        email=req.email, phone=req.phone, nickname=req.nickname,
        gender=req.gender, birth_year=req.birth_year, region=req.region,
        register_source=req.register_source,
    )
    if req.fav_genres or req.fav_scenes or req.extra_info:
        with system._conn() as conn:
            conn.execute(
                "INSERT OR REPLACE INTO user_preferences (user_id, fav_genres, fav_scenes, extra_info, created_at, updated_at) VALUES (?, ?, ?, ?, datetime('now'), datetime('now'))",
                (user_id, req.fav_genres, req.fav_scenes, req.extra_info),
            )
    return {"user_id": user_id, "message": "registered"}


@app.get("/api/users/search")
def search_users(q: str = Query(..., min_length=1), limit: int = 20):
    pattern = f"%{q}%"
    with system._conn() as conn:
        rows = conn.execute(
            "SELECT u.user_id, u.nickname, u.email, u.region, u.register_time, u.register_source FROM users u WHERE u.nickname LIKE ? OR u.email LIKE ? ORDER BY u.register_time DESC LIMIT ?",
            (pattern, pattern, limit),
        ).fetchall()
    return [dict(r) for r in rows]


@app.get("/api/users/{user_id}")
def get_user(user_id: int):
    info = system.get_user_info(user_id)
    if not info: raise HTTPException(status_code=404, detail="User not found")
    # Fetch details
    with system._conn() as conn:
        pref = conn.execute("SELECT * FROM user_preferences WHERE user_id=?", (user_id,)).fetchone()
        profile = conn.execute("SELECT * FROM user_profiles WHERE user_id=?", (user_id,)).fetchone()
        segment = conn.execute(
            "SELECT s.segment_name FROM user_segments s JOIN user_segment_membership m ON s.segment_id=m.segment_id WHERE m.user_id=?",
            (user_id,)).fetchone()

    info["preferences"] = dict(pref) if pref else {}
    info["profile"] = dict(profile) if profile else {}
    info["segment"] = segment["segment_name"] if segment else "Unknown"
    info["recent_logs"] = system.get_user_recent_logs(user_id, limit=5)
    info["feedbacks"] = system.get_user_feedbacks(user_id)
    return info


# --- Task Runner ---
def _run_task(task_id: str, action: str, func):
    tasks_status[task_id] = {"action": action, "status": "running"}
    try:
        func()
        tasks_status[task_id] = {"action": action, "status": "completed"}
    except Exception as exc:
        print(f"!!! Task {action} failed: {exc}")
        tasks_status[task_id] = {"action": action, "status": "failed", "error": str(exc)}


def _start_task(action: str, func):
    task_id = str(uuid.uuid4())
    tasks_status[task_id] = {"action": action, "status": "queued"}
    threading.Thread(target=_run_task, args=(task_id, action, func), daemon=True).start()
    return task_id


@app.get("/api/actions/status")
def action_status(task_id: Optional[str] = None):
    if task_id: return tasks_status.get(task_id, {"status": "unknown"})
    return tasks_status


@app.post("/api/actions/init_db")
def action_init_db(): return {"task_id": _start_task("init_db", init_db_script.init_db)}


@app.post("/api/actions/simulate_data")
def action_simulate_data(): return {"task_id": _start_task("simulate_data", simulate_data_script.main)}


@app.post("/api/actions/generate_dashboard")
def action_generate_dashboard(): return {"task_id": _start_task("generate_dashboard", generate_dashboard_script.main)}


@app.get("/")
def root():
    return {"message": "Music API Online. Visit /static/admin.html"}


if __name__ == "__main__":
    uvicorn.run("api.server:app", host="127.0.0.1", port=8001, reload=True)
