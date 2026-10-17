/**
 * Smart Helmet Guard - Frontend Core Application
 * File: frontend/app.js
 * 
 * Implements:
 * 1. Mobile camera stream & permission handling
 * 2. In-memory frame resize (~320px) and detection loop
 * 3. State machine (BLOCKED -> AUTHORIZED -> WARNING -> VIOLATION)
 * 4. Real confidence bar telemetry (never fake percentages)
 * 5. Servo control dispatcher (Route 1 direct / Route 2 cloud relay)
 */

// ==========================================
// 1. CONFIGURATION PARAMETERS
// ==========================================
const CONFIG = {
  REQUIRED_HELMET_COUNT: 3,     // Pre-start consecutive helmet detections to authorize
  NO_HELMET_ALERT_TRIGGER: 5,   // Consecutive no-helmet readings to trigger warning
  DEFAULT_WARNING_DURATION: 120,// Warning timer in seconds (real setting)
  POLL_INTERVAL_MS: 3000,       // Interval between inference calls (~3s matches latency)
  SHARED_SECRET: "smart_guard_secret_123", // NodeMCU shared secret key
  IMAGE_CAPTURE_WIDTH: 320      // Resized image width for low latency
};

// ==========================================
// 2. APPLICATION STATE
// ==========================================
let state = {
  isMonitoring: false,
  systemState: "BLOCKED",       // "BLOCKED" | "AUTHORIZED" | "WARNING" | "VIOLATION"
  consecutiveHelmets: 0,
  consecutiveNoHelmets: 0,
  lastNoHelmetConfidence: 0.0,  // Most recent no-helmet confidence for violation records
  warningSecondsLeft: 120,
  warningTimerId: null,
  detectionTimerId: null,
  facingMode: "user",           // "user" (front) or "environment" (rear)
  stream: null,
  bestNoHelmetFrame: null,      // Kept in memory only, cleared after upload
  nodeMcuReachable: false
};

// ==========================================
// 3. DOM ELEMENTS
// ==========================================
const videoElem = document.getElementById("camera-stream");
const canvasElem = document.getElementById("capture-canvas");
const placeholderElem = document.getElementById("camera-placeholder");
const promptTitle = document.getElementById("camera-prompt-title");
const promptMsg = document.getElementById("camera-prompt-msg");

const warningBanner = document.getElementById("warning-banner");
const warningCountdown = document.getElementById("warning-countdown");

// Note: state-badge element exists in HTML but badge appearance is driven by
// setting className on stateText and stateIcon independently.
const stateIcon = document.getElementById("state-icon");
const stateText = document.getElementById("state-text");
const latencyDisplay = document.getElementById("latency-display");

const helmetConfVal = document.getElementById("helmet-conf-val");
const helmetConfBar = document.getElementById("helmet-conf-bar");
const nohelmetConfVal = document.getElementById("nohelmet-conf-val");
const nohelmetConfBar = document.getElementById("nohelmet-conf-bar");

const helmetCountDisplay = document.getElementById("helmet-consecutive-count");
const nohelmetCountDisplay = document.getElementById("nohelmet-consecutive-count");

const btnToggle = document.getElementById("btn-toggle-monitor");
const btnToggleText = document.getElementById("btn-monitor-text");
const btnFlipCam = document.getElementById("btn-flip-cam");
const btnTestServo = document.getElementById("btn-test-servo");

const inputVehicle = document.getElementById("input-vehicle");
const selectRoute = document.getElementById("select-route");
const inputNodeMcuIp = document.getElementById("input-nodemcu-ip");
const selectPreset = document.getElementById("select-preset");
const hwStatusChip = document.getElementById("hardware-status");
const hwStatusText = document.getElementById("hardware-status-text");

// ==========================================
// 4. CAMERA INITIALIZATION & CONTROLS
// ==========================================
async function startCamera() {
  stopCamera();
  try {
    const constraints = {
      video: {
        facingMode: state.facingMode,
        width: { ideal: 640 },
        height: { ideal: 480 }
      },
      audio: false
    };

    state.stream = await navigator.mediaDevices.getUserMedia(constraints);
    videoElem.srcObject = state.stream;
    placeholderElem.style.display = "none";
    return true;
  } catch (err) {
    console.error("Camera access error:", err);
    placeholderElem.style.display = "flex";
    if (err.name === "NotAllowedError" || err.name === "PermissionDeniedError") {
      promptTitle.textContent = "Camera Permission Denied";
      promptMsg.textContent = "Please grant camera permission in your browser address bar settings to allow detection.";
    } else {
      promptTitle.textContent = "Camera Error";
      promptMsg.textContent = err.message || "Could not access camera device.";
    }
    return false;
  }
}

function stopCamera() {
  if (state.stream) {
    state.stream.getTracks().forEach(track => track.stop());
    state.stream = null;
  }
  videoElem.srcObject = null;
  placeholderElem.style.display = "flex";
  promptTitle.textContent = "Camera Inactive";
  promptMsg.textContent = "Press 'Start Monitoring' to enable helmet detection.";
}

// Flip between front and rear camera
btnFlipCam.addEventListener("click", async () => {
  state.facingMode = state.facingMode === "user" ? "environment" : "user";
  if (state.isMonitoring) {
    await startCamera();
  }
});

// ==========================================
// 5. FRAME CAPTURE (IN-MEMORY RESIZE)
// ==========================================
function captureFrameBlob() {
  return new Promise((resolve) => {
    if (!videoElem.videoWidth) {
      resolve(null);
      return;
    }

    const videoAspect = videoElem.videoHeight / videoElem.videoWidth;
    const targetWidth = CONFIG.IMAGE_CAPTURE_WIDTH;
    const targetHeight = Math.round(targetWidth * videoAspect);

    canvasElem.width = targetWidth;
    canvasElem.height = targetHeight;

    const ctx = canvasElem.getContext("2d");
    ctx.drawImage(videoElem, 0, 0, targetWidth, targetHeight);

    canvasElem.toBlob((blob) => {
      resolve(blob);
    }, "image/jpeg", 0.75);
  });
}

// ==========================================
// 6. DETECTION & INFERENCE LOOP
// ==========================================
async function runDetectionCycle() {
  if (!state.isMonitoring) return;

  const frameBlob = await captureFrameBlob();
  if (!frameBlob) {
    scheduleNextCycle();
    return;
  }

  const formData = new FormData();
  formData.append("file", frameBlob, "frame.jpg");

  try {
    const startTime = performance.now();
    const response = await fetch("/api/detect", {
      method: "POST",
      body: formData
    });

    if (!response.ok) {
      throw new Error(`HTTP error ${response.status}`);
    }

    const result = await response.json();
    handleDetectionResult(result, frameBlob);

  } catch (err) {
    console.warn("Detection cycle error:", err);
    updateTelemetry({
      state: "UNCERTAIN",
      helmet_confidence: 0,
      no_helmet_confidence: 0,
      latency_ms: 0,
      details: "Network or backend unreachable"
    });
  }

  scheduleNextCycle();
}

function scheduleNextCycle() {
  if (state.isMonitoring) {
    state.detectionTimerId = setTimeout(runDetectionCycle, CONFIG.POLL_INTERVAL_MS);
  }
}

// ==========================================
// 7. STATE MACHINE & DECISION LOGIC
// ==========================================
function handleDetectionResult(result, frameBlob) {
  updateTelemetry(result);

  const modelState = result.state; // "HELMET_DETECTED" | "NO_HELMET_DETECTED" | "UNCERTAIN"

  // STATE: START BLOCKED (Pre-Start Check)
  if (state.systemState === "BLOCKED") {
    if (modelState === "HELMET_DETECTED") {
      state.consecutiveHelmets++;
      if (state.consecutiveHelmets >= CONFIG.REQUIRED_HELMET_COUNT) {
        // Authorize Start!
        transitionTo("AUTHORIZED");
      }
    } else {
      // Non-helmet or uncertain resets the consecutive authorization counter
      state.consecutiveHelmets = 0;
    }
  }

  // STATE: START AUTHORIZED (Active Monitoring)
  else if (state.systemState === "AUTHORIZED") {
    if (modelState === "NO_HELMET_DETECTED") {
      state.consecutiveNoHelmets++;
      state.bestNoHelmetFrame = frameBlob; // Cache best no-helmet frame in memory
      state.lastNoHelmetConfidence = result.no_helmet_confidence || 0.0;

      if (state.consecutiveNoHelmets >= CONFIG.NO_HELMET_ALERT_TRIGGER) {
        // Trigger Warning Countdown!
        transitionTo("WARNING");
      }
    } else if (modelState === "HELMET_DETECTED") {
      // Reset no-helmet counter
      state.consecutiveNoHelmets = 0;
    }
    // UNCERTAIN readings do not increment or reset counters
  }

  // STATE: WARNING ACTIVE
  else if (state.systemState === "WARNING") {
    if (modelState === "HELMET_DETECTED") {
      // Helmet worn again before warning expired!
      cancelWarning();
      transitionTo("AUTHORIZED");
    }
    // Helmet remains off, countdown continues
  }

  updateCounterDisplays();
}

function transitionTo(newState) {
  state.systemState = newState;

  if (newState === "AUTHORIZED") {
    // Reset pre-start helmet counter now that authorization is granted
    state.consecutiveHelmets = 0;
    setSystemBadge("AUTHORIZED", "START AUTHORIZED (90°)", "state-authorized", "🔓");
    warningBanner.style.display = "none";
    sendServoCommand(90);
  } else if (newState === "BLOCKED") {
    setSystemBadge("BLOCKED", "START BLOCKED (0°)", "state-blocked", "🔒");
    warningBanner.style.display = "none";
    sendServoCommand(0);
  } else if (newState === "WARNING") {
    setSystemBadge("WARNING", "WARNING: HELMET REMOVED", "state-warning", "⚠️");
    startWarningCountdown();
  } else if (newState === "VIOLATION") {
    setSystemBadge("VIOLATION", "DEMO VIOLATION LOGGED", "state-blocked", "🚨");
    warningBanner.style.display = "none";
    onViolationConfirmed();
  }
}

function startWarningCountdown() {
  const preset = parseInt(selectPreset.value, 10) || 120;
  state.warningSecondsLeft = preset;
  warningCountdown.textContent = `${state.warningSecondsLeft}s`;
  warningBanner.style.display = "flex";

  if (state.warningTimerId) clearInterval(state.warningTimerId);

  state.warningTimerId = setInterval(() => {
    state.warningSecondsLeft--;
    warningCountdown.textContent = `${state.warningSecondsLeft}s`;

    if (state.warningSecondsLeft <= 0) {
      clearInterval(state.warningTimerId);
      state.warningTimerId = null; // Prevent stale timer reference
      transitionTo("VIOLATION");
    }
  }, 1000);
}

function cancelWarning() {
  if (state.warningTimerId) {
    clearInterval(state.warningTimerId);
    state.warningTimerId = null;
  }
  state.consecutiveNoHelmets = 0;
  warningBanner.style.display = "none";
}

function onViolationConfirmed() {
  console.log("Confirmed demonstration violation for vehicle:", inputVehicle.value);

  if (navigator.geolocation) {
    navigator.geolocation.getCurrentPosition(
      (pos) => {
        const loc = `${pos.coords.latitude.toFixed(5)}, ${pos.coords.longitude.toFixed(5)}`;
        sendViolationRecord(loc);
      },
      () => {
        sendViolationRecord("Unavailable");
      },
      { timeout: 3000 }
    );
  } else {
    sendViolationRecord("Unavailable");
  }
}

function captureEvidenceDataURL() {
  /**
   * Captures the current camera frame directly as a data:image/jpeg;base64,... string.
   * Uses canvas.toDataURL() instead of Blob+FileReader to guarantee correct MIME type.
   */
  if (!videoElem.videoWidth) return "";
  try {
    const evidenceCanvas = document.createElement("canvas");
    evidenceCanvas.width = Math.min(videoElem.videoWidth, 640);
    const aspect = videoElem.videoHeight / videoElem.videoWidth;
    evidenceCanvas.height = Math.round(evidenceCanvas.width * aspect);
    const ctx = evidenceCanvas.getContext("2d");
    ctx.drawImage(videoElem, 0, 0, evidenceCanvas.width, evidenceCanvas.height);
    return evidenceCanvas.toDataURL("image/jpeg", 0.8);
  } catch (e) {
    console.warn("Failed to capture evidence frame:", e);
    return "";
  }
}

function sendViolationRecord(locationStr) {
  const vehicle = inputVehicle.value.trim() || "DEMO-VEHICLE";

  // Capture evidence frame directly from camera as a proper data:image/jpeg URL
  const evidenceDataURL = captureEvidenceDataURL();
  const confidence = state.lastNoHelmetConfidence;
  postViolationPayload(vehicle, evidenceDataURL, locationStr, confidence);
}

async function postViolationPayload(vehicle, base64Image, locationStr, confidence) {
  try {
    const res = await fetch("/api/violations", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        vehicle_number: vehicle,
        image_base64: base64Image,
        location: locationStr,
        confidence: confidence || 0.0
      })
    });
    if (res.ok) {
      const data = await res.json();
      console.log("Violation record saved to database, ID:", data.id);
      // Release the cached no-helmet frame from memory after successful upload
      state.bestNoHelmetFrame = null;
      state.lastNoHelmetConfidence = 0.0;
    }
  } catch (err) {
    console.warn("Failed to record violation:", err);
  }
}

// ==========================================
// 8. TELEMETRY & UI UPDATERS
// ==========================================
function updateTelemetry(result) {
  const helmetPct = Math.min(100, Math.max(0, result.helmet_confidence || 0));
  const nohelmetPct = Math.min(100, Math.max(0, result.no_helmet_confidence || 0));

  helmetConfVal.textContent = `${helmetPct.toFixed(1)}%`;
  helmetConfBar.style.width = `${helmetPct}%`;

  nohelmetConfVal.textContent = `${nohelmetPct.toFixed(1)}%`;
  nohelmetConfBar.style.width = `${nohelmetPct}%`;

  latencyDisplay.textContent = result.latency_ms ? `${Math.round(result.latency_ms)} ms` : "-- ms";
}

function updateCounterDisplays() {
  helmetCountDisplay.textContent = state.consecutiveHelmets;
  nohelmetCountDisplay.textContent = state.consecutiveNoHelmets;
}

function setSystemBadge(statusClass, labelText, colorClass, iconEmoji) {
  stateText.textContent = labelText;
  stateIcon.textContent = iconEmoji;

  stateText.className = "state-value " + colorClass;
}

// ==========================================
// 9. SERVO HARDWARE CONTROL (ROUTES 1 & 2)
// ==========================================
async function sendServoCommand(angle) {
  const route = selectRoute.value;
  console.log(`Sending Servo Angle: ${angle}° via ${route}`);

  if (route === "route1") {
    // Route 1: Direct phone to NodeMCU via hotspot
    const ip = inputNodeMcuIp.value.trim();
    if (!ip) return;
    const url = `http://${ip}/servo?angle=${angle}&key=${CONFIG.SHARED_SECRET}`;

    try {
      const resp = await fetch(url, { method: "GET", mode: "cors" });
      if (resp.ok) {
        setHardwareStatus(true, `NodeMCU: CONNECTED (${angle}°)`);
      } else {
        setHardwareStatus(false, "NodeMCU: ERROR");
      }
    } catch (err) {
      // Local HTTP call might be blocked if mixed content flag is not set
      setHardwareStatus(false, "NodeMCU: NOT REACHABLE (Check Hotspot)");
    }
  } else {
    // Route 2: Cloud Relay (/api/command)
    try {
      const resp = await fetch("/api/command", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          angle: angle,
          secret: CONFIG.SHARED_SECRET
        })
      });
      if (resp.ok) {
        setHardwareStatus(true, `Relay: QUEUED (${angle}°)`);
      }
    } catch (err) {
      setHardwareStatus(false, "Relay: FAILED");
    }
  }
}

function setHardwareStatus(connected, text) {
  state.nodeMcuReachable = connected;
  hwStatusText.textContent = text;
  hwStatusChip.className = connected ? "status-chip chip-connected" : "status-chip chip-disconnected";
}

// ==========================================
// 10. USER INTERACTIONS & EVENT LISTENERS
// ==========================================
btnToggle.addEventListener("click", async () => {
  if (!state.isMonitoring) {
    // Start Monitoring
    const ok = await startCamera();
    if (ok) {
      state.isMonitoring = true;
      btnToggleText.textContent = "Stop Monitoring";
      btnToggle.classList.add("btn-active-stop");
      transitionTo("BLOCKED"); // Initial state is blocked
      runDetectionCycle();
    }
  } else {
    // Stop Monitoring
    state.isMonitoring = false;
    btnToggleText.textContent = "Start Monitoring";
    btnToggle.classList.remove("btn-active-stop");
    cancelWarning();
    if (state.detectionTimerId) clearTimeout(state.detectionTimerId);
    stopCamera();
    transitionTo("BLOCKED");
  }
});

btnTestServo.addEventListener("click", async () => {
  // Manual Sweep Test
  btnTestServo.disabled = true;
  btnTestServo.textContent = "Sweeping: 90°...";
  await sendServoCommand(90);
  setTimeout(async () => {
    btnTestServo.textContent = "Sweeping: 0°...";
    await sendServoCommand(0);
    setTimeout(() => {
      btnTestServo.disabled = false;
      btnTestServo.textContent = "Simulate Manual Servo Sweep (0° ⇄ 90°)";
    }, 1500);
  }, 2000);
});

// Show / hide the NodeMCU IP input depending on selected route
const nodeMcuIpWrap = document.getElementById("nodemcu-ip-wrap");
function updateRouteVisibility() {
  if (nodeMcuIpWrap) {
    nodeMcuIpWrap.style.display = selectRoute.value === "route1" ? "flex" : "none";
  }
}
selectRoute.addEventListener("change", updateRouteVisibility);
updateRouteVisibility(); // apply on page load
