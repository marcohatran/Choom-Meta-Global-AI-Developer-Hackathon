import os

os.environ["STORE"] = "memory"

import pytest
from fastapi.testclient import TestClient

from app import agents, muse
from app.agents import WRITING_KEYS, gateway, ielts_overall
from app.main import app


def test_ielts_rounding():
    assert ielts_overall([6, 6, 6, 6.5]) == 6.0     # 6.125
    assert ielts_overall([6, 6, 6.5, 6.5]) == 6.5   # 6.25 rounds up
    assert ielts_overall([6.5, 6.5, 7, 7]) == 7.0   # 6.75 rounds up
    assert ielts_overall([5, 5, 5.5, 5]) == 5.0


def raw(issues):
    return {"criteria": [{"key": k, "band": 6.3, "comment": "ok"} for k in WRITING_KEYS], "strengths": ["a"],
            "issues": issues, "improved_version": "better", "next_step": "x"}


def test_gateway_drops_invented_quotes_and_rounds():
    essay = "I has went to school yesterday. It were fun."
    g = gateway(raw([{"quote": "I has went", "criterion": "grammar", "problem": "p", "fix": "I went"},
                     {"quote": "not in essay", "criterion": "grammar", "problem": "p", "fix": "f"},
                     {"quote": "i HAS went", "criterion": "grammar", "problem": "dup", "fix": "f"}]), essay, WRITING_KEYS)
    assert [i["quote"] for i in g["issues"]] == ["I has went"]
    assert all(c["band"] == 6.5 for c in g["criteria"]) and g["overall"] == 6.5


def test_gateway_rejects_missing_criteria():
    r = raw([])
    r["criteria"] = r["criteria"][:3]
    with pytest.raises(muse.MuseError):
        gateway(r, "text", WRITING_KEYS)


def test_api_validation_and_quota(monkeypatch):
    async def fake_grade(*a):
        return {"overall": 6.0, "criteria": [], "issues": [], "strengths": [], "next_step": "", "improved_version": ""}
    monkeypatch.setattr(agents, "grade_writing", fake_grade)
    monkeypatch.setattr("app.main.LEARNER_DAILY", 2)
    c = TestClient(app)
    assert c.post("/api/writing/grade", json={"task_type": "task9", "question": "q" * 20, "essay": "e" * 30}).status_code == 422
    body = {"task_type": "task2", "question": "Discuss both views.", "essay": "word " * 30}
    assert c.post("/api/writing/grade", json=body).status_code == 200
    assert c.post("/api/writing/grade", json=body).status_code == 200
    assert c.post("/api/writing/grade", json=body).status_code == 429
    assert len(c.get("/api/me").json()["attempts"]) == 2
    assert c.post("/api/speaking/grade", data={"part": "part1", "question": "q"},
                  files={"audio": ("a.wav", b"not a wav", "audio/wav")}).status_code in (422, 429)
    assert c.get("/api/nope").status_code == 404
