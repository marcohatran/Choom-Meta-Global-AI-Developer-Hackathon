"""Choom API + static web app, one Cloud Run service."""

import json
import logging
import os
import random
import secrets
import time
from pathlib import Path

import base64

from fastapi import Depends, FastAPI, File, Form, HTTPException, Request, Response, UploadFile
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from app import agents, muse
from app.content import SPEAKING_QUESTIONS, TASK2_QUESTIONS
from app.store import db, now, today

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s %(message)s")
log = logging.getLogger("choom")

LEARNER_DAILY = int(os.environ.get("AI_LEARNER_DAILY", "40"))
GLOBAL_DAILY = int(os.environ.get("AI_GLOBAL_DAILY", "3000"))
SECURE = os.environ.get("STORE", "firestore") != "memory"
STATIC = Path(__file__).parent / "static"
IMAGE_TYPES = {"image/jpeg", "image/png", "image/webp"}

app = FastAPI(title="Choom", docs_url=None, redoc_url=None)


@app.on_event("startup")
async def seed_charts():
    """Ship a few verified Task 1 charts so the first learner never waits for image generation."""
    for f in (Path(__file__).parent / "seed").glob("*.json"):
        c = json.loads(f.read_text())
        if not await db.get(f"charts/{c['id']}"):
            await db.set(f"charts/{c['id']}", c, merge=False)


@app.middleware("http")
async def headers(request: Request, call_next):
    t = time.time()
    resp = await call_next(request)
    resp.headers["X-Content-Type-Options"] = "nosniff"
    resp.headers["Referrer-Policy"] = "same-origin"
    resp.headers["Permissions-Policy"] = "microphone=(self), camera=(self)"
    if request.url.path.startswith("/api/"):
        log.info("%s %s %s %.0fms", request.method, request.url.path, resp.status_code, (time.time() - t) * 1000)
    return resp


@app.exception_handler(muse.MuseError)
async def muse_error(_: Request, e: muse.MuseError):
    log.error("muse error: %s", e)
    return JSONResponse({"detail": "The AI examiner is busy right now. Please try again in a moment."}, status_code=503)


@app.exception_handler(ValueError)
async def value_error(_: Request, e: ValueError):
    return JSONResponse({"detail": str(e)}, status_code=422)


def learner(request: Request, response: Response) -> str:
    lid = request.cookies.get("cid", "")
    if not (len(lid) == 32 and lid.isalnum()):
        lid = secrets.token_hex(16)
    response.set_cookie("cid", lid, max_age=365 * 86400, httponly=True, samesite="lax", secure=SECURE)
    return lid


async def quota(lid: str = Depends(learner)) -> str:
    """Cost guard: per-learner and global daily caps on AI actions."""
    if await db.incr(f"usage/{today()}", "calls") > GLOBAL_DAILY:
        raise HTTPException(429, "Choom has reached today's AI capacity. Please come back tomorrow.")
    if await db.incr(f"usage/{today()}_{lid}", "calls") > LEARNER_DAILY:
        raise HTTPException(429, f"You have used today's {LEARNER_DAILY} AI checks. See you tomorrow!")
    return lid


async def save_attempt(lid: str, skill: str, kind: str, question: str, answer: str, result: dict) -> str:
    return await db.add(f"learners/{lid}/attempts", {"skill": skill, "kind": kind, "question": question[:1000],
                                                     "answer": answer[:6000], "result": result, "created": now()})


# ---------- profile & plan ----------

class Onboard(BaseModel):
    name: str = Field("", max_length=40)
    target: float = Field(ge=4, le=9)
    current: float | None = Field(None, ge=0, le=9)
    test_date: str = Field("", max_length=10)
    minutes_per_day: int = Field(30, ge=10, le=120)
    weakest: str = Field("writing", pattern="^(writing|speaking|reading|listening)$")
    lang: str = Field("en", pattern="^(en|vi)$")


@app.post("/api/onboard")
async def onboard(body: Onboard, lid: str = Depends(quota)):
    profile = body.model_dump()
    plan = await agents.make_plan(profile)
    await db.set(f"learners/{lid}", {**profile, "plan": plan, "created": now()})
    return {"plan": plan}


@app.get("/api/me")
async def me(lid: str = Depends(learner)):
    profile = await db.get(f"learners/{lid}")
    attempts = await db.list(f"learners/{lid}/attempts", 50)
    return {"profile": profile, "attempts": attempts, "weak_areas": agents.weak_areas(attempts)}


@app.post("/api/reset")
async def reset(response: Response):
    response.delete_cookie("cid")
    return {"ok": True}


# ---------- writing ----------

@app.get("/api/writing/task2")
async def task2_question():
    return {"question": random.choice(TASK2_QUESTIONS)}


@app.get("/api/writing/task1")
async def task1_existing():
    charts = await db.list("charts", 20)
    if not charts:
        return {"chart": None}
    c = random.choice(charts)
    return {"chart": {k: c[k] for k in ("id", "title", "question", "verified")}}


@app.post("/api/writing/task1/new")
async def task1_new(_: str = Depends(quota)):
    c = await agents.new_chart()
    return {"chart": {k: c[k] for k in ("id", "title", "question", "verified")}}


@app.get("/api/charts/{cid}.webp")
async def chart_image(cid: str):
    if not cid.isalnum() or len(cid) > 40:
        raise HTTPException(404)
    c = await db.get(f"charts/{cid}")
    if not c:
        raise HTTPException(404)
    return Response(base64.b64decode(c["image"]), media_type="image/webp",
                    headers={"Cache-Control": "public, max-age=86400"})


async def _read_image(photo: UploadFile) -> tuple[bytes, str]:
    if photo.content_type not in IMAGE_TYPES:
        raise ValueError("Please upload a JPG, PNG or WebP photo.")
    img = await photo.read(8_000_001)
    if len(img) > 8_000_000:
        raise ValueError("The photo is too large (max 8 MB).")
    return img, photo.content_type


@app.post("/api/writing/ocr")
async def writing_ocr(photo: UploadFile = File(...), _: str = Depends(quota)):
    img, mime = await _read_image(photo)
    r = await agents.ocr(img, mime)
    if not r["legible"]:
        raise ValueError("We could not read the handwriting clearly. Try a sharper photo in good light.")
    return {"text": r["text"]}


class WritingIn(BaseModel):
    task_type: str = Field(pattern="^(task1|task2)$")
    question: str = Field(min_length=10, max_length=1500)
    essay: str = Field(min_length=20, max_length=6000)
    chart_id: str | None = Field(None, max_length=40)


@app.post("/api/writing/grade")
async def writing_grade(body: WritingIn, lid: str = Depends(quota)):
    chart = None
    if body.task_type == "task1" and body.chart_id:
        chart = await db.get(f"charts/{body.chart_id}") if body.chart_id.isalnum() else None
    result = await agents.grade_writing(body.task_type, body.question, body.essay, chart)
    result["attempt_id"] = await save_attempt(lid, "writing", body.task_type, body.question, body.essay, result)
    return result


# ---------- speaking ----------

@app.get("/api/speaking/question")
async def speaking_question(part: str = "part1"):
    if part not in SPEAKING_QUESTIONS:
        raise HTTPException(404)
    return {"part": part, "question": random.choice(SPEAKING_QUESTIONS[part])}


@app.post("/api/speaking/grade")
async def speaking_grade(part: str = Form(..., pattern="^part[123]$"), question: str = Form(..., max_length=800),
                         audio: UploadFile = File(...), lid: str = Depends(quota)):
    wav = await audio.read(20_000_001)
    if len(wav) > 20_000_000 or wav[:4] != b"RIFF" or wav[8:12] != b"WAVE":
        raise ValueError("Please send a WAV recording under 3 minutes.")
    result = await agents.grade_speaking(part, question, wav)
    result["attempt_id"] = await save_attempt(lid, "speaking", part, question, result["transcript"], result)
    return result


# ---------- coach ----------

class Msg(BaseModel):
    role: str = Field(pattern="^(user|assistant)$")
    content: str = Field(max_length=4000)


class CoachIn(BaseModel):
    message: str = Field(min_length=1, max_length=1500)
    history: list[Msg] = Field(default_factory=list, max_length=20)


@app.post("/api/coach")
async def coach(body: CoachIn, lid: str = Depends(quota)):
    return await agents.coach(lid, [m.model_dump() for m in body.history], body.message)


class DrillAnswer(BaseModel):
    title: str = Field(max_length=200)
    correct: int = Field(ge=0, le=10)
    total: int = Field(ge=1, le=10)


@app.post("/api/drill/done")
async def drill_done(body: DrillAnswer, lid: str = Depends(learner)):
    await db.add(f"learners/{lid}/drills", {**body.model_dump(), "created": now()})
    return {"ok": True}


@app.get("/health")
async def health():
    return {"ok": True}


app.mount("/static", StaticFiles(directory=STATIC), name="static")


@app.get("/{path:path}")
async def spa(path: str):
    if path.startswith("api/"):
        raise HTTPException(404)
    return FileResponse(STATIC / "index.html", headers={"Cache-Control": "no-cache"})
