"""
Smart Helmet Guard - Phase 2 Model Verification Script
File: backend/test_roboflow.py

Purpose:
Test and verify the Roboflow helmet detection model on test photos.
Measures:
1. Detected classes ('helmet', 'nohelmet', etc.)
2. Model confidence percentage
3. Round-trip API latency (time taken for prediction)

Security Note:
Never hardcode your API key here!
Set it in PowerShell before running:
    $env:ROBOFLOW_API_KEY = "your_actual_key_here"
    $env:ROBOFLOW_MODEL_ID = "helmet-5dgng/1"   (or whatever version is in your Roboflow Deploy tab)
"""

import os
import sys
import time
import requests

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass


def test_model(image_path: str):
    # 1. Retrieve configuration from environment variables
    api_key = os.environ.get("ROBOFLOW_API_KEY")
    model_id = os.environ.get("ROBOFLOW_MODEL_ID", "helmet-5dgng/1")

    if not api_key:
        print("\n[ERROR] ROBOFLOW_API_KEY environment variable is not set!")
        print("Please set it in PowerShell before running:")
        print('    $env:ROBOFLOW_API_KEY = "your_private_api_key_from_roboflow"\n')
        return

    # 2. Check if the test image exists
    if not os.path.exists(image_path):
        print(f"\n[ERROR] Test image file not found: {image_path}")
        print("Please check the path and try again.\n")
        return

    print("=" * 60)
    print(" Smart Helmet Guard - Model Verification Test")
    print("=" * 60)
    print(f"Target Image : {image_path}")
    print(f"Model ID     : {model_id}")
    print("Sending image to Roboflow Inference API...")

    url = f"https://detect.roboflow.com/{model_id}?api_key={api_key}"

    start_time = time.time()
    try:
        with open(image_path, "rb") as img_file:
            response = requests.post(
                url,
                files={"file": img_file},
                timeout=15
            )
        elapsed_ms = (time.time() - start_time) * 1000

    except requests.exceptions.Timeout:
        print("\n[ERROR] Request timed out (took longer than 15 seconds).")
        print("Check your internet connection and try again.")
        return
    except requests.exceptions.RequestException as e:
        print(f"\n[ERROR] Network error occurred: {e}")
        return

    # 3. Handle HTTP response status
    if response.status_code == 401 or response.status_code == 403:
        print(f"\n[ERROR] Authentication failed (Status {response.status_code}).")
        print("Your ROBOFLOW_API_KEY appears to be invalid or unauthorized.")
        return
    elif response.status_code == 404:
        print(f"\n[ERROR] Model not found (Status 404).")
        print(f"Roboflow could not find model ID '{model_id}'.")
        print("Check the exact model name and version number in the Roboflow Deploy tab.")
        return
    elif response.status_code == 429:
        print("\n[ERROR] Rate limit reached (Status 429).")
        print("Your Roboflow free-tier inference quota has been reached.")
        return
    elif response.status_code != 200:
        print(f"\n[ERROR] API returned error status {response.status_code}:")
        print(response.text)
        return

    # 4. Parse detections
    data = response.json()
    predictions = data.get("predictions", [])

    print("\n--- RESULTS ---")
    print(f"Round-trip latency: {elapsed_ms:.1f} ms")
    print(f"Total detections  : {len(predictions)}")

    if not predictions:
        print("\nNo objects detected above the default threshold.")
        print("(This typically represents an empty scene or an unrecognized object.)")
    else:
        print("\nDetected Objects:")
        for idx, pred in enumerate(predictions, 1):
            class_name = pred.get("class", "unknown")
            confidence = pred.get("confidence", 0.0) * 100
            box_x = pred.get("x", 0)
            box_y = pred.get("y", 0)
            box_w = pred.get("width", 0)
            box_h = pred.get("height", 0)
            print(f"  [{idx}] Class: '{class_name}' | Confidence: {confidence:.1f}% | Box: (x={box_x:.0f}, y={box_y:.0f}, w={box_w:.0f}, h={box_h:.0f})")

    print("\n" + "=" * 60)
    print("Verification Completed.")
    print("=" * 60)


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage:")
        print("    python backend/test_roboflow.py <path_to_test_image>")
        print("\nExample:")
        print("    python backend/test_roboflow.py test_images/helmet.jpg")
    else:
        test_model(sys.argv[1])
