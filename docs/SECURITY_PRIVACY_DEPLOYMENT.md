# Smart Helmet Guard: Security, Privacy, and Deployment

Consistent with `ARCHITECTURE.md`.

---

## 1. Safety boundary

- The servo is a simulation. Nothing is connected to an engine, ignition, or fuel system.
- Records are demonstration records, not e-challans. Nothing is sent to any authority.
- A real deployment would need legal authorization, consent, secure integration, and proper review processes.

## 2. Secrets and keys

| Secret | Where it lives | Never put it in |
|---|---|---|
| `ROBOFLOW_API_KEY` | Backend environment variable | Frontend code, chat, screenshots, GitHub |
| `NODEMCU_SECRET` | Backend environment variable and NodeMCU firmware | Public repository |
| Dashboard password | Backend environment variable | Frontend code |
| Database URL | Backend environment variable | Public repository |

- Add a `.gitignore` that excludes `.env` files and any firmware file holding the Wi-Fi password and secret.
- Use a private repository, or keep secrets in a separate untracked file.
- If any key is exposed, regenerate it immediately (Roboflow: Settings, API Keys).
- Use the Roboflow **private** key on the backend only.

## 3. Access control

- NodeMCU commands (Route 1 and Route 2) require the shared secret. There is no open, unauthenticated control endpoint.
- `GET /api/violations`, `PATCH /api/violations/{id}`, and `GET /dashboard` require the dashboard password.
- The phone-to-NodeMCU route (Route 1) works over the local hotspot only. The secret is still required.
- The secret travels over the local hotspot in plain HTTP on Route 1, so treat it as a demo-level protection, not strong security. Say this honestly.
- Add basic limits (for example, size limits on uploaded frames) to the backend.

## 4. Privacy design

1. Capture a frame on the phone.
2. Send it to the backend over HTTPS, resized small.
3. The backend holds it **in memory only**, calls Roboflow, returns the state, and discards it.
4. The phone keeps the best no-helmet frame **in memory**.
5. Only if a violation is confirmed does the phone upload that one image with the metadata.
6. Ordinary frames are never saved to disk or the database.

**What to check, because hosting platforms may keep data you did not intend:**

- Application logs: never log image data or base64 strings.
- Temporary files: do not write frames to disk, and check that no library does it for you.
- Debugging tools and error trackers: make sure they do not capture request bodies.
- Database backups: stored images will exist inside backups.
- Roboflow: frames reach Roboflow's servers. Check its current terms on how inference images are handled, and tell judges.

**Honest limits**

- Frames leave the phone (backend, then Roboflow). Do not claim "nothing leaves the device".
- Memory-only handling reduces storage but cannot guarantee that a third-party service keeps nothing.

**People**

- Use only volunteers who agreed to appear in photos and records.
- Delete demonstration records after the exhibition.
- Do not use real vehicle numbers of other people. Use a sample number such as `DL01AB1234`.

## 5. Location

- Request the phone location with permission (needs HTTPS).
- If denied or unavailable, store "Unavailable".
- Never invent or simulate coordinates and present them as real.

## 6. Deployment

**Hosting:** a free cloud host such as Render serves the backend and frontend over HTTPS. HTTPS is required for camera and location access. Free tiers can sleep when idle, so the first request can be slow. Verify the host's current free-tier terms before depending on it.

**Environment variables**

```
ROBOFLOW_API_KEY=...
ROBOFLOW_MODEL_ID=...        # exact id/version from the Deploy dialog
NODEMCU_SECRET=...
DASHBOARD_PASSWORD=...
DATABASE_URL=...
```

**Backend dependencies (to verify at build time):** FastAPI, Uvicorn, `inference-sdk` (or `requests`), `python-multipart`, and a database driver for the chosen free database.

**Database:** Render's free filesystem is temporary, so local SQLite data can disappear on restart. Use a free hosted database after checking its terms, or accept data loss for a one-day demo.

**Network layout on exhibition day**

- Phone hotspot on, set to **2.4 GHz**.
- NodeMCU joins the hotspot.
- Phone uses mobile data to reach the cloud backend.
- Route 1: phone calls the NodeMCU directly (Chrome flag "Insecure origins treated as secure" with the NodeMCU address added).
- Route 2 (backup): phone sends the command to the cloud and the NodeMCU polls about once per second.
- The NodeMCU IP may change on the hotspot. Check it each session, or set a static IP in the firmware.

## 7. Failure handling

| Failure | System behavior |
|---|---|
| Backend down or sleeping | Error shown, state `UNCERTAIN`, no violation, no authorization |
| Roboflow error or quota | Error shown, `UNCERTAIN` |
| Mobile data lost | Error shown, `UNCERTAIN` |
| NodeMCU unreachable | Shows NOT CONNECTED, never CONNECTED unless reachable |
| Camera denied or blocked | Clear message, `UNCERTAIN` |
| Location denied | Location "Unavailable" |
| Long period of `UNCERTAIN` | Optional "monitoring lost" alert after about 30 s (an alert only, never a violation) |

## 8. Exhibition-day checklist

**Night before**

- [ ] Charge phone and power bank (check the power bank does not auto-shut-off at low current)
- [ ] Flash the final firmware and note the NodeMCU IP
- [ ] Confirm the Roboflow quota is available
- [ ] Confirm every secret is set on the host
- [ ] Remove old test records from the dashboard

**Before judges arrive**

- [ ] Start the hotspot (2.4 GHz) and confirm the NodeMCU joined
- [ ] Wake the backend (open the page, wait for the first response)
- [ ] Set the Chrome flag on the demo phone and test a servo move
- [ ] Allow camera and location permissions
- [ ] Enter the vehicle number
- [ ] Check the demo warning setting (2 minutes for the real run, 15 s preset for short demos)
- [ ] Test Route 2 once as the backup
- [ ] Display the credit: "Helmet model and dataset by kle, CC BY 4.0, Roboflow Universe"

**If something fails**

- NodeMCU not reachable: switch to Route 2.
- Backend slow: wait, since a cold start can take a while on free hosting.
- Model quota reached: switch to the fallback model (Teachable Machine) or show recorded results.

## 9. What to tell judges (short, accurate)

- **AI:** an object-detection model finds the helmet or no-helmet in each frame and reports a confidence. A confidence is not a guarantee.
- **Embedded:** the NodeMCU receives a command and moves the servo. It does not run AI.
- **IoT:** the phone sends commands over the hotspot, with a cloud relay as backup.
- **Privacy:** ordinary frames are processed and discarded. Only a confirmed violation image is stored. Frames still pass through our backend and Roboflow.
- **Limits:** small test set, simulated start only, demonstration records, not a road-ready system.
