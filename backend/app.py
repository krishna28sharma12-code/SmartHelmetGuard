"""
Smart Helmet Guard - Main Backend Application
File: backend/app.py

FastAPI server providing:
1. /api/detect - In-memory frame inference and state mapping
2. /api/command - Servo command relay (Route 2 backup)
3. /api/command/poll - NodeMCU command polling
4. /api/auth/verify - Dashboard password verification
5. /api/violations - CRUD for demonstration violation records
6. Serves frontend static web files over HTTP/HTTPS
"""

import os
import time
import base64
import binascii
from typing import Optional

from fastapi import FastAPI, UploadFile, File, HTTPException, Header
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, HTMLResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

from backend.helmet_detector import HelmetDetector
from backend.decision_engine import evaluate_frame
from backend import database

# ==========================================
# APP SETUP
# ==========================================
app = FastAPI(
    title="Smart Helmet Guard Backend",
    description="Backend API for AI-based helmet detection and authorization prototype",
    version="1.0.0"
)

# Enable CORS for local network and mobile devices
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ==========================================
# GLOBAL OBJECTS & CONFIG
# ==========================================
detector = HelmetDetector()

# In-memory command relay store for Route 2 (backup)
current_servo_command = {
    "angle": 0,
    "timestamp": 0
}

NODEMCU_SECRET = os.environ.get("NODEMCU_SECRET", "smart_guard_secret_123")
DASHBOARD_PASSWORD = os.environ.get("DASHBOARD_PASSWORD", "admin123")

# Resolve the frontend directory path once at startup
frontend_dir = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "frontend"
)


# ==========================================
# REQUEST / RESPONSE MODELS
# ==========================================
class CommandRequest(BaseModel):
    angle: int
    secret: str


class ViolationCreate(BaseModel):
    vehicle_number: str
    image_base64: str = ""
    location: str = "Unavailable"
    confidence: float = 0.0


class ViolationUpdate(BaseModel):
    status: str
    notes: str = ""


class AuthRequest(BaseModel):
    password: str


# ==========================================
# HELPER: password guard
# ==========================================
def require_dashboard_password(
    header_pwd: Optional[str],
    query_pwd: Optional[str]
) -> None:
    """Raises 401 if neither the header nor query-param password matches."""
    pwd = header_pwd or query_pwd
    if pwd != DASHBOARD_PASSWORD:
        raise HTTPException(
            status_code=401,
            detail="Unauthorized: Invalid dashboard password"
        )


# ==========================================
# ROUTES
# ==========================================

@app.get("/api/health")
def health_check():
    return {
        "status": "online",
        "model_id": detector.model_id,
        "detector_ready": bool(detector.api_key)
    }


@app.post("/api/detect")
async def detect_frame(file: UploadFile = File(...)):
    """
    Receives an image frame, runs inference in-memory,
    maps it to a state, and discards the frame immediately.
    Never saves ordinary frames to disk.
    """
    try:
        image_bytes = await file.read()
        if not image_bytes:
            raise HTTPException(status_code=400, detail="Empty image data")

        success, raw_result = detector.detect(image_bytes)
        del image_bytes  # discard immediately

        return evaluate_frame(success, raw_result)

    except HTTPException:
        raise
    except Exception as e:
        return {
            "state": "UNCERTAIN",
            "helmet_confidence": 0.0,
            "no_helmet_confidence": 0.0,
            "latency_ms": 0.0,
            "details": f"Server error processing frame: {str(e)}"
        }


@app.post("/api/command")
def send_command(cmd: CommandRequest):
    """
    Route 2 (backup): Phone posts servo angle here if Route 1 is unavailable.
    Requires shared secret key.
    """
    if cmd.secret != NODEMCU_SECRET:
        raise HTTPException(status_code=401, detail="Invalid shared secret key")

    if cmd.angle not in (0, 90):
        raise HTTPException(status_code=400, detail="Angle must be 0 or 90")

    global current_servo_command
    current_servo_command = {
        "angle": cmd.angle,
        "timestamp": time.time()
    }
    return {"status": "command_queued", "angle": cmd.angle}


@app.get("/api/command/poll")
def poll_command(key: Optional[str] = None):
    """
    Route 2 (backup): NodeMCU polls this endpoint ~once per second.
    Requires shared secret key via query param.
    """
    if key != NODEMCU_SECRET:
        raise HTTPException(status_code=401, detail="Invalid shared secret key")

    return current_servo_command


@app.post("/api/auth/verify")
def verify_password(auth: AuthRequest):
    """Verifies reviewer password for Authority Portal access."""
    if auth.password == DASHBOARD_PASSWORD:
        return {"authenticated": True}
    raise HTTPException(status_code=401, detail="Invalid dashboard password")


def normalize_evidence_image(value: str) -> str:
    """Validate and normalize an evidence image data URL before storing it."""
    if not value or not value.strip():
        raise HTTPException(status_code=400, detail="Evidence image is missing. Capture a camera frame before saving a violation.")

    value = value.strip()
    mime = "image/jpeg"
    payload = value
    if value.startswith("data:"):
        try:
            header, payload = value.split(",", 1)
        except ValueError:
            raise HTTPException(status_code=400, detail="Evidence image data URL is malformed.")
        if ";base64" not in header:
            raise HTTPException(status_code=400, detail="Evidence image must be Base64 encoded.")
        mime = header[5:].split(";", 1)[0].lower()
        if mime not in ("image/jpeg", "image/png", "image/webp"):
            raise HTTPException(status_code=400, detail="Unsupported evidence image type.")
    else:
        # Accept legacy raw Base64 payloads, treating them as JPEG.
        mime = "image/jpeg"

    try:
        raw = base64.b64decode(payload, validate=True)
    except (binascii.Error, ValueError):
        raise HTTPException(status_code=400, detail="Evidence image contains invalid Base64 data.")

    if len(raw) < 100:
        raise HTTPException(status_code=400, detail="Evidence image is empty or incomplete.")
    valid = (
        (mime == "image/jpeg" and raw.startswith(b"\xff\xd8\xff")) or
        (mime == "image/png" and raw.startswith(b"\x89PNG\r\n\x1a\n")) or
        (mime == "image/webp" and len(raw) >= 12 and raw[:4] == b"RIFF" and raw[8:12] == b"WEBP")
    )
    if not valid:
        raise HTTPException(status_code=400, detail="Evidence bytes do not match the declared image format.")

    return f"data:{mime};base64,{base64.b64encode(raw).decode('ascii')}"


@app.post("/api/violations")
def record_violation(v: ViolationCreate):
    """Creates a demonstration violation record only with valid image evidence."""
    normalized_image = normalize_evidence_image(v.image_base64)
    record_id = database.create_violation(
        vehicle_number=v.vehicle_number,
        image_base64=normalized_image,
        location=v.location,
        confidence=v.confidence
    )
    return {"id": record_id, "status": "PENDING"}


@app.get("/api/violations")
def get_violations(
    status: Optional[str] = None,
    x_dashboard_password: Optional[str] = Header(None, alias="X-Dashboard-Password"),
    password: Optional[str] = None
):
    """Lists all demonstration violation records (password protected)."""
    require_dashboard_password(x_dashboard_password, password)
    return database.list_violations(status_filter=status)


@app.patch("/api/violations/{violation_id}")
def update_status(
    violation_id: str,
    update: ViolationUpdate,
    x_dashboard_password: Optional[str] = Header(None, alias="X-Dashboard-Password"),
    password: Optional[str] = None
):
    """Updates violation status to REVIEWED or DISMISSED (password protected)."""
    require_dashboard_password(x_dashboard_password, password)

    try:
        ok = database.update_violation_status(
            violation_id=violation_id,
            new_status=update.status,
            notes=update.notes
        )
        if not ok:
            raise HTTPException(status_code=404, detail="Violation record not found")
        return {"id": violation_id, "status": update.status}
    except ValueError as ve:
        raise HTTPException(status_code=400, detail=str(ve))


@app.delete("/api/violations/{violation_id}")
def remove_violation(
    violation_id: str,
    x_dashboard_password: Optional[str] = Header(None, alias="X-Dashboard-Password"),
    password: Optional[str] = None
):
    """Deletes a demonstration violation record (password protected)."""
    require_dashboard_password(x_dashboard_password, password)

    ok = database.delete_violation(violation_id)
    if not ok:
        raise HTTPException(status_code=404, detail="Violation record not found")
    return {"deleted": True, "id": violation_id}


# ==========================================
# FRONTEND SERVING
# ==========================================

@app.get("/dashboard", response_class=HTMLResponse)
def get_dashboard():
    """Serves the authority dashboard page at /dashboard (shortcut)."""
    dashboard_path = os.path.join(frontend_dir, "dashboard.html")
    if os.path.exists(dashboard_path):
        return FileResponse(dashboard_path, media_type="text/html")
    raise HTTPException(status_code=404, detail="Dashboard not found")


if os.path.exists(frontend_dir):
    app.mount("/", StaticFiles(directory=frontend_dir, html=True), name="frontend")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("backend.app:app", host="0.0.0.0", port=8000, reload=True)
