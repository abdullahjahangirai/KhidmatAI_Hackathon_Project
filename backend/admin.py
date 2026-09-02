"""KhidmatAI Admin Dashboard API.

All data is persisted in SQLite via backend.database.
Endpoints are mounted under /api via the admin_router.
"""

from __future__ import annotations

import json
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any

from fastapi import APIRouter, File, Header, HTTPException, UploadFile
from pydantic import BaseModel

from . import database as db

ADMIN_TOKEN = "khidmatai-admin-2024"
ADMIN_USERNAME = "admin"
ADMIN_PASSWORD = "khidmatai2024"

BASE_DIR = Path(__file__).resolve().parent.parent
UPLOAD_DIR = BASE_DIR / "frontend" / "uploads" / "hero"

_ALLOWED_IMAGE_EXT = {".jpg", ".jpeg", ".png", ".webp", ".gif"}
_ALLOWED_VIDEO_EXT = {".mp4", ".webm", ".ogg", ".mov", ".m4v"}
_MAX_IMAGE_BYTES = 8 * 1024 * 1024   # 8 MB
_MAX_VIDEO_BYTES = 60 * 1024 * 1024  # 60 MB


# ---------------------------------------------------------------------------
# Auth helper
# ---------------------------------------------------------------------------
def verify_admin(x_admin_key: str | None = Header(default=None)) -> None:
    if x_admin_key != ADMIN_TOKEN:
        raise HTTPException(status_code=401, detail="Unauthorized. Invalid or missing admin token.")


def _public_org(org: dict) -> dict:
    """Strip secrets (password hash) before an org leaves the API."""
    org.pop("password_hash", None)
    return org


# ---------------------------------------------------------------------------
# Pydantic models
# ---------------------------------------------------------------------------
class LoginRequest(BaseModel):
    username: str
    password: str


class ContactInfoUpdate(BaseModel):
    phone: str = ""
    email: str = ""
    helpline: str = ""
    address: str = ""


class TickerUpdate(BaseModel):
    ticker_text: list[str]


class HeroSlideAdd(BaseModel):
    title: str = ""
    description: str = ""
    image: str = ""          # image URL or /static/uploads/hero/... path
    video: str = ""          # short video URL or /static/uploads/hero/... path
    button_text: str = ""
    button_url: str = ""
    bg_color: str = ""       # fallback background for slides without media
    active: bool = True


class HeroSlideUpdate(BaseModel):
    title: str | None = None
    description: str | None = None
    image: str | None = None
    video: str | None = None
    button_text: str | None = None
    button_url: str | None = None
    bg_color: str | None = None
    active: bool | None = None


class SlideReorder(BaseModel):
    ordered_ids: list[str]


class AlertAdd(BaseModel):
    text: str


class AlertUpdate(BaseModel):
    text: str | None = None
    active: bool | None = None


class AlertReorder(BaseModel):
    ordered_ids: list[str]


class OrgRegistration(BaseModel):
    name: str
    org_type: str
    contact: str
    email: str
    password: str = ""
    address: str
    province: str = ""
    description: str = ""


class OrgStatusUpdate(BaseModel):
    status: str  # "approved", "rejected", "pending", or "suspended"


class OrgEdit(BaseModel):
    name: str | None = None
    org_type: str | None = None
    contact: str | None = None
    address: str | None = None
    province: str | None = None
    description: str | None = None
    website: str | None = None
    city: str | None = None
    services: str | None = None
    opening_hours: str | None = None
    pricing: str | None = None
    discount: str | None = None


class ProgramCreate(BaseModel):
    id: str = ""
    title: str
    category: str = ""
    type: str = ""
    description: str = ""
    address: str = ""
    phone_number: str = ""
    support: list[str] = []
    eligibility: list[str] = []
    documents: list[str] = []
    application: str = ""
    locations: list[str] = []
    keywords: list[str] = []
    source_name: str = ""
    source_url: str = ""


class ProgramUpdate(BaseModel):
    title: str | None = None
    category: str | None = None
    type: str | None = None
    description: str | None = None
    address: str | None = None
    phone_number: str | None = None
    support: list[str] | None = None
    eligibility: list[str] | None = None
    documents: list[str] | None = None
    application: str | None = None
    locations: list[str] | None = None
    keywords: list[str] | None = None
    source_name: str | None = None
    source_url: str | None = None


# ---------------------------------------------------------------------------
# Router
# ---------------------------------------------------------------------------
router = APIRouter(prefix="/api")


# ===================================================================
# AUTH
# ===================================================================
@router.post("/admin/login")
def admin_login(req: LoginRequest):
    if req.username.strip() == ADMIN_USERNAME and req.password.strip() == ADMIN_PASSWORD:
        return {"success": True, "token": ADMIN_TOKEN, "username": ADMIN_USERNAME}
    raise HTTPException(status_code=401, detail="Invalid credentials.")


# ===================================================================
# ANALYTICS (real SQLite counts — lightweight hackathon analytics)
# ===================================================================

@router.get("/admin/analytics")
def admin_analytics(x_admin_key: str | None = Header(default=None)):
    verify_admin(x_admin_key)
    return {"success": True, "analytics": db.get_analytics_summary()}


# ===================================================================
# SETTINGS (contact, ticker, hero slides, alerts) — backed by SQLite settings table
# ===================================================================

def _normalize_slide(s: dict) -> dict:
    """Map any stored slide (legacy or current schema) to the rich schema."""
    url = str(s.get("url") or "")
    legacy_type = str(s.get("type") or "")
    return {
        "id": s.get("id", ""),
        "title": s.get("title") or s.get("caption") or "",
        "description": s.get("description") or "",
        "image": s.get("image") or (url if legacy_type == "image" else ""),
        "video": s.get("video") or (url if legacy_type == "video" else ""),
        "button_text": s.get("button_text") or "",
        "button_url": s.get("button_url") or "",
        "bg_color": s.get("bg_color") or "",
        "active": s.get("active", True),
        "order": s.get("order", 0),
    }


def _normalize_landing_slide(s: dict) -> dict:
    """Map any stored landing hero slide to the current schema."""
    return {
        "id": s.get("id", ""),
        "title": s.get("title", ""),
        "description": s.get("description", ""),
        "image": s.get("image", ""),
        "video": s.get("video", ""),
        "button_text": s.get("button_text", ""),
        "button_url": s.get("button_url", ""),
        "active": bool(s.get("active", True)),
        "order": int(s.get("order", 0)),
    }


# Default landing hero shown until the admin customizes it. Completely
# independent from the dashboard hero slider ("hero_slides" setting).
_DEFAULT_LANDING_SLIDES = [
    {
        "id": "landing_default",
        "title": "Helping people find the right support when they need it most.",
        "description": "KhidmatAI brings welfare programs, education opportunities, healthcare pathways, financial assistance and local services into one simple experience.",
        "image": "/static/assets/hero-community.png",
        "video": "",
        "button_text": "Find support",
        "button_url": "/register",
        "active": True,
        "order": 0,
    }
]


def _get_landing_slides() -> list[dict]:
    slides = db.get_setting("landing_hero_slides", None)
    if slides is None:
        return [dict(s) for s in _DEFAULT_LANDING_SLIDES]
    return slides


def _get_alerts() -> list[dict]:
    """Read alerts; migrate legacy ticker_text entries on first use."""
    alerts = db.get_setting("alerts", None)
    if alerts is None:
        legacy = db.get_setting("ticker_text", [])
        if not isinstance(legacy, list):
            legacy = []
        alerts = [
            {"id": f"alert_{uuid.uuid4().hex[:8]}", "text": str(t), "active": True, "order": i}
            for i, t in enumerate(legacy)
        ]
        # persist the migration immediately so alert IDs stay stable across reads
        db.set_setting("alerts", alerts)
    return sorted(alerts, key=lambda a: a.get("order", 0))


@router.get("/admin/settings")
def admin_get_settings(x_admin_key: str | None = Header(default=None)):
    verify_admin(x_admin_key)
    slides = sorted(db.get_setting("hero_slides", []), key=lambda s: s.get("order", 0))
    return {
        "contact_info": db.get_setting("contact_info", {}),
        "landing_hero_slides": [_normalize_landing_slide(s) for s in sorted(_get_landing_slides(), key=lambda s: s.get("order", 0))],
        "ticker_text": db.get_setting("ticker_text", []),
        "alerts": _get_alerts(),
        "hero_slides": [_normalize_slide(s) for s in slides],
        "organizations": [_public_org(o) for o in db.get_organizations()],
    }


@router.post("/admin/settings/contact")
def admin_update_contact(update: ContactInfoUpdate, x_admin_key: str | None = Header(default=None)):
    verify_admin(x_admin_key)
    ci = db.get_setting("contact_info", {})
    if update.phone:
        ci["phone"] = update.phone
    if update.email:
        ci["email"] = update.email
    if update.helpline:
        ci["helpline"] = update.helpline
    if update.address:
        ci["address"] = update.address
    db.set_setting("contact_info", ci)
    return {"success": True, "contact_info": ci}


@router.post("/admin/settings/ticker")
def admin_update_ticker(update: TickerUpdate, x_admin_key: str | None = Header(default=None)):
    verify_admin(x_admin_key)
    db.set_setting("ticker_text", update.ticker_text)
    return {"success": True, "ticker_text": update.ticker_text}


# ===================================================================
# HERO SLIDES
# ===================================================================

@router.post("/admin/hero-slides/upload")
async def admin_upload_slide_media(
    x_admin_key: str | None = Header(default=None),
    file: UploadFile = File(...),
):
    """Upload a hero image or short video; returns the served URL."""
    verify_admin(x_admin_key)
    ext = Path(file.filename or "").suffix.lower()
    if ext in _ALLOWED_IMAGE_EXT:
        kind, max_bytes = "image", _MAX_IMAGE_BYTES
    elif ext in _ALLOWED_VIDEO_EXT:
        kind, max_bytes = "video", _MAX_VIDEO_BYTES
    else:
        raise HTTPException(
            status_code=400,
            detail="Unsupported file type. Allowed: JPG, PNG, WEBP, GIF images and MP4, WEBM, OGG, MOV videos.",
        )

    data = await file.read()
    if not data:
        raise HTTPException(status_code=400, detail="The uploaded file is empty.")
    if len(data) > max_bytes:
        raise HTTPException(
            status_code=413,
            detail=f"File too large. Maximum {max_bytes // (1024 * 1024)} MB for {kind}s.",
        )

    UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
    fname = f"{uuid.uuid4().hex}{ext}"
    (UPLOAD_DIR / fname).write_bytes(data)
    return {"success": True, "kind": kind, "url": f"/static/uploads/hero/{fname}"}


@router.post("/admin/hero-slides/add")
def admin_add_slide(slide: HeroSlideAdd, x_admin_key: str | None = Header(default=None)):
    verify_admin(x_admin_key)
    slides = db.get_setting("hero_slides", [])
    new_slide = {
        "id": f"slide_{uuid.uuid4().hex[:8]}",
        "title": slide.title.strip(),
        "description": slide.description.strip(),
        "image": slide.image.strip(),
        "video": slide.video.strip(),
        "button_text": slide.button_text.strip(),
        "button_url": slide.button_url.strip(),
        "bg_color": slide.bg_color.strip(),
        "active": bool(slide.active),
        "order": len(slides),
    }
    slides.append(new_slide)
    db.set_setting("hero_slides", slides)
    return {"success": True, "slide": _normalize_slide(new_slide)}


@router.put("/admin/hero-slides/{slide_id}")
def admin_update_slide(
    slide_id: str, updates: HeroSlideUpdate,
    x_admin_key: str | None = Header(default=None),
):
    verify_admin(x_admin_key)
    slides = db.get_setting("hero_slides", [])
    for s in slides:
        if s.get("id") == slide_id:
            data = {k: v for k, v in updates.model_dump().items() if v is not None}
            if not data:
                raise HTTPException(status_code=400, detail="No fields to update.")
            s.update(data)
            db.set_setting("hero_slides", slides)
            return {"success": True, "slide": _normalize_slide(s)}
    raise HTTPException(status_code=404, detail="Slide not found.")


@router.delete("/admin/hero-slides/{slide_id}")
def admin_delete_slide(slide_id: str, x_admin_key: str | None = Header(default=None)):
    verify_admin(x_admin_key)
    slides = [s for s in db.get_setting("hero_slides", []) if s.get("id") != slide_id]
    db.set_setting("hero_slides", slides)
    return {"success": True}


@router.post("/admin/hero-slides/reorder")
def admin_reorder_slides(reorder: SlideReorder, x_admin_key: str | None = Header(default=None)):
    verify_admin(x_admin_key)
    slides = db.get_setting("hero_slides", [])
    slides_map = {s["id"]: s for s in slides}
    reordered = []
    for i, sid in enumerate(reorder.ordered_ids):
        if sid in slides_map:
            slides_map[sid]["order"] = i
            reordered.append(slides_map[sid])
    # keep any ids not included in the payload at the end
    for s in slides:
        if s.get("id") not in reorder.ordered_ids:
            s["order"] = len(reordered)
            reordered.append(s)
    db.set_setting("hero_slides", reordered)
    return {"success": True, "hero_slides": [_normalize_slide(s) for s in reordered]}


# ===================================================================
# LANDING PAGE HERO SLIDES — fully separate from the dashboard hero slider
# ===================================================================

class LandingHeroSlideAdd(BaseModel):
    title: str = ""
    description: str = ""
    image: str = ""
    video: str = ""
    button_text: str = ""
    button_url: str = ""
    active: bool = True


class LandingHeroSlideUpdate(BaseModel):
    title: str | None = None
    description: str | None = None
    image: str | None = None
    video: str | None = None
    button_text: str | None = None
    button_url: str | None = None
    active: bool | None = None


@router.get("/admin/landing-hero")
def admin_get_landing_slides(x_admin_key: str | None = Header(default=None)):
    verify_admin(x_admin_key)
    slides = [_normalize_landing_slide(s) for s in sorted(_get_landing_slides(), key=lambda s: s.get("order", 0))]
    return {"landing_hero_slides": slides}


@router.post("/admin/landing-hero/upload")
async def admin_upload_landing_hero_media(
    x_admin_key: str | None = Header(default=None),
    file: UploadFile = File(...),
):
    """Upload a landing hero image or short video; returns the served URL."""
    return await admin_upload_slide_media(x_admin_key=x_admin_key, file=file)


@router.post("/admin/landing-hero/add")
def admin_add_landing_slide(slide: LandingHeroSlideAdd, x_admin_key: str | None = Header(default=None)):
    verify_admin(x_admin_key)
    slides = _get_landing_slides()
    new_slide = {
        "id": f"lslide_{uuid.uuid4().hex[:8]}",
        "title": slide.title.strip(),
        "description": slide.description.strip(),
        "image": slide.image.strip(),
        "video": slide.video.strip(),
        "button_text": slide.button_text.strip(),
        "button_url": slide.button_url.strip(),
        "active": bool(slide.active),
        "order": len(slides),
    }
    slides.append(new_slide)
    db.set_setting("landing_hero_slides", slides)
    return {"success": True, "slide": _normalize_landing_slide(new_slide)}


@router.put("/admin/landing-hero/{slide_id}")
def admin_update_landing_slide(slide_id: str, updates: LandingHeroSlideUpdate, x_admin_key: str | None = Header(default=None)):
    verify_admin(x_admin_key)
    slides = _get_landing_slides()
    for s in slides:
        if s.get("id") == slide_id:
            data = {k: v for k, v in updates.model_dump().items() if v is not None}
            if not data:
                raise HTTPException(status_code=400, detail="No fields to update.")
            s.update(data)
            db.set_setting("landing_hero_slides", slides)
            return {"success": True, "slide": _normalize_landing_slide(s)}
    raise HTTPException(status_code=404, detail="Landing slide not found.")


@router.delete("/admin/landing-hero/{slide_id}")
def admin_delete_landing_slide(slide_id: str, x_admin_key: str | None = Header(default=None)):
    verify_admin(x_admin_key)
    slides = [s for s in _get_landing_slides() if s.get("id") != slide_id]
    db.set_setting("landing_hero_slides", slides)
    return {"success": True}


@router.post("/admin/landing-hero/reorder")
def admin_reorder_landing_slides(reorder: SlideReorder, x_admin_key: str | None = Header(default=None)):
    verify_admin(x_admin_key)
    slides = _get_landing_slides()
    slides_map = {s.get("id"): s for s in slides}
    reordered = []
    for i, sid in enumerate(reorder.ordered_ids):
        if sid in slides_map:
            slides_map[sid]["order"] = i
            reordered.append(slides_map[sid])
    # keep any ids not included in the payload at the end
    for s in slides:
        if s.get("id") not in reorder.ordered_ids:
            s["order"] = len(reordered)
            reordered.append(s)
    db.set_setting("landing_hero_slides", reordered)
    return {"success": True, "landing_hero_slides": [_normalize_landing_slide(s) for s in reordered]}


# ===================================================================
# TICKER & ALERTS
# ===================================================================

@router.get("/admin/alerts")
def admin_get_alerts(x_admin_key: str | None = Header(default=None)):
    verify_admin(x_admin_key)
    return {"alerts": _get_alerts()}


@router.post("/admin/alerts/add")
def admin_add_alert(req: AlertAdd, x_admin_key: str | None = Header(default=None)):
    verify_admin(x_admin_key)
    text = req.text.strip()
    if not text:
        raise HTTPException(status_code=400, detail="Alert text cannot be empty.")
    alerts = _get_alerts()
    alert = {"id": f"alert_{uuid.uuid4().hex[:8]}", "text": text, "active": True, "order": len(alerts)}
    alerts.append(alert)
    db.set_setting("alerts", alerts)
    return {"success": True, "alert": alert}


@router.put("/admin/alerts/{alert_id}")
def admin_update_alert(
    alert_id: str, updates: AlertUpdate,
    x_admin_key: str | None = Header(default=None),
):
    verify_admin(x_admin_key)
    alerts = _get_alerts()
    for a in alerts:
        if a.get("id") == alert_id:
            data = {k: v for k, v in updates.model_dump().items() if v is not None}
            if not data:
                raise HTTPException(status_code=400, detail="No fields to update.")
            a.update(data)
            db.set_setting("alerts", alerts)
            return {"success": True, "alert": a}
    raise HTTPException(status_code=404, detail="Alert not found.")


@router.delete("/admin/alerts/{alert_id}")
def admin_delete_alert(alert_id: str, x_admin_key: str | None = Header(default=None)):
    verify_admin(x_admin_key)
    alerts = [a for a in _get_alerts() if a.get("id") != alert_id]
    db.set_setting("alerts", alerts)
    return {"success": True}


@router.post("/admin/alerts/reorder")
def admin_reorder_alerts(reorder: AlertReorder, x_admin_key: str | None = Header(default=None)):
    verify_admin(x_admin_key)
    alerts = _get_alerts()
    alert_map = {a["id"]: a for a in alerts}
    reordered = []
    for i, aid in enumerate(reorder.ordered_ids):
        if aid in alert_map:
            alert_map[aid]["order"] = i
            reordered.append(alert_map[aid])
    for a in alerts:
        if a.get("id") not in reorder.ordered_ids:
            a["order"] = len(reordered)
            reordered.append(a)
    db.set_setting("alerts", reordered)
    return {"success": True, "alerts": reordered}


# ===================================================================
# ORGANIZATION APPROVALS
# ===================================================================

@router.get("/admin/organizations")
def admin_get_orgs(x_admin_key: str | None = Header(default=None)):
    verify_admin(x_admin_key)
    return {"organizations": [_public_org(o) for o in db.get_organizations()]}


@router.get("/admin/organizations/pending")
def admin_get_pending_orgs(x_admin_key: str | None = Header(default=None)):
    verify_admin(x_admin_key)
    return {"organizations": [_public_org(o) for o in db.get_organizations(status="pending")]}


@router.put("/admin/organizations/{org_id}/status")
def admin_update_org_status(
    org_id: str, body: OrgStatusUpdate,
    x_admin_key: str | None = Header(default=None),
):
    verify_admin(x_admin_key)
    allowed = {"approved", "rejected", "pending", "suspended"}
    if body.status not in allowed:
        raise HTTPException(status_code=400, detail=f"Invalid status. Must be one of: {', '.join(sorted(allowed))}")
    if not db.update_org_status_generic(org_id, body.status):
        raise HTTPException(status_code=404, detail="Organization not found.")
    return {"success": True, "status": body.status}


@router.post("/admin/organizations/{org_id}/approve")
def admin_approve_org(org_id: str, x_admin_key: str | None = Header(default=None)):
    verify_admin(x_admin_key)
    if not db.update_org_status(org_id, "approved"):
        raise HTTPException(status_code=404, detail="Organization not found.")
    return {"success": True}


@router.post("/admin/organizations/{org_id}/reject")
def admin_reject_org(org_id: str, x_admin_key: str | None = Header(default=None)):
    verify_admin(x_admin_key)
    if not db.update_org_status(org_id, "rejected"):
        raise HTTPException(status_code=404, detail="Organization not found.")
    return {"success": True}


@router.post("/admin/organizations/{org_id}/suspend")
def admin_suspend_org(org_id: str, x_admin_key: str | None = Header(default=None)):
    """Suspend an organization — blocks its login and dashboard access instantly."""
    verify_admin(x_admin_key)
    if not db.update_org_status(org_id, "suspended"):
        raise HTTPException(status_code=404, detail="Organization not found.")
    return {"success": True, "status": "suspended"}


@router.put("/admin/organizations/{org_id}")
def admin_edit_org(
    org_id: str, updates: OrgEdit,
    x_admin_key: str | None = Header(default=None),
):
    """Admin-side edit of an organization profile (cannot change email/status)."""
    verify_admin(x_admin_key)
    data = {k: v for k, v in updates.model_dump().items() if v is not None}
    if not data:
        raise HTTPException(status_code=400, detail="No fields to update.")
    updated = db.update_org_profile(org_id, data)
    if not updated:
        raise HTTPException(status_code=404, detail="Organization not found.")
    updated.pop("password_hash", None)
    return {"success": True, "organization": updated}


@router.delete("/admin/organizations/{org_id}")
def admin_delete_org(org_id: str, x_admin_key: str | None = Header(default=None)):
    verify_admin(x_admin_key)
    if not db.delete_organization(org_id):
        raise HTTPException(status_code=404, detail="Organization not found.")
    return {"success": True}


# ===================================================================
# ORGANIZATION POSTS VERIFICATION
# ===================================================================

@router.get("/admin/org-posts")
def admin_get_org_posts(
    status: str = "all",
    x_admin_key: str | None = Header(default=None),
):
    """All organization posts with their verification status (for admin review)."""
    verify_admin(x_admin_key)
    posts = db.get_org_posts(status=status)
    return {"posts": posts, "count": len(posts)}


@router.post("/admin/org-posts/{post_id}/approve")
def admin_approve_org_post(post_id: str, x_admin_key: str | None = Header(default=None)):
    verify_admin(x_admin_key)
    if not db.update_org_post_status(post_id, "approved"):
        raise HTTPException(status_code=404, detail="Post not found.")
    return {"success": True, "status": "approved"}


@router.post("/admin/org-posts/{post_id}/reject")
def admin_reject_org_post(post_id: str, x_admin_key: str | None = Header(default=None)):
    verify_admin(x_admin_key)
    if not db.update_org_post_status(post_id, "rejected"):
        raise HTTPException(status_code=404, detail="Post not found.")
    return {"success": True, "status": "rejected"}


@router.delete("/admin/org-posts/{post_id}")
def admin_delete_org_post(post_id: str, x_admin_key: str | None = Header(default=None)):
    verify_admin(x_admin_key)
    if not db.delete_org_post(post_id):
        raise HTTPException(status_code=404, detail="Post not found.")
    return {"success": True}


# ===================================================================
# PROGRAM MANAGEMENT (CRUD)
# ===================================================================

@router.get("/admin/programs")
def admin_get_programs(
    q: str = "", category: str = "all", province: str = "all",
    x_admin_key: str | None = Header(default=None),
):
    verify_admin(x_admin_key)
    programs = db.get_programs_filtered(category=category, q=q, province=province)
    return {"programs": programs, "count": len(programs)}


@router.post("/admin/programs/add")
def admin_add_program(prog: ProgramCreate, x_admin_key: str | None = Header(default=None)):
    verify_admin(x_admin_key)
    program_id = prog.id.strip() if prog.id.strip() else f"prog_{uuid.uuid4().hex[:10]}"
    item = {
        "id": program_id,
        "title": prog.title.strip(),
        "category": prog.category.strip(),
        "type": prog.type.strip(),
        "description": prog.description.strip(),
        "address": prog.address.strip(),
        "phone_number": prog.phone_number.strip(),
        "support": prog.support,
        "eligibility": prog.eligibility,
        "documents": prog.documents,
        "application": prog.application.strip(),
        "locations": prog.locations,
        "keywords": prog.keywords,
        "source_name": prog.source_name.strip(),
        "source_url": prog.source_url.strip(),
        "verified_at": datetime.now().isoformat(),
    }
    ok = db.insert_program(item)
    if not ok:
        raise HTTPException(status_code=409, detail="Program with this ID already exists.")
    return {"success": True, "program": item}


@router.put("/admin/programs/{program_id}")
def admin_update_program(
    program_id: str, updates: ProgramUpdate,
    x_admin_key: str | None = Header(default=None),
):
    verify_admin(x_admin_key)
    data = {k: v for k, v in updates.model_dump().items() if v is not None}
    if not data:
        raise HTTPException(status_code=400, detail="No fields to update.")
    ok = db.update_program(program_id, data)
    if not ok:
        raise HTTPException(status_code=404, detail="Program not found.")
    return {"success": True}


@router.delete("/admin/programs/{program_id}")
def admin_delete_program(program_id: str, x_admin_key: str | None = Header(default=None)):
    verify_admin(x_admin_key)
    if not db.delete_program(program_id):
        raise HTTPException(status_code=404, detail="Program not found.")
    return {"success": True}


# ===================================================================
# PUBLIC ENDPOINTS (no auth required)
# ===================================================================

@router.get("/public/settings")
def public_settings():
    slides = [_normalize_slide(s) for s in sorted(db.get_setting("hero_slides", []), key=lambda s: s.get("order", 0))]
    landing = [_normalize_landing_slide(s) for s in sorted(_get_landing_slides(), key=lambda s: s.get("order", 0))]
    return {
        "contact_info": db.get_setting("contact_info", {}),
        "landing_hero_slides": [s for s in landing if s.get("active", True)],
        "ticker_text": db.get_setting("ticker_text", []),
        "alerts": [a for a in _get_alerts() if a.get("active", True)],
        "hero_slides": [s for s in slides if s.get("active", True)],
    }


@router.get("/public/approved-organizations")
def public_approved_orgs():
    return {"organizations": [_public_org(o) for o in db.get_organizations(status="approved")]}


@router.post("/organizations/register")
def register_organization(reg: OrgRegistration):
    pw_hash = ""
    if reg.password:
        import bcrypt as _bcrypt
        pw_hash = _bcrypt.hashpw(reg.password.encode(), _bcrypt.gensalt()).decode()
    new_org = {
        "id": f"org_{uuid.uuid4().hex[:10]}",
        "name": reg.name.strip(),
        "org_type": reg.org_type.strip(),
        "contact": reg.contact.strip(),
        "email": reg.email.strip().lower(),
        "password_hash": pw_hash,
        "address": reg.address.strip(),
        "province": reg.province.strip(),
        "description": reg.description.strip(),
    }
    db.insert_organization(new_org)
    return {
        "success": True,
        "message": "Registration submitted. Your organization will be reviewed and approved by admin.",
        "id": new_org["id"],
    }
