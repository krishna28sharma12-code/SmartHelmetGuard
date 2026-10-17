"""
Smart Helmet Guard - Helmet Detector
File: backend/helmet_detector.py

Calls Roboflow Inference API with image bytes held in memory.
Never writes image files to disk.
"""

import os
import time
import requests
from typing import Dict, Any, Tuple


class HelmetDetector:
    def __init__(self):
        self.api_key = os.environ.get("ROBOFLOW_API_KEY", "")
        self.model_id = os.environ.get("ROBOFLOW_MODEL_ID", "safety-helemt/3")

    def detect(self, image_bytes: bytes) -> Tuple[bool, Dict[str, Any]]:
        """
        Sends image bytes to Roboflow inference API.
        Returns (success, result_dict)
        """
        if not self.api_key:
            return False, {
                "error": "ROBOFLOW_API_KEY is not configured",
                "state": "UNCERTAIN"
            }

        # Validate image bytes - check JPEG/PNG magic bytes
        if len(image_bytes) < 100:
            return False, {
                "error": "Image data too small (possible empty frame)",
                "state": "UNCERTAIN",
                "latency_ms": 0
            }

        # JPEG: FF D8 FF | PNG: 89 50 4E 47
        is_jpeg = image_bytes[:3] == b'\xff\xd8\xff'
        is_png = image_bytes[:4] == b'\x89PNG'
        if not (is_jpeg or is_png):
            return False, {
                "error": "Invalid image format (expected JPEG or PNG)",
                "state": "UNCERTAIN",
                "latency_ms": 0
            }

        mime_type = "image/jpeg" if is_jpeg else "image/png"
        url = f"https://detect.roboflow.com/{self.model_id}?api_key={self.api_key}"

        start_time = time.time()
        try:
            response = requests.post(
                url,
                files={"file": ("frame.jpg", image_bytes, mime_type)},
                timeout=12
            )
            latency_ms = (time.time() - start_time) * 1000

            if response.status_code != 200:
                return False, {
                    "error": f"API returned status {response.status_code}",
                    "details": response.text[:200],
                    "latency_ms": latency_ms,
                    "state": "UNCERTAIN"
                }

            data = response.json()
            predictions = data.get("predictions", [])

            return True, {
                "predictions": predictions,
                "latency_ms": round(latency_ms, 1)
            }

        except requests.exceptions.Timeout:
            return False, {
                "error": "Request timed out",
                "latency_ms": (time.time() - start_time) * 1000,
                "state": "UNCERTAIN"
            }
        except requests.exceptions.RequestException as e:
            return False, {
                "error": f"Network error: {str(e)}",
                "latency_ms": (time.time() - start_time) * 1000,
                "state": "UNCERTAIN"
            }
