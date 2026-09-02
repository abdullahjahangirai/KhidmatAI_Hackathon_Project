"""SQLite database module for KhidmatAI welfare platform.

Handles all persistence: programs, organizations, settings, and users.
Tables are auto-created and seeded from JSON data files on first startup.
"""

import json
import os
import sqlite3
from datetime import datetime
from pathlib import Path
from typing import Any

import bcrypt

BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BASE_DIR / "data"
DB_PATH = BASE_DIR / "khidmatai.db"


# ---------------------------------------------------------------------------
# Connection helpers
# ---------------------------------------------------------------------------

def get_connection() -> sqlite3.Connection:
    """Return a new connection with row-factory enabled."""
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


def _row_to_dict(row: sqlite3.Row | None) -> dict | None:
    return dict(row) if row else None


# ---------------------------------------------------------------------------
# Schema
# ---------------------------------------------------------------------------

SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS programs (
    id              TEXT PRIMARY KEY,
    title           TEXT NOT NULL,
    category        TEXT DEFAULT '',
    type            TEXT DEFAULT '',
    description     TEXT DEFAULT '',
    address         TEXT DEFAULT '',
    phone_number    TEXT DEFAULT '',
    support         TEXT DEFAULT '[]',
    eligibility     TEXT DEFAULT '[]',
    documents       TEXT DEFAULT '[]',
    application     TEXT DEFAULT '',
    locations       TEXT DEFAULT '[]',
    keywords        TEXT DEFAULT '[]',
    latitude        REAL,
    longitude       REAL,
    source_name     TEXT DEFAULT '',
    source_url      TEXT DEFAULT '',
    verified_at     TEXT DEFAULT '',
    dynamic_saved   INTEGER DEFAULT 0
);

CREATE TABLE IF NOT EXISTS organizations (
    id              TEXT PRIMARY KEY,
    name            TEXT NOT NULL,
    org_type        TEXT DEFAULT '',
    contact         TEXT DEFAULT '',
    email           TEXT DEFAULT '',
    password_hash   TEXT DEFAULT '',
    address         TEXT DEFAULT '',
    province        TEXT DEFAULT '',
    description     TEXT DEFAULT '',
    status          TEXT DEFAULT 'pending',
    submitted_at    TEXT DEFAULT '',
    reviewed_at     TEXT DEFAULT ''
);

CREATE TABLE IF NOT EXISTS org_posts (
    id              TEXT PRIMARY KEY,
    org_id          TEXT NOT NULL,
    org_name        TEXT DEFAULT '',
    title           TEXT NOT NULL,
    description     TEXT DEFAULT '',
    category        TEXT DEFAULT 'General',
    post_type       TEXT DEFAULT 'Program',
    eligibility     TEXT DEFAULT '[]',
    documents       TEXT DEFAULT '[]',
    location        TEXT DEFAULT '',
    contact         TEXT DEFAULT '',
    website         TEXT DEFAULT '',
    pricing         TEXT DEFAULT 'Free',
    image           TEXT DEFAULT '',
    status          TEXT DEFAULT 'pending',
    created_at      TEXT DEFAULT '',
    reviewed_at     TEXT DEFAULT ''
);

CREATE TABLE IF NOT EXISTS analytics_events (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    event_type      TEXT NOT NULL,
    meta            TEXT DEFAULT '',
    created_at      TEXT DEFAULT ''
);

CREATE TABLE IF NOT EXISTS facilities (
    id              TEXT PRIMARY KEY,
    name            TEXT NOT NULL,
    category        TEXT DEFAULT '',
    city            TEXT DEFAULT '',
    zone            TEXT DEFAULT '',
    address         TEXT DEFAULT '',
    phone           TEXT DEFAULT '',
    facility_type   TEXT DEFAULT '',
    lat             REAL,
    lon             REAL,
    source          TEXT DEFAULT 'overpass',
    collected_at    TEXT DEFAULT ''
);

CREATE TABLE IF NOT EXISTS settings (
    key     TEXT PRIMARY KEY,
    value   TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS users (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    name            TEXT NOT NULL,
    email           TEXT UNIQUE NOT NULL,
    password_hash   TEXT NOT NULL,
    phone           TEXT DEFAULT '',
    city            TEXT DEFAULT '',
    cnic            TEXT DEFAULT '',
    created_at      TEXT DEFAULT '',
    applications    TEXT DEFAULT '[]'
);

CREATE TABLE IF NOT EXISTS universities (
    id              TEXT PRIMARY KEY,
    title           TEXT NOT NULL,
    category        TEXT DEFAULT '',
    type            TEXT DEFAULT '',
    description     TEXT DEFAULT '',
    address         TEXT DEFAULT '',
    phone_number    TEXT DEFAULT '',
    support         TEXT DEFAULT '[]',
    eligibility     TEXT DEFAULT '[]',
    documents       TEXT DEFAULT '[]',
    application     TEXT DEFAULT '',
    locations       TEXT DEFAULT '[]',
    keywords        TEXT DEFAULT '[]',
    latitude        REAL,
    longitude       REAL,
    source_name     TEXT DEFAULT '',
    source_url      TEXT DEFAULT '',
    verified_at     TEXT DEFAULT ''
);
"""


# ---------------------------------------------------------------------------
# Initialization
# ---------------------------------------------------------------------------

def init_db() -> None:
    """Create tables if missing, run migrations, and seed from JSON data on first run."""
    conn = get_connection()
    try:
        conn.executescript(SCHEMA_SQL)
        _run_migrations(conn)

        # Seed programs from multiple JSON sources
        for fname in (
            "programs.json",
            "assistance.json",
            "welfare_programs.json",
            "aid_and_support.json",
            "hospitals.json",
            "dynamic_welfare.json",
        ):
            _seed_programs(conn, fname)

        _seed_universities(conn, "universities.json")
        _seed_settings(conn)

        conn.commit()
    finally:
        conn.close()


# ---------------------------------------------------------------------------
# Schema migrations
# ---------------------------------------------------------------------------

def _run_migrations(conn: sqlite3.Connection) -> None:
    """Add columns that may be missing from older database versions."""
    # Add password_hash to organizations if missing
    cols = {row["name"] for row in conn.execute("PRAGMA table_info(organizations)").fetchall()}
    if "password_hash" not in cols:
        conn.execute("ALTER TABLE organizations ADD COLUMN password_hash TEXT DEFAULT ''")
    # Extended organization profile fields (organization ecosystem)
    for col, default in (
        ("website", ""), ("city", ""), ("services", ""),
        ("opening_hours", ""), ("pricing", ""), ("discount", ""),
    ):
        if col not in cols:
            conn.execute(f"ALTER TABLE organizations ADD COLUMN {col} TEXT DEFAULT '{default}'")
    conn.commit()


# ---------------------------------------------------------------------------
# Seeding helpers
# ---------------------------------------------------------------------------

def _seed_programs(conn: sqlite3.Connection, filename: str) -> None:
    fpath = DATA_DIR / filename
    if not fpath.exists():
        return
    try:
        items = json.loads(fpath.read_text(encoding="utf-8"))
    except Exception:
        return
    if not isinstance(items, list):
        return

    rows = []
    for item in items:
        if not isinstance(item, dict) or not item.get("id"):
            continue
        rows.append((
            str(item["id"]),
            str(item.get("title", "")),
            str(item.get("category", "")),
            str(item.get("type", "")),
            str(item.get("description", "")),
            str(item.get("address", "")),
            str(item.get("phone_number", "")),
            json.dumps(item.get("support", []), ensure_ascii=False),
            json.dumps(item.get("eligibility", []), ensure_ascii=False),
            json.dumps(item.get("documents", []), ensure_ascii=False),
            str(item.get("application", "")),
            json.dumps(item.get("locations", []), ensure_ascii=False),
            json.dumps(item.get("keywords", []), ensure_ascii=False),
            item.get("latitude"),
            item.get("longitude"),
            str(item.get("source_name", "")),
            str(item.get("source_url", "")),
            str(item.get("verified_at", "")),
            1 if item.get("dynamic_saved") else 0,
        ))

    if rows:
        conn.executemany(
            """INSERT OR IGNORE INTO programs
               (id,title,category,type,description,address,phone_number,
                support,eligibility,documents,application,locations,keywords,
                latitude,longitude,source_name,source_url,verified_at,dynamic_saved)
               VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            rows,
        )


def _seed_universities(conn: sqlite3.Connection, filename: str) -> None:
    fpath = DATA_DIR / filename
    if not fpath.exists():
        return
    try:
        items = json.loads(fpath.read_text(encoding="utf-8"))
    except Exception:
        return
    if not isinstance(items, list):
        return

    rows = []
    for item in items:
        if not isinstance(item, dict) or not item.get("id"):
            continue
        rows.append((
            str(item["id"]),
            str(item.get("title", "")),
            str(item.get("category", "")),
            str(item.get("type", "")),
            str(item.get("description", "")),
            str(item.get("address", "")),
            str(item.get("phone_number", "")),
            json.dumps(item.get("support", []), ensure_ascii=False),
            json.dumps(item.get("eligibility", []), ensure_ascii=False),
            json.dumps(item.get("documents", []), ensure_ascii=False),
            str(item.get("application", "")),
            json.dumps(item.get("locations", []), ensure_ascii=False),
            json.dumps(item.get("keywords", []), ensure_ascii=False),
            item.get("latitude"),
            item.get("longitude"),
            str(item.get("source_name", "")),
            str(item.get("source_url", "")),
            str(item.get("verified_at", "")),
        ))

    if rows:
        conn.executemany(
            """INSERT OR IGNORE INTO universities
               (id,title,category,type,description,address,phone_number,
                support,eligibility,documents,application,locations,keywords,
                latitude,longitude,source_name,source_url,verified_at)
               VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            rows,
        )


def _seed_settings(conn: sqlite3.Connection) -> None:
    cur = conn.execute("SELECT COUNT(*) FROM settings")
    if cur.fetchone()[0] > 0:
        return

    defaults = {
        "contact_info": {
            "phone": "+92-21-111-999-000",
            "email": "support@khidmatai.pk",
            "helpline": "0800-55555",
            "address": "KhidmatAI Centre, Karachi, Pakistan",
        },
        "ticker_text": [
            "PM Youth Skill Development Program: Registrations now open!",
            "Emergency Helpline 1122 active 24/7 across all provinces.",
            "BISP Kafalat: New quarterly disbursement starts soon.",
        ],
        "hero_slides": [
            {
                "id": "slide1",
                "type": "color",
                "url": "",
                "bg_color": "#0A5C36",
                "caption": "Pakistan's Premier Welfare Navigator",
                "caption_urdu": "پاکستان کے ہر شہری کے لیے",
                "order": 0,
            }
        ],
    }
    for key, value in defaults.items():
        conn.execute(
            "INSERT OR IGNORE INTO settings (key, value) VALUES (?, ?)",
            (key, json.dumps(value, ensure_ascii=False)),
        )


# ---------------------------------------------------------------------------
# Program CRUD
# ---------------------------------------------------------------------------

def _parse_program(row: sqlite3.Row) -> dict[str, Any]:
    """Convert a raw DB row into a clean dict with parsed JSON fields."""
    d = dict(row)
    for field in ("support", "eligibility", "documents", "locations", "keywords"):
        try:
            d[field] = json.loads(d.get(field, "[]"))
        except Exception:
            d[field] = []
    d["dynamic_saved"] = bool(d.get("dynamic_saved", 0))
    return d


def get_all_programs() -> list[dict[str, Any]]:
    conn = get_connection()
    try:
        rows = conn.execute("SELECT * FROM programs").fetchall()
        return [_parse_program(r) for r in rows]
    finally:
        conn.close()


def get_programs_filtered(
    category: str = "all", q: str = "", province: str = "all"
) -> list[dict[str, Any]]:
    conn = get_connection()
    try:
        query = "SELECT * FROM programs WHERE 1=1"
        params: list[Any] = []

        if category and category != "all":
            query += " AND LOWER(category) LIKE ?"
            params.append(f"%{category.lower()}%")

        if province and province != "all":
            prov = f"%{province.lower()}%"
            query += " AND (LOWER(locations) LIKE ? OR LOWER(description) LIKE ?)"
            params.extend([prov, prov])

        if q:
            search = f"%{q.lower()}%"
            query += (
                " AND (LOWER(title) LIKE ? OR LOWER(description) LIKE ?"
                " OR LOWER(keywords) LIKE ? OR LOWER(category) LIKE ?)"
            )
            params.extend([search] * 4)

        rows = conn.execute(query, params).fetchall()
        return [_parse_program(r) for r in rows]
    finally:
        conn.close()


def insert_program(item: dict[str, Any]) -> bool:
    conn = get_connection()
    try:
        cur = conn.execute(
            """INSERT OR IGNORE INTO programs
               (id,title,category,type,description,address,phone_number,
                support,eligibility,documents,application,locations,keywords,
                latitude,longitude,source_name,source_url,verified_at,dynamic_saved)
               VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            (
                str(item.get("id", "")),
                str(item.get("title", "")),
                str(item.get("category", "")),
                str(item.get("type", "")),
                str(item.get("description", "")),
                str(item.get("address", "")),
                str(item.get("phone_number", "")),
                json.dumps(item.get("support", []), ensure_ascii=False),
                json.dumps(item.get("eligibility", []), ensure_ascii=False),
                json.dumps(item.get("documents", []), ensure_ascii=False),
                str(item.get("application", "")),
                json.dumps(item.get("locations", []), ensure_ascii=False),
                json.dumps(item.get("keywords", []), ensure_ascii=False),
                item.get("latitude"),
                item.get("longitude"),
                str(item.get("source_name", "")),
                str(item.get("source_url", "")),
                str(item.get("verified_at", "")),
                1 if item.get("dynamic_saved") else 0,
            ),
        )
        conn.commit()
        # INSERT OR IGNORE silently skips rows with an existing id —
        # report that as failure so callers can reject duplicates (409).
        return cur.rowcount > 0
    except Exception:
        return False
    finally:
        conn.close()


def update_program(program_id: str, updates: dict[str, Any]) -> bool:
    """Update an existing program. Only provided fields are updated."""
    conn = get_connection()
    try:
        sets: list[str] = []
        params: list[Any] = []
        json_fields = {"support", "eligibility", "documents", "locations", "keywords"}
        for key, val in updates.items():
            if key == "id":
                continue
            if key in json_fields:
                sets.append(f"{key}=?")
                params.append(json.dumps(val, ensure_ascii=False))
            elif key == "dynamic_saved":
                sets.append(f"{key}=?")
                params.append(1 if val else 0)
            else:
                sets.append(f"{key}=?")
                params.append(val)
        if not sets:
            return False
        params.append(program_id)
        cur = conn.execute(
            f"UPDATE programs SET {', '.join(sets)} WHERE id=?",
            params,
        )
        conn.commit()
        return cur.rowcount > 0
    finally:
        conn.close()


def delete_program(program_id: str) -> bool:
    """Delete a program by ID."""
    conn = get_connection()
    try:
        cur = conn.execute("DELETE FROM programs WHERE id=?", (program_id,))
        conn.commit()
        return cur.rowcount > 0
    finally:
        conn.close()


def get_program_by_id(program_id: str) -> dict[str, Any] | None:
    """Fetch a single program by ID."""
    conn = get_connection()
    try:
        row = conn.execute("SELECT * FROM programs WHERE id=?", (program_id,)).fetchone()
        return _parse_program(row) if row else None
    finally:
        conn.close()


def program_count() -> int:
    conn = get_connection()
    try:
        return conn.execute("SELECT COUNT(*) FROM programs").fetchone()[0]
    finally:
        conn.close()


# ---------------------------------------------------------------------------
# University helpers
# ---------------------------------------------------------------------------

def _parse_university(row: sqlite3.Row) -> dict[str, Any]:
    d = dict(row)
    for field in ("support", "eligibility", "documents", "locations", "keywords"):
        try:
            d[field] = json.loads(d.get(field, "[]"))
        except Exception:
            d[field] = []
    return d


def get_all_universities() -> list[dict[str, Any]]:
    conn = get_connection()
    try:
        rows = conn.execute("SELECT * FROM universities").fetchall()
        return [_parse_university(r) for r in rows]
    finally:
        conn.close()


def get_universities_filtered(city: str = "Karachi", q: str = "") -> list[dict[str, Any]]:
    conn = get_connection()
    try:
        query = "SELECT * FROM universities WHERE 1=1"
        params: list[Any] = []

        if city:
            c = f"%{city.lower()}%"
            query += (
                " AND (LOWER(locations) LIKE ? OR LOWER(address) LIKE ?"
                " OR LOWER(description) LIKE ?)"
            )
            params.extend([c, c, c])

        if q:
            search = f"%{q.lower()}%"
            query += " AND (LOWER(title) LIKE ? OR LOWER(keywords) LIKE ?)"
            params.extend([search, search])

        rows = conn.execute(query, params).fetchall()
        return [_parse_university(r) for r in rows]
    finally:
        conn.close()


# ---------------------------------------------------------------------------
# Organization CRUD
# ---------------------------------------------------------------------------

def _parse_org(row: sqlite3.Row) -> dict[str, Any]:
    return dict(row)


def get_organizations(status: str | None = None) -> list[dict[str, Any]]:
    conn = get_connection()
    try:
        if status and status != "all":
            rows = conn.execute(
                "SELECT * FROM organizations WHERE status = ?", (status,)
            ).fetchall()
        else:
            rows = conn.execute("SELECT * FROM organizations").fetchall()
        return [_parse_org(r) for r in rows]
    finally:
        conn.close()


def insert_organization(org: dict[str, Any]) -> None:
    conn = get_connection()
    try:
        pw_hash = org.get("password_hash", "")
        conn.execute(
            """INSERT INTO organizations
               (id,name,org_type,contact,email,password_hash,address,province,description,status,submitted_at)
               VALUES (?,?,?,?,?,?,?,?,?,?,?)""",
            (
                org["id"], org["name"], org["org_type"], org["contact"],
                org["email"], pw_hash, org["address"], org.get("province", ""),
                org.get("description", ""), "pending",
                datetime.now().isoformat(),
            ),
        )
        conn.commit()
    finally:
        conn.close()


def update_org_status(org_id: str, status: str) -> bool:
    conn = get_connection()
    try:
        cur = conn.execute(
            "UPDATE organizations SET status=?, reviewed_at=? WHERE id=?",
            (status, datetime.now().isoformat(), org_id),
        )
        conn.commit()
        return cur.rowcount > 0
    finally:
        conn.close()


def get_org_by_email(email: str) -> dict[str, Any] | None:
    conn = get_connection()
    try:
        row = conn.execute(
            "SELECT * FROM organizations WHERE email=?", (email.strip().lower(),)
        ).fetchone()
        return dict(row) if row else None
    finally:
        conn.close()


def update_org_status_generic(org_id: str, new_status: str) -> bool:
    """Update organization status to any value: approved, rejected, or pending."""
    conn = get_connection()
    try:
        cur = conn.execute(
            "UPDATE organizations SET status=?, reviewed_at=? WHERE id=?",
            (new_status, datetime.now().isoformat(), org_id),
        )
        conn.commit()
        return cur.rowcount > 0
    finally:
        conn.close()


def delete_organization(org_id: str) -> bool:
    """Delete an organization and all of its posts (cascade)."""
    conn = get_connection()
    try:
        conn.execute("DELETE FROM org_posts WHERE org_id=?", (org_id,))
        cur = conn.execute("DELETE FROM organizations WHERE id=?", (org_id,))
        conn.commit()
        return cur.rowcount > 0
    finally:
        conn.close()


def get_org_by_id(org_id: str) -> dict[str, Any] | None:
    conn = get_connection()
    try:
        row = conn.execute("SELECT * FROM organizations WHERE id=?", (org_id,)).fetchone()
        return dict(row) if row else None
    finally:
        conn.close()


def update_org_profile(org_id: str, updates: dict[str, Any]) -> dict[str, Any] | None:
    """Update editable organization profile fields (email, password and status stay fixed)."""
    allowed = (
        "name", "org_type", "contact", "address", "province", "description",
        "website", "city", "services", "opening_hours", "pricing", "discount",
    )
    conn = get_connection()
    try:
        existing = conn.execute("SELECT id FROM organizations WHERE id=?", (org_id,)).fetchone()
        if not existing:
            return None
        sets, params = [], []
        for key in allowed:
            if key in updates and updates[key] is not None:
                sets.append(f"{key}=?")
                params.append(str(updates[key]).strip())
        if sets:
            conn.execute(
                f"UPDATE organizations SET {', '.join(sets)} WHERE id=?",
                (*params, org_id),
            )
            conn.commit()
        row = conn.execute("SELECT * FROM organizations WHERE id=?", (org_id,)).fetchone()
        return dict(row) if row else None
    finally:
        conn.close()


def org_count(status: str | None = None) -> int:
    conn = get_connection()
    try:
        if status:
            return conn.execute(
                "SELECT COUNT(*) FROM organizations WHERE status=?", (status,)
            ).fetchone()[0]
        return conn.execute("SELECT COUNT(*) FROM organizations").fetchone()[0]
    finally:
        conn.close()


# ---------------------------------------------------------------------------
# Organization posts CRUD
# ---------------------------------------------------------------------------

def _parse_org_post(row: sqlite3.Row) -> dict[str, Any]:
    d = dict(row)
    for field in ("eligibility", "documents"):
        try:
            d[field] = json.loads(d.get(field, "[]"))
        except Exception:
            d[field] = []
    return d


def insert_org_post(post: dict[str, Any]) -> dict[str, Any]:
    conn = get_connection()
    try:
        conn.execute(
            """INSERT INTO org_posts
               (id,org_id,org_name,title,description,category,post_type,
                eligibility,documents,location,contact,website,pricing,image,
                status,created_at,reviewed_at)
               VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            (
                post["id"], post["org_id"], post.get("org_name", ""),
                post["title"], post.get("description", ""),
                post.get("category", "General"), post.get("post_type", "Program"),
                json.dumps(post.get("eligibility", []), ensure_ascii=False),
                json.dumps(post.get("documents", []), ensure_ascii=False),
                post.get("location", ""), post.get("contact", ""),
                post.get("website", ""), post.get("pricing", "Free"),
                post.get("image", ""), post.get("status", "pending"),
                datetime.now().isoformat(), "",
            ),
        )
        conn.commit()
    finally:
        conn.close()
    return get_org_post_by_id(post["id"]) or post


def get_org_posts(
    org_id: str | None = None, status: str | None = None,
    category: str = "", q: str = "",
    orgs_approved_only: bool = False,
) -> list[dict[str, Any]]:
    conn = get_connection()
    try:
        query = "SELECT p.* FROM org_posts p"
        params: list[Any] = []
        if orgs_approved_only:
            # Public feed: only posts belonging to currently approved organizations
            # (suspending an org instantly hides its live posts from citizens).
            query += " JOIN organizations o ON o.id = p.org_id AND o.status = 'approved'"
        query += " WHERE 1=1"
        if org_id:
            query += " AND p.org_id=?"
            params.append(org_id)
        if status and status != "all":
            query += " AND p.status=?"
            params.append(status)
        if category and category != "all":
            query += " AND LOWER(p.category) LIKE ?"
            params.append(f"%{category.lower()}%")
        if q:
            search = f"%{q.lower()}%"
            query += " AND (LOWER(p.title) LIKE ? OR LOWER(p.description) LIKE ?)"
            params.extend([search, search])
        query += " ORDER BY p.created_at DESC"
        rows = conn.execute(query, params).fetchall()
        return [_parse_org_post(r) for r in rows]
    finally:
        conn.close()


def get_org_post_by_id(post_id: str) -> dict[str, Any] | None:
    conn = get_connection()
    try:
        row = conn.execute("SELECT * FROM org_posts WHERE id=?", (post_id,)).fetchone()
        return _parse_org_post(row) if row else None
    finally:
        conn.close()


def update_org_post(post_id: str, updates: dict[str, Any]) -> bool:
    """Update post content owned by an organization (status changes use update_org_post_status)."""
    conn = get_connection()
    try:
        json_fields = {"eligibility", "documents"}
        sets: list[str] = []
        params: list[Any] = []
        for key, val in updates.items():
            if key in ("id", "org_id", "org_name", "status", "created_at", "reviewed_at"):
                continue
            sets.append(f"{key}=?")
            if key in json_fields:
                params.append(json.dumps(val, ensure_ascii=False))
            else:
                params.append(str(val))
        if not sets:
            return False
        params.append(post_id)
        cur = conn.execute(
            f"UPDATE org_posts SET {', '.join(sets)} WHERE id=?", params
        )
        conn.commit()
        return cur.rowcount > 0
    finally:
        conn.close()


def update_org_post_status(post_id: str, status: str) -> bool:
    conn = get_connection()
    try:
        cur = conn.execute(
            "UPDATE org_posts SET status=?, reviewed_at=? WHERE id=?",
            (status, datetime.now().isoformat(), post_id),
        )
        conn.commit()
        return cur.rowcount > 0
    finally:
        conn.close()


def delete_org_post(post_id: str) -> bool:
    conn = get_connection()
    try:
        cur = conn.execute("DELETE FROM org_posts WHERE id=?", (post_id,))
        conn.commit()
        return cur.rowcount > 0
    finally:
        conn.close()


def org_post_count(status: str | None = None) -> int:
    conn = get_connection()
    try:
        if status:
            return conn.execute(
                "SELECT COUNT(*) FROM org_posts WHERE status=?", (status,)
            ).fetchone()[0]
        return conn.execute("SELECT COUNT(*) FROM org_posts").fetchone()[0]
    finally:
        conn.close()


# ---------------------------------------------------------------------------
# Analytics events
# ---------------------------------------------------------------------------

def log_event(event_type: str, meta: Any = None) -> None:
    """Best-effort analytics logging; never raises into request handlers."""
    try:
        conn = get_connection()
        try:
            conn.execute(
                "INSERT INTO analytics_events (event_type, meta, created_at) VALUES (?,?,?)",
                (
                    event_type,
                    json.dumps(meta, ensure_ascii=False) if meta is not None else "",
                    datetime.now().isoformat(),
                ),
            )
            conn.commit()
        finally:
            conn.close()
    except Exception:
        pass


def get_analytics_summary() -> dict[str, Any]:
    """Real database counts for the admin analytics panel."""
    conn = get_connection()
    try:
        def _count(sql: str, params: tuple = ()) -> int:
            return conn.execute(sql, params).fetchone()[0]

        return {
            "total_users": _count("SELECT COUNT(*) FROM users"),
            "total_programs": _count("SELECT COUNT(*) FROM programs"),
            "total_orgs": _count("SELECT COUNT(*) FROM organizations"),
            "verified_orgs": _count("SELECT COUNT(*) FROM organizations WHERE status='approved'"),
            "pending_orgs": _count("SELECT COUNT(*) FROM organizations WHERE status='pending'"),
            "org_posts": _count("SELECT COUNT(*) FROM org_posts"),
            "approved_org_posts": _count("SELECT COUNT(*) FROM org_posts WHERE status='approved'"),
            "ai_queries": _count("SELECT COUNT(*) FROM analytics_events WHERE event_type='ai_query'"),
            "program_matches": _count("SELECT COUNT(*) FROM analytics_events WHERE event_type='program_match'"),
            "searches": _count("SELECT COUNT(*) FROM analytics_events WHERE event_type='search'"),
        }
    finally:
        conn.close()


# ---------------------------------------------------------------------------
# Settings CRUD
# ---------------------------------------------------------------------------

def get_setting(key: str, default: Any = None) -> Any:
    conn = get_connection()
    try:
        row = conn.execute("SELECT value FROM settings WHERE key=?", (key,)).fetchone()
        if row is None:
            return default
        try:
            return json.loads(row["value"])
        except Exception:
            return row["value"]
    finally:
        conn.close()


def set_setting(key: str, value: Any) -> None:
    conn = get_connection()
    try:
        raw = json.dumps(value, ensure_ascii=False) if not isinstance(value, str) else value
        conn.execute(
            "INSERT OR REPLACE INTO settings (key, value) VALUES (?, ?)",
            (key, raw),
        )
        conn.commit()
    finally:
        conn.close()


# ---------------------------------------------------------------------------
# User CRUD
# ---------------------------------------------------------------------------

def create_user(
    name: str, email: str, password: str,
    phone: str = "", city: str = "", cnic: str = "",
) -> dict | None:
    conn = get_connection()
    try:
        pw_hash = bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()
        cur = conn.execute(
            """INSERT INTO users (name,email,password_hash,phone,city,cnic,created_at)
               VALUES (?,?,?,?,?,?,?)""",
            (name, email, pw_hash, phone, city, cnic, datetime.now().isoformat()),
        )
        conn.commit()
        row = conn.execute("SELECT * FROM users WHERE id=?", (cur.lastrowid,)).fetchone()
        return _parse_user(row) if row else None
    except sqlite3.IntegrityError:
        return None
    finally:
        conn.close()


def get_user_by_email(email: str) -> dict | None:
    conn = get_connection()
    try:
        row = conn.execute("SELECT * FROM users WHERE email=?", (email,)).fetchone()
        return _parse_user(row) if row else None
    finally:
        conn.close()


def get_user_by_id(user_id: int) -> dict | None:
    conn = get_connection()
    try:
        row = conn.execute("SELECT * FROM users WHERE id=?", (user_id,)).fetchone()
        return _parse_user(row) if row else None
    finally:
        conn.close()


def update_user_profile(
    user_id: int,
    name: str | None = None,
    phone: str | None = None,
    city: str | None = None,
    cnic: str | None = None,
) -> dict | None:
    """Update editable profile fields (email stays fixed as the login identity)."""
    conn = get_connection()
    try:
        existing = conn.execute("SELECT id FROM users WHERE id=?", (user_id,)).fetchone()
        if not existing:
            return None
        updates: dict[str, str] = {}
        if name is not None and name.strip():
            updates["name"] = name.strip()[:200]
        if phone is not None:
            updates["phone"] = phone.strip()[:30]
        if city is not None:
            updates["city"] = city.strip()[:100]
        if cnic is not None:
            updates["cnic"] = cnic.strip()[:20]
        if updates:
            set_clause = ", ".join(f"{k}=?" for k in updates)
            conn.execute(
                f"UPDATE users SET {set_clause} WHERE id=?",
                (*updates.values(), user_id),
            )
            conn.commit()
        row = conn.execute("SELECT * FROM users WHERE id=?", (user_id,)).fetchone()
        return _parse_user(row) if row else None
    finally:
        conn.close()


def update_user_applications(user_id: int, applications: list) -> None:
    conn = get_connection()
    try:
        conn.execute(
            "UPDATE users SET applications=? WHERE id=?",
            (json.dumps(applications, ensure_ascii=False), user_id),
        )
        conn.commit()
    finally:
        conn.close()


def _parse_user(row: sqlite3.Row | None) -> dict | None:
    if not row:
        return None
    d = dict(row)
    try:
        d["applications"] = json.loads(d.get("applications", "[]"))
    except Exception:
        d["applications"] = []
    d.pop("password_hash", None)
    return d


def verify_password(plain: str, hashed: str) -> bool:
    try:
        return bcrypt.checkpw(plain.encode(), hashed.encode())
    except Exception:
        return False


def user_count() -> int:
    conn = get_connection()
    try:
        return conn.execute("SELECT COUNT(*) FROM users").fetchone()[0]
    finally:
        conn.close()


# ---------------------------------------------------------------------------
# Facility CRUD (geo-collected locations)
# ---------------------------------------------------------------------------

def get_all_facilities() -> list[dict[str, Any]]:
    conn = get_connection()
    try:
        rows = conn.execute("SELECT * FROM facilities ORDER BY city, name").fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()


def get_facilities_filtered(
    city: str = "all", category: str = "all"
) -> list[dict[str, Any]]:
    conn = get_connection()
    try:
        query = "SELECT * FROM facilities WHERE 1=1"
        params: list[Any] = []
        if city and city.lower() != "all":
            query += " AND LOWER(city) = ?"
            params.append(city.lower())
        if category and category.lower() != "all":
            query += " AND LOWER(category) = ?"
            params.append(category.lower())
        query += " ORDER BY name"
        rows = conn.execute(query, params).fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()


def insert_facility(fac: dict[str, Any]) -> bool:
    """Insert a facility. Returns False if duplicate (by lat/lon proximity or name)."""
    conn = get_connection()
    try:
        # Duplicate check: same name in same city
        dup = conn.execute(
            "SELECT id FROM facilities WHERE LOWER(name)=? AND LOWER(city)=?",
            (fac.get("name", "").strip().lower(), fac.get("city", "").strip().lower()),
        ).fetchone()
        if dup:
            return False
        conn.execute(
            """INSERT INTO facilities
               (id,name,category,city,zone,address,phone,facility_type,lat,lon,source,collected_at)
               VALUES (?,?,?,?,?,?,?,?,?,?,?,?)""",
            (
                fac["id"], fac["name"], fac.get("category", ""),
                fac.get("city", ""), fac.get("zone", ""),
                fac.get("address", ""), fac.get("phone", ""),
                fac.get("facility_type", ""),
                fac.get("lat"), fac.get("lon"),
                fac.get("source", "overpass"),
                datetime.now().isoformat(),
            ),
        )
        conn.commit()
        return True
    except Exception:
        return False
    finally:
        conn.close()


def facility_count() -> int:
    conn = get_connection()
    try:
        return conn.execute("SELECT COUNT(*) FROM facilities").fetchone()[0]
    finally:
        conn.close()
