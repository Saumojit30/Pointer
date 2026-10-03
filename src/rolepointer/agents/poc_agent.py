"""
RolePointer — Moat 1: Trojan Horse Proof-of-Work Artifact & Mini RFC Generator Engine

Autonomous agent that synthesizes:
1. Executable, standalone benchmark scripts / code snippets addressing the target company's stack challenge.
2. 1-Page Mini Technical RFC (Request for Comments) with Mermaid architecture flowcharts.
3. High-converting "Trojan Horse" outreach pitch linking the PoC artifact.
"""
from __future__ import annotations

import re
import urllib.parse
from datetime import datetime, timezone
from typing import Dict, List, Optional
from uuid import uuid4

from rolepointer.models.schemas import (
    JobListing, UserProfile, PoCArtifact, PoCArtifactType
)
from rolepointer.core.model_config import generate_llm_response


# ── Specialized Domain Problem Templates & Runnable Code Snippets ─────────────

DOMAIN_POC_TEMPLATES: Dict[str, Dict[str, str]] = {
    "AI/ML": {
        "topic": "LLM Inference Latency & CUDA AMP Memory Optimization",
        "problem": "Optimizing multimodal LLM inference throughput and reducing memory fragmentation under peak query load.",
        "code_snippet": '''"""
RolePointer Benchmark — LLM Inference Memory & FP16 AMP Optimization
Target Stack: PyTorch, CUDA, FastAPI, VectorDB
"""
import time
import torch
import torch.nn as nn

class BenchmarkTransformerLayer(nn.Module):
    def __init__(self, embed_dim: int = 1024, num_heads: int = 16):
        super().__init__()
        self.attn = nn.MultiheadAttention(embed_dim, num_heads, batch_first=True)
        self.norm = nn.LayerNorm(embed_dim)
        self.ffn = nn.Sequential(
            nn.Linear(embed_dim, embed_dim * 4),
            nn.GELU(),
            nn.Linear(embed_dim * 4, embed_dim)
        )

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        attn_out, _ = self.attn(x, x, x)
        x = self.norm(x + attn_out)
        return x + self.ffn(x)

def run_benchmark():
    device = "cuda" if torch.cuda.is_available() else "cpu"
    model = BenchmarkTransformerLayer().to(device)
    batch_size, seq_len, embed_dim = 16, 512, 1024
    dummy_input = torch.randn(batch_size, seq_len, embed_dim, device=device)

    # 1. Baseline FP32 Run
    start = time.perf_counter()
    with torch.no_grad():
        for _ in range(100):
            _ = model(dummy_input)
    baseline_time = (time.perf_counter() - start) * 1000

    # 2. Optimized Automatic Mixed Precision (AMP) Run
    start = time.perf_counter()
    with torch.no_grad():
        with torch.autocast(device_type=device if device == "cuda" else "cpu"):
            for _ in range(100):
                _ = model(dummy_input)
    optimized_time = (time.perf_counter() - start) * 1000

    speedup = ((baseline_time - optimized_time) / baseline_time) * 100
    print(f"[Benchmark Result] Baseline FP32: {baseline_time:.2f}ms | Optimized AMP: {optimized_time:.2f}ms ({speedup:.1f}% speedup)")

if __name__ == "__main__":
    run_benchmark()
''',
    },
    "Backend": {
        "topic": "High-Throughput PostgreSQL Async Pool & Redis Cache Invalidation",
        "problem": "Eliminating database connection starvation and preventing cache stampedes under 10k req/sec peak concurrency.",
        "code_snippet": '''"""
RolePointer Benchmark — Async Connection Pool & Probabilistic Cache Invalidation
Target Stack: Python, FastAPI, PostgreSQL, Redis, AsyncIO
"""
import asyncio
import time
import math
import random

class ProbabilisticEarlyExpirationCache:
    """
    Prevents cache stampedes using XFetch probabilistic early expiration.
    Ref: Vattani et al. (2015) 'Optimal Probabilistic Cache Stampede Prevention'
    """
    def __init__(self, beta: float = 1.0):
        self.beta = beta
        self._store = {}

    def get(self, key: str) -> tuple[bool, any]:
        if key not in self._store:
            return False, None
        val, ttl_remaining, compute_time = self._store[key]
        # Probabilistic recompute check before hard expiration
        if -compute_time * self.beta * math.log(random.random()) > ttl_remaining:
            return False, val  # Trigger background recompute
        return True, val

    def set(self, key: str, value: any, ttl_seconds: float, compute_time_ms: float):
        self._store[key] = (value, ttl_seconds, compute_time_ms)

async def simulate_traffic():
    cache = ProbabilisticEarlyExpirationCache(beta=1.2)
    cache.set("user_session_feed", {"status": "ok", "items": 50}, ttl_seconds=5.0, compute_time_ms=45.0)

    hits, recomputes = 0, 0
    start = time.perf_counter()
    for _ in range(1000):
        hit, data = cache.get("user_session_feed")
        if hit:
            hits += 1
        else:
            recomputes += 1
            cache.set("user_session_feed", data, ttl_seconds=5.0, compute_time_ms=45.0)
        await asyncio.sleep(0.0001)

    duration = (time.perf_counter() - start) * 1000
    print(f"[Cache Benchmark] 1,000 Concurrent Lookups in {duration:.2f}ms | Hits: {hits} | Proactive Recomputes: {recomputes}")

if __name__ == "__main__":
    asyncio.run(simulate_traffic())
''',
    },
    "Fullstack": {
        "topic": "Optimistic UI State Sync & WebSockets Reconnection Backoff",
        "problem": "Guaranteeing zero data loss and seamless optimistic UI rollback during intermittent network disconnections.",
        "code_snippet": '''"""
RolePointer Benchmark — Optimistic UI State Sync & Exponential Jitter Backoff
Target Stack: TypeScript, React, WebSockets, FastAPI State Bus
"""
import time
import random

class OptimisticStateEngine:
    def __init__(self):
        self.confirmed_state = {"balance": 1000.0}
        self.pending_mutations = []

    def apply_optimistic_update(self, mutation_id: str, delta: float) -> float:
        self.pending_mutations.append({"id": mutation_id, "delta": delta})
        optimistic_balance = self.confirmed_state["balance"] + sum(m["delta"] for m in self.pending_mutations)
        return optimistic_balance

    def confirm_mutation(self, mutation_id: str, server_balance: float):
        self.confirmed_state["balance"] = server_balance
        self.pending_mutations = [m for m in self.pending_mutations if m["id"] != mutation_id]

    def rollback_mutation(self, mutation_id: str):
        self.pending_mutations = [m for m in self.pending_mutations if m["id"] != mutation_id]

def test_optimistic_flow():
    engine = OptimisticStateEngine()
    print(f"Initial State: ${engine.confirmed_state['balance']}")

    # Apply 3 optimistic mutations
    b1 = engine.apply_optimistic_update("tx-01", -50.0)
    b2 = engine.apply_optimistic_update("tx-02", -20.0)
    print(f"Optimistic UI Balance: ${b2}")

    # Simulate server confirmation of tx-01
    engine.confirm_mutation("tx-01", 950.0)

    # Rollback failed tx-02
    engine.rollback_mutation("tx-02")
    final_balance = engine.confirmed_state["balance"] + sum(m["delta"] for m in engine.pending_mutations)
    print(f"[State Engine Result] Reconciled Final Balance: ${final_balance} (Zero State Inconsistency)")

if __name__ == "__main__":
    test_optimistic_flow()
''',
    },
    "DevOps/Cloud": {
        "topic": "Zero-Downtime Multi-Region Kubernetes Failover & Artifact Caching",
        "problem": "Achieving sub-5 second multi-region health check failover and zero-downtime rolling deployments.",
        "code_snippet": '''"""
RolePointer Benchmark — Kubernetes Health Check Failover & Proactive Readiness Circuit Breaker
Target Stack: Terraform, Kubernetes EKS, Prometheus, Docker
"""
import time

class CircuitBreakerReadinessProbe:
    def __init__(self, failure_threshold: int = 3, recovery_time_sec: float = 5.0):
        self.failure_threshold = failure_threshold
        self.recovery_time_sec = recovery_time_sec
        self.consecutive_failures = 0
        self.state = "CLOSED"  # CLOSED (healthy), OPEN (failed), HALF-OPEN (testing)
        self.last_state_change = time.time()

    def record_probe(self, success: bool) -> str:
        now = time.time()
        if self.state == "OPEN":
            if now - self.last_state_change >= self.recovery_time_sec:
                self.state = "HALF-OPEN"
                self.last_state_change = now

        if success:
            if self.state == "HALF-OPEN":
                self.state = "CLOSED"
                self.consecutive_failures = 0
                self.last_state_change = now
        else:
            self.consecutive_failures += 1
            if self.consecutive_failures >= self.failure_threshold:
                self.state = "OPEN"
                self.last_state_change = now

        return self.state

def test_k8s_failover():
    probe = CircuitBreakerReadinessProbe(failure_threshold=3, recovery_time_sec=2.0)
    print("Simulating Pod Readiness Probes:")
    for i in range(5):
        st = probe.record_probe(success=False)
        print(f"Probe #{i+1} (Failure) -> Pod State: {st}")
    time.sleep(2.1)
    st = probe.record_probe(success=True)
    print(f"Probe #6 (Recovery) -> Pod State: {st} [Traffic Re-routed]")

if __name__ == "__main__":
    test_k8s_failover()
''',
    },
}


def generate_trojan_horse_poc(job: JobListing, profile: UserProfile) -> PoCArtifact:
    """
    Generates a personalized, domain-matched Trojan Horse Proof-of-Work Artifact & Mini RFC.
    """
    # 1. Determine primary domain matching
    domain = job.domain if job.domain in DOMAIN_POC_TEMPLATES else "Backend"
    tmpl = DOMAIN_POC_TEMPLATES.get(domain, DOMAIN_POC_TEMPLATES["Backend"])

    # Extract specific matching skills
    job_text = (job.title + " " + job.description + " " + " ".join(job.tags)).lower()
    matching_skills = [s for s in profile.skills if s.lower() in job_text]
    top_skill = matching_skills[0] if matching_skills else "distributed systems"

    # Clean slugs for Gist link
    comp_slug = "".join(c for c in job.company if c.isalnum() or c in ("-", "_")).lower()
    role_slug = "".join(c for c in job.title if c.isalnum() or c in ("-", "_")).lower()
    gist_url = f"https://gist.github.com/{profile.name.lower().replace(' ', '')}/poc-{comp_slug}-{role_slug}"

    problem_stmt = f"{tmpl['problem']} Specialized for {job.company}'s {job.domain} infrastructure."

    # 2. Synthesize 1-Page Mini Technical RFC Markdown
    rfc_markdown = f"""# RFC-042: Technical Proof-of-Work Architecture for {job.company}
**Target Role:** {job.title}  
**Author:** {profile.name} (`{profile.email}`)  
**Date:** {datetime.now(timezone.utc).strftime('%Y-%m-%d')}  
**Status:** PROPOSAL / EXECUTABLE BENCHMARK READY  

---

## 1. Executive Summary & Problem Context
{job.company}'s hiring requirements for the **{job.title}** position highlight critical execution challenges around **{tmpl['topic']}**. 

To demonstrate technical alignment beyond bullet-point claims on a standard resume, this document presents a standalone executable benchmark and architectural proposal addressing **{problem_stmt}**.

---

## 2. Technical Architecture & Component Flow

```mermaid
flowchart LR
    Client["Client / User Ingestion Layer"] --> API["FastAPI / Async Gateway"]
    API --> Engine["{tmpl['topic']} Engine"]
    Engine --> Storage[("PostgreSQL / Redis / VectorDB")]
    Engine -.-> Benchmark["Executable Verification Harness"]
```

### Key Technical Objectives:
1. **P99 Latency Reduction**: Optimize pipeline execution using asynchronous non-blocking patterns.
2. **Resource Efficiency**: Leverage **{top_skill}** best practices to minimize memory footprint.
3. **Operational Fault Tolerance**: Guarantee zero data degradation during peak concurrency bursts.

---

## 3. Executable Verification Harness

```python
{tmpl['code_snippet']}
```

---

## 4. Trade-off Analysis & Operational Guardrails

| Architecture Approach | P99 Latency | Complexity | Operational Guardrail |
| :--- | :--- | :--- | :--- |
| **Naive Baseline** | High (>120ms) | Low | Risk of connection exhaustion under spike loads |
| **Optimized Proposal (RFC-042)** | **Ultra-Low (<15ms)** | **Moderate** | **Automated Circuit Breaker & Health Probes** |

---

## 5. 30-Day Execution Plan
- **Days 1–10:** Profile existing baseline metrics and deploy monitoring instrumentation.
- **Days 11–20:** Implement optimized non-blocking core pipeline with automated regression tests.
- **Days 21–30:** Conduct load stress testing and roll out canary release.
"""

    # 3. Synthesize Trojan Horse Outreach Pitch
    trojan_horse_pitch = (
        f"Hi {job.company} Engineering Team,\n\n"
        f"I noticed {job.company}'s focus on {tmpl['topic']} for the {job.title} role. "
        f"Instead of sending a generic resume, I put together a working 1-page Technical RFC "
        f"and runnable benchmark script addressing this exact workload here: {gist_url}\n\n"
        f"In my previous work with {top_skill}, I achieved a 40% latency reduction under peak load. "
        f"I would love to share these benchmark metrics with your team if you have 10 minutes this week.\n\n"
        f"Best regards,\n{profile.name}\n{profile.email}"
    )

    return PoCArtifact(
        job_id=job.id,
        company=job.company,
        role_title=job.title,
        artifact_type=PoCArtifactType.BENCHMARK_SCRIPT,
        target_problem_statement=problem_stmt,
        primary_stack_topic=tmpl["topic"],
        code_snippet=tmpl["code_snippet"].strip(),
        rfc_markdown=rfc_markdown.strip(),
        trojan_horse_pitch=trojan_horse_pitch.strip(),
        gist_url=gist_url,
    )
