"use strict";
const $ = (s, el = document) => el.querySelector(s);
const view = $("#view");
const esc = (s) => String(s ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" })[c]);
const LABEL = { task: "Task response", coherence: "Coherence & cohesion", lexical: "Lexical resource", grammar: "Grammar range & accuracy",
  fluency: "Fluency & coherence", pronunciation: "Pronunciation" };
const SKILL_ROUTE = { writing: "#/writing", speaking: "#/speaking", reading: "#/coach", listening: "#/coach" };

async function api(path, opts = {}) {
  const o = { credentials: "same-origin", ...opts };
  if (o.json) { o.method = o.method || "POST"; o.headers = { "Content-Type": "application/json" }; o.body = JSON.stringify(o.json); }
  const r = await fetch(path, o);
  const data = await r.json().catch(() => ({}));
  if (!r.ok) {
    const d = data.detail;
    throw new Error(typeof d === "string" ? d : Array.isArray(d) ? d.map((x) => x.msg).join("; ") : "Something went wrong.");
  }
  return data;
}

// Multi-agent progress: stages advance on estimated timings; finish() ticks the rest.
function stages(el, list) {
  el.innerHTML = `<ul class="stages">${list.map((s) => `<li>${s[0]} <span class="model">${s[1]}</span></li>`).join("")}</ul>`;
  const lis = [...el.querySelectorAll("li")];
  let i = 0, timer;
  const step = () => {
    lis.forEach((li, j) => { li.className = j < i ? "ok" : j === i ? "on" : ""; });
    if (i < lis.length - 1) timer = setTimeout(() => { i++; step(); }, list[i][2] || 4000);
  };
  step();
  return () => { clearTimeout(timer); lis.forEach((li) => (li.className = "ok")); };
}

function errorNote(el, e) { el.innerHTML = `<div class="note coral" role="alert">${esc(e.message)}</div>`; }

// ---------- router ----------
const routes = { today, writing, speaking, coach, progress };
async function route() {
  const name = (location.hash.replace("#/", "") || "today").split("?")[0];
  document.querySelectorAll(".nav a").forEach((a) => a.toggleAttribute("aria-current", a.getAttribute("href") === `#/${name}`));
  document.querySelectorAll(".nav a[aria-current]").forEach((a) => a.setAttribute("aria-current", "page"));
  view.innerHTML = `<p class="muted">Loading…</p>`;
  try { await (routes[name] || today)(); } catch (e) { errorNote(view, e); }
  view.focus({ preventScroll: true });
  window.scrollTo(0, 0);
}
window.addEventListener("hashchange", route);
route();

// ---------- Today / onboarding ----------
async function today() {
  const me = await api("/api/me");
  if (!me.profile) return onboarding();
  const p = me.profile, plan = p.plan;
  const last = me.attempts[0];
  view.innerHTML = `
  <div class="hero stack">
    <span class="label" style="color:#D3E9E3">Hi ${esc(p.name || "there")} · target band ${esc(p.target)}${p.test_date ? ` · test on ${esc(p.test_date)}` : ""}</span>
    <h1>${esc(plan.headline)}</h1>
    <div class="row"><span class="pill">Now ≈ ${esc(plan.current_estimate)}</span><span class="pill">${esc(plan.weekly_hours)} h / week</span>
    <span class="pill meta">Planned by Muse Spark</span></div>
  </div>
  <div class="grid2" style="margin-top:16px">
    <section class="card stack" aria-labelledby="mission">
      <div class="row sp"><h2 id="mission">Today's mission</h2><span class="pill amber">${esc(plan.today.minutes)} min · ${esc(plan.today.skill)}</span></div>
      <h3 style="font:500 22px/1.3 var(--serif)">${esc(plan.today.title)}</h3>
      <ol class="steps">${plan.today.steps.map((s) => `<li>${esc(s)}</li>`).join("")}</ol>
      <div class="row"><a class="btn" href="${SKILL_ROUTE[plan.today.skill] || "#/coach"}">Start now</a>
      <a class="btn ghost" href="#/coach">Ask the coach to adjust</a></div>
    </section>
    <section class="card stack">
      <h2>Latest result</h2>
      ${last ? `<div class="row"><span class="big">${esc(last.result.overall)}</span><div><b>${esc(last.skill)} · ${esc(last.kind)}</b>
        <p class="label">${new Date(last.created * 1000).toLocaleString()}</p></div></div>
        <p class="muted">${esc(last.result.next_step)}</p>`
        : `<p class="muted">No attempts yet. Do one Writing or Speaking task and Choom's examiner will grade it in under a minute.</p>`}
      <a class="btn ghost sm" href="#/progress">See progress</a>
    </section>
  </div>
  <section class="card stack" style="margin-top:16px"><h2>Your plan</h2>
    <div class="timeline">${plan.phases.map((ph) => `<div class="phase"><span class="label">${/^week/i.test(ph.weeks) ? "" : "Weeks "}${esc(ph.weeks)}</span>
      <h3>${esc(ph.focus)}</h3><p class="muted" style="font-size:14px">Milestone: ${esc(ph.milestone)}</p></div>`).join("")}</div>
  </section>
  <section class="card stack" style="margin-top:16px"><h2>Tips for you</h2><ul class="steps">${plan.tips.map((t) => `<li>${esc(t)}</li>`).join("")}</ul></section>
  <p class="label" style="margin-top:18px">Not you? <button class="btn ghost sm" id="reset">Start over</button></p>`;
  $("#reset").onclick = async () => { await api("/api/reset", { method: "POST" }); sessionStorage.clear(); route(); };
}

function onboarding() {
  view.innerHTML = `
  <div class="hero stack"><span class="label" style="color:#D3E9E3">Choom · AI IELTS examiner and coach</span>
    <h1>Know your real band. Close the gap, 15 minutes a day.</h1>
    <p class="muted">Examiner-grade feedback on Writing and Speaking, a plan built around your test date, and a coach agent that acts on your data.</p></div>
  <form class="card stack" id="ob" style="margin-top:16px">
    <h2>Set up your plan (30 seconds)</h2>
    <div class="field-grid">
      <label class="f">First name<input type="text" name="name" maxlength="40" autocomplete="given-name"></label>
      <label class="f">Target band<select name="target">${[5.5, 6, 6.5, 7, 7.5, 8, 8.5].map((b) => `<option ${b === 7 ? "selected" : ""}>${b}</option>`).join("")}</select></label>
      <label class="f">Latest band (if you have one)<select name="current"><option value="">Not sure</option>${[4, 4.5, 5, 5.5, 6, 6.5, 7, 7.5].map((b) => `<option>${b}</option>`).join("")}</select></label>
      <label class="f">Test date<input type="date" name="test_date"></label>
      <label class="f">Minutes per day<select name="minutes_per_day">${[15, 30, 45, 60, 90].map((m) => `<option ${m === 30 ? "selected" : ""}>${m}</option>`).join("")}</select></label>
      <label class="f">Weakest skill<select name="weakest"><option>writing</option><option>speaking</option><option>reading</option><option>listening</option></select></label>
      <label class="f">Feedback language<select name="lang"><option value="en">English</option><option value="vi">Tiếng Việt</option></select></label>
    </div>
    <div class="row"><button class="btn" type="submit">Build my plan</button><span class="label">No sign-up. Your data stays tied to this browser.</span></div>
    <div id="ob-status" aria-live="polite"></div>
  </form>`;
  const d = new Date(Date.now() + 70 * 864e5); $("[name=test_date]").value = d.toISOString().slice(0, 10);
  $("#ob").onsubmit = async (ev) => {
    ev.preventDefault();
    const f = Object.fromEntries(new FormData(ev.target));
    const body = { ...f, target: +f.target, current: f.current ? +f.current : null, minutes_per_day: +f.minutes_per_day };
    const btn = ev.submitter; btn.disabled = true;
    const done = stages($("#ob-status"), [["Reading your goal and test date", "code", 800], ["Planner agent drafting phases and today's mission", "Muse Spark", 9000]]);
    try { await api("/api/onboard", { json: body }); done(); route(); } catch (e) { errorNote($("#ob-status"), e); btn.disabled = false; }
  };
}

// ---------- Writing ----------
async function writing() {
  const task = sessionStorage.getItem("wtask") || "task2";
  view.innerHTML = `
  <div class="page-h"><div><span class="label">Writing examiner</span><h1>Write. Get graded like the real exam.</h1></div>
    <div class="seg" role="group" aria-label="Task"><button data-t="task1" aria-pressed="${task === "task1"}">Task 1 · Academic</button><button data-t="letter" aria-pressed="${task === "letter"}">Task 1 · Letter (GT)</button><button data-t="task2" aria-pressed="${task === "task2"}">Task 2 · Essay</button></div></div>
  <div class="grid2">
    <section class="card stack">
      <div id="prompt" class="stack"><p class="muted">Loading task…</p></div>
      <label class="f"><span class="row sp">Your answer <span class="label" id="wc">0 words</span></span>
        <textarea id="essay" placeholder="Type your answer here, or upload a photo of your handwritten answer."></textarea></label>
      <div class="row"><button class="btn" id="grade">Grade my answer</button>
        <label class="btn ghost">Upload handwriting photo<input type="file" accept="image/jpeg,image/png,image/webp" capture="environment" id="photo" class="sr"></label></div>
      <div id="wstatus" aria-live="polite"></div>
    </section>
    <section class="card stack" id="wresult"><h2>Examiner report</h2><p class="muted">Your band, the four official criteria, the exact sentences that hold you back and a stronger version of your answer appear here.</p></section>
  </div>`;
  view.querySelectorAll(".seg button").forEach((b) => (b.onclick = () => { sessionStorage.setItem("wtask", b.dataset.t); writing(); }));
  const essay = $("#essay"), wc = $("#wc");
  essay.value = sessionStorage.getItem("draft_" + task) || "";
  const count = () => { const n = essay.value.trim().split(/\s+/).filter(Boolean).length; wc.textContent = `${n} words · aim ${task === "task2" ? 250 : 150}+`; };
  essay.oninput = () => { sessionStorage.setItem("draft_" + task, essay.value); count(); }; count();

  let current = { question: "", chart_id: null };
  async function loadChart(fresh, kind = "chart") {
    const box = $("#prompt");
    if (fresh) {
      const done = stages(box, kind === "process"
        ? [["Designing the stages of a process", "Muse Spark", 6000], ["Drawing the diagram", "Muse Image", 16000], ["Reading every stage label back in order", "Muse Spark vision", 6000]]
        : [["Designing realistic exam data", "Muse Spark", 6000], ["Drawing the chart", "Muse Image", 16000], ["Reading the chart back to verify every value", "Muse Spark vision", 6000]]);
      try { const r = await api(`/api/writing/task1/new?kind=${kind}`, { method: "POST" }); done(); return showChart(r.chart); }
      catch (e) { return errorNote(box, e); }
    }
    const r = await api("/api/writing/task1");
    if (!r.chart) return loadChart(true);
    showChart(r.chart);
  }
  function showChart(c) {
    current = { question: c.question, chart_id: c.id };
    $("#prompt").innerHTML = `<div class="row sp"><h2>${esc(c.title)}</h2><div class="row"><button class="btn ghost sm" id="newchart">New chart</button><button class="btn ghost sm" id="newproc">New process</button></div></div>
      <p>${esc(c.question)}</p><div class="chart"><img src="/api/charts/${esc(c.id)}.webp" alt="Task 1 ${c.kind === "process" ? "process diagram" : "chart"}: ${esc(c.title)}"></div>
      <div class="row"><span class="pill meta">Generated by Muse Image</span>${c.verified ? `<span class="pill">${c.kind === "process" ? "Every stage label verified by vision" : "Values verified by vision"}</span>` : ""}</div>`;
    $("#newchart").onclick = () => loadChart(true);
    $("#newproc").onclick = () => loadChart(true, "process");
  }
  if (task === "task1") await loadChart(false);
  else if (task === "letter") {
    const show = async () => { const r = await api("/api/writing/letter"); current = { question: r.question, chart_id: null };
      $("#prompt").innerHTML = `<div class="row sp"><h2>Task 1 · General Training</h2><button class="btn ghost sm" id="newq">Another letter</button></div><p style="font:500 17px/1.5 var(--serif);white-space:pre-line">${esc(r.question)}</p><p class="label">20 minutes in the exam. Task 2 counts twice as much as Task 1.</p>`;
      $("#newq").onclick = show; };
    await show();
  } else {
    const r = await api("/api/writing/task2"); current = { question: r.question, chart_id: null };
    const show = (q) => { $("#prompt").innerHTML = `<div class="row sp"><h2>Task 2</h2><button class="btn ghost sm" id="newq">Another question</button></div><p style="font:500 18px/1.5 var(--serif)">${esc(q)}</p><p class="label">Write at least 250 words. 40 minutes in the exam.</p>`;
      $("#newq").onclick = async () => { const r2 = await api("/api/writing/task2"); current.question = r2.question; show(r2.question); }; };
    show(r.question);
  }

  $("#photo").onchange = async (ev) => {
    const file = ev.target.files[0]; if (!file) return;
    const fd = new FormData(); fd.append("photo", file);
    const done = stages($("#wstatus"), [["Reading your handwriting", "Muse Spark vision", 8000]]);
    try { const r = await api("/api/writing/ocr", { method: "POST", body: fd }); done(); essay.value = r.text; essay.oninput();
      $("#wstatus").innerHTML = `<div class="note teal">Transcribed from your photo, mistakes kept as written. Check it, then press Grade.</div>`; }
    catch (e) { errorNote($("#wstatus"), e); }
  };
  $("#grade").onclick = async () => {
    const btn = $("#grade"); btn.disabled = true;
    const done = stages($("#wstatus"), [["Examiner agent scoring the four criteria", "Muse Spark", 14000], ["Checking every quote against your text", "code", 1500], ["Applying Choom calibration rules", "code", 1500]]);
    try {
      const r = await api("/api/writing/grade", { json: { task_type: task, question: current.question, essay: essay.value, chart_id: current.chart_id } });
      done(); $("#wstatus").innerHTML = ""; renderGrade($("#wresult"), r, essay.value, "writing");
      $("#wresult").scrollIntoView({ behavior: "smooth", block: "start" });
    } catch (e) { errorNote($("#wstatus"), e); }
    btn.disabled = false;
  };
}

function highlight(text, issues, fillers) {
  let html = esc(text);
  for (const i of issues || []) {
    const q = esc(i.quote).replace(/[.*+?^${}()|[\]\\]/g, "\\$&").replace(/\s+/g, "\\s+");
    html = html.replace(new RegExp(q, "i"), (m) => `<mark title="${esc(i.problem)}">${m}</mark>`);
  }
  if (fillers) html = html.replace(/\b(um+|uh+|er+|erm|ah+|hmm+)\b/gi, '<mark class="filler">$1</mark>');
  return html;
}

function renderGrade(el, r, source, skill) {
  el.innerHTML = `
    <div class="row sp"><h2>Examiner report</h2><span class="pill meta">Muse Spark + Choom calibration</span></div>
    <div class="row"><span class="big">${esc(r.overall)}</span><div><b>Estimated overall band</b>
      ${r.range ? `<p class="label">Likely range ${esc(r.range[0])}–${esc(r.range[1])}${r.word_count ? ` · ${esc(r.word_count)} words` : ""}</p>` : ""}</div></div>
    ${r.metrics ? `<div class="grid4">${[["wpm", "words / min"], ["filler_rate", "fillers / 100 words"], ["lexical_diversity", "word variety"], ["seconds", "seconds"]]
      .map(([k, l]) => `<div class="card" style="padding:12px"><b style="font:600 22px var(--serif)">${esc(r.metrics[k])}</b><p class="label">${l}</p></div>`).join("")}</div>` : ""}
    <div>${r.criteria.map((c) => `<div class="crit"><span>${esc(LABEL[c.key] || c.key)}${c.estimated ? ' <span class="pill plain">estimate</span>' : ""}</span>
      <span class="bar"><i style="width:${(c.band / 9) * 100}%"></i></span><b>${esc(c.band)}</b><p>${esc(c.comment)}</p></div>`).join("")}</div>
    ${(r.adjustments || []).length ? `<div class="note"><b>Calibrated:</b> ${r.adjustments.map(esc).join(" ")}</div>` : ""}
    ${r.strengths.length ? `<div><h3>What works</h3><ul class="steps">${r.strengths.map((s) => `<li>${esc(s)}</li>`).join("")}</ul></div>` : ""}
    ${r.issues.length ? `<div class="stack"><h3>What holds your band back</h3>${r.issues.map((i) => `<div class="issue"><q>${esc(i.quote)}</q>
      <p>${esc(i.problem)}</p><p class="fix">→ ${esc(i.fix)}</p></div>`).join("")}</div>` : ""}
    <details><summary><b>${skill === "speaking" ? "Your transcript" : "Your answer"}, marked</b></summary><p class="essay" style="margin-top:8px">${highlight(source, r.issues, skill === "speaking")}</p></details>
    ${r.improved_version ? `<details><summary><b>${skill === "speaking" ? "Band 7.5 model answer" : "One band higher: your answer, upgraded"}</b></summary><p class="essay" style="margin-top:8px">${esc(r.improved_version)}</p></details>` : ""}
    <div class="note teal"><b>Next step:</b> ${esc(r.next_step)}</div>
    <a class="btn ghost sm" href="#/coach">Ask the coach what to practise</a>`;
}

// ---------- Speaking ----------
async function speaking() {
  const part = sessionStorage.getItem("spart") || "part1";
  view.innerHTML = `
  <div class="page-h"><div><span class="label">Speaking examiner</span><h1>Speak. Hear what an examiner hears.</h1></div>
    <div class="seg" role="group" aria-label="Part">${["part1", "part2", "part3"].map((p) => `<button data-p="${p}" aria-pressed="${p === part}">Part ${p.slice(-1)}</button>`).join("")}</div></div>
  <div class="grid2">
    <section class="card stack">
      <div class="row sp"><span class="label">Question</span><button class="btn ghost sm" id="newsq">Another question</button></div>
      <p id="sq" style="font:500 20px/1.45 var(--serif)">…</p>
      <p class="label">${part === "part2" ? "Speak for 1–2 minutes." : part === "part1" ? "Answer in 2–4 sentences (about 20–30 seconds)." : "Give a developed answer with reasons and an example (40–60 seconds)."}</p>
      <div class="row"><button class="btn" id="rec">Start recording</button><span id="timer" class="label" aria-live="polite"></span></div>
      <div id="sstatus" aria-live="polite"></div>
    </section>
    <section class="card stack" id="sresult"><h2>Examiner report</h2><p class="muted">Muse Voice Transcribe writes down exactly what you said, fillers included. Choom measures your pace and word variety, then the examiner agent grades you on the four speaking criteria.</p></section>
  </div>`;
  view.querySelectorAll(".seg button").forEach((b) => (b.onclick = () => { sessionStorage.setItem("spart", b.dataset.p); speaking(); }));
  let question = "";
  const loadQ = async () => { const r = await api(`/api/speaking/question?part=${part}`); question = r.question; $("#sq").textContent = question; };
  $("#newsq").onclick = loadQ; await loadQ();

  let rec = null, chunks = [], t0 = 0, tick, stream;
  $("#rec").onclick = async () => {
    const btn = $("#rec");
    if (rec) { rec.stop(); return; }
    try { stream = await navigator.mediaDevices.getUserMedia({ audio: true }); }
    catch { return errorNote($("#sstatus"), new Error("Microphone access is needed. Allow it in your browser and try again.")); }
    chunks = []; rec = new MediaRecorder(stream);
    rec.ondataavailable = (e) => chunks.push(e.data);
    rec.onstop = async () => {
      clearInterval(tick); stream.getTracks().forEach((t) => t.stop()); rec = null;
      btn.textContent = "Start recording"; btn.classList.remove("rec"); btn.disabled = true; $("#timer").textContent = "";
      const done = stages($("#sstatus"), [["Converting audio", "browser", 600], ["Transcribing your answer", "Muse Voice Transcribe", 3500], ["Measuring pace, fillers and word variety", "code", 800], ["Examiner agent grading four criteria", "Muse Spark", 14000]]);
      try {
        const wav = await toWav16k(new Blob(chunks, { type: rec?.mimeType || chunks[0]?.type }));
        const fd = new FormData(); fd.append("part", part); fd.append("question", question); fd.append("audio", wav, "answer.wav");
        const r = await api("/api/speaking/grade", { method: "POST", body: fd });
        done(); $("#sstatus").innerHTML = ""; renderGrade($("#sresult"), r, r.transcript, "speaking");
      } catch (e) { errorNote($("#sstatus"), e); }
      btn.disabled = false;
    };
    rec.start(); t0 = Date.now();
    btn.textContent = "Stop and grade"; btn.classList.add("rec");
    const max = part === "part2" ? 150 : 90;
    tick = setInterval(() => { const s = Math.round((Date.now() - t0) / 1000);
      $("#timer").innerHTML = `<span class="rec-dot"></span> ${s}s / ${max}s`; if (s >= max) rec?.stop(); }, 250);
  };
}

// Browser audio (webm/ogg/mp4) -> mono 16 kHz PCM16 WAV, the format Muse Voice Transcribe accepts.
async function toWav16k(blob) {
  const ctx = new (window.AudioContext || window.webkitAudioContext)();
  const decoded = await ctx.decodeAudioData(await blob.arrayBuffer()); ctx.close();
  const off = new OfflineAudioContext(1, Math.ceil(decoded.duration * 16000), 16000);
  const src = off.createBufferSource(); src.buffer = decoded; src.connect(off.destination); src.start();
  const pcm = (await off.startRendering()).getChannelData(0);
  const buf = new ArrayBuffer(44 + pcm.length * 2), v = new DataView(buf);
  const w = (o, s) => [...s].forEach((c, i) => v.setUint8(o + i, c.charCodeAt(0)));
  w(0, "RIFF"); v.setUint32(4, 36 + pcm.length * 2, true); w(8, "WAVE"); w(12, "fmt "); v.setUint32(16, 16, true);
  v.setUint16(20, 1, true); v.setUint16(22, 1, true); v.setUint32(24, 16000, true); v.setUint32(28, 32000, true);
  v.setUint16(32, 2, true); v.setUint16(34, 16, true); w(36, "data"); v.setUint32(40, pcm.length * 2, true);
  for (let i = 0; i < pcm.length; i++) v.setInt16(44 + i * 2, Math.max(-1, Math.min(1, pcm[i])) * 0x7fff, true);
  return new Blob([buf], { type: "audio/wav" });
}

// ---------- Coach ----------
function coach() {
  const hist = JSON.parse(sessionStorage.getItem("coach") || "[]");
  view.innerHTML = `
  <div class="page-h"><div><span class="label">Coach agent</span><h1>Ask what to do next.</h1></div><span class="pill meta">Muse Wonder · tool calling</span></div>
  <section class="card stack">
    <div class="chat" id="chat"></div>
    <form class="row" id="cf"><input type="text" id="cm" maxlength="1500" placeholder="e.g. What should I practise today?" style="flex:1" aria-label="Message">
      <button class="btn">Send</button></form>
    <div class="row" id="sugg">${["What is my weakest area and why?", "Make me a 15-minute drill for it", "Am I on track for my test date?", "Tôi nên luyện gì hôm nay?"]
      .map((s) => `<button class="btn ghost sm">${esc(s)}</button>`).join("")}</div>
  </section>`;
  const chat = $("#chat");
  const draw = () => {
    chat.innerHTML = hist.length ? "" : `<p class="muted">The coach reads your real scores and errors with tools, writes drills through a sub-agent, and can change today's mission.</p>`;
    hist.forEach((m) => {
      const d = document.createElement("div");
      if (m.role === "user") { d.className = "bubble user"; d.textContent = m.content; chat.append(d); return; }
      d.className = "bubble bot";
      d.innerHTML = `${m.trace?.length ? `<div class="trace">${m.trace.map((t) => `<span>⚙ ${esc(t.tool)}${t.args && Object.keys(t.args).length ? `(${esc(Object.values(t.args).filter((x) => typeof x !== "object").join(", ").slice(0, 40))})` : "()"}</span>`).join("")}</div>` : ""}${esc(m.content)}`;
      chat.append(d);
      (m.artifacts || []).forEach((a) => chat.append(artifact(a)));
    });
  };
  const send = async (text) => {
    if (!text.trim()) return;
    const history = hist.map(({ role, content }) => ({ role, content })).slice(-10);
    hist.push({ role: "user", content: text }); draw();
    const s = document.createElement("div"); s.className = "bubble bot"; chat.append(s);
    const done = stages(s, [["Coach planning which tools to call", "Muse Wonder", 3500], ["Reading your scores and error patterns", "tools", 2500], ["Writing the answer, drills and mission", "Muse Wonder + Spark", 12000]]);
    try { const r = await api("/api/coach", { json: { message: text, history } }); done();
      hist.push({ role: "assistant", content: r.reply, trace: r.trace, artifacts: r.artifacts }); }
    catch (e) { hist.push({ role: "assistant", content: e.message }); }
    sessionStorage.setItem("coach", JSON.stringify(hist.slice(-20))); draw();
    chat.lastElementChild?.scrollIntoView({ behavior: "smooth", block: "nearest" });
  };
  $("#cf").onsubmit = (e) => { e.preventDefault(); const v = $("#cm").value; $("#cm").value = ""; send(v); };
  $("#sugg").querySelectorAll("button").forEach((b) => (b.onclick = () => send(b.textContent)));
  draw();
}

function artifact(a) {
  const d = document.createElement("div"); d.className = "card stack"; d.style.maxWidth = "92%";
  if (a.type === "mission") {
    d.innerHTML = `<div class="row sp"><b>Today's mission updated</b><span class="pill amber">${esc(a.minutes)} min · ${esc(a.skill)}</span></div>
      <h3>${esc(a.title)}</h3><ol class="steps">${a.steps.map((s) => `<li>${esc(s)}</li>`).join("")}</ol><a class="btn sm" href="#/today">Open Today</a>`;
    return d;
  }
  let right = 0, answered = 0;
  d.innerHTML = `<div class="row sp"><b>${esc(a.title)}</b><span class="pill meta">Drill sub-agent · Muse Spark</span></div>` +
    a.items.map((it, i) => `<div class="drill-item" data-i="${i}"><p><b>${i + 1}.</b> ${esc(it.prompt)}</p>${it.options.length
      ? it.options.map((o) => `<button class="opt">${esc(o)}</button>`).join("")
      : `<details><summary>Show model answer</summary><p class="fix">${esc(it.answer)}</p><p class="label">${esc(it.explanation)}</p></details>`}<p class="label exp" hidden>${esc(it.explanation)}</p></div>`).join("");
  d.querySelectorAll(".drill-item").forEach((box) => {
    const it = a.items[+box.dataset.i];
    box.querySelectorAll(".opt").forEach((b) => (b.onclick = () => {
      if (box.dataset.done) return; box.dataset.done = 1; answered++;
      const ok = b.textContent.trim().toLowerCase() === it.answer.trim().toLowerCase(); if (ok) right++;
      b.classList.add(ok ? "right" : "wrong");
      box.querySelectorAll(".opt").forEach((o) => { if (o.textContent.trim().toLowerCase() === it.answer.trim().toLowerCase()) o.classList.add("right"); });
      box.querySelector(".exp").hidden = false;
      const mcq = a.items.filter((x) => x.options.length).length;
      if (answered === mcq) api("/api/drill/done", { json: { title: a.title.slice(0, 200), correct: right, total: Math.max(1, mcq) } }).catch(() => {});
    }));
  });
  return d;
}

// ---------- Progress ----------
async function progress() {
  const me = await api("/api/me");
  const at = [...me.attempts].reverse();
  const series = (sk) => at.filter((a) => a.skill === sk).map((a) => a.result.overall);
  const spark = (vals, color) => {
    if (!vals.length) return `<p class="muted">No attempts yet.</p>`;
    const W = 320, H = 110, x = (i) => vals.length === 1 ? W / 2 : 10 + (i * (W - 20)) / (vals.length - 1), y = (v) => H - 10 - ((v - 3) / 6) * (H - 20);
    return `<svg class="spark" viewBox="0 0 ${W} ${H}" role="img" aria-label="Band trend: ${vals.join(", ")}">
      ${[4, 5, 6, 7, 8].map((b) => `<line x1="0" x2="${W}" y1="${y(b)}" y2="${y(b)}" stroke="#E1E4DC"/><text x="0" y="${y(b) - 2}" font-size="9" fill="#5C675F">${b}</text>`).join("")}
      <polyline fill="none" stroke="${color}" stroke-width="2.5" points="${vals.map((v, i) => `${x(i)},${y(v)}`).join(" ")}"/>
      ${vals.map((v, i) => `<circle cx="${x(i)}" cy="${y(v)}" r="3.5" fill="${color}"/>`).join("")}</svg>`;
  };
  const target = me.profile?.target;
  view.innerHTML = `
  <div class="page-h"><div><span class="label">Progress</span><h1>Every attempt, every pattern.</h1></div>${target ? `<span class="pill amber">Target ${esc(target)}</span>` : ""}</div>
  <div class="grid2">
    <section class="card stack"><h2>Writing band</h2>${spark(series("writing"), "#0E6B5C")}</section>
    <section class="card stack"><h2>Speaking band</h2>${spark(series("speaking"), "#0866FF")}</section>
  </div>
  <section class="card stack" style="margin-top:16px"><h2>Weak areas (computed from all your feedback)</h2>
    ${me.weak_areas.length ? `<table><tr><th>Area</th><th>Issues found</th><th>Avg band</th></tr>${me.weak_areas.map((w) => {
      const [sk, k] = w.area.split(":"); return `<tr><td>${esc(sk)} · ${esc(LABEL[k] || k)}</td><td>${esc(w.issues)}</td><td>${esc(w.avg_band)}</td></tr>`; }).join("")}</table>` : `<p class="muted">Do a few attempts to see patterns.</p>`}
  </section>
  <section class="card stack" style="margin-top:16px"><h2>History</h2>
    ${me.attempts.length ? `<table><tr><th>When</th><th>Task</th><th>Band</th><th>Next step</th></tr>${me.attempts.map((a) => `<tr><td>${new Date(a.created * 1000).toLocaleDateString()}</td>
      <td>${esc(a.skill)} · ${esc(a.kind)}</td><td><b>${esc(a.result.overall)}</b></td><td class="muted">${esc(a.result.next_step)}</td></tr>`).join("")}</table>` : `<p class="muted">Nothing yet.</p>`}
  </section>`;
}
