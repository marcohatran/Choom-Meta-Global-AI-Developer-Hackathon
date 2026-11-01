"""Choom agents on Meta Muse. Orchestration and guardrails live here; prompts and calibration come from `brain.pack`.

Principle: the model proposes, code decides. Every model output passes a gateway (schema, quote check,
band rounding, calibration) before a learner sees it or it is stored.
"""

import asyncio
import base64
import json
import random
import re

from app import muse
from app.brain import pack
from app.store import db, now

WRITING_KEYS = ["task", "coherence", "lexical", "grammar"]
SPEAKING_KEYS = ["fluency", "lexical", "grammar", "pronunciation"]


def _obj(props: dict) -> dict:
    return {"type": "object", "properties": props, "required": list(props), "additionalProperties": False}


S, N, B = {"type": "string"}, {"type": "number"}, {"type": "boolean"}


def _arr(item: dict) -> dict:
    return {"type": "array", "items": item}


def _grade_schema(keys: list[str]) -> dict:
    return _obj({
        "criteria": _arr(_obj({"key": {"type": "string", "enum": keys}, "band": N, "comment": S})),
        "strengths": _arr(S),
        "issues": _arr(_obj({"quote": S, "criterion": {"type": "string", "enum": keys}, "problem": S, "fix": S})),
        "improved_version": S,
        "next_step": S,
    })


PLAN_SCHEMA = _obj({
    "headline": S, "current_estimate": N, "weekly_hours": N,
    "phases": _arr(_obj({"weeks": S, "focus": S, "milestone": S})),
    "today": _obj({"title": S, "skill": {"type": "string", "enum": ["writing", "speaking", "reading", "listening"]},
                   "minutes": N, "steps": _arr(S)}),
    "tips": _arr(S),
})
CHART_SPEC_SCHEMA = _obj({
    "title": S, "chart_type": {"type": "string", "enum": ["bar", "line", "pie"]}, "unit": S,
    "categories": _arr(S), "series": _arr(_obj({"name": S, "values": _arr(N)})), "question": S,
})
CHART_READ_SCHEMA = _obj({"readable": B, "categories": _arr(S), "series": _arr(_obj({"name": S, "values": _arr(N)}))})
OCR_SCHEMA = _obj({"legible": B, "text": S})
DRILL_SCHEMA = _obj({"title": S, "items": _arr(_obj({"prompt": S, "options": _arr(S), "answer": S, "explanation": S}))})


# ---------- shared guardrails ----------

def half(x: float) -> float:
    return min(9.0, max(0.0, round(float(x) * 2) / 2))


def ielts_overall(bands: list[float]) -> float:
    """Official IELTS rounding: mean to nearest half band, .25 rounds up to .5 and .75 up to the next band."""
    m = sum(bands) / len(bands)
    whole, frac = divmod(m, 1)
    return whole + (0.0 if frac < 0.25 else 0.5 if frac < 0.75 else 1.0)


def _norm(s: str) -> str:
    return re.sub(r"\s+", " ", re.sub(r"[“”\"'’‘]", "", s)).strip().lower()


def gateway(raw: dict, source: str, keys: list[str]) -> dict:
    """Accept only well-formed grades. Quotes must exist verbatim in the learner's text."""
    crit = {c["key"]: c for c in raw.get("criteria", []) if c.get("key") in keys}
    if set(crit) != set(keys):
        raise muse.MuseError("examiner returned incomplete criteria")
    criteria = [{"key": k, "band": half(crit[k]["band"]), "comment": crit[k]["comment"].strip()[:400]} for k in keys]
    body, seen, issues = _norm(source), set(), []
    for i in raw.get("issues", []):
        q = _norm(i.get("quote", ""))
        if q and q in body and q not in seen and i.get("criterion") in keys:
            seen.add(q)
            issues.append({k: i[k].strip()[:400] for k in ("quote", "criterion", "problem", "fix")})
    improved = raw.get("improved_version", "").strip()
    return {
        "criteria": criteria,
        "overall": ielts_overall([c["band"] for c in criteria]),
        "strengths": [s.strip()[:300] for s in raw.get("strengths", [])][:3],
        "issues": issues[:6],
        "improved_version": improved if 0 < len(improved) < max(4000, 3 * len(source)) else "",
        "next_step": raw.get("next_step", "").strip()[:400],
    }


def data_url(img: bytes, mime: str) -> str:
    return f"data:{mime};base64,{base64.b64encode(img).decode()}"


# ---------- Planner ----------

async def make_plan(profile: dict) -> dict:
    plan = await muse.json_call(pack.PLANNER, {"learner": profile, "policy": pack.plan_policy(profile)}, PLAN_SCHEMA)
    plan["current_estimate"] = half(plan["current_estimate"])
    plan["today"]["minutes"] = max(10, min(60, int(plan["today"]["minutes"])))
    return plan


# ---------- Writing ----------

async def ocr(img: bytes, mime: str) -> dict:
    return await muse.json_call(pack.OCR, "Transcribe the handwritten answer in this photo.", OCR_SCHEMA,
                                images=[data_url(img, mime)])


async def new_chart() -> dict:
    """Task 1 generator: Spark designs the data, Muse Image draws it, Spark vision reads it back as ground truth."""
    topic = random.choice(["energy", "transport", "tourism", "education", "employment", "water use", "waste and recycling",
                           "media and internet", "health", "food and farming", "population", "sport"])
    spec = await muse.json_call(pack.CHART_SPEC, {"topic": topic, "seed": random.randint(1, 10_000)}, CHART_SPEC_SCHEMA,
                                effort="medium")
    img = await muse.image(pack.chart_image_prompt(spec))
    read = await muse.json_call(pack.CHART_READ, "Read every labelled value in this chart.", CHART_READ_SCHEMA,
                                images=[data_url(img, "image/webp")])
    truth = {"categories": read["categories"], "series": read["series"]} if read["readable"] else \
        {"categories": spec["categories"], "series": spec["series"]}
    doc = {"title": spec["title"], "question": spec["question"], "unit": spec["unit"], "truth": truth,
           "verified": read["readable"], "image": base64.b64encode(img).decode(), "created": now()}
    doc["id"] = await db.add("charts", doc)
    return doc


async def grade_writing(task_type: str, question: str, essay: str, chart: dict | None) -> dict:
    payload = {"task_type": task_type, "question": question, "essay": essay, "word_count": len(essay.split())}
    if chart:
        payload["chart_data"] = chart["truth"]
    raw = await muse.json_call(pack.writing_examiner(task_type), payload, _grade_schema(WRITING_KEYS), effort="medium")
    return pack.calibrate_writing(gateway(raw, essay, WRITING_KEYS), essay, task_type)


# ---------- Speaking ----------

async def grade_speaking(part: str, question: str, wav: bytes) -> dict:
    asr = await muse.transcribe(wav)
    transcript = (asr.get("transcript") or "").strip()
    if len(transcript.split()) < 5:
        raise ValueError("We could not hear enough speech. Please answer for at least 20 seconds.")
    metrics = pack.speech_metrics(transcript, int(asr.get("audioDurationMs") or 0))
    raw = await muse.json_call(pack.SPEAKING, {"part": part, "question": question, "transcript": transcript,
                                               "delivery_metrics": metrics}, _grade_schema(SPEAKING_KEYS), effort="medium")
    out = pack.calibrate_speaking(gateway(raw, transcript, SPEAKING_KEYS), metrics)
    return {**out, "transcript": transcript, "metrics": metrics}


# ---------- Coach (Muse Wonder, tool calling, delegates to sub-agents) ----------

def _tool(name: str, desc: str, props: dict | None = None, required: list | None = None) -> dict:
    params = {"type": "object", "properties": props or {}}
    if required:
        params["required"] = required
    return {"type": "function", "function": {"name": name, "description": desc, "parameters": params}}


MISSION_SKILL = {"type": "string", "enum": ["writing", "speaking", "reading", "listening"]}
TOOLS = [
    _tool("get_profile", "Learner goal, test date, plan and today's mission."),
    _tool("get_attempts", "Recent graded attempts with bands and issues.",
          {"skill": {"type": "string", "enum": ["writing", "speaking", "any"]}}),
    _tool("get_weak_areas", "Error categories ranked by frequency across all attempts."),
    _tool("create_drill", "Ask the drill-writer sub-agent for a short targeted practice set.",
          {"skill": S, "focus": S, "count": {"type": "integer", "minimum": 3, "maximum": 6}}, ["skill", "focus"]),
    _tool("set_today_mission", "Replace today's mission on the learner's plan.",
          {"title": S, "skill": MISSION_SKILL, "minutes": {"type": "integer", "minimum": 10, "maximum": 60}, "steps": _arr(S)},
          ["title", "skill", "minutes", "steps"]),
]


def weak_areas(attempts: list[dict]) -> list[dict]:
    counts: dict[str, int] = {}
    for a in attempts:
        for i in a.get("result", {}).get("issues", []):
            k = f'{a["skill"]}:{i["criterion"]}'
            counts[k] = counts.get(k, 0) + 1
        for c in a.get("result", {}).get("criteria", []):
            counts.setdefault(f'{a["skill"]}:{c["key"]}', 0)
    lows: dict[str, list[float]] = {}
    for a in attempts:
        for c in a.get("result", {}).get("criteria", []):
            lows.setdefault(f'{a["skill"]}:{c["key"]}', []).append(c["band"])
    rows = [{"area": k, "issues": v, "avg_band": round(sum(lows.get(k, [0])) / max(1, len(lows.get(k, []))), 1)}
            for k, v in counts.items()]
    return sorted(rows, key=lambda r: (-r["issues"], r["avg_band"]))[:6]


def _brief(a: dict) -> dict:
    r = a.get("result", {})
    return {"skill": a["skill"], "when": a.get("created"), "question": a.get("question", "")[:160], "overall": r.get("overall"),
            "criteria": {c["key"]: c["band"] for c in r.get("criteria", [])},
            "issues": [f'{i["criterion"]}: {i["problem"]}' for i in r.get("issues", [])][:4]}


async def drill(skill: str, focus: str, count: int = 4, profile: dict | None = None) -> dict:
    d = await muse.json_call(pack.DRILL, {"skill": skill, "focus": focus, "count": max(3, min(6, count)),
                                          "target_band": (profile or {}).get("target")}, DRILL_SCHEMA)
    d["items"] = d["items"][:6]
    return d


async def coach(learner: str, history: list[dict], message: str) -> dict:
    profile = await db.get(f"learners/{learner}") or {}
    attempts = await db.list(f"learners/{learner}/attempts", 30)
    trace, artifacts = [], []

    async def run(name: str, args: dict):
        if name == "get_profile":
            return {k: profile.get(k) for k in ("name", "target", "test_date", "minutes_per_day", "weakest", "plan")}
        if name == "get_attempts":
            sk = args.get("skill", "any")
            return [_brief(a) for a in attempts if sk in ("any", a["skill"])][:8]
        if name == "get_weak_areas":
            return weak_areas(attempts)
        if name == "create_drill":
            d = await drill(str(args.get("skill", "writing"))[:20], str(args.get("focus", ""))[:200],
                            int(args.get("count", 4)), profile)
            artifacts.append({"type": "drill", **d})
            return {"created": d["title"], "items": len(d["items"])}
        if name == "set_today_mission":
            plan = profile.get("plan") or {}
            plan["today"] = {"title": str(args["title"])[:120], "skill": args["skill"],
                             "minutes": max(10, min(60, int(args["minutes"]))), "steps": [str(s)[:200] for s in args["steps"]][:6]}
            profile["plan"] = plan
            await db.set(f"learners/{learner}", {"plan": plan})
            artifacts.append({"type": "mission", **plan["today"]})
            return {"ok": True}
        return {"error": "unknown tool"}

    msgs = [{"role": "system", "content": pack.COACH}]
    msgs += [{"role": m["role"], "content": m["content"]} for m in history[-10:]]
    msgs.append({"role": "user", "content": message})
    for _ in range(5):
        m = await muse.chat(msgs, model=muse.AGENT, tools=TOOLS, effort=None)
        calls = m.get("tool_calls") or []
        if not calls:
            return {"reply": (m.get("content") or "").strip(), "trace": trace, "artifacts": artifacts}
        msgs.append({"role": "assistant", "content": m.get("content") or "", "tool_calls": calls})

        async def one(c):
            try:
                args = json.loads(c["function"].get("arguments") or "{}")
            except json.JSONDecodeError:
                args = {}
            trace.append({"tool": c["function"]["name"], "args": args})
            try:
                res = await run(c["function"]["name"], args)
            except Exception as e:  # tool errors go back to the model, not to the user
                res = {"error": str(e)[:200]}
            return {"role": "tool", "tool_call_id": c["id"], "content": json.dumps(res, ensure_ascii=False, default=str)}

        msgs += await asyncio.gather(*(one(c) for c in calls))  # parallel tool calls
    return {"reply": "I gathered your data but ran out of steps. Ask me again in a simpler way.", "trace": trace,
            "artifacts": artifacts}
