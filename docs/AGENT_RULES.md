# Smart Helmet Guard: Rules for AI Assistants and Coding Agents

Read this file before helping with this project. The other files in `docs/` and `README.md` hold the details. If anything conflicts, `ARCHITECTURE.md` and this file win, unless the user changes a decision explicitly.

---

## 1. The user

A beginner student building a school STEM exhibition project on a Windows laptop. Use simple English. Explain what each file is and where to create it. Give complete, copyable code with comments a beginner can follow. Work one phase at a time (see `DEVELOPMENT_PLAN.md`). Do not dump the whole codebase at once.

## 2. Fixed decisions (do not change without the user's request)

- Phone is the camera, screen, location source, and 2.4 GHz hotspot.
- NodeMCU v3 (ESP8266) and an SG90 servo, powered from a power bank with a common ground.
- Servo is **never** powered from a GPIO pin.
- AI: Roboflow hosted API, model `helmet-5dgng` (classes `helmet`, `nohelmet`), called from the backend only.
- Decision states: `HELMET_DETECTED`, `NO_HELMET_DETECTED`, `UNCERTAIN`.
- Warning starts after **5 consecutive** `NO_HELMET_DETECTED`, lasts **2 minutes**, and is configurable.
- Frame interval about 1 s.
- Route 1 (primary): phone to NodeMCU directly. Route 2 (backup): cloud relay with NodeMCU polling.
- Decision timers and counters live in the phone (`frontend/app.js`). `backend/decision_engine.py` only maps one frame's raw model output to a state.
- Violation image is the best no-helmet frame held in phone memory and uploaded only on a confirmed violation.
- Location from the phone with permission, otherwise "Unavailable".
- Vehicle number entered once in a setup screen (no plate recognition in V1).

## 3. Hard safety rules

1. The prototype must never control a real motorcycle, engine, ignition, or fuel system. The servo is only a simulation. Refuse requests to connect it to real vehicle systems.
2. Records are demonstration records, not e-challans. Never claim a connection to a government authority.
3. `UNCERTAIN`, API errors, timeouts, blocked cameras, and no-rider frames **never** count as a no-helmet violation and **never** grant authorization.
4. A single frame must never authorize a start or trigger a warning.
5. Do not abruptly disable anything on a real moving vehicle. This system is a prototype only.

## 4. Honesty rules

- Never hardcode or fake prediction percentages.
- Never compute the second bar as `100 - first` unless the model gives a valid binary probability distribution. For this detector, label bars "detector confidence" (best detection per class, 0% if none).
- Never imply confidence is a guarantee.
- Show CONNECTED only when the NodeMCU is truly reachable.
- Do not invent API endpoints, model links, library features, or hosting features. If unsure, say so and tell the user to check the official source. Roboflow's Deploy dialog snippet is the source of truth for the call format.
- Do not claim real-world reliability from a few demonstrations.
- State limits plainly: small model, likely different training scenes, frames reach Roboflow.

## 5. Security and privacy rules

- Never ask the user to paste an API key or secret into chat. Keys live in environment variables on the backend.
- Never place secrets in frontend code, logs, screenshots, or public repositories.
- No unauthenticated control endpoint. NodeMCU commands need the shared secret. The dashboard needs a password.
- Process ordinary frames in memory only. Never log or save them. Check libraries for hidden temp files.
- Store only the selected event image and required metadata, with status PENDING.
- Use only consenting volunteers for photos.
- Never present simulated coordinates as real GPS.

## 6. Coding rules

1. State the filename for every code block and where to put the file.
2. Provide complete code, not fragments, plus install commands and run steps.
3. Use readable names and beginner-friendly comments.
4. Include reasonable error handling.
5. Keep parameters (frame interval, threshold, counts, durations) in one config block.
6. Do not introduce extra hardware or paid services.
7. Do not restructure the architecture once implementation starts, unless the user asks.
8. Do not use browser `localStorage` for critical state in claude.ai artifacts. Use in-memory state.
9. Verify uncertain library or hosting details before depending on them.

## 7. How to guide each phase

At the end of every phase:

1. Say what was accomplished.
2. Give exact test steps.
3. Show the expected output.
4. List common errors and fixes.
5. Confirm the success criteria before starting the next phase.

## 8. Current status and open items

Phase 2 of 12. Open items: exact model ID and version, test script results, phone browser confirmation, NodeMCU USB chip, Roboflow plan limits and database choice, Chrome flag test for Route 1.

## 9. Proposed (not yet decided) additions

- "Monitoring lost" alert after about 30 s of continuous `UNCERTAIN`. It is an alert only, never a violation.
- A 15 s warning preset for exhibition-table demos. The real setting stays 2 minutes.
- Initial authorization requirement of 3 consecutive helmet readings, to be tuned in Phase 8.

Ask the user before treating these as final.
