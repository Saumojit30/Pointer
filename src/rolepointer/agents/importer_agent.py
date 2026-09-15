"""
RolePointer — Resume & Candidate Profile Importer Agent
Extracts structured skills, experience summary, target roles, salary expectations,
and preference guardrails from raw resume text, markdown, or profile snippets.
Includes both LLM-powered extraction and a deterministic fallback parser.
"""
from __future__ import annotations

import json
import re
from typing import List, Optional
from loguru import logger

from rolepointer.core.model_config import get_strands_model
from rolepointer.models.schemas import UserProfile, WorkplaceType


TECH_SKILL_TAXONOMY = [
    "Python", "FastAPI", "Django", "Flask", "Go", "Golang", "Rust", "Java", "Spring Boot",
    "Node.js", "TypeScript", "JavaScript", "React", "Next.js", "Vue", "Angular",
    "PostgreSQL", "MySQL", "MongoDB", "Redis", "Kafka", "RabbitMQ", "Elasticsearch",
    "AWS", "GCP", "Azure", "Docker", "Kubernetes", "Terraform", "CI/CD", "Linux",
    "PyTorch", "TensorFlow", "LangChain", "LlamaIndex", "Hugging Face", "OpenAI",
    "GraphQL", "REST APIs", "Microservices", "System Design", "Distributed Systems"
]

DOMAIN_TAXONOMY = {
    "AI/ML": ["pytorch", "tensorflow", "llm", "langchain", "machine learning", "deep learning", "nlp", "computer vision", "rag"],
    "Backend": ["fastapi", "django", "postgres", "redis", "kafka", "microservices", "distributed systems", "database", "sql", "api"],
    "Fullstack": ["react", "next.js", "vue", "frontend", "typescript", "javascript", "full stack", "fullstack", "ui/ux"],
    "DevOps/Cloud": ["kubernetes", "docker", "terraform", "aws", "gcp", "azure", "ci/cd", "helm", "devops", "infrastructure"],
}


def _heuristic_fallback_parse(raw_text: str) -> UserProfile:
    """Deterministic regex & keyword parser when LLM is unavailable."""
    lines = [l.strip() for l in raw_text.splitlines() if l.strip()]
    name = lines[0] if lines else "Candidate"
    # Clean up name if it starts with # or title
    name = re.sub(r"^[#\s\-*]+", "", name).strip()
    if len(name) > 40:
        name = "Candidate"

    # Extract email
    email_match = re.search(r"[\w\.-]+@[\w\.-]+\.\w+", raw_text)
    email = email_match.group(0) if email_match else "candidate@example.com"

    # Extract phone
    phone_match = re.search(r"(?:\+\d{1,3}[-.\s]?)?\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4}", raw_text)
    phone = phone_match.group(0) if phone_match else "+1 (555) 000-0000"

    # Extract skills
    lower_text = raw_text.lower()
    matched_skills = [skill for skill in TECH_SKILL_TAXONOMY if re.search(r"\b" + re.escape(skill.lower()) + r"\b", lower_text)]
    if not matched_skills:
        matched_skills = ["Python", "FastAPI", "PostgreSQL", "AWS"]

    # Identify domains
    matched_domains = []
    for domain, keywords in DOMAIN_TAXONOMY.items():
        if any(kw in lower_text for kw in keywords):
            matched_domains.append(domain)
    if not matched_domains:
        matched_domains = ["Backend", "AI/ML"]

    # Target roles
    target_roles = []
    if "AI/ML" in matched_domains:
        target_roles.append("AI Systems Engineer")
    if "Backend" in matched_domains:
        target_roles.append("Senior Backend Engineer")
    if "Fullstack" in matched_domains:
        target_roles.append("Lead Full Stack Engineer")
    if "DevOps/Cloud" in matched_domains:
        target_roles.append("Cloud Platform Architect")
    if not target_roles:
        target_roles = ["Senior Software Engineer"]

    # Extract experience summary
    summary_lines = lines[1:5] if len(lines) > 1 else lines
    exp_summary = " ".join(summary_lines)[:350]
    if len(exp_summary) < 30:
        exp_summary = f"Senior Software Engineer specializing in {', '.join(matched_skills[:4])}."

    # Dealbreakers
    dealbreakers = ["unpaid overtime", "on-call weekend shifts", "crypto/gambling", "staffing agency"]
    if "legacy" in lower_text or "php" in lower_text:
        dealbreakers.append("legacy php")

    return UserProfile(
        name=name,
        email=email,
        phone=phone,
        location="Remote / San Francisco, CA",
        country_preference=["United States", "United Kingdom", "Germany", "India"],
        city_preference=["San Francisco", "London", "Bangalore", "Berlin", "New York"],
        preferred_workplace_types=[WorkplaceType.REMOTE, WorkplaceType.HYBRID],
        target_domains=matched_domains,
        target_roles=target_roles,
        skills=matched_skills,
        experience_summary=exp_summary,
        min_salary_floor=130000.0,
        dealbreakers=dealbreakers,
    )


def import_profile_from_text(raw_text: str) -> UserProfile:
    """
    Parses resume or LinkedIn profile text into a structured UserProfile model.
    Attempts LLM inference via Strands Bedrock/Ollama; falls back to heuristic extractor on error.
    """
    if not raw_text or len(raw_text.strip()) < 20:
        logger.warning("[ImporterAgent] Input text too short, using heuristic fallback")
        return _heuristic_fallback_parse(raw_text or "Software Engineer")

    sample = raw_text[:3500]
    prompt = (
        "You are an expert technical talent agent. Parse the following candidate resume / profile text and extract a structured JSON profile matching this exact format:\n"
        "{\n"
        '  "name": "Candidate Full Name",\n'
        '  "email": "email@example.com",\n'
        '  "phone": "+1 555-...",\n'
        '  "location": "City, State/Country",\n'
        '  "target_domains": ["AI/ML", "Backend"],\n'
        '  "target_roles": ["Senior Backend Engineer", "AI Systems Engineer"],\n'
        '  "skills": ["Python", "FastAPI", "AWS", "Docker"],\n'
        '  "experience_summary": "2-3 concise sentences highlighting core expertise, years of experience, and highest scale achievements.",\n'
        '  "min_salary_floor": 130000.0,\n'
        '  "dealbreakers": ["unpaid overtime", "on-call weekend shifts", "crypto/gambling"]\n'
        "}\n\n"
        f"RESUME TEXT:\n{sample}\n\n"
        "Return ONLY the raw JSON object. Do not include markdown code fences or conversational text."
    )

    try:
        model = get_strands_model()
        response = model(prompt)
        content = response if isinstance(response, str) else getattr(response, "text", str(response))
        
        # Clean JSON fences
        cleaned = re.sub(r"^```[a-zA-Z]*\n?", "", content.strip())
        cleaned = re.sub(r"\n?```$", "", cleaned.strip())
        data = json.loads(cleaned)

        profile = UserProfile(
            name=data.get("name", "Alex Morgan"),
            email=data.get("email", "alex.morgan@example.com"),
            phone=data.get("phone", "+1 (555) 234-5678"),
            location=data.get("location", "San Francisco, CA"),
            country_preference=["United States", "United Kingdom", "Germany", "India"],
            city_preference=["San Francisco", "London", "Bangalore", "Berlin", "New York"],
            preferred_workplace_types=[WorkplaceType.REMOTE, WorkplaceType.HYBRID],
            target_domains=data.get("target_domains", ["Backend", "AI/ML"]),
            target_roles=data.get("target_roles", ["Senior Software Engineer"]),
            skills=data.get("skills", ["Python", "FastAPI", "PostgreSQL"]),
            experience_summary=data.get("experience_summary", "Experienced software engineer."),
            min_salary_floor=float(data.get("min_salary_floor", 125000.0)),
            dealbreakers=data.get("dealbreakers", ["unpaid overtime", "crypto/gambling"]),
        )
        logger.info(f"[ImporterAgent] Successfully parsed candidate profile for: {profile.name}")
        return profile
    except Exception as e:
        logger.warning(f"[ImporterAgent] LLM parsing failed ({e}), falling back to deterministic parser")
        return _heuristic_fallback_parse(raw_text)
