# Smart Helmet Guard: Development Plan

Build one phase at a time. Do not move on until the success criteria are met. Settings below match `ARCHITECTURE.md`.

**Settings used throughout**

| Parameter | Value |
|---|---|
| Frame interval | about 1 s |
| Confidence threshold | tuned from test photos (start at 0.50, adjust in Phase 2) |
| Readings to authorize | 3 consecutive `HELMET_DETECTED` (initial proposal, tune in Phase 8) |
| Consecutive no-helmet count | 5 |
| Warning duration | 120 s |
| Optional "monitoring lost" alert | after about 30 s of continuous `UNCERTAIN` (proposed; an alert only, never a violation) |
| Optional demo preset | warning of 15 s for the exhibition table (2 minutes stays the real setting) |

---

## Phase 1: Environment and hardware

**Goal:** Windows laptop ready, hardware identified.
**Do:** Install Python (tick "Add Python to PATH") and Arduino IDE. Identify the NodeMCU USB chip (CH340 or CP2102) and install its driver. Confirm the phone browser is Chrome.
**Test:** `python --version` works. Arduino IDE sees the NodeMCU on a COM port.
**Common errors:** No COM port, usually a charge-only USB cable or a missing driver.
**Success:** Python runs and the COM port appears.

## Phase 2: Model selection and verification

**Goal:** Prove the Roboflow model gives usable predictions.
**Do:** Get the exact model ID and version for `helmet-5dgng` from its Deploy dialog. Confirm the class list contains `helmet` and `nohelmet`. Run `backend/test_roboflow.py` on test photos. Set the key with `$env:ROBOFLOW_API_KEY="..."` in PowerShell only.
**Test:** 30 to 40 photos of consenting volunteers (see `TESTING.md`). Record class, confidence, and response time.
**Common errors:** 401/403 (wrong key), 404 (wrong model ID), 429 (quota).
**Success:** About 90% correct on your own photos (our own target, not a standard), very few false "nohelmet" on helmeted riders, no detection on empty scenes, and a measured response time.
**Fallback:** Fork and train in your own workspace, then Teachable Machine.

## Phase 3: Mobile web page with camera

**Goal:** A phone page with live camera preview.
**Do:** Build `frontend/index.html`, `style.css`, `app.js` with Start/Stop buttons and permission handling. Serve over HTTPS.
**Test:** Open on the phone, allow the camera, see the preview. Deny the permission and confirm a clear instruction appears.
**Common errors:** Camera blocked on plain HTTP. Browsers need HTTPS.
**Success:** Preview works and the denied-permission message appears.

**Early spike (about 30 minutes, right after Phase 3):** Try phone to NodeMCU over the hotspot with the Chrome flag. If Route 1 fails, switch to Route 2 and note it.

## Phase 4: Connect model to camera

**Goal:** Frames go to the backend and a prediction returns.
**Do:** Build `backend/app.py` (`POST /api/detect`) and `helmet_detector.py`. The frame stays in memory and is never saved.
**Test:** Hold a helmet up and check the returned state in the browser developer tools or on screen.
**Common errors:** CORS errors, large frames (resize to about 320 px wide), slow responses.
**Success:** A state returns about every second, with no image files written to disk.

## Phase 5: Confidence bars

**Goal:** Two proportional bars showing real model output.
**Do:** Helmet (green) and No Helmet (red), labeled "detector confidence". Show the best detection per class, 0% if none. Yellow for uncertain. Always show status text too.
**Test:** Values change live with no page refresh.
**Common errors:** Faking the second bar as 100 minus the first. Do not do this.
**Success:** Bar lengths match the numbers, and numbers come only from the model.

## Phase 6: NodeMCU firmware and servo test (no AI)

**Goal:** Servo moves on command.
**Do:** Wire servo signal to one GPIO pin, servo power from the 5V supply (power bank), common ground with the NodeMCU. Never power the servo from a GPIO pin. Write `firmware/nodemcu_servo.ino`. Select the NodeMCU 1.0 (ESP-12E) board in Arduino IDE.
**Test:** Sweep 0° to 90° to 0° from a simple sketch.
**Common errors:** Servo jitter or board resets (weak power, missing common ground).
**Success:** Reliable 0° and 90° moves with no resets.

## Phase 7: Phone to NodeMCU communication

**Goal:** The phone's command moves the servo.
**Do:** NodeMCU joins the 2.4 GHz hotspot and serves `/servo?angle=90&key=SECRET` with CORS handling. Add Route 2: `POST /api/command` and `GET /api/command/poll`.
**Test:** Press a test button on the phone page and the servo moves. Power off the NodeMCU and confirm the page shows NOT CONNECTED.
**Common errors:** Mixed-content block (flag not set), IP address changed, hotspot on 5 GHz.
**Success:** Reliable commands, and the status shows CONNECTED only when truly reachable.

## Phase 8: Start authorization logic

**Goal:** Servo follows detection.
**Do:** Implement the BLOCKED to AUTHORIZED transition in `frontend/app.js`. Require consecutive helmet readings above the threshold.
**Test:** Helmet shown, servo goes to 90°. No helmet, it stays at 0°. Camera covered, no change plus the "CHECK CAMERA / HELMET STATUS" message.
**Success:** A single good frame never authorizes, and `UNCERTAIN` never authorizes.

## Phase 9: Monitoring and warning countdown

**Goal:** Warning flow works.
**Do:** After authorization, count consecutive `NO_HELMET_DETECTED`. At 5, start the 120 s countdown. A helmet reading cancels it and resets the counter. `UNCERTAIN` does not count.
**Test:** Run the example sequence from `TESTING.md` (Tests 3 and 4).
**Success:** The countdown starts only after 5 consecutive no-helmet readings and cancels when the helmet returns.

## Phase 10: Potential violation record

**Goal:** Record created after the warning ends.
**Do:** Keep the best no-helmet frame in phone memory only. At warning end, upload it with timestamp, location (or "Unavailable"), vehicle number, and status PENDING through `POST /api/violations`.
**Test:** Run Test 5 in `TESTING.md`.
**Success:** Exactly one record per violation, labeled as a demonstration record.

## Phase 11: Dashboard and database

**Goal:** Authority dashboard shows records.
**Do:** `database.py` plus `GET /dashboard`, `GET /api/violations`, and `PATCH /api/violations/{id}`, all password protected. Choose a free hosted database after checking its current free-tier terms. Render's free filesystem is temporary, so do not rely on local SQLite there.
**Test:** Create a record on the phone and see it on the dashboard. Mark it Reviewed.
**Success:** Records persist after a backend restart.

## Phase 12: Full test and exhibition preparation

**Goal:** Ready for judges.
**Do:** Run every test in `TESTING.md`. Follow the checklist in `SECURITY_PRIVACY_DEPLOYMENT.md`. Rehearse the 10-step demonstration. Prepare a short explanation of the AI, the embedded system, the IoT link, and privacy.
**Success:** All tests pass or have a documented limitation, and a full rehearsal runs without help.

---

## Exhibition demonstration steps

1. Open the app on the phone, allow the camera, enter the vehicle number, press Start Monitoring.
2. Show a person wearing a helmet. Bars and status update from real output.
3. NodeMCU receives authorization and the servo moves to 90° (simulated start authorization).
4. Remove the helmet from view. The no-helmet status appears.
5. The warning countdown begins.
6. Put the helmet back on before it ends. The warning disappears.
7. Repeat and keep the helmet off for the full period (use the demo preset if time is short).
8. A potential violation record is created.
9. Show the record on the authority dashboard.

## Future scope (not part of the prototype)

Number plate recognition, mobile notifications, GPS, remote dashboard, better models, offline inference, accident sensors, and authorized traffic-management integration. Each needs extra work, data, or legal authorization.
