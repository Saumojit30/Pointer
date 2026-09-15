"""
RolePointer — Deterministic Mock Feeds & Demo Listings
Provides rich, realistic fixtures for testing, offline demos, and verification.
Covering AI/ML, Backend, Fullstack, DevOps across SF, London, Bangalore, Berlin, and Worldwide Remote.
"""
from __future__ import annotations

from typing import List
from rolepointer.models.schemas import JobListing, WorkplaceType, ExperienceLevel


MOCK_JOBS: List[JobListing] = [
    JobListing(
        id="mock-job-01",
        title="Senior AI Platform Engineer",
        company="CognitiveFlow AI",
        location="Remote (Worldwide)",
        country="United States",
        city="San Francisco",
        workplace_type=WorkplaceType.REMOTE,
        domain="AI/ML",
        experience_level=ExperienceLevel.SENIOR,
        salary_range="$160,000 - $210,000",
        salary_min=160000.0,
        salary_max=210000.0,
        tags=["Python", "FastAPI", "PyTorch", "AWS", "Docker", "Kubernetes", "Redis", "LangChain"],
        description=(
            "We are seeking a Senior AI Platform Engineer to architect high-throughput LLM agent serving infrastructure. "
            "Responsibilities: Build distributed agent pipelines using Python and FastAPI. Optimize inference latency with Redis caching and AWS Bedrock. "
            "Lead Kubernetes deployment across multi-region clusters. Requirements: 5+ years backend engineering, strong Python skills, "
            "proven experience building production AI systems. Flexible remote work culture with no unpaid overtime."
        ),
        url="https://cognitiveflow.ai/careers/ai-platform-engineer",
        source="MockFeed",
    ),
    JobListing(
        id="mock-job-02",
        title="Staff Backend Systems Architect",
        company="ScaleSphere Cloud",
        location="San Francisco, CA, US",
        country="United States",
        city="San Francisco",
        workplace_type=WorkplaceType.HYBRID,
        domain="Backend",
        experience_level=ExperienceLevel.STAFF_LEAD,
        salary_range="$180,000 - $235,000",
        salary_min=180000.0,
        salary_max=235000.0,
        tags=["Python", "PostgreSQL", "FastAPI", "AWS", "Kafka", "Docker", "Distributed Systems"],
        description=(
            "ScaleSphere is hiring a Staff Backend Systems Architect to lead our core data ingestion and transactional engine. "
            "You will design event-driven architectures in Python and Kafka handling 50,000 events/sec with sub-50ms latency. "
            "Must have deep expertise with PostgreSQL query optimization, async Python, and AWS architecture. "
            "Hybrid setup in downtown San Francisco with generous equity."
        ),
        url="https://scalesphere.io/jobs/backend-architect",
        source="MockFeed",
    ),
    JobListing(
        id="mock-job-03",
        title="Lead Full Stack Engineer",
        company="FintechNexus Global",
        location="London, UK",
        country="United Kingdom",
        city="London",
        workplace_type=WorkplaceType.HYBRID,
        domain="Fullstack",
        experience_level=ExperienceLevel.SENIOR,
        salary_range="£95,000 - £125,000",
        salary_min=120000.0,
        salary_max=160000.0,
        tags=["React", "TypeScript", "Python", "FastAPI", "PostgreSQL", "Next.js", "Docker"],
        description=(
            "Join our London hub to build real-time financial portfolio visualization interfaces. "
            "Requires solid mastery of modern React/Next.js alongside FastAPI backend microservices. "
            "Collaborate with quants and product teams to deliver high-security trading dashboards."
        ),
        url="https://fintechnexus.co.uk/careers/lead-fullstack",
        source="MockFeed",
    ),
    JobListing(
        id="mock-job-04",
        title="Senior Cloud DevOps & SRE",
        company="Aether Data Labs",
        location="Berlin, Germany",
        country="Germany",
        city="Berlin",
        workplace_type=WorkplaceType.ONSITE,
        domain="DevOps/Cloud",
        experience_level=ExperienceLevel.SENIOR,
        salary_range="€85,000 - €110,000",
        salary_min=95000.0,
        salary_max=120000.0,
        tags=["Terraform", "Kubernetes", "AWS", "CI/CD", "Prometheus", "Docker", "Python"],
        description=(
            "Aether Labs is looking for a Senior DevOps & Reliability Engineer to maintain our EU cloud infrastructure. "
            "You will write Infrastructure as Code (Terraform), manage EKS Kubernetes clusters, and automate zero-downtime CI/CD pipelines. "
            "Strict 38-hour work week, comprehensive health benefits, and German language training."
        ),
        url="https://aetherlabs.de/jobs/devops-sre",
        source="MockFeed",
    ),
    JobListing(
        id="mock-job-05",
        title="Principal AI Research Engineer",
        company="DeepMind Innovations",
        location="Bangalore, India",
        country="India",
        city="Bangalore",
        workplace_type=WorkplaceType.HYBRID,
        domain="AI/ML",
        experience_level=ExperienceLevel.STAFF_LEAD,
        salary_range="₹4,500,000 - ₹6,500,000",
        salary_min=130000.0,
        salary_max=170000.0,
        tags=["Python", "PyTorch", "LLMs", "Transformers", "CUDA", "FastAPI", "VectorDB"],
        description=(
            "Join our Bangalore R&D center to train and evaluate state-of-the-art multimodal reasoning models. "
            "Hands-on experience with transformer architectures, fine-tuning techniques (LoRA/QLoRA), and vector databases required. "
            "State of the art compute cluster access with competitive global compensation."
        ),
        url="https://deepmindinnovations.in/careers/principal-ai",
        source="MockFeed",
    ),
    JobListing(
        id="mock-job-06",
        title="On-Call Crypto Contract Developer (Dealbreaker Test)",
        company="ShadowCasino Staking",
        location="Remote",
        country="Worldwide",
        city="Remote",
        workplace_type=WorkplaceType.REMOTE,
        domain="Backend",
        experience_level=ExperienceLevel.MID,
        salary_range="Commission / Token Only",
        salary_min=30000.0,
        salary_max=50000.0,
        tags=["Solidity", "Crypto", "Gambling", "Smart Contracts", "Legacy PHP"],
        description=(
            "Urgent crypto gambling platform needs a weekend warrior. Must be available for 24/7 on-call weekend shifts and unpaid overtime. "
            "Experience maintaining legacy PHP code and smart contract staking protocols. No base salary guarantee."
        ),
        url="https://shadowcasino.io/jobs/crypto-dev",
        source="MockFeed",
    ),
]


def get_mock_jobs() -> List[JobListing]:
    """Returns deep copies of deterministic mock jobs."""
    return [JobListing(**j.model_dump()) for j in MOCK_JOBS]
