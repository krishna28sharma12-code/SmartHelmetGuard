# Smart Helmet Guard: Testing Plan

Matches the settings in `DEVELOPMENT_PLAN.md`: frame about 1 s, 5 consecutive no-helmet readings, 120 s warning (15 s demo preset allowed for table demos).

Use **consenting volunteers only**. Images pass through the backend and Roboflow.

---

## Part A: System tests

| # | Scenario | Expected result |
|---|---|---|
| 1 | Helmet clearly visible | `HELMET_DETECTED`, helmet bar filled, real percentages shown |
| 2 | No helmet visible | `NO_HELMET_DETECTED`, no-helmet bar filled, start stays BLOCKED |
| 3 | Helmet removed after start | After 5 consecutive no-helmet readings the warning countdown begins |
| 4 | Helmet worn again before the warning ends | Warning cancelled, counter reset |
| 5 | No helmet for the whole warning | One potential violation record created, status PENDING |
| 6 | Camera blocked | `UNCERTAIN`, no violation declared |
| 7 | Rider leaves the frame | "No rider in view" handled separately, no violation |
| 8 | NodeMCU disconnected | Page shows NOT CONNECTED, servo state never shown as successful |
| 9 | Mobile data lost | Error message, state `UNCERTAIN`, no violation, no authorization |
| 10 | Low-confidence prediction | `UNCERTAIN` or continued verification, never a violation |
| 11 | Camera permission denied | Clear instruction to enable the camera permission |
| 12 | Ordinary frame processed | No frame is saved to disk or the database |
| 13 | Confirmed demo event | Only the selected event image and required metadata are stored |
| 14 | Helmet held in hand or on the handlebar | Record what happens. Note it as a known limitation if it reads as `helmet` |
| 15 | Backend asleep or down | Error shown, `UNCERTAIN`, no violation |
| 16 | Location permission denied | Location saved as "Unavailable", no invented coordinates |
| 17 | Wrong or missing secret key sent to NodeMCU | Command rejected, servo does not move |
| 18 | Dashboard opened without the password | Access refused |

### Example timeline for Tests 3 to 5

```
T=00 s  Helmet detected      -> START AUTHORIZED, servo 90°
T=01 s  No helmet (1)        -> counter = 1
T=02 s  No helmet (2)
T=03 s  No helmet (3)
T=04 s  No helmet (4)
T=05 s  No helmet (5)        -> WARNING starts (120 s)
T=20 s  Helmet detected      -> warning cancelled, counter = 0   (Test 4)
...or the helmet stays off for 120 s -> violation record (Test 5)
```

An `UNCERTAIN` reading in the middle neither adds to the counter nor cancels the warning in a way that creates a violation.

---

## Part B: Measuring model accuracy

**Photo set (30 to 40 photos, taken from the distance and angle where the phone will be mounted)**

- About 10 wearing a helmet (different angles and lighting)
- About 10 with no helmet
- About 5 hard cases (cap, hood, scarf, hand over head)
- About 5 with no person in view
- About 5 with poor light or blur

**Results table**

| Photo | Truth | Model output | Confidence | Correct? |
|---|---|---|---|---|
| 1 | Helmet | helmet | 87% | Yes |
| 2 | No helmet | nohelmet | 64% | Yes |
| 3 | Cap | helmet | 71% | No |

**Calculate**

- **Overall accuracy** = correct photos / total photos.
- **False "nohelmet"**: helmeted rider called nohelmet. This causes false violations, so it is the most important count.
- **False "helmet"**: bare head called helmet. This wrongly authorizes a start.
- **Empty-scene detections**: any detection on a scene with no rider.
- **Confidence of wrong answers**: if wrong answers tend to have low confidence, a higher threshold will turn them into `UNCERTAIN`.
- **Response time** per call, which sets the frame interval.

**Threshold selection:** try several thresholds on the same photos and pick the one with the fewest harmful errors (false "helmet" and false "nohelmet"), accepting more `UNCERTAIN` results as the trade-off.

**Suggested pass target:** about 90% correct on your own photos, with very few false "nohelmet" on helmeted riders. This is our own target, not an industry standard.

---

## Part C: Honest reporting

- A small test set shows how the model behaves on *your* photos. It does not prove real-world reliability.
- State the number of photos used, the lighting, and the people involved when presenting.
- Report errors openly. Judges value honest limits over perfect-looking demos.

## Part D: Hardware checks

- Servo reaches 0° and 90° repeatedly with no jitter or resets.
- NodeMCU reconnects automatically after a power cycle and after the hotspot restarts.
- Hotspot is set to 2.4 GHz.
- Power bank does not shut off at low current (some do). If it does, use a different power bank.
