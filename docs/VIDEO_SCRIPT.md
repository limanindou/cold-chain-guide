# Video: recording plan and script (target 2:35, hard max 2:55)

Live app: https://d2wcjncrzc05nu.cloudfront.net · Time ×45 · Responders: Nurse Thandi → Manager Pieter → Pharmacist Aisha

## 1. Timer cheat sheet (measured on the live stack)

| What | Real setting | At ×45 (what you'll see) |
|---|---|---|
| Vaccine fridge grace (temperature) | 15 min | **20 s** |
| Blood bank: power-loss grace | 5 min | **6 s** → nurse rings about 5 s after **Power cut** |
| Each responder's time to answer | 10 min | **13 s** → nurse → manager about 21 s after Power cut |
| ⚠️ Manager must tap before | | **about 34 s after Power cut** (or the pharmacist rings) |
| Recovery check after a tap | 5 min | every 6 s → **Resolved** about 6–15 s after **Restore** |
| Silent sensor detected | 5 min offline | 20 s + next 1-minute check → **20–80 s** (cut the wait) |
| Insulin at home grace | 30 min | 40 s (too long for a scene, so not used for the door demo) |

## 2. Before you press record

- [ ] Close other dashboard tabs: one browser tab runs the simulator, and two would fight.
- [ ] Open https://d2wcjncrzc05nu.cloudfront.net → **Reset demo** → wait **2–3 minutes** so the charts fill.
- [ ] Dark mode, browser zoom **110%**, window maximised at 1920×1080, bookmarks bar hidden (Ctrl+Shift+B).
- [ ] Windows **Focus / Do not disturb** on; close Slack/WhatsApp; mute email pop-ups.
- [ ] Tab 2: Gmail (to show one alert email). Tab 3: AWS Console → Step Functions → `coldchain-guard-incident`.
- [ ] Recorder: **Clipchamp** (built into Windows 11) or Xbox Game Bar (**Win+Alt+R**) or OBS. 1080p, microphone on.
- [ ] **No music** (or royalty-free music you have rights to). No third-party logos on screen.

## 3. Record in takes (then edit together)

The demo depends on live timers, so record **one long continuous take** of the dashboard (about 4–5 min) and cut the
waiting out afterwards. Then record short **B-roll** clips. You can record the voice-over live, or afterwards over the edit.

### Take A: the dashboard (one continuous recording, follow the clock)

| When (from start of take) | Click | What you should see |
|---|---|---|
| 0:00 | Nothing. Slowly hover over the four cards | All green, ×45 badge |
| 0:15 | Simulator → **Vaccine fridge → Door open (brief)** | Red spike, card amber **Grace period** |
| ~0:40 | Wait | Back to green; timeline shows **Recovered · no alarm**; no phone rings |
| 0:50 | Simulator → **Blood bank → ⚡ Power cut** | Card shows **On battery · 97%**; *Power lost* incident opens while still in range |
| ~0:55 | Wait, don't tap | **Nurse Thandi** phone rings ("Escalates in 13 s") |
| ~1:05 | Wait | Line climbs through the red band |
| ~1:11 | Wait | Nurse ignored → **Manager Pieter** phone rings; timeline shows *Escalated* |
| **~1:15** | Manager phone → **Moved to backup cooler** (must be before ~1:24) | Check animation, card **Being handled** |
| 1:20 | Simulator → **Blood bank → ✅ Restore** | Back on mains, line falls into the green band |
| ~1:35 | Wait | **Resolved**, then **Evidence sealed** in the timeline |
| 1:40 | Simulator → **Insulin at home → 📡 Sensor goes silent** | Card stops updating |
| ~2:00–2:40 | Wait (cut this in editing) | Card greys out, "Silent for …", **No data**; *Sensor silent* alert; patient's phone rings |
| then | Simulator → **Insulin at home → ✅ Restore** | Readings resume, "Sensor back online" |
| then | Click the **Blood bank** incident in *Recent incidents* | Incident page |
| then | Scroll: chart, escalation ladder, evidence card → **Verify** | ✅ **Match: report is untouched** |
| then | Header → **Profiles** | Six profile cards |

If something goes wrong: **Reset demo**, wait 1 minute, and redo that part.

### B-roll (short separate clips, 5–10 s each)

1. **Step Functions graph:** on the Blood bank incident page click **View workflow in AWS console** → *Graph view*.
   Show the path: Wait (grace) → NotifyResponder → **Escalate** → NotifyResponder → RecordAction → … → BuildEvidence (green).
2. **Gmail:** the "[ColdChain Guard] Action needed: Blood bank…" email arriving.
3. **Architecture diagram:** open `docs/architecture.png` full screen.

## 4. The edit (final timeline, about 2:35)

| Time | Use footage | Voice-over (calm, about 2.5 words/second) |
|---|---|---|
| 0:00–0:14 | Black → slow fade into the green dashboard | "It's 2 a.m. The power goes out at a clinic. By morning, a fridge full of vaccines is warm, and nobody knows for how long. Fridges fail silently." |
| 0:14–0:28 | Take A 0:00–0:14 | "This is ColdChain Guard. Four fridges: vaccines, a blood bank, insulin at a patient's home, frozen plasma. All in range, and no workflow is running. For this demo, time runs forty-five times faster." |
| 0:28–0:44 | Take A door spike → Recovered (speed up the wait 2×) | "Someone opens the vaccine fridge. The line spikes red, but instead of beeping, ColdChain Guard waits a grace period. It recovers, so the incident closes quietly. No alarm. Smart, not noisy." |
| 0:44–1:12 | Take A Power cut → battery badge → nurse rings → manager rings (+ 2 s Gmail B-roll) | "Now a real problem: a power cut at the blood bank. The sensor has a backup battery, so it reports the power loss before anything warms up. The nurse on duty is alerted, in the app and by email. She doesn't answer, and that silence is the signal. The alert escalates to the facility manager automatically." |
| 1:12–1:24 | B-roll: Step Functions graph | "This is the workflow. A wait state is a free timer. The alert is a paused callback that costs nothing. And a timeout turns silence into escalation." |
| 1:24–1:40 | Take A manager taps → Restore → Resolved → Evidence sealed | "The manager taps 'Moved to backup cooler'. The link works once. Power comes back, the temperature returns to the safe range, and the incident resolves." |
| 1:40–1:54 | Take A insulin **Sensor goes silent** → (cut) → greyed card + alert | "And if the sensor itself dies, at home, with the Wi-Fi down in the outage, the silence is the alarm. A tiny once-a-minute check, the only thing that runs while all is well, catches it." |
| 1:54–2:12 | Take A incident page → escalation ladder → **Verify ✅ Match** | "Every incident ends with an evidence report: how long, how warm, who was alerted, and who acted. It's fingerprinted with SHA-256, and anyone can verify it, so a pharmacist can decide: use it, or discard it." |
| 2:12–2:30 | B-roll diagram (5 s) → Take A Profiles page | "It's all serverless: API Gateway, Lambda, Step Functions, DynamoDB, S3, SES and CloudFront, in one SAM template. In production, the sensors connect through AWS IoT Core. Profiles are just data: vaccines, blood, insulin, lab samples, donor milk. One engine for any cold chain." |
| 2:30–2:38 | Logo or dashboard, fade out | "ColdChain Guard. So medicine is still safe when it reaches the patient." |

Editing tips (Clipchamp): split clips at the waits, delete the dead time, use **Speed 2×** on the door wait, add a
small text overlay "time ×45 · waits shortened" during cuts (honest and judge-friendly), and export at **1080p**.

## 5. Upload checklist

- [ ] Length **under 3:00** (aim for 2:35–2:45).
- [ ] YouTube → visibility **Public** (not Unlisted).
- [ ] Title: *ColdChain Guard: a serverless watchdog that saves medicines when the fridge fails (AWS hackathon)*.
- [ ] Description: one paragraph, plus the live app link and the Builder Center article link.
- [ ] Open the link in a **private window** to confirm it plays without signing in.
- [ ] Paste the link into the **demo field** of the submission and into `docs/WRITEUP.md`.
