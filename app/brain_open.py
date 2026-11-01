"""Open prompt pack: simplified prompts and no calibration. Production uses the proprietary pack in app/private."""

PLANNER = "You are an IELTS study planner. Build a realistic plan for the learner described in the JSON."
OCR = "Transcribe the handwritten English text in the image exactly. Set legible=false if you cannot read it."
CHART_SPEC = "Invent data for an IELTS Academic Writing Task 1 chart and write the task question."
CHART_READ = "Read the categories, series names and values from the chart image."
SPEAKING = "You are an IELTS speaking examiner. Grade the transcript on the four speaking criteria, bands 0-9."
COACH = "You are Choom, an IELTS coach. Use the tools to look at the learner's data before giving advice. Be brief."
DRILL = "Write a short IELTS practice set for the requested skill and focus."


def writing_examiner(task_type: str) -> str:
    return f"You are an IELTS examiner. Grade this Writing {task_type} answer on the four writing criteria, bands 0-9."


def chart_image_prompt(spec: dict) -> str:
    return f"A clean {spec['chart_type']} chart titled '{spec['title']}' with labelled values: {spec['series']}"


def plan_policy(profile: dict) -> dict:
    return {}


def speech_metrics(transcript: str, duration_ms: int) -> dict:
    words = len(transcript.split())
    return {"words": words, "seconds": round(duration_ms / 1000, 1),
            "wpm": round(words / max(duration_ms / 60000, 1e-6)) if duration_ms else None}


def calibrate_writing(grade: dict, essay: str, task_type: str) -> dict:
    return grade


def calibrate_speaking(grade: dict, metrics: dict) -> dict:
    return grade
