# Smart Helmet Guard

**AI-Based Helmet Detection, Vehicle Start Authorization, and Helmet Compliance Monitoring**

A school-level STEM exhibition prototype. A phone camera and an AI model check whether a two-wheeler rider is wearing a helmet. A servo motor *simulates* vehicle-start authorization. If the helmet stays off, a *demonstration* violation record is created.

> **Safety boundary:** The servo only represents a start-authorization mechanism. Nothing connects to a real engine, ignition, or fuel system. No real e-challans are issued, and nothing is sent to any government system. All records are demonstration records.

---

## What it does (in order)

1. The phone camera takes a small picture about once per second.
2. The cloud backend asks the AI model: helmet, no helmet, or unsure?
3. The phone shows two confidence bars, the status, and any countdown.
4. **Before start:** helmet detected in several consecutive readings, so the servo moves to 90° (START AUTHORIZED). Otherwise it stays at 0° (START BLOCKED).
5. **After start:** the camera keeps checking. 5 consecutive no-helmet readings begin a **2-minute warning**.
6. Helmet detected again, so the warning is cancelled. Otherwise a **potential violation record** is saved (image, time, location, vehicle number, status PENDING).
7. A password-protected **authority dashboard** lists the records. A reviewer marks each Reviewed or Dismissed.

`UNCERTAIN` readings (blur, blocked camera, no rider, API error) are **never** counted as violations or as authorizations.

---

## Fixed decisions

| Topic | Decision |
|---|---|
| Camera and screen | Android phone, Chrome browser (to be confirmed) |
| Microcontroller | NodeMCU v3 (ESP8266), no AI on it |
| Actuator | SG90 servo: 0° = blocked, 90° = authorized |
| Power | Power bank, common ground, servo never powered from a GPIO pin |
| Network | Phone hotspot, **2.4 GHz** |
| AI model (V1) | Roboflow hosted API, public Universe model `helmet-5dgng` (classes `helmet`, `nohelmet`), called only from the backend |
| Where decision logic lives (V1) | Phone (`frontend/app.js`) for timers and counters. The backend only maps one frame's model output to a state |
| NodeMCU route | **Route 1 (primary):** phone to NodeMCU directly over the hotspot. **Route 2 (backup):** phone to cloud, NodeMCU polls about once per second |
| Frame interval | About 1 second (may slow to 1.5 to 2 s after measuring latency) |
| No-helmet trigger | 5 consecutive `NO_HELMET_DETECTED` readings |
| Warning duration | 2 minutes (configurable) |
| Violation image | Best no-helmet frame held in phone memory, uploaded only when a violation is confirmed |
| Location | Phone location API with permission, else "Unavailable" (never invented) |

---

## Documents

| File | Purpose |
|---|---|
| `docs/ARCHITECTURE.md` | Components, data flow, states, endpoints, routes |
| `docs/DEVELOPMENT_PLAN.md` | The 12 build phases with tests and success criteria |
| `docs/TESTING.md` | 13+ test scenarios and how to measure model accuracy |
| `docs/SECURITY_PRIVACY_DEPLOYMENT.md` | Keys, privacy, hosting, exhibition-day checklist |
| `docs/AGENT_RULES.md` | Rules for any AI assistant helping build this project |

---

## Planned folder structure

```
smart-helmet-guard/
├── README.md
├── docs/
├── frontend/
│   ├── index.html
│   ├── style.css
│   └── app.js
├── backend/
│   ├── app.py
│   ├── helmet_detector.py
│   ├── decision_engine.py
│   ├── database.py
│   └── requirements.txt
└── firmware/
    └── nodemcu_servo.ino
```

---

---

## Current Status: ALL PHASES COMPLETED (Phases 1 - 12)

| Phase | Description | Status |
|---|---|---|
| **Phase 1** | Python environment & hardware preparation | ✅ Complete |
| **Phase 2** | AI model selection & verification (`test_roboflow.py`) | ✅ Complete (`safety-helemt/3` verified ~90.5%) |
| **Phase 3** | Mobile-first web app with camera preview (`index.html`) | ✅ Complete |
| **Phase 4** | In-memory frame inference API (`/api/detect`) | ✅ Complete |
| **Phase 5** | Real-time honest detector confidence bars | ✅ Complete |
| **Phase 6** | NodeMCU firmware & servo controller (`firmware/nodemcu_servo.ino`) | ✅ Complete |
| **Phase 7** | Direct Route 1 HTTP & Route 2 Cloud Relay (`/api/command`) | ✅ Complete |
| **Phase 8** | Start authorization logic (3 consecutive helmet readings) | ✅ Complete |
| **Phase 9** | 5 consecutive no-helmet alert & countdown timer | ✅ Complete |
| **Phase 10**| Demonstration violation record creation (`POST /api/violations`) | ✅ Complete |
| **Phase 11**| Password-protected Authority Dashboard (`/dashboard`) + MongoDB Atlas & SQLite | ✅ Complete |
| **Phase 12**| Exhibition test suite & presentation rehearsal | ✅ Complete |

---

## Quickstart Guide

### 1. Install Backend Dependencies
```bash
pip install -r backend/requirements.txt
```

### 2. Configure Environment (`.env`)
Ensure `.env` contains:
```env
ROBOFLOW_API_KEY=your_key_here
ROBOFLOW_MODEL_ID=safety-helemt/3
MONGODB_URI=mongodb+srv://<username>:<password>@cluster0.t4detqw.mongodb.net/?retryWrites=true&w=majority&appName=Cluster0
NODEMCU_SECRET=smart_guard_secret_123
DASHBOARD_PASSWORD=admin123
```

### 3. Run the Backend Server
```bash
python -m uvicorn backend.app:app --host 0.0.0.0 --port 8000
```
- Open Mobile Camera Monitor: `http://localhost:8000/`
- Open Authority Review Portal: `http://localhost:8000/dashboard` (Default Password: `admin123`)

### 4. Flash NodeMCU Firmware (`firmware/nodemcu_servo.ino`)
1. Open `firmware/nodemcu_servo.ino` in Arduino IDE.
2. Select Board: **NodeMCU 1.0 (ESP-12E Module)**.
3. Update `WIFI_SSID` and `WIFI_PASSWORD` with your 2.4 GHz phone hotspot credentials.
4. Wire SG90 Servo:
   - **Signal (Orange/Yellow):** NodeMCU Pin `D4` (GPIO2)
   - **VCC (Red):** External 5V Power Bank (NEVER power from NodeMCU GPIO or 3.3V)
   - **GND (Brown/Black):** Common Ground with NodeMCU GND and Power Bank GND
5. Upload the sketch and note the NodeMCU IP address shown in Serial Monitor (115200 baud).

---

## Exhibition Demonstration Steps

1. **Setup:** Turn on 2.4 GHz phone hotspot, power NodeMCU with power bank, and start backend.
2. **Launch:** Open `http://<laptop-ip>:8000/` in the phone browser, enter vehicle plate, and press **Start Monitoring**.
3. **Helmet Verification:** Show a helmet to the camera. The green confidence bar rises to ~90%. After 3 consecutive helmet readings, state changes to **START AUTHORIZED** and servo turns to **90°**.
4. **Helmet Removal & Warning:** Remove helmet. After 5 consecutive readings without a helmet, the warning banner triggers with a countdown (120s or 15s demo preset).
5. **Recovery (Test 4):** Put helmet back on before timer reaches 0s -> Warning disappears, servo stays authorized.
6. **Violation Trigger (Test 5):** Leave helmet off until countdown finishes -> A demonstration violation record with camera evidence is logged.
7. **Authority Review:** Open `/dashboard`, log in with `admin123`, view the captured evidence image, and mark the record **Reviewed**.

---

## Credit & Honest Limits

- **Model & Dataset:** Roboflow Universe model.
- **Safety Boundary:** The servo is strictly a simulation of vehicle-start authorization. Nothing connects to real vehicle ignition or engine systems.
- **Privacy Design:** Normal video frames are processed in-memory only and immediately discarded. Only a confirmed violation snapshot is retained for demonstration review.
