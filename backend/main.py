from __future__ import annotations
import random
import sqlite3
from contextlib import contextmanager
from datetime import datetime, date, time, timedelta
from typing import Literal, Optional
from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

database_path = "cat_companion.db"
max_bond_level_per_day = 10.0

app = FastAPI(title="Cat Companion Backend")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@contextmanager
def get_conn():
    conn = sqlite3.connect(database_path)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()

# initialize the database tables for quests and interaction logs
def init_db():
    with get_conn() as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS quests (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                quest_type TEXT NOT NULL,
                title TEXT NOT NULL,
                time_mode TEXT NOT NULL,
                exact_time TEXT,
                timeframe TEXT,
                scheduled_time TEXT NOT NULL,
                duration_minutes INTEGER NOT NULL,
                response_window_end TEXT NOT NULL,
                status TEXT NOT NULL,
                quest_date TEXT NOT NULL,
                created_at TEXT NOT NULL
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS interaction_logs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                device_id TEXT,
                event_type TEXT NOT NULL,
                quest_id INTEGER,
                message TEXT NOT NULL,
                bond_change REAL NOT NULL,
                timestamp TEXT NOT NULL,
                FOREIGN KEY (quest_id) REFERENCES quests(id)
            )
            """
        )

@app.on_event("startup")
def on_startup():
    init_db()

QuestType = Literal["hydration", "stretch", "plants", "tidy"]
TimeMode = Literal["exact", "timeframe"]
Timeframe = Literal["morning", "afternoon", "evening"]
EventType = Literal["pet", "quest_completed", "quest_skipped"]

class QuestCreate(BaseModel):
    quest_type: QuestType
    time_mode: TimeMode
    duration_minutes: int = Field(ge=1, le=180)
    exact_time: Optional[str] = None
    timeframe: Optional[Timeframe] = None

    def title(self):
        labels = {
            "hydration": "Drink water",
            "stretch": "Stretch",
            "plants": "Water plants",
            "tidy": "Tidy up",
        }
        return labels[self.quest_type]

class DeviceEventCreate(BaseModel):
    device_id: str = "cat_01"
    event_type: EventType
    quest_id: Optional[int] = None
    timestamp: Optional[str] = None

def now_local():
    return datetime.now()

def today_str():
    return date.today().isoformat()

def parse_time_str(time):
    return datetime.strptime(time, "%H:%M").time()

def parse_iso(datetime_str):
    return datetime.fromisoformat(datetime_str)

def timeframe_bounds(timeframe):
    if timeframe == "morning":
        return time(9, 0), time(12, 0)
    if timeframe == "afternoon":
        return time(13, 0), time(17, 0)
    return time(18, 0), time(21, 0)

def random_time_in_timeframe(timeframe):
    start_time, end_time = timeframe_bounds(timeframe)
    start_minutes = start_time.hour * 60 + start_time.minute
    end_minutes = end_time.hour * 60 + end_time.minute
    chosen = random.randint(start_minutes, end_minutes - 1)
    hour = chosen // 60
    minute = chosen % 60
    return f"{hour:02d}:{minute:02d}"

def to_datetime_for_today(hour_min):
    time = parse_time_str(hour_min)
    return datetime.combine(date.today(), time)

def compute_response_window_end(scheduled_time, duration_minutes):
    start_datetime = to_datetime_for_today(scheduled_time)
    end_datetime = start_datetime + timedelta(minutes=duration_minutes)
    return end_datetime.isoformat(timespec="minutes")

def get_existing_windows_for_today(conn):
    rows = conn.execute(
        """
        SELECT scheduled_time, response_window_end
        FROM quests
        WHERE quest_date = ?
        """,
        (today_str(),),
    ).fetchall()
    windows = []
    for row in rows:
        start_time = to_datetime_for_today(row["scheduled_time"])
        end_time = parse_iso(row["response_window_end"])
        windows.append((start_time, end_time))
    return windows

def overlaps(existing, candidate_start, candidate_end):
    for start, end in existing:
        if candidate_start < end and candidate_end > start:
            return True
    return False

def choose_non_conflicting_time(conn, timeframe, duration_minutes):
    existing = get_existing_windows_for_today(conn)
    for _ in range(50):
        hour_min = random_time_in_timeframe(timeframe)
        start_time = to_datetime_for_today(hour_min)
        end_time = start_time + timedelta(minutes=duration_minutes)
        if not overlaps(existing, start_time, end_time):
            return hour_min
    return random_time_in_timeframe(timeframe)

def get_bond_level_today(conn):
    start = datetime.combine(date.today(), time.min).isoformat()
    end = datetime.combine(date.today(), time.max).isoformat()
    row = conn.execute(
        """
        SELECT COALESCE(SUM(bond_change), 0) AS total
        FROM interaction_logs
        WHERE timestamp >= ? AND timestamp <= ?
        """,
        (start, end),
    ).fetchone()
    total = float(row["total"] or 0)
    return max(0.0, min(max_bond_level_per_day, total))

def event_bond_change(event_type):
    if event_type == "pet":
        return 1.0
    elif event_type == "quest_completed":
        return 2.0
    else:
        return -0.5

def event_message(event_type, quest_title):
    if event_type == "pet":
        return "Petted the cat"
    elif event_type == "quest_completed":
        return f"Completed quest: {quest_title or 'Quest'}"
    else:
        return f"Skipped quest: {quest_title or 'Quest'}"

def auto_update_overdue_quests(conn):
    now = now_local()
    rows = conn.execute(
        """
        SELECT *
        FROM quests
        WHERE quest_date = ? AND status IN ('pending', 'active')
        ORDER BY scheduled_time ASC
        """,
        (today_str(),),
    ).fetchall()
    for row in rows:
        scheduled_start = to_datetime_for_today(row["scheduled_time"])
        response_end = parse_iso(row["response_window_end"])
        if scheduled_start <= now <= response_end and row["status"] == "pending":
            conn.execute(
                "UPDATE quests SET status = 'active' WHERE id = ?",
                (row["id"],),
            )
        if now > response_end and row["status"] in ("pending", "active"):
            conn.execute(
                "UPDATE quests SET status = 'skipped' WHERE id = ?",
                (row["id"],),
            )
            conn.execute(
                """
                INSERT INTO interaction_logs (device_id, event_type, quest_id, message, bond_change, timestamp)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    "system",
                    "quest_skipped",
                    row["id"],
                    f"Skipped quest: {row['title']}",
                    -0.5,
                    now.isoformat(timespec="seconds"),
                ),
            )

def quest_row_to_dict(row):
    return {
        "id": row["id"],
        "quest_type": row["quest_type"],
        "title": row["title"],
        "time_mode": row["time_mode"],
        "exact_time": row["exact_time"],
        "timeframe": row["timeframe"],
        "scheduled_time": row["scheduled_time"],
        "duration_minutes": row["duration_minutes"],
        "response_window_end": row["response_window_end"],
        "status": row["status"],
        "quest_date": row["quest_date"],
        "created_at": row["created_at"],
    }

@app.get("/")
def root():
    return {"message": "Cat Companion backend is running."}

# create a new quest with the given details
@app.post("/quests")
def create_quest(payload: QuestCreate):
    if payload.time_mode == "exact" and not payload.exact_time:
        raise HTTPException(status_code=400, detail="exact_time is required for exact mode")
    if payload.time_mode == "timeframe" and not payload.timeframe:
        raise HTTPException(status_code=400, detail="timeframe is required for timeframe mode")

    with get_conn() as conn:
        auto_update_overdue_quests(conn)
        if payload.time_mode == "exact":
            scheduled_time = payload.exact_time
        else:
            scheduled_time = choose_non_conflicting_time(
                conn,
                payload.timeframe,
                payload.duration_minutes,
            )
        response_window_end = compute_response_window_end(
            scheduled_time,
            payload.duration_minutes,
        )
        created_at = now_local().isoformat(timespec="seconds")
        cur = conn.execute(
            """
            INSERT INTO quests (
                quest_type, title, time_mode, exact_time, timeframe,
                scheduled_time, duration_minutes, response_window_end,
                status, quest_date, created_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                payload.quest_type,
                payload.title(),
                payload.time_mode,
                payload.exact_time,
                payload.timeframe,
                scheduled_time,
                payload.duration_minutes,
                response_window_end,
                "pending",
                today_str(),
                created_at,
            ),
        )
        quest_id = cur.lastrowid
        row = conn.execute("SELECT * FROM quests WHERE id = ?", (quest_id,)).fetchone()
        return {"quest": quest_row_to_dict(row)}

# delete a quest by id 
@app.delete("/quests/{quest_id}")
def delete_quest(quest_id: int):
    with get_conn() as conn:
        row = conn.execute("SELECT * FROM quests WHERE id = ?", (quest_id,)).fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="Quest not found")
        conn.execute("DELETE FROM quests WHERE id = ?", (quest_id,))
        return {"ok": True, "deleted_quest_id": quest_id}

# send data to the frontend dashboard, including the current bond level, today's quests and interaction logs
@app.get("/dashboard")
def get_dashboard():
    with get_conn() as conn:
        auto_update_overdue_quests(conn)
        quests = conn.execute(
            """
            SELECT * FROM quests
            WHERE quest_date = ?
            ORDER BY scheduled_time ASC
            """,
            (today_str(),),
        ).fetchall()
        today_start = datetime.combine(date.today(), time.min).isoformat()
        tomorrow_start = datetime.combine(date.today() + timedelta(days=1), time.min).isoformat()
        logs = conn.execute(
            """
            SELECT * FROM interaction_logs
            WHERE timestamp >= ? AND timestamp < ?
            ORDER BY timestamp DESC
            LIMIT 100
            """,
            (today_start, tomorrow_start),
        ).fetchall()
        return {
            "bond_level": get_bond_level_today(conn),
            "bond_max": max_bond_level_per_day,
            "quests": [quest_row_to_dict(q) for q in quests],
            "interaction_logs": [
                {
                    "id": row["id"],
                    "device_id": row["device_id"],
                    "event_type": row["event_type"],
                    "quest_id": row["quest_id"],
                    "message": row["message"],
                    "bond_change": row["bond_change"],
                    "timestamp": row["timestamp"],
                }
                for row in logs
            ],
        }

# communicate with the Feather; send details on the current active request (if any)
@app.get("/device-state")
def get_device_state(device_id: str = Query(default="cat_01")):
    with get_conn() as conn:
        auto_update_overdue_quests(conn)
        active = conn.execute(
            """
            SELECT * FROM quests
            WHERE quest_date = ? AND status = 'active'
            ORDER BY scheduled_time ASC
            LIMIT 1
            """,
            (today_str(),),
        ).fetchone()
        active_quest = None
        if active:
            active_quest = {
                "id": active["id"],
                "quest_type": active["quest_type"],
                "title": active["title"],
                "scheduled_time": active["scheduled_time"],
                "duration_minutes": active["duration_minutes"],
                "response_window_end": active["response_window_end"],
            }
        return {
            "device_id": device_id,
            "active_quest": active_quest,
        }

# fetch the device events, store interaction logs, and update the bond level accordingly
# if the event is related to a quest, update the quest status as well 
@app.post("/device-events")
def create_device_event(payload: DeviceEventCreate):
    with get_conn() as conn:
        auto_update_overdue_quests(conn)
        timestamp = payload.timestamp or now_local().isoformat(timespec="seconds")
        bond_change = event_bond_change(payload.event_type)
        quest_title = None
        if payload.quest_id is not None:
            quest_row = conn.execute(
                "SELECT title FROM quests WHERE id = ?",
                (payload.quest_id,),
            ).fetchone()
            if quest_row:
                quest_title = quest_row["title"]
        message = event_message(payload.event_type, quest_title)
        conn.execute(
            """
            INSERT INTO interaction_logs (device_id, event_type, quest_id, message, bond_change, timestamp)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (
                payload.device_id,
                payload.event_type,
                payload.quest_id,
                message,
                bond_change,
                timestamp,
            ),
        )
        if payload.event_type == "quest_completed" and payload.quest_id is not None:
            conn.execute(
                "UPDATE quests SET status = 'completed' WHERE id = ?",
                (payload.quest_id,),
            )
        elif payload.event_type == "quest_skipped" and payload.quest_id is not None:
            conn.execute(
                "UPDATE quests SET status = 'skipped' WHERE id = ?",
                (payload.quest_id,),
            )
        return {
            "ok": True,
            "bond_level": get_bond_level_today(conn),
            "message": message,
        }
