"""
Deliverable #7 - Test cases for the internship matching RAG pipeline.

Runs 9 synthetic candidate profiles straight through
app.services.internship_matcher.match_resume_to_internships(), bypassing
the API/DB/auth layer entirely, so this is fast to run and easy to read.
Each profile is built as a ResumeMatchProfile the same way
app/services/resume_profile.py would build one from a real parsed resume.

Requires the FAISS index to exist first (built automatically on `uvicorn`
startup, or manually via `python -m app.services.internship_index`), and
that step needs one-time internet access to download the
sentence-transformers embedding model.

Run with:
    python test_matching_scenarios.py
"""
from __future__ import annotations

import json

from app.services.internship_matcher import match_resume_to_internships
from app.services.resume_profile import ResumeMatchProfile

CASES: list[tuple[str, ResumeMatchProfile]] = [
    (
        "Skill-based matching (strong Python + SQL, no degree info)",
        ResumeMatchProfile(
            skills="Python, SQL, Pandas, REST APIs",
            education=None,
            professional_summary="Backend-leaning developer comfortable with data-heavy APIs.",
            location="Bengaluru, India",
            extracted_text="Python SQL Pandas REST APIs backend developer",
        ),
    ),
    (
        "Education-based matching (M.Tech CS, thin skills)",
        ResumeMatchProfile(
            skills="C++",
            education="M.Tech in Computer Science, IIT Delhi",
            professional_summary=None,
            location="Delhi, India",
            extracted_text="M.Tech Computer Science student",
        ),
    ),
    (
        "Experience-based matching (prior internship in cloud/devops)",
        ResumeMatchProfile(
            skills="AWS, Docker, Linux, CI/CD",
            education="B.Tech in Information Technology, NIT Trichy",
            professional_summary="DevOps enthusiast.",
            location="Chennai, India",
            extracted_text="",
            supporting_text="DevOps Intern at CloudNine - set up CI/CD pipelines and managed AWS infra",
        ),
    ),
    (
        "Project-based matching (ML side projects, no formal experience)",
        ResumeMatchProfile(
            skills="Python, Scikit-learn",
            education="B.Tech in Computer Science, VIT Vellore",
            professional_summary=None,
            location="Vellore, India",
            extracted_text="",
            supporting_text="Movie Recommendation System - built a collaborative-filtering recommender - Python, Scikit-learn, Pandas",
        ),
    ),
    (
        "Multiple-skill matching (full-stack + data)",
        ResumeMatchProfile(
            skills="React, Node.js, Python, SQL, Machine Learning",
            education="B.Tech in Computer Science, BITS Pilani",
            professional_summary="Full-stack developer moving into data science.",
            location="Pune, India",
            extracted_text="",
        ),
    ),
    (
        "AI/ML internship seeker",
        ResumeMatchProfile(
            skills="Python, TensorFlow, PyTorch, Machine Learning, Deep Learning",
            education="B.Tech in Computer Science, IIT Bombay",
            professional_summary="Aspiring ML engineer with coursework in deep learning.",
            location="Mumbai, India",
            extracted_text="",
        ),
    ),
    (
        "Backend development internship seeker",
        ResumeMatchProfile(
            skills="Java, Spring Boot, SQL, Microservices, REST APIs",
            education="B.Tech in Computer Science, Anna University",
            professional_summary="Backend developer focused on scalable services.",
            location="Chennai, India",
            extracted_text="",
        ),
    ),
    (
        "Data Science internship seeker",
        ResumeMatchProfile(
            skills="Python, Pandas, NumPy, SQL, Data Visualization, Statistics",
            education="M.Sc in Data Science, Pune University",
            professional_summary="Data science postgrad focused on analytics.",
            location="Pune, India",
            extracted_text="",
        ),
    ),
    (
        "Generative AI internship seeker",
        ResumeMatchProfile(
            skills="Python, LLMs, LangChain, Prompt Engineering, NLP",
            education="B.Tech in Computer Science, IIIT Hyderabad",
            professional_summary="Building with LLMs and RAG pipelines.",
            location="Hyderabad, India",
            extracted_text="",
            supporting_text="RAG Chatbot - built a retrieval-augmented chatbot over internal docs - LangChain, FAISS, Groq",
        ),
    ),
]


def main() -> None:
    for title, profile in CASES:
        print("=" * 100)
        print(title)
        print("-" * 100)
        result = match_resume_to_internships(profile, k=3)
        if not result["results"]:
            print("No matches (empty query - unexpected for these synthetic profiles).")
            continue
        for m in result["results"]:
            print(
                f"  [{m['match_percentage']:>5.1f}%  {m['match_label']:<14}] "
                f"{m['role_title']} @ {m['company']} ({m['domain']}, {m['location']}, {m['mode']})"
            )
            print(f"      matched: {m['matched_skills']} | missing: {m['missing_skills']}")
        if result["summary"]:
            print(f"  Groq summary: {result['summary']}")
        print()


if __name__ == "__main__":
    main()
