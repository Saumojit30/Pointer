# RolePointer 🎯

**Autonomous Job Discovery, Guardrail Triage & Tailored Career Pipeline**
Built with **Strands SDK**, **FastAPI**, and modern local-first multi-agent architecture.

---

## 🚀 Key Features

1. **Multi-Feed Discovery Engine**: Aggregates real-time listings from Remote boards (Jobicy, RemoteOK), Global Country/City boards (Arbeitnow, US, UK, India, Germany), Hacker News *"Who is Hiring"*, and universal URL job scrapers.
2. **Fit Evaluator & Dealbreaker Sentinel**: Computes semantic match scores (0–100%), extracts pros & cons, and alerts on anti-goals (on-call shifts, crypto/gambling, lack of salary floor).
3. **Opportunity Triage Guardrail**: Human-in-the-loop 1-click decision card (*Skip / Save / Prepare Package / Mock Interview*).
4. **Drafter & ATS Reviewer Pipeline**: Generates targeted CV bullets and high-impact 4-sentence pitches, verified for zero hallucinations.
5. **Instant ATS PDF Compiler**: Fast ReportLab engine producing clean, single-page ATS-optimized PDFs in under 50ms without MiKTeX bloat.
6. **Interactive Mock Interview Simulator**: Tailored technical and behavioral question generator with real-time response scoring and feedback.

---

## 🛠️ Quick Start

```powershell
# 1. Install dependencies with uv
uv sync

# 2. Configure environment
cp .env.example .env

# 3. Run FastAPI Application
uv run uvicorn rolepointer.api.main:app --reload --port 8000
```
Open your browser at `http://127.0.0.1:8000` to access the RolePointer Dashboard.
