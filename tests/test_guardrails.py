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


def test_official_writing_rules():
    pack = pytest.importorskip("app.private.pack")
    q = "Some people think that governments should invest more in public transport than in building new roads."
    essay = q + " I agree with this idea because buses are cheap."
    assert pack.own_words(essay, q) == 9                       # copied rubric is discounted
    g = pack.calibrate_writing(raw([]), essay, "task2", q)
    assert {c["band"] for c in g["criteria"]} == {1.0}        # 20 words or fewer -> Band 1
    one_para = " ".join(["Cities need better buses and trains for workers."] * 30)
    g = pack.calibrate_writing({**raw([]), "criteria": [{"key": k, "band": 7.0, "comment": ""} for k in WRITING_KEYS]},
                               one_para, "task2", q)
    assert next(c["band"] for c in g["criteria"] if c["key"] == "coherence") == 5.0


def test_letter_endpoint_and_task_type():
    c = TestClient(app)
    q = c.get("/api/writing/letter").json()["question"]
    assert "Begin your letter" in q and q.count("•") == 3
    assert c.post("/api/writing/grade", json={"task_type": "map", "question": q, "essay": "x" * 30}).status_code == 422
