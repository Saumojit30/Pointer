"""
RolePointer — Interactive Mock Interview Simulator
Generates company-specific interview questions and evaluates user responses with actionable feedback.
"""
from __future__ import annotations

from typing import List, Optional, Union
from loguru import logger

from rolepointer.models.schemas import (
    JobListing, UserProfile, MockInterviewSession, MockInterviewQuestion, MockInterviewEvaluation
)


def generate_mock_interview_questions(job: JobListing, profile: UserProfile) -> List[MockInterviewQuestion]:
    """Creates 4 targeted interview questions (2 technical, 1 system design, 1 behavioral STAR)."""
    questions = [
        MockInterviewQuestion(
            question_id=1,
            category="Technical Architecture",
            question=f"How would you approach designing and optimizing a high-concurrency API service in {job.tags[0] if job.tags else 'Python'} for {job.company}'s {job.domain} workflow?",
            guidance="Focus on async I/O, database indexing, caching strategies with Redis, and handling connection pools."
        ),
        MockInterviewQuestion(
            question_id=2,
            category="System Design & Reliability",
            question=f"Suppose {job.company}'s primary service experiences sudden traffic spikes causing cascading p99 latency degradation. Walk us through how you would diagnose, mitigate, and architect resilience.",
            guidance="Mention circuit breakers, rate limiting, autoscaling, distributed tracing, and graceful degradation."
        ),
        MockInterviewQuestion(
            question_id=3,
            category="Behavioral & STAR",
            question="Tell me about a time you had a technical disagreement with a teammate regarding system architecture. How did you resolve it?",
            guidance="Structure your response: Situation, Task, Action, and Result. Highlight data-driven evaluation and consensus."
        ),
        MockInterviewQuestion(
            question_id=4,
            category="Company & Role Alignment",
            question=f"Why are you interested in joining {job.company} specifically as a {job.title}, and what unique impact will you bring in the first 90 days?",
            guidance="Connect your experience with {job.company}'s domain and outline a 30-60-90 day onboarding and contribution roadmap."
        ),
    ]
    logger.info(f"[InterviewAgent] Generated 4 mock interview questions for {job.title} @ {job.company}")
    return questions


def evaluate_interview_answer(
    question: MockInterviewQuestion,
    user_answer: str,
    context: Optional[Union[JobListing, UserProfile]] = None
) -> MockInterviewEvaluation:
    """Evaluates candidate's answer with strengths, weaknesses, and a reference model answer."""
    ans_clean = user_answer.strip().lower()
    word_count = len(user_answer.split())

    domain = "Backend & Cloud"
    company = "the engineering"
    if isinstance(context, JobListing):
        domain = context.domain
        company = context.company

    score = 50
    strengths: List[str] = []
    improvements: List[str] = []

    # Evaluation heuristics
    if word_count >= 15:
        score += 20
        strengths.append("Provided structured response with engineering context.")
    else:
        improvements.append("Answer is somewhat brief; elaborate with concrete examples and metrics.")

    technical_terms = ["latency", "cache", "redis", "async", "scale", "metric", "sla", "index", "concurrency", "test", "star", "result", "postgres", "fastapi", "python"]
    found_terms = [t for t in technical_terms if t in ans_clean]
    if len(found_terms) >= 2:
        score += 20
        strengths.append(f"Demonstrated domain mastery mentioning: {', '.join(found_terms[:3])}.")
    else:
        improvements.append("Incorporate more technical precision and engineering terminology.")

    if any(k in ans_clean for k in ["measured", "result", "improved", "reduced", "%", "seconds", "10m", "scale"]):
        score += 10
        strengths.append("Framed contributions with measurable outcomes and business impact.")
    else:
        improvements.append("Quantify results with percentages, throughput numbers, or latency savings.")

    final_score = min(95, max(35, score))

    ideal_answer = (
        f"An exemplary response for '{question.question}' would: "
        f"1. Acknowledge key trade-offs in {domain} systems. "
        f"2. Cite a specific past project where you delivered measurable latency or throughput improvements. "
        f"3. Tie the solution back to {company}'s reliability and product goals."
    )

    evaluation = MockInterviewEvaluation(
        question_id=question.question_id,
        user_answer=user_answer,
        score=final_score,
        strengths=strengths,
        improvements=improvements,
        suggested_ideal_answer=ideal_answer,
    )
    logger.info(f"[InterviewAgent] Evaluated Q{question.question_id} -> Score: {final_score}%")
    return evaluation
