"""
RolePointer — Evaluation Runner & LangSmith Sync
Runs all benchmark cases through the live agent pipeline, computes rubric metrics,
and optionally syncs traces and evaluation feedback to LangSmith.
"""
from __future__ import annotations
import os
from datetime import datetime, timezone
from loguru import logger

from rolepointer.core.settings import settings
from rolepointer.models.schemas import GhostRiskLevel
from rolepointer.feeds.link_and_ghost_verifier import detect_ghost_job
from rolepointer.agents.fit_evaluator import evaluate_job_fit
from rolepointer.agents.drafter import draft_tailored_package
from rolepointer.agents.cold_angle_agent import generate_high_leverage_cold_angle
from rolepointer.evals.schemas import AgentEvalResult, BenchmarkSummary
from rolepointer.evals.rubrics import (
    evaluate_star_bullets, evaluate_cold_angle_structure,
    evaluate_dealbreaker_accuracy, evaluate_ghost_accuracy
)
from rolepointer.evals.benchmark_dataset import BENCHMARK_CASES


def run_evaluation_suite(sync_langsmith: bool = True) -> BenchmarkSummary:
    """
    Executes the complete agent evaluation suite across all benchmark test cases.
    Returns structured summary and optionally logs to LangSmith.
    """
    logger.info(f"[Evals] Starting RolePointer Agent Evaluation Suite ({len(BENCHMARK_CASES)} cases)...")
    results = []
    langsmith_client = None

    # Check LangSmith Configuration
    is_langsmith_enabled = settings.langsmith_tracing or bool(settings.langsmith_api_key) or os.getenv("LANGSMITH_API_KEY")
    if is_langsmith_enabled and sync_langsmith:
        try:
            from langsmith import Client  # type: ignore
            langsmith_client = Client(
                api_key=settings.langsmith_api_key or os.getenv("LANGSMITH_API_KEY"),
                api_url=settings.langsmith_endpoint,
            )
            logger.info(f"[Evals] Connected to LangSmith project: {settings.langsmith_project}")
        except Exception as e:
            logger.warning(f"[Evals] LangSmith connection note: {e}")

    for case in BENCHMARK_CASES:
        # 1. Evaluate Fit and Dealbreakers
        fit_eval = evaluate_job_fit(case.job_listing, case.candidate_profile)
        dealbreaker_reason = fit_eval.dealbreaker_alerts[0].explanation if fit_eval.dealbreaker_alerts else None
        dealbreaker_score = evaluate_dealbreaker_accuracy(
            actual_dealbreaker=fit_eval.has_dealbreaker,
            expected_dealbreaker=case.expected_dealbreaker,
            actual_reason=dealbreaker_reason,
            expected_contains=case.expected_dealbreaker_reason_contains
        )

        # 2. Evaluate Anti-Ghost Heuristics
        ghost_analysis = detect_ghost_job(case.job_listing)
        ghost_score = evaluate_ghost_accuracy(
            actual_risk=ghost_analysis.risk_level,
            expected_risk=case.expected_ghost_risk
        )

        # 3. Generate and Evaluate STAR Resume Bullets
        tailored_package = draft_tailored_package(case.job_listing, case.candidate_profile)
        star_score = evaluate_star_bullets(tailored_package.tailored_experience_bullets)

        # 4. Generate and Evaluate 4-Sentence Cold Angle
        cold_angle = generate_high_leverage_cold_angle(case.job_listing, case.candidate_profile)
        cold_score = evaluate_cold_angle_structure(cold_angle.email_body_4_sentences, case.candidate_profile.skills)

        # Aggregate Case Score
        overall_score = round(
            0.30 * dealbreaker_score.score +
            0.25 * ghost_score.score +
            0.25 * star_score.score +
            0.20 * cold_score.score,
            2
        )
        passed = (
            dealbreaker_score.passed and
            ghost_score.passed and
            star_score.passed and
            cold_score.passed
        )

        case_result = AgentEvalResult(
            case_id=case.id,
            case_name=case.name,
            star_bullet_score=star_score,
            cold_angle_score=cold_score,
            dealbreaker_score=dealbreaker_score,
            ghost_detection_score=ghost_score,
            overall_score=overall_score,
            passed=passed,
        )
        results.append(case_result)

        # Log trace to LangSmith if available
        if langsmith_client:
            try:
                langsmith_client.create_run(
                    name=f"eval_{case.id}_{case.name}",
                    run_type="chain",
                    project_name=settings.langsmith_project,
                    inputs={
                        "job_title": case.job_listing.title,
                        "company": case.job_listing.company,
                        "candidate": case.candidate_profile.name,
                        "salary_floor": case.candidate_profile.salary_floor_usd,
                    },
                    outputs={
                        "fit_score": fit_eval.score,
                        "dealbreaker_triggered": fit_eval.has_dealbreaker,
                        "ghost_risk": ghost_analysis.risk_level.value,
                        "pitch": cold_angle.email_body_4_sentences,
                    },
                    extra={
                        "metrics": {
                            "star_score": star_score.score,
                            "cold_angle_score": cold_score.score,
                            "dealbreaker_score": dealbreaker_score.score,
                            "ghost_score": ghost_score.score,
                            "overall_score": overall_score,
                        }
                    }
                )
            except Exception as e:
                logger.debug(f"[Evals] LangSmith run logging note: {e}")

    # Compute Benchmark Summary
    total = len(results)
    passed_count = sum(1 for r in results if r.passed)
    avg_overall = round(sum(r.overall_score for r in results) / total, 2) if total else 0.0
    avg_star = round(sum(r.star_bullet_score.score for r in results) / total, 2) if total else 0.0
    avg_cold = round(sum(r.cold_angle_score.score for r in results) / total, 2) if total else 0.0
    dealbreaker_recall = round(sum(1 for r in results if r.dealbreaker_score.passed) / total, 2) if total else 0.0
    ghost_f1 = round(sum(r.ghost_detection_score.score for r in results) / total, 2) if total else 0.0

    summary = BenchmarkSummary(
        total_cases=total,
        passed_cases=passed_count,
        average_overall_score=avg_overall,
        average_star_score=avg_star,
        average_cold_angle_score=avg_cold,
        dealbreaker_recall=dealbreaker_recall,
        ghost_detection_f1=ghost_f1,
        case_results=results,
        timestamp=datetime.now(timezone.utc).isoformat()
    )

    logger.info(
        f"[Evals] Benchmark Complete: {passed_count}/{total} cases passed "
        f"(Avg Score: {avg_overall:.0%}, STAR: {avg_star:.0%}, Pitch: {avg_cold:.0%}, Dealbreaker Recall: {dealbreaker_recall:.0%})"
    )

    return summary
