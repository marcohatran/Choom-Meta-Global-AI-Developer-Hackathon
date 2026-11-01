# Choom: an AI IELTS examiner and coach on Meta Muse

**Live:** https://choom-muse-388628850368.asia-southeast1.run.app · Meta Global AI Developer Hackathon, Startup track, theme *Build for Your World*.

About 3.5 million IELTS tests are taken every year at roughly $180–340 per attempt. Candidates are weakest at the two skills that need a human examiner: Writing and Speaking. A human examiner is the expensive part of preparation, and most learners never get one. Choom gives every learner an examiner-grade report in under 30 seconds, and a coach agent that turns those reports into tomorrow's practice.

## What it does

| Feature | Meta models |
| --- | --- |
| **Planner**: builds a plan from the target band, test date and minutes per day, and says honestly whether the goal is realistic | Muse Spark (structured output) |
| **Writing examiner**: grades Task 1 and Task 2 on the four official criteria, quotes the exact sentences that cost marks, and writes a version one band higher | Muse Spark (structured output) |
| **Handwriting**: photograph a handwritten essay and Choom transcribes it, keeping your mistakes so they can be graded | Muse Spark vision |
| **Task 1 generator**: Spark designs realistic exam data, Muse Image draws the chart, and Spark vision reads the image back so the essay is graded against the chart the learner actually saw | Muse Spark, Muse Image, Muse Spark vision |
| **Speaking examiner**: record an answer in the browser. Voice Transcribe keeps fillers ("um", "uh"), code measures pace, fillers and word variety, then Spark grades the four speaking criteria | Muse Voice Transcribe, Muse Spark |
| **Coach agent**: reads your real scores with tools (parallel tool calls), asks a drill-writer sub-agent for targeted practice, and rewrites today's mission | Muse Wonder (tool calling) + Muse Spark sub-agent |

## How it is built

```
Browser (vanilla JS SPA; mic -> 16 kHz WAV in the browser)
   │
Cloud Run: FastAPI (one service)
   ├─ agents.py   orchestration: planner, examiners, chart pipeline, coach tool loop
   ├─ muse.py     Meta Model API client (chat, json_schema, vision, images, ASR), retries
   ├─ brain       prompt pack + calibration policy (proprietary, loaded at runtime)
   └─ store.py    Firestore (prod) / in-memory (dev)
```

The model proposes and code decides. Every model output passes a gateway before a learner sees it:

- strict JSON schema
- every quoted "mistake" must exist verbatim in the learner's text, or it is dropped
- bands are rounded to half bands
- the overall band uses official IELTS rounding
- calibration rules (length, structure, delivery metrics) can cap a criterion and tell the learner why

Production guardrails:

- per-learner and global daily AI quotas
- input size and type validation at the boundary
- learner text is always passed as data, never as instructions
- retries with backoff on Muse 429 and 5xx errors
- security headers
- a cookie-scoped anonymous identity, so there is no sign-up friction

## Run locally

```bash
cp .env.example .env              # set MUSE_API_KEY
uv sync
STORE=memory uv run uvicorn app.main:app --port 8080 --env-file .env
uv run pytest -q
```

The public repo ships a simplified open prompt pack (`app/brain_open.py`). The production prompt pack and calibration policy are proprietary and are loaded from `app/private/` when present.

## Deploy

```bash
docker build --platform linux/amd64 -t $REGION-docker.pkg.dev/$PROJECT/cloud-run-source-deploy/choom-muse:TAG .
docker push $REGION-docker.pkg.dev/$PROJECT/cloud-run-source-deploy/choom-muse:TAG
gcloud run deploy choom-muse --image ... --region $REGION --env-vars-file env.yaml
```
