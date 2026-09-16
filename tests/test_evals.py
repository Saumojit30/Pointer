"""
RolePointer — Agent Evaluation Suite Tests
Validates the evaluation framework, rubrics, benchmark dataset, and LangSmith integration.
"""
import pytest
from rolepointer.evals import (
    run_evaluation_suite, BENCHMARK_CASES,
    evaluate_star_bullets, evaluate_cold_angle_structure,
    evaluate_dealbreaker_accuracy, evaluate_ghost_accuracy
)
from rolepointer.models.schemas import GhostRiskLevel


def test_star_bullet_rubric():
    # High-quality bullets with metrics and strong action verbs
    good_bullets = [
        "Architected distributed event streaming platform handling 50k+ RPS with 99.99% uptime.",
        "Optimized PostgreSQL query execution plans reducing p99 latency by 45% ($120k cloud savings).",
        "Deployed automated CI/CD pipeline on Kubernetes accelerating release velocity by 3x."
    ]
    score = evaluate_star_bullets(good_bullets)
    assert score.passed is True
    assert score.score >= 0.80

    # Low-quality bullets without metrics
    bad_bullets = [
        "Responsible for working on backend tasks.",
        "Helped team with some meetings and bugs."
    ]
    bad_score = evaluate_star_bullets(bad_bullets)
    assert bad_score.score < 0.50


def test_cold_angle_rubric():
    good_pitch = (
        "Noticed CloudScale AI is scaling real-time distributed pipelines. "
        "At my previous role, I architected Kafka event backends processing 50k+ RPS with 99.99% SLA. "
        "I can help eliminate throughput bottlenecks in your distributed event streams within 30 days. "
        "Open to a brief 10-minute technical exchange next Tuesday?"
    )
    score = evaluate_cold_angle_structure(good_pitch, candidate_skills=["Kafka", "Python", "Go"])
    assert score.passed is True
    assert score.score >= 0.80


def test_dealbreaker_and_ghost_rubrics():
    dealbreaker_score = evaluate_dealbreaker_accuracy(
        actual_dealbreaker=True,
        expected_dealbreaker=True,
        actual_reason="Salary below floor",
        expected_contains="Salary"
    )
    assert dealbreaker_score.passed is True
    assert dealbreaker_score.score == 1.0

    ghost_score = evaluate_ghost_accuracy(
        actual_risk=GhostRiskLevel.HIGH_GHOST_RISK,
        expected_risk=GhostRiskLevel.HIGH_GHOST_RISK
    )
    assert ghost_score.passed is True
    assert ghost_score.score == 1.0


def test_full_benchmark_suite_execution():
    """Runs the full evaluation suite across all benchmark cases."""
    summary = run_evaluation_suite(sync_langsmith=False)
    assert summary.total_cases == len(BENCHMARK_CASES)
    assert summary.total_cases >= 5
    assert summary.passed_cases >= 4
    assert summary.average_overall_score >= 0.80
    assert summary.dealbreaker_recall >= 0.80
    assert summary.ghost_detection_f1 >= 0.80
    assert len(summary.case_results) == summary.total_cases
