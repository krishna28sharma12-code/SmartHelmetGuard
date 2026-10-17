"""
Smart Helmet Guard - Decision Engine (Per-Frame Mapping)
File: backend/decision_engine.py

Maps ONE frame's raw Roboflow model output to a state.
States:
- HELMET_DETECTED: Helmet found with confidence >= threshold
- NO_HELMET_DETECTED: No helmet found
- UNCERTAIN: API error, timeout, or invalid frame

Honesty Rule:
Never fake confidence values. Never compute second bar as (100 - first).
Only report real detector confidences.
"""

from typing import Dict, Any, List

# Configurable Parameters
CONFIDENCE_THRESHOLD = 0.50  # 50% threshold default

HELMET_CLASSES = {"safety-helmets", "helmet", "with_helmet", "with-helmet", "helmets"}
NO_HELMET_CLASSES = {"nohelmet", "no_helmet", "no-helmet", "without_helmet", "without-helmet"}


def evaluate_frame(success: bool, result_data: Dict[str, Any], threshold: float = CONFIDENCE_THRESHOLD) -> Dict[str, Any]:
    """
    Evaluates one frame.
    Returns:
    {
        "state": "HELMET_DETECTED" | "NO_HELMET_DETECTED" | "UNCERTAIN",
        "helmet_confidence": float (0-100),
        "no_helmet_confidence": float (0-100),
        "latency_ms": float,
        "details": str
    }
    """
    if not success:
        return {
            "state": "UNCERTAIN",
            "helmet_confidence": 0.0,
            "no_helmet_confidence": 0.0,
            "latency_ms": result_data.get("latency_ms", 0.0),
            "details": result_data.get("error", "Detection failed")
        }

    predictions: List[Dict[str, Any]] = result_data.get("predictions", [])
    latency_ms = result_data.get("latency_ms", 0.0)

    best_helmet_conf = 0.0
    best_no_helmet_conf = 0.0

    for pred in predictions:
        class_name = str(pred.get("class", "")).strip().lower()
        conf = float(pred.get("confidence", 0.0))

        if class_name in HELMET_CLASSES:
            if conf > best_helmet_conf:
                best_helmet_conf = conf
        elif class_name in NO_HELMET_CLASSES:
            if conf > best_no_helmet_conf:
                best_no_helmet_conf = conf

    helmet_pct = round(best_helmet_conf * 100, 1)
    no_helmet_pct = round(best_no_helmet_conf * 100, 1)

    # Decision mapping
    if best_helmet_conf >= threshold:
        state = "HELMET_DETECTED"
        details = f"Helmet detected with {helmet_pct}% confidence"
    elif best_no_helmet_conf >= threshold:
        state = "NO_HELMET_DETECTED"
        details = f"No-helmet condition detected with {no_helmet_pct}% confidence"
    elif not predictions:
        # In a 1-class model (like safety-helemt/3), 0 detections means helmet was NOT detected
        state = "NO_HELMET_DETECTED"
        details = "No helmet detected in frame"
    else:
        # Detections existed but below threshold
        state = "UNCERTAIN"
        details = f"Detection confidence ({helmet_pct}%) below {threshold * 100}% threshold"

    return {
        "state": state,
        "helmet_confidence": helmet_pct,
        "no_helmet_confidence": no_helmet_pct,
        "latency_ms": latency_ms,
        "details": details
    }
