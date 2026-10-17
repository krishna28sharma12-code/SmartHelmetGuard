"""
Smart Helmet Guard - Hybrid Database Module (MongoDB & SQLite)
File: backend/database.py

Supports:
1. Cloud MongoDB Atlas (set MONGODB_URI in .env)
2. Local SQLite fallback (helmet_guard.db) if MongoDB is not configured

Stores demonstration violation records:
- vehicle_number
- timestamp
- location
- image_base64
- confidence
- status (PENDING, REVIEWED, DISMISSED)
- reviewer_notes
"""

import os
import sqlite3
from datetime import datetime
from typing import List, Dict, Any, Optional

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

MONGODB_URI = os.environ.get("MONGODB_URI", "").strip()
DB_PATH = os.environ.get("SQLITE_DB_PATH", os.path.join(os.path.dirname(os.path.abspath(__file__)), "helmet_guard.db"))

use_mongo = False
mongo_col = None

if MONGODB_URI:
    try:
        from pymongo import MongoClient
        from bson import ObjectId

        mongo_client = MongoClient(MONGODB_URI, serverSelectionTimeoutMS=5000)
        # Test connection ping
        mongo_client.admin.command('ping')
        mongo_db = mongo_client["smart_helmet_guard"]
        mongo_col = mongo_db["violations"]
        use_mongo = True
        print("[DATABASE] Successfully connected to Cloud MongoDB!")
    except Exception as e:
        print(f"[DATABASE WARNING] Failed to connect to MongoDB ({e}). Falling back to local SQLite.")
        use_mongo = False


# ==========================================
# SQLITE ENGINE
# ==========================================
def get_sqlite_conn():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_sqlite():
    with get_sqlite_conn() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS violations (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                vehicle_number TEXT NOT NULL,
                timestamp TEXT NOT NULL,
                location TEXT DEFAULT 'Unavailable',
                image_base64 TEXT,
                confidence REAL DEFAULT 0.0,
                status TEXT DEFAULT 'PENDING',
                reviewer_notes TEXT DEFAULT ''
            )
        """)
        conn.commit()


# ==========================================
# UNIFIED DATABASE API
# ==========================================
def create_violation(
    vehicle_number: str,
    image_base64: str,
    location: str = "Unavailable",
    confidence: float = 0.0
) -> Any:
    """Inserts a new demonstration violation record with status PENDING."""
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    if use_mongo and mongo_col is not None:
        doc = {
            "vehicle_number": vehicle_number,
            "timestamp": timestamp,
            "location": location,
            "image_base64": image_base64,
            "confidence": confidence,
            "status": "PENDING",
            "reviewer_notes": ""
        }
        res = mongo_col.insert_one(doc)
        return str(res.inserted_id)

    # SQLite Fallback
    with get_sqlite_conn() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO violations (vehicle_number, timestamp, location, image_base64, confidence, status)
            VALUES (?, ?, ?, ?, ?, 'PENDING')
        """, (vehicle_number, timestamp, location, image_base64, confidence))
        conn.commit()
        # Return as str to match the MongoDB ObjectId string shape
        return str(cursor.lastrowid)


def list_violations(status_filter: Optional[str] = None) -> List[Dict[str, Any]]:
    """Retrieves all violation records, newest first."""
    if use_mongo and mongo_col is not None:
        query = {"status": status_filter} if status_filter else {}
        cursor = mongo_col.find(query).sort("_id", -1)
        records = []
        for doc in cursor:
            doc["id"] = str(doc.pop("_id"))
            records.append(doc)
        return records

    # SQLite Fallback
    with get_sqlite_conn() as conn:
        cursor = conn.cursor()
        if status_filter:
            cursor.execute("SELECT * FROM violations WHERE status = ? ORDER BY id DESC", (status_filter,))
        else:
            cursor.execute("SELECT * FROM violations ORDER BY id DESC")
        rows = []
        for row in cursor.fetchall():
            rec = dict(row)
            rec["id"] = str(rec["id"])  # Normalize to str to match MongoDB
            rows.append(rec)
        return rows


def get_violation(violation_id: Any) -> Optional[Dict[str, Any]]:
    """Retrieves a single violation record by ID."""
    if use_mongo and mongo_col is not None:
        from bson import ObjectId
        try:
            doc = mongo_col.find_one({"_id": ObjectId(str(violation_id))})
            if doc:
                doc["id"] = str(doc.pop("_id"))
                return doc
        except Exception:
            return None

    # SQLite Fallback
    with get_sqlite_conn() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM violations WHERE id = ?", (int(violation_id),))
        row = cursor.fetchone()
        if row is None:
            return None
        rec = dict(row)
        rec["id"] = str(rec["id"])  # Normalize to str to match MongoDB
        return rec


def update_violation_status(violation_id: Any, new_status: str, notes: str = "") -> bool:
    """Updates violation status to REVIEWED or DISMISSED."""
    if new_status not in ("PENDING", "REVIEWED", "DISMISSED"):
        raise ValueError("Invalid status. Must be PENDING, REVIEWED, or DISMISSED")

    if use_mongo and mongo_col is not None:
        from bson import ObjectId
        try:
            res = mongo_col.update_one(
                {"_id": ObjectId(str(violation_id))},
                {"$set": {"status": new_status, "reviewer_notes": notes}}
            )
            return res.modified_count > 0 or res.matched_count > 0
        except Exception as e:
            print("[MONGO UPDATE ERROR]", e)
            return False

    # SQLite Fallback
    with get_sqlite_conn() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            UPDATE violations
            SET status = ?, reviewer_notes = ?
            WHERE id = ?
        """, (new_status, notes, int(violation_id)))
        conn.commit()
        return cursor.rowcount > 0


def delete_violation(violation_id: Any) -> bool:
    """Deletes a violation record (useful for clearing demo test records)."""
    if use_mongo and mongo_col is not None:
        from bson import ObjectId
        try:
            res = mongo_col.delete_one({"_id": ObjectId(str(violation_id))})
            return res.deleted_count > 0
        except Exception:
            return False

    with get_sqlite_conn() as conn:
        cursor = conn.cursor()
        cursor.execute("DELETE FROM violations WHERE id = ?", (int(violation_id),))
        conn.commit()
        return cursor.rowcount > 0


# Initialize SQLite table on load
init_sqlite()
