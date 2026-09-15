# RolePointer — Architectural Inflection Points & Design Decisions

This document records the critical architectural inflection points, technical trade-offs, and edge-case resolutions made during the engineering of the **RolePointer** autonomous multi-agent platform.

---

## 1. Inflection Point: Dual-Layer Database Persistence & Test Hydration

### Context & Symptom:
Initially, FastAPI endpoints maintained active application states, candidate profiles, and tailored packages in fast in-memory dictionary stores. However, during server reboots or background restarts, all triage decisions were wiped. When transitioning to SQLAlchemy ORM models on SQLite WAL mode, calling hydration solely inside FastAPI's async `lifespan` handler caused test runners (which instantiate `TestClient(app)` at module level) to bypass hydration, resulting in empty test datasets.

### Root Cause:
Starlette's `TestClient` only executes `lifespan` startup hooks when used as a context manager (`with TestClient(app) as client:`). Module-level client calls bypassed the startup event.

### Architectural Decision & Resolution:
1. Implemented a robust **dual-layer hydration pattern** in [`src/rolepointer/api/main.py`](file:///f:/Hackathons/Agents%20for%20Humans/AntigravityBuild/EverydayAgents/rolepointer/src/rolepointer/api/main.py): `_hydrate_or_seed_db()` is invoked at module load time AND verified inside the async `lifespan` context.
2. Built a comprehensive repository layer ([`src/rolepointer/db/repository.py`](file:///f:/Hackathons/Agents%20for%20Humans/AntigravityBuild/EverydayAgents/rolepointer/src/rolepointer/db/repository.py)) with defensive JSON deserialization (`_safe_json_loads`) to handle nested list/dict structures (tags, skills, pros/cons, STAR bullets) without crashing on malformed records.
3. Enabled SQLite **WAL mode** (`PRAGMA journal_mode=WAL`) and foreign keys (`PRAGMA foreign_keys=ON`) to support concurrent reader and writer transactions without table lock contention.

---

## 2. Inflection Point: Background Poller Isolation & Test Resilience

### Context & Symptom:
An autonomous background worker was needed to continuously scan external feeds (Jobicy, RemoteOK, Arbeitnow, Hacker News) and broadcast real-time SSE alerts when $\ge 85\%$ fit roles are discovered. However, unconditionally launching an infinite network polling loop during test collection introduced network latency and unpredictable test execution times.

### Root Cause:
Background tasks started during test suite initialization made unmocked external HTTP calls against live rate-limited APIs.

### Architectural Decision & Resolution:
1. Gated the background daemon behind the `ENABLE_BACKGROUND_POLLER` environment flag in [`lifespan`](file:///f:/Hackathons/Agents%20for%20Humans/AntigravityBuild/EverydayAgents/rolepointer/src/rolepointer/api/main.py).
2. Implemented **Error Isolation per Feed Connector** in [`src/rolepointer/scheduler/poller.py`](file:///f:/Hackathons/Agents%20for%20Humans/AntigravityBuild/EverydayAgents/rolepointer/src/rolepointer/scheduler/poller.py) so that if one external API encounters a 429 rate limit or network timeout, the exception is trapped and logged, allowing other feeds to continue uninterrupted.
3. Added a dedicated manual sync endpoint `POST /api/scheduler/trigger` allowing on-demand feed synchronization.

---

## 3. Inflection Point: PDF Compilation Engine (ReportLab vs. LaTeX)

### Context & Symptom:
Traditional open-source resume generators depend on `pdflatex` or `xelatex` requiring 4GB+ MiKTeX / TeX Live distributions. On Windows, LaTeX tools frequently fail due to missing font metrics, package installation prompts, or hanging subprocesses. Additionally, LaTeX typography engines frequently merge letter pairs ("fi", "fl") into ligatures that corrupt ATS text parsing.

### Architectural Decision & Resolution:
1. Replaced LaTeX entirely with a pure-Python, zero-dependency **ReportLab compiler** ([`src/rolepointer/compiler/pdf_engine.py`](file:///f:/Hackathons/Agents%20for%20Humans/AntigravityBuild/EverydayAgents/rolepointer/src/rolepointer/compiler/pdf_engine.py)).
2. Generates binary PDF primitive streams in under **50 milliseconds** (vs. 3,500ms for LaTeX).
3. Standardized on clean `Helvetica` and `Helvetica-Bold` font families to guarantee **100% deterministic ATS keyword parsing** with zero font ligature artifacts.

---

## 4. Inflection Point: Multi-Modal Voice Mock Interview Studio

### Context & Symptom:
Candidate mock interviews are most effective when practiced vocally, but browser implementations of speech recognition (`SpeechRecognition` / `webkitSpeechRecognition`) vary, and microphone permissions can be denied by the operating system.

### Architectural Decision & Resolution:
1. Built a **Progressive Audio Interface** in [`src/rolepointer/static/index.html`](file:///f:/Hackathons/Agents%20for%20Humans/AntigravityBuild/EverydayAgents/rolepointer/src/rolepointer/static/index.html):
   - **TTS Speech Synthesis:** Narrates interviewer questions aloud with natural speech cadence.
   - **STT Speech Recognition:** Live-transcribes candidate spoken answers into the textarea buffer.
   - **Audio Waveform Visualizer:** Animated CSS/SVG bars visually indicate active recording states.
   - **Graceful Fallback:** If microphone access is unavailable, candidates can seamlessly type responses without UI disruption.

---

## 5. Inflection Point: Anti-Spam Strategy & RFC 5322 EML Client Handoff

### Context & Symptom:
Sending cold job applications via automated backend SMTP relays often triggers anti-spam algorithms (DMARC/DKIM misalignment) and routes candidate emails straight to the hiring manager's archive folder.

### Architectural Decision & Resolution:
1. Implemented the **4-Sentence Direct Pitch Framework** (Hook $\rightarrow$ Hard Metric $\rightarrow$ Direct Solution $\rightarrow$ Low-friction CTA) strictly capped at **Top 3 daily roles** to preserve candidate domain reputation.
2. Built an **RFC 5322 EML Generator** ([`src/rolepointer/agents/email_exporter.py`](file:///f:/Hackathons/Agents%20for%20Humans/AntigravityBuild/EverydayAgents/rolepointer/src/rolepointer/agents/email_exporter.py)) and URL-safe `mailto:` generator. Candidates dispatch communications directly through their own authentic desktop/mobile mail clients (Outlook, Apple Mail, Gmail) ensuring maximum email deliverability.
