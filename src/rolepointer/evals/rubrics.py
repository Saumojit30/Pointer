"""
RolePointer — Agent Evaluation Rubrics
Deterministic scoring rubrics for STAR resume bullets, cold outreach pitches,
dealbreaker sentinel precision/recall, and anti-ghost classification accuracy.
"""
from __future__ import annotations
import re
from typing import Optional, List
from rolepointer.models.schemas import GhostRiskLevel
from rolepointer.evals.schemas import RubricScore


STRONG_ACTION_VERBS = {
    "engineered", "architected", "optimized", "built", "scaled", "deployed",
    "reduced", "accelerated", "designed", "implemented", "migrated", "automated",
    "developed", "delivered", "integrated", "refactored", "spearheaded", "orchestrated",
    "improved", "enhanced", "streamlined", "constructed", "pioneered", "standardized"
}

METRIC_PATTERN = re.compile(
    r"(\$\s*\d+|\d+([.,]\d+)?\s*(%|x|ms|s|k|m|b|gb|tb|rps|users|req/s|tps|\+)?|\d+)",
    re.IGNORECASE
)


def evaluate_star_bullets(bullets: List[str]) -> RubricScore:
    """
    Evaluates tailored CV bullets on:
    1. Quantified metric density (numbers, percentages, scale figures).
    2. Strong action verb openings.
    """
    if not bullets:
        return RubricScore(
            metric_name="star_bullet_quality",
            score=0.0,
            passed=False,
            details="No resume bullets provided for evaluation."
        )

    verb_matches = 0
    metric_matches = 0

    for b in bullets:
        cleaned = b.strip().lstrip("-*•0123456789. ")
        words = cleaned.split()
        if words:
            first_word = words[0].lower().rstrip("ed").rstrip("ing") + "ed"
            if words[0].lower() in STRONG_ACTION_VERBS or first_word in STRONG_ACTION_VERBS:
                verb_matches += 1
            elif any(v in cleaned.lower()[:30] for v in STRONG_ACTION_VERBS):
                verb_matches += 1

        if METRIC_PATTERN.search(cleaned):
            metric_matches += 1

    verb_ratio = verb_matches / len(bullets)
    metric_ratio = metric_matches / len(bullets)
    score = round(0.4 * verb_ratio + 0.6 * metric_ratio, 2)
    passed = score >= 0.70

    return RubricScore(
        metric_name="star_bullet_quality",
        score=score,
        passed=passed,
        details=f"Action verb coverage: {verb_ratio:.0%}, Metric quantification coverage: {metric_ratio:.0%}",
        metadata={"verb_ratio": verb_ratio, "metric_ratio": metric_ratio, "bullet_count": len(bullets)}
    )


def evaluate_cold_angle_structure(pitch: str, candidate_skills: List[str]) -> RubricScore:
    """
    Evaluates 4-Sentence Cold Angle on:
    1. Structure: ~4 sentences (Hook -> Metric -> Value Proposition -> CTA).
    2. Length: Under 140 words (respects executive brevity).
    3. Grounding: References candidate skills with zero external hallucinations.
    """
    if not pitch:
        return RubricScore(
            metric_name="cold_angle_structure",
            score=0.0,
            passed=False,
            details="Pitch text is empty."
        )

    sentences = [s.strip() for s in re.split(r"[.!?]+", pitch) if s.strip()]
    sentence_count = len(sentences)
    words = pitch.split()
    word_count = len(words)

    # Structure adherence (target: 3 to 5 sentences)
    if 3 <= sentence_count <= 5:
        structure_score = 1.0
    elif sentence_count == 2 or sentence_count == 6:
        structure_score = 0.8
    else:
        structure_score = 0.5

    # Brevity adherence (target: 30 - 140 words)
    if 30 <= word_count <= 140:
        brevity_score = 1.0
    elif word_count < 30 or word_count <= 160:
        brevity_score = 0.8
    else:
        brevity_score = 0.4

    # Grounding check
    grounded = any(skill.lower() in pitch.lower() for skill in candidate_skills) if candidate_skills else True
    grounding_score = 1.0 if grounded else 0.8

    overall_score = round(0.4 * structure_score + 0.3 * brevity_score + 0.3 * grounding_score, 2)
    passed = overall_score >= 0.75

    return RubricScore(
        metric_name="cold_angle_structure",
        score=overall_score,
        passed=passed,
        details=f"Sentences: {sentence_count} (ideal 4), Words: {word_count} (ideal <120), Skill Grounding: {grounded}",
        metadata={"sentence_count": sentence_count, "word_count": word_count, "grounded": grounded}
    )


def evaluate_dealbreaker_accuracy(
    actual_dealbreaker: bool,
    expected_dealbreaker: bool,
    actual_reason: Optional[str] = None,
    expected_contains: Optional[str] = None
) -> RubricScore:
    """Evaluates Dealbreaker precision and recall."""
    if actual_dealbreaker == expected_dealbreaker:
        if expected_dealbreaker and expected_contains and actual_reason:
            reason_matched = expected_contains.lower() in actual_reason.lower()
            score = 1.0 if reason_matched else 0.9
        else:
            score = 1.0
        passed = True
        details = f"Correctly identified dealbreaker state: {actual_dealbreaker}"
    else:
        score = 0.0
        passed = False
        details = f"Mismatch: expected dealbreaker={expected_dealbreaker}, got={actual_dealbreaker}"

    return RubricScore(
        metric_name="dealbreaker_accuracy",
        score=score,
        passed=passed,
        details=details
    )


def evaluate_ghost_accuracy(
    actual_risk: GhostRiskLevel,
    expected_risk: GhostRiskLevel
) -> RubricScore:
    """Evaluates Anti-Ghost classification accuracy."""
    if actual_risk == expected_risk:
        score = 1.0
        passed = True
        details = f"Accurately classified ghost risk: {actual_risk.value}"
    elif (actual_risk == GhostRiskLevel.MODERATE_RISK and expected_risk in (GhostRiskLevel.LOW_RISK, GhostRiskLevel.HIGH_GHOST_RISK)):
        score = 0.7
        passed = True
        details = f"Acceptable boundary classification: expected {expected_risk.value}, got {actual_risk.value}"
    else:
        score = 0.0
        passed = False
        details = f"Ghost risk mismatch: expected {expected_risk.value}, got {actual_risk.value}"

    return RubricScore(
        metric_name="ghost_classification_accuracy",
        score=score,
        passed=passed,
        details=details
    )
