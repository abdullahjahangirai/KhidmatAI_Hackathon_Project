import json
import os
import time
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any

from fastapi import APIRouter, HTTPException, Header, Request
from pydantic import BaseModel

BASE_DIR = Path(__file__).resolve().parent.parent
ADMIN_DATA_FILE = BASE_DIR / "data" / "admin_data.json"

ADMIN_TOKEN = "khidmatai-admin-2024"
ADMIN_USERNAME = "admin"
ADMIN_PASSWORD = "khidmatai2024"

# ---------------------------------------------------------------------------
# Data helpers
# ---------------------------------------------------------------------------

def _default_admin_data() -> dict:
    return {
        "contact_info": {
            "phone": "+92-21-111-999-000",
            "email": "support@khidmatai.pk",
            "helpline": "0800-55555",
            "address": "KhidmatAI Centre, Karachi, Pakistan"
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
                "caption_urdu": "\u067e\u0627\u06a9\u0633\u062a\u0627\u0646 \u06a9\u06d2 \u06c1\u0631 \u0634\u06c1\u0631\u06cc \u06a9\u06d2 \u0644\u06cc\u06d2",
                "order": 0
            }
        ],
        "organizations": []
    }


def load_admin_data() -> dict:
    if not ADMIN_DATA_FILE.exists():
        data = _default_admin_data()
        save_admin_data(data)
        return data
    try:
        return json.loads(ADMIN_DATA_FILE.read_text(encoding="utf-8"))
    except Exception:
        return _default_admin_data()


def save_admin_data(data: dict) -> None:
    ADMIN_DATA_FILE.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")


def verify_admin(x_admin_key: str | None = Header(default=None)) -> None:
    if x_admin_key != ADMIN_TOKEN:
        raise HTTPException(status_code=401, detail="Unauthorized. Invalid or missing admin token.")


# ---------------------------------------------------------------------------
# Models
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
    type: str = "color"
    url: str = ""
    bg_color: str = "#0A5C36"
    caption: str = ""
    caption_urdu: str = ""


class SlideReorder(BaseModel):
    ordered_ids: list[str]


class OrgRegistration(BaseModel):
    name: str
    org_type: str
    contact: str
    email: str
    address: str
    province: str = ""
    description: str = ""


# ---------------------------------------------------------------------------
# Router
# ---------------------------------------------------------------------------

router = APIRouter(prefix="/api")


# Auth
@router.post("/admin/login")
def admin_login(req: LoginRequest):
    if req.username.strip() == ADMIN_USERNAME and req.password.strip() == ADMIN_PASSWORD:
        return {"success": True, "token": ADMIN_TOKEN, "username": ADMIN_USERNAME}
    raise HTTPException(status_code=401, detail="Invalid credentials.")


# Settings
@router.get("/admin/settings")
def admin_get_settings(x_admin_key: str | None = Header(default=None)):
    verify_admin(x_admin_key)
    return load_admin_data()


@router.post("/admin/settings/contact")
def admin_update_contact(update: ContactInfoUpdate, x_admin_key: str | None = Header(default=None)):
    verify_admin(x_admin_key)
    data = load_admin_data()
    ci = data.get("contact_info", {})
    if update.phone:
        ci["phone"] = update.phone
    if update.email:
        ci["email"] = update.email
    if update.helpline:
        ci["helpline"] = update.helpline
    if update.address:
        ci["address"] = update.address
    data["contact_info"] = ci
    save_admin_data(data)
    return {"success": True, "contact_info": ci}


@router.post("/admin/settings/ticker")
def admin_update_ticker(update: TickerUpdate, x_admin_key: str | None = Header(default=None)):
    verify_admin(x_admin_key)
    data = load_admin_data()
    data["ticker_text"] = update.ticker_text
    save_admin_data(data)
    return {"success": True, "ticker_text": data["ticker_text"]}


# Hero Slides
@router.post("/admin/hero-slides/add")
def admin_add_slide(slide: HeroSlideAdd, x_admin_key: str | None = Header(default=None)):
    verify_admin(x_admin_key)
    data = load_admin_data()
    slides = data.get("hero_slides", [])
    new_slide = {
        "id": f"slide_{uuid.uuid4().hex[:8]}",
        "type": slide.type,
        "url": slide.url,
        "bg_color": slide.bg_color or "#0A5C36",
        "caption": slide.caption,
        "caption_urdu": slide.caption_urdu,
        "order": len(slides)
    }
    slides.append(new_slide)
    data["hero_slides"] = slides
    save_admin_data(data)
    return {"success": True, "slide": new_slide}


@router.delete("/admin/hero-slides/{slide_id}")
def admin_delete_slide(slide_id: str, x_admin_key: str | None = Header(default=None)):
    verify_admin(x_admin_key)
    data = load_admin_data()
    slides = [s for s in data.get("hero_slides", []) if s.get("id") != slide_id]
    data["hero_slides"] = slides
    save_admin_data(data)
    return {"success": True}


@router.post("/admin/hero-slides/reorder")
def admin_reorder_slides(reorder: SlideReorder, x_admin_key: str | None = Header(default=None)):
    verify_admin(x_admin_key)
    data = load_admin_data()
    slides_map = {s["id"]: s for s in data.get("hero_slides", [])}
    reordered = []
    for i, sid in enumerate(reorder.ordered_ids):
        if sid in slides_map:
            slides_map[sid]["order"] = i
            reordered.append(slides_map[sid])
    data["hero_slides"] = reordered
    save_admin_data(data)
    return {"success": True, "hero_slides": reordered}


# Organization Approvals
@router.get("/admin/organizations")
def admin_get_orgs(x_admin_key: str | None = Header(default=None)):
    verify_admin(x_admin_key)
    data = load_admin_data()
    return {"organizations": data.get("organizations", [])}


@router.post("/admin/organizations/{org_id}/approve")
def admin_approve_org(org_id: str, x_admin_key: str | None = Header(default=None)):
    verify_admin(x_admin_key)
    data = load_admin_data()
    orgs = data.get("organizations", [])
    for org in orgs:
        if org.get("id") == org_id:
            org["status"] = "approved"
            org["reviewed_at"] = datetime.now().isoformat()
            break
    else:
        raise HTTPException(status_code=404, detail="Organization not found.")
    data["organizations"] = orgs
    save_admin_data(data)
    return {"success": True}


@router.post("/admin/organizations/{org_id}/reject")
def admin_reject_org(org_id: str, x_admin_key: str | None = Header(default=None)):
    verify_admin(x_admin_key)
    data = load_admin_data()
    orgs = data.get("organizations", [])
    for org in orgs:
        if org.get("id") == org_id:
            org["status"] = "rejected"
            org["reviewed_at"] = datetime.now().isoformat()
            break
    else:
        raise HTTPException(status_code=404, detail="Organization not found.")
    data["organizations"] = orgs
    save_admin_data(data)
    return {"success": True}


@router.delete("/admin/organizations/{org_id}")
def admin_delete_org(org_id: str, x_admin_key: str | None = Header(default=None)):
    verify_admin(x_admin_key)
    data = load_admin_data()
    orgs = [o for o in data.get("organizations", []) if o.get("id") != org_id]
    data["organizations"] = orgs
    save_admin_data(data)
    return {"success": True}


# ---------------------------------------------------------------------------
# PUBLIC Endpoints (no auth required)
# ---------------------------------------------------------------------------

@router.get("/public/settings")
def public_settings():
    data = load_admin_data()
    return {
        "contact_info": data.get("contact_info", {}),
        "ticker_text": data.get("ticker_text", []),
        "hero_slides": sorted(data.get("hero_slides", []), key=lambda x: x.get("order", 0))
    }


@router.get("/public/approved-organizations")
def public_approved_orgs():
    data = load_admin_data()
    approved = [o for o in data.get("organizations", []) if o.get("status") == "approved"]
    return {"organizations": approved}


@router.post("/organizations/register")
def register_organization(reg: OrgRegistration):
    data = load_admin_data()
    orgs = data.get("organizations", [])
    new_org = {
        "id": f"org_{uuid.uuid4().hex[:10]}",
        "name": reg.name.strip(),
        "org_type": reg.org_type.strip(),
        "contact": reg.contact.strip(),
        "email": reg.email.strip(),
        "address": reg.address.strip(),
        "province": reg.province.strip(),
        "description": reg.description.strip(),
        "status": "pending",
        "submitted_at": datetime.now().isoformat()
    }
    orgs.append(new_org)
    data["organizations"] = orgs
    save_admin_data(data)
    return {
        "success": True,
        "message": "Registration submitted. Your organization will be reviewed and approved by admin.",
        "id": new_org["id"]
    }
