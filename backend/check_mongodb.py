"""Safe MongoDB Atlas diagnostic for Smart Helmet Guard.

Run from the project root:
    python -m backend.check_mongodb

Does not print credentials or image contents.
"""
import os
import sys
from pathlib import Path
from urllib.parse import urlsplit

try:
    from dotenv import load_dotenv
    load_dotenv(Path(__file__).resolve().parents[1] / ".env")
    load_dotenv()
except ImportError:
    pass

uri = os.environ.get("MONGODB_URI", "").strip()
if not uri:
    print("FAIL: MONGODB_URI is not set. Check the .env file in the project root.")
    sys.exit(2)

try:
    from pymongo import MongoClient
except ImportError:
    print("FAIL: pymongo is not installed in this Python environment.")
    print("Run: python -m pip install -r backend/requirements.txt")
    sys.exit(2)

try:
    parsed = urlsplit(uri.replace("mongodb+srv://", "https://", 1))
    print("URI configured: YES")
    print("URI scheme:", "mongodb+srv" if uri.startswith("mongodb+srv://") else "mongodb/other")
    print("Atlas host:", parsed.hostname or "could not parse")
    client = MongoClient(uri, serverSelectionTimeoutMS=10000, connectTimeoutMS=10000)
    ping = client.admin.command("ping")
    print("MongoDB ping: PASS", "ok=", ping.get("ok"))

    db = client["smart_helmet_guard"]
    col = db["violations"]
    print("Database:", db.name)
    print("Collection:", col.name)
    print("Total violation records:", col.count_documents({}))

    for doc in col.find({}, {"vehicle_number": 1, "image_base64": 1, "timestamp": 1}).sort("_id", -1).limit(5):
        image = doc.get("image_base64") or ""
        image = image.strip() if isinstance(image, str) else ""
        print("--- Latest record ---")
        print("Vehicle:", doc.get("vehicle_number", "(missing)"))
        print("Timestamp:", doc.get("timestamp", "(missing)"))
        print("Image field type:", type(doc.get("image_base64")).__name__)
        print("Image string length:", len(image))
        print("Has data URL prefix:", image.startswith("data:image/"))
        print("Looks like placeholder:", image.lower() in ("sample_frame_data", "sample_mongodb_frame"))
        if image.startswith("data:") and "," in image:
            header, payload = image.split(",", 1)
            print("Image MIME:", header[5:].split(";", 1)[0])
            print("Has base64 marker:", ";base64" in header)
            print("Base64 payload non-empty:", bool(payload))
        else:
            print("Image format: raw base64 or missing/invalid data URL")
    client.close()
    print("\nRESULT: MongoDB is reachable. Check image fields above and confirm the dashboard uses this backend.")
except Exception as exc:
    print("\nMongoDB connection: FAIL")
    print("Error type:", type(exc).__name__)
    # PyMongo exception text normally contains topology/host details but not credentials.
    # Redact the URI just in case a driver/version includes it.
    msg = str(exc).replace(uri, "<MONGODB_URI_REDACTED>")
    print("Error:", msg[:1800])
    print("\nCheck Atlas Network Access, database user/password encoding, SRV DNS, system date/time, and outbound TLS/network restrictions.")
    sys.exit(1)
