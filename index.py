#!/usr/bin/env python3
"""
NHAI Rajmarg Yatra — Vehicle → FASTag (Vercel)
  GET /vehtofastaginfo?veh=RJ14CV0002
  GET /enotice?veh=RJ14CV0002
"""

from __future__ import annotations

import re
from typing import Any

import requests
from flask import Flask, jsonify, request

app = Flask(__name__)

BASE = "https://rajmargyatra.nhai.gov.in"
UA = (
    "Mozilla/5.0 (Linux; Android 10; K) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/131.0.0.0 Mobile Safari/537.36"
)
TIMEOUT = 28

STATUS_MAP = {
    "A": "Active",
    "I": "Inactive",
    "B": "Blacklisted",
    "C": "Closed",
    "E": "Exempted",
    "N": "New",
}


def session() -> requests.Session:
    s = requests.Session()
    s.headers.update(
        {
            "User-Agent": UA,
            "Accept": "application/json, text/plain, */*",
            "Accept-Language": "en-IN,en;q=0.9,hi;q=0.8",
            "Content-Type": "application/json",
            "Origin": BASE,
            "Referer": f"{BASE}/",
            "Sec-Fetch-Site": "same-origin",
            "Sec-Fetch-Mode": "cors",
            "Sec-Fetch-Dest": "empty",
        }
    )
    return s


def normalize_veh(veh: str) -> str:
    return re.sub(r"[^A-Za-z0-9]", "", veh).upper()


def fetch_fastag(veh: str) -> dict[str, Any]:
    s = session()
    try:
        s.get(BASE + "/", timeout=TIMEOUT)
    except Exception:
        pass

    r = s.post(
        f"{BASE}/nhai/api/annualpass/v2.0/vehicleAnnualPassDetails",
        json={"vehRegNumber": veh},
        timeout=TIMEOUT,
    )
    if r.status_code not in (200, 201):
        return {
            "ok": False,
            "vehicle": veh,
            "error": f"HTTP {r.status_code}",
            "raw": r.text[:300],
        }

    try:
        body = r.json()
    except Exception:
        return {"ok": False, "vehicle": veh, "error": "bad JSON", "raw": r.text[:300]}

    if body.get("status") != 200:
        return {
            "ok": False,
            "vehicle": veh,
            "error": body.get("message") or "API status not 200",
            "raw": body,
        }

    data = body.get("data") or []
    if not data:
        return {
            "ok": True,
            "vehicle": veh,
            "found": False,
            "message": body.get("message") or "No data",
            "count": 0,
            "tags": [],
        }

    block = data[0] if isinstance(data, list) else data
    tags_raw = block.get("tags") or []
    tags = []
    for t in tags_raw:
        st = t.get("TAGSTATUS") or ""
        tags.append(
            {
                "tag_id": t.get("TAGID"),
                "tid": t.get("TID"),
                "reg_number": t.get("REGNUMBER") or t.get("NPCI_REGNUMBER"),
                "vehicle_class": t.get("VEHICLECLASS"),
                "status_code": st,
                "status": STATUS_MAP.get(st, st),
                "issue_date": t.get("ISSUEDATE"),
                "bank_id": t.get("BANKID"),
                "bank_name": t.get("BANKNAME"),
                "commercial": t.get("COMVEHICLE") == "T",
                "exc_code": t.get("EXCCODE"),
            }
        )

    active = [t for t in tags if t["status_code"] == "A"]
    return {
        "ok": True,
        "vehicle": veh,
        "found": True,
        "message": block.get("message") or body.get("message"),
        "total_valid_tags": block.get("totalValidTags"),
        "vahan_category": block.get("VAHAN_CATEGORY"),
        "annual_pass": block.get("ANNUAL_PASS_DETAILS") or {},
        "count": len(tags),
        "active_count": len(active),
        "tags": tags,
    }


def fetch_enotice(veh: str) -> dict[str, Any]:
    s = session()
    try:
        s.get(BASE + "/", timeout=TIMEOUT)
    except Exception:
        pass

    r = s.post(
        f"{BASE}/nhai/api/v2.0/enoticedata",
        json={"vehRegNumber": veh},
        timeout=TIMEOUT,
    )
    if r.status_code not in (200, 201):
        return {
            "ok": False,
            "vehicle": veh,
            "error": f"HTTP {r.status_code}",
            "raw": r.text[:300],
        }
    try:
        body = r.json()
    except Exception:
        return {"ok": False, "vehicle": veh, "error": "bad JSON", "raw": r.text[:300]}

    data = body.get("data") or {}
    return {
        "ok": body.get("status") == 200,
        "vehicle": veh,
        "enotice_exists": data.get("enoticeExists"),
        "enotice_data": data.get("enoticeData"),
        "enotice_url": data.get("enoticeUrl"),
        "enotice_error": data.get("enoticeErrMessage"),
    }


@app.get("/")
def home():
    return jsonify(
        {
            "service": "NHAI Rajmarg Yatra FASTag",
            "endpoints": {
                "fastag": "/vehtofastaginfo?veh=RJ14CV0002",
                "enotice": "/enotice?veh=RJ14CV0002",
                "health": "/health",
            },
        }
    )


@app.get("/health")
def health():
    return jsonify({"ok": True})


@app.get("/vehtofastaginfo")
@app.get("/vehtofastaginfo/")
def vehtofastaginfo():
    veh = (
        request.args.get("veh")
        or request.args.get("vehicle")
        or request.args.get("vrn")
        or ""
    ).strip()
    if not veh:
        return jsonify({"ok": False, "error": "pass ?veh=REGNO"}), 400
    veh = normalize_veh(veh)
    if len(veh) < 6:
        return jsonify({"ok": False, "error": "invalid vehicle number", "vehicle": veh}), 400
    result = fetch_fastag(veh)
    return jsonify(result), (200 if result.get("ok") else 502)


@app.get("/enotice")
@app.get("/enotice/")
def enotice():
    veh = (
        request.args.get("veh")
        or request.args.get("vehicle")
        or request.args.get("vrn")
        or ""
    ).strip()
    if not veh:
        return jsonify({"ok": False, "error": "pass ?veh=REGNO"}), 400
    veh = normalize_veh(veh)
    result = fetch_enotice(veh)
    return jsonify(result), (200 if result.get("ok") else 502)
