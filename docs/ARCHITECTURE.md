# Smart Helmet Guard: System Architecture

School-level STEM exhibition prototype. A phone camera and AI check whether a two-wheeler rider is wearing a helmet. A servo *simulates* start authorization. A *demonstration* violation record is created if the helmet stays off.

**Safety boundary:** The servo is only a simulation. Nothing connects to a real engine, ignition, or fuel system. No real e-challans are issued and nothing is sent to any government system.

---

## 1. High-Level Architecture

```
┌─────────────────────────────────────────────┐
│ PHONE (Android, Chrome, 2.4 GHz hotspot)    │
│  - Camera web page (HTTPS)                  │
│  - Captures a frame about every 1 second    │
│  - Shows bars, status, countdown, events    │
│  - Decision logic: counters and timers (V1) │
│  - Location (with permission)               │
└───────┬──────────────────────┬──────────────┘
        │ frame (HTTPS)        │ servo command
        ▼                      │
┌─────────────────────┐        │  Route 1 (primary): direct over hotspot
│ CLOUD BACKEND       │        │  Route 2 (backup): via cloud relay
│ (e.g. Render)       │        ▼
│  - Holds API key    │   ┌──────────────────────┐
│  - Calls Roboflow   │   │ NodeMCU v3 (ESP8266) │
│  - Violation API    │   │  - Joins hotspot     │
│  - Dashboard API    │   │  - Drives servo      │
│  - Command relay    │   └─────────┬────────────┘
└───┬─────────────┬───┘             ▼
    │             │            ┌──────────┐
    ▼             ▼            │ SG90     │
┌──────────┐ ┌──────────┐      │ servo    │
│ ROBOFLOW │ │ DATABASE │      │ 0° / 90° │
│ hosted   │ │ (free    │      └──────────┘
│ model    │ │ hosted)  │
└──────────┘ └────┬─────┘
                  ▼
        ┌───────────────────────┐
        │ AUTHORITY DASHBOARD   │
        │ (password protected)  │
        └───────────────────────┘
```

---

## 2. Components

### 2.1 Phone (frontend)
| Item | Detail |
|---|---|
| Role | Camera, screen, location source, Wi-Fi hotspot, decision timers and counters |
| Files | `frontend/index.html`, `style.css`, `app.js` |
| Hosting | Served by the cloud backend over HTTPS (camera needs HTTPS) |
| Network | Mobile data to reach cloud. Hotspot (2.4 GHz) for NodeMCU |

Responsibilities:
- Camera preview, Start / Stop Monitoring, permission handling
- Send one small frame about every 1 second
- Show Helmet and No Helmet confidence bars (labeled "detector confidence")
- Show status text so color is never the only signal
- Run the counters, warning countdown, and state machine
- Command the NodeMCU
- Keep the best no-helmet frame in memory and upload it only if a violation is confirmed

### 2.2 Cloud backend
| Item | Detail |
|---|---|
| Role | Hide the API key, call Roboflow, store records, serve dashboard |
| Files | `backend/app.py`, `helmet_detector.py`, `decision_engine.py`, `database.py` |
| Host | Free cloud host such as Render (may sleep when idle) |

Responsibilities:
- Receive frame, call Roboflow, return a prediction, discard the frame (never saved)
- `helmet_detector.py` calls Roboflow. `decision_engine.py` maps one frame's raw result to `HELMET_DETECTED`, `NO_HELMET_DETECTED`, or `UNCERTAIN` (per-frame only, no timers)
- Store violation records
- Serve the authority dashboard
- Relay servo commands (backup route)

### 2.3 Roboflow hosted model
- Public Universe model "helemt Computer Vision Model" by *kle* (`helmet-5dgng`)
- Object detection, classes: `helmet`, `nohelmet`
- CC BY 4.0 (credit on project page and exhibition board)
- Called only from the backend
- Exact model ID and version to be copied from its Deploy dialog

### 2.4 NodeMCU v3 (ESP8266)
- Joins the phone's hotspot
- Runs a tiny web server (Route 1) or polls the cloud (Route 2)
- Moves the servo: 0° = blocked, 90° = authorized
- Does **not** run AI
- Every command needs the shared secret key

### 2.5 Servo and power
- SG90 servo simulates start authorization
- Power bank gives stable 5V to NodeMCU and servo
- Common ground. Servo is never powered from a GPIO pin

### 2.6 Database
- Render's free filesystem is temporary, so SQLite data could be lost
- A free hosted database is the likely choice (check current free-tier terms first)

### 2.7 Authority dashboard
- Separate, password-protected page
- Shows image, vehicle number, location, time, status
- Buttons: Reviewed / Dismissed
- Demo only

---

## 3. Data Flow

### 3.1 Detection loop (every ~1 second)
```
Phone captures frame
   → POST /api/detect (HTTPS) to backend
   → Backend calls Roboflow with the API key
   → Roboflow returns detections + confidence
   → Backend maps to a state and returns it. Frame is discarded.
   → Phone updates bars, status text, counters
```

### 3.2 Servo command
```
Route 1 (primary):  Phone → http://<nodemcu-ip>/servo?angle=90&key=SECRET → servo moves
Route 2 (backup):   Phone → Cloud → NodeMCU polls cloud (~1 s) → servo moves
```

### 3.3 Violation
```
Warning ends with no helmet
   → Phone uploads: best no-helmet frame, timestamp, location, vehicle number
   → POST /api/violations → saved with status PENDING
   → Appears on the authority dashboard
```

---

## 4. Decision States

| State | Meaning |
|---|---|
| `HELMET_DETECTED` | Helmet found with enough confidence |
| `NO_HELMET_DETECTED` | `nohelmet` found with enough confidence |
| `UNCERTAIN` | Low confidence, camera blocked, no rider, API error, or timeout |

**Rules**
- `UNCERTAIN` never counts as no-helmet and never triggers a violation
- API or connection failure is an error state, never a violation and never an authorization
- Empty detection result means "no rider in view", handled separately

### State machine
```
                 ┌───────────────┐
   Start ──────► │   BLOCKED     │ servo 0°
                 │ (pre-start)   │
                 └──────┬────────┘
                        │ several consistent HELMET readings
                        ▼
                 ┌───────────────┐
                 │  AUTHORIZED   │ servo 90°
                 │ (monitoring)  │◄────────────────┐
                 └──────┬────────┘                 │
                        │ 5 consecutive            │ helmet detected again
                        │ NO_HELMET                │ (counter resets)
                        ▼                          │
                 ┌───────────────┐                 │
                 │   WARNING     │─────────────────┘
                 │ 2-min timer   │
                 └──────┬────────┘
                        │ timer ends, no helmet
                        ▼
                 ┌───────────────┐
                 │  VIOLATION    │ record created, status PENDING
                 └───────────────┘
```

---

## 5. Configurable Parameters

Kept in one config block, never hard-coded in the logic.

| Parameter | Default | Note |
|---|---|---|
| Frame interval | ~1 s | May slow to 1.5 to 2 s based on measured latency |
| Confidence threshold | tuned (start 0.50) | Set from test photos |
| Readings needed to authorize | 3 consecutive (initial proposal) | Tune in Phase 8 |
| Consecutive no-helmet count | 5 | Starts the warning |
| Warning duration | 2 min (120 s) | Optional 15 s demo preset |
| Monitoring-lost alert | ~30 s of `UNCERTAIN` (proposed) | Alert only, never a violation |
| Violation criteria | warning ends with no helmet | |

---

## 6. Proposed API Endpoints (backend)

| Endpoint | Purpose |
|---|---|
| `POST /api/detect` | Receive frame, return state and confidences |
| `POST /api/violations` | Create a violation record (PENDING) |
| `GET /api/violations` | List records (dashboard, password required) |
| `PATCH /api/violations/{id}` | Mark Reviewed / Dismissed |
| `POST /api/command` | Phone sends a servo command (Route 2) |
| `GET /api/command/poll` | NodeMCU polls for the latest command (Route 2) |
| `GET /dashboard` | Authority dashboard page |

All command endpoints need the shared secret key. Dashboard endpoints need the password.

---

## 7. NodeMCU Communication Routes

| | Route 1 (primary) | Route 2 (backup) |
|---|---|---|
| Path | Phone → NodeMCU over hotspot | Phone → Cloud → NodeMCU polls |
| Delay | Very low | About 1 second |
| Browser setting | Needs Chrome flag "Insecure origins treated as secure" | None |
| NodeMCU code | Must handle CORS | Must poll HTTPS (`setInsecure()`) |
| Risk | Flag may fail. NodeMCU IP may change | Needs mobile data and cloud up |

Reason for the flag: an HTTPS page cannot call plain `http://` local devices ("mixed content"). Test this early.

---

## 8. Security, Privacy, Failure Handling, Deployment

See `SECURITY_PRIVACY_DEPLOYMENT.md`.

## 9. Fallbacks for the AI Model

1. Roboflow hosted API (current choice)
2. Same dataset forked and trained in own Roboflow workspace
3. Teachable Machine (Helmet, No Helmet, Empty)
4. Later upgrade to a small YOLO model

## 10. Limits to State Honestly

- Small, unproven model, tested only on a few photos so far
- Likely trained on traffic scenes, while the camera here is close to the rider
- Free-plan quotas and speed may limit continuous use
- Confidence bars are not a guarantee of correctness
- A few successful demos do not prove real-world reliability

## 11. Resolved and Open Design Points

**Resolved:** Decision timers and counters live on the phone for V1. `backend/decision_engine.py` only converts one frame's model output into a state.

**Open:** exact model ID and version for `helmet-5dgng`, Chrome flag test for Route 1, NodeMCU USB chip, Roboflow free-plan limits and database choice, phone browser confirmation.
