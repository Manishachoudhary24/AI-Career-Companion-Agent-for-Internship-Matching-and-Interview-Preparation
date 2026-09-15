# ---------------------------------------------------------------------------
# SYNTHETIC INTERNSHIP POSTINGS GENERATOR
# ---------------------------------------------------------------------------
# Produces app/data/internships.json — a fictional-but-realistic catalog of
# internship postings used as the knowledge base for the RAG matching
# endpoint (see app/services/internship_index.py). Companies are invented
# (never real orgs) so nothing here reads as an actual posting from a real
# company. Run this whenever you want to regenerate the dataset:
#
#   python -m app.data.generate_internships
#
# Deterministic (random.seed below) so re-running produces the same file
# unless the pools/templates are edited.
# ---------------------------------------------------------------------------

import json
import random
import uuid
from pathlib import Path

random.seed(42)

OUTPUT_PATH = Path(__file__).resolve().parent / "internships.json"

# Company names are built from a prefix + suffix pool rather than hardcoded
# one-by-one, so we get many plausible-sounding fictional companies without
# any of them colliding with a real one.
COMPANY_PREFIXES = [
    "Vertexa", "Nimbus", "Quantumly", "Brightloop", "Cobalt", "Skyfield",
    "Northstar", "Pixelforge", "Ironbridge", "Solvex", "Everdata", "Lumenary",
    "Cascade", "Orbital", "Redwood", "Crestline", "Amberline", "Fernwood",
    "Bluepeak", "Silverline", "Trueform", "Wavecrest", "Highfield", "Clearwater",
    "Granite", "Meridian", "Foxglove", "Driftwood", "Basecrest", "Zenoak",
]
COMPANY_SUFFIXES = [
    "Analytics", "Systems", "Labs", "Technologies", "Softworks", "Cloud",
    "Digital", "Networks", "Solutions", "Robotics", "AI", "Dynamics",
    "Software", "Innovations", "Ventures", "Studio", "Works",
]
COMPANY_LEGAL = ["Pvt Ltd", "Inc", "LLP", ""]


def _make_companies(n: int) -> list[str]:
    seen = set()
    companies = []
    while len(companies) < n:
        name = f"{random.choice(COMPANY_PREFIXES)} {random.choice(COMPANY_SUFFIXES)}"
        legal = random.choice(COMPANY_LEGAL)
        full = f"{name} {legal}".strip()
        if full not in seen:
            seen.add(full)
            companies.append(full)
    return companies


LOCATIONS = [
    "Bengaluru, India", "Hyderabad, India", "Pune, India", "Chennai, India",
    "Mumbai, India", "Gurugram, India", "Noida, India", "Kolkata, India",
    "Remote", "Ahmedabad, India", "Jaipur, India", "Kochi, India",
]
MODES = ["Remote", "Onsite", "Hybrid"]
EDUCATION_LEVELS = [
    "Pursuing B.Tech/B.E.", "Pursuing B.Tech/B.E. (CS/IT preferred)",
    "Pursuing BCA/MCA", "Pursuing B.Sc (CS/IT/Stats)", "Pursuing M.Tech/M.E.",
    "Any Bachelor's degree (final year)", "Pursuing MBA",
]

# Each domain: role title pool, required-skill pool, preferred-skill pool,
# and a description template. Skill pools mostly reuse KNOWN_SKILLS from
# resume_parser.py (kept as plain strings here to avoid a cross-module
# import into a data-generation script) plus a few domain-specific extras
# for the non-tech tracks.
DOMAINS = {
    "Software Development": {
        "roles": ["Software Engineering Intern", "Backend Developer Intern",
                  "Full-Stack Developer Intern", "Java Developer Intern"],
        "required": ["Python", "Java", "C++", "JavaScript", "Data Structures",
                     "Algorithms", "Git", "SQL", "REST API"],
        "preferred": ["Docker", "AWS", "Spring Boot", "Django", "FastAPI",
                      "Kubernetes", "CI/CD"],
        "desc": "Work with the engineering team to design, build, and test "
                "features for our production {product}. You'll pair with "
                "senior engineers, write clean code, and ship real features "
                "used by customers.",
    },
    "Data Science": {
        "roles": ["Data Science Intern", "Machine Learning Intern",
                  "AI Research Intern", "Data Analyst Intern"],
        "required": ["Python", "Machine Learning", "Pandas", "NumPy",
                     "SQL", "Data Analysis", "Scikit-learn", "Statistics"],
        "preferred": ["Deep Learning", "TensorFlow", "PyTorch", "NLP",
                      "Computer Vision", "Power BI", "Tableau"],
        "desc": "Analyze large datasets and build predictive models to "
                "support our {product} team's decisions. Exposure to the "
                "full ML lifecycle: data cleaning, modeling, evaluation, "
                "and deployment.",
    },
    "Web Development": {
        "roles": ["Frontend Developer Intern", "Web Developer Intern",
                  "React Developer Intern", "UI Engineering Intern"],
        "required": ["HTML", "CSS", "JavaScript", "React", "Git",
                     "REST API", "Bootstrap"],
        "preferred": ["TypeScript", "Tailwind CSS", "Node.js", "GraphQL",
                      "Vue", "Angular"],
        "desc": "Build and ship user-facing features for our {product} "
                "web app, working closely with design and backend teams "
                "on performance and accessibility.",
    },
    "DevOps/Cloud": {
        "roles": ["DevOps Intern", "Cloud Engineering Intern",
                  "Site Reliability Intern", "Platform Engineering Intern"],
        "required": ["Linux", "Docker", "Git", "AWS", "CI/CD", "Python"],
        "preferred": ["Kubernetes", "Terraform", "Jenkins", "Azure", "GCP",
                      "Monitoring"],
        "desc": "Support the platform team in automating deployments, "
                "improving CI/CD pipelines, and monitoring reliability for "
                "our {product} infrastructure.",
    },
    "QA/Testing": {
        "roles": ["QA Engineering Intern", "Test Automation Intern",
                  "Software Testing Intern"],
        "required": ["Python", "Java", "Selenium", "Git", "SQL",
                     "Problem Solving"],
        "preferred": ["CI/CD", "JIRA", "REST API", "Docker"],
        "desc": "Design and automate test suites for our {product} "
                "platform, working with developers to catch regressions "
                "before release.",
    },
    "Mobile Development": {
        "roles": ["Android Developer Intern", "iOS Developer Intern",
                  "Mobile App Developer Intern"],
        "required": ["Kotlin", "Java", "Swift", "Git", "REST API"],
        "preferred": ["React Native", "Firebase", "SQLite", "CI/CD"],
        "desc": "Build features for our {product} mobile app used by "
                "thousands of users, from UI polish to backend "
                "integration.",
    },
    "Cybersecurity": {
        "roles": ["Cybersecurity Intern", "Security Analyst Intern",
                  "Application Security Intern"],
        "required": ["Linux", "Networking", "Python", "SQL",
                     "Problem Solving"],
        "preferred": ["AWS", "Docker", "Git", "CI/CD"],
        "desc": "Assist the security team with vulnerability assessments "
                "and secure code review for our {product} systems.",
    },
    "UI/UX Design": {
        "roles": ["UI/UX Design Intern", "Product Design Intern"],
        "required": ["Figma", "Adobe XD", "Wireframing", "User Research"],
        "preferred": ["HTML", "CSS", "Prototyping", "Design Systems"],
        "desc": "Design intuitive, accessible interfaces for our "
                "{product} product, collaborating closely with engineering "
                "and product teams.",
    },
    "Product Management": {
        "roles": ["Product Management Intern", "Associate Product Intern"],
        "required": ["Excel", "Communication", "Problem Solving",
                     "Market Research"],
        "preferred": ["SQL", "JIRA", "Agile", "Data Analysis"],
        "desc": "Support the product team in gathering requirements, "
                "analyzing user feedback, and prioritizing the roadmap for "
                "{product}.",
    },
    "Digital Marketing": {
        "roles": ["Digital Marketing Intern", "SEO Intern",
                  "Content Marketing Intern"],
        "required": ["SEO", "Content Writing", "Social Media Marketing",
                     "Excel"],
        "preferred": ["Google Analytics", "Communication", "Market Research"],
        "desc": "Plan and execute digital campaigns to grow awareness of "
                "our {product} product across channels.",
    },
    "Business Analysis": {
        "roles": ["Business Analyst Intern", "Operations Intern"],
        "required": ["Excel", "SQL", "Data Analysis", "Communication"],
        "preferred": ["Power BI", "Tableau", "JIRA", "Problem Solving"],
        "desc": "Analyze business processes and data to recommend "
                "improvements for our {product} operations.",
    },
    "Finance": {
        "roles": ["Finance Intern", "Financial Analyst Intern"],
        "required": ["Excel", "Financial Modeling", "Communication"],
        "preferred": ["SQL", "Power BI", "Data Analysis"],
        "desc": "Support the finance team with budgeting, forecasting, and "
                "financial modeling for {product}'s growth initiatives.",
    },
}

PRODUCTS = [
    "customer analytics platform", "payments gateway", "logistics tracker",
    "e-commerce marketplace", "healthtech app", "edtech platform",
    "SaaS dashboard", "IoT monitoring suite", "fintech app", "CRM tool",
    "internal developer platform", "recommendation engine", "chat platform",
]


def _pick_skills(pool: list[str], min_n: int, max_n: int) -> list[str]:
    n = min(len(pool), random.randint(min_n, max_n))
    return random.sample(pool, n)


def generate_postings(n_total: int = 180) -> list[dict]:
    companies = _make_companies(max(40, n_total // 4))
    postings = []

    domain_names = list(DOMAINS.keys())
    # Weight tech domains higher than the non-tech ones for the mix.
    tech_domains = domain_names[:7]
    other_domains = domain_names[7:]
    weighted_domains = tech_domains * 3 + other_domains

    for _ in range(n_total):
        domain_name = random.choice(weighted_domains)
        domain = DOMAINS[domain_name]
        company = random.choice(companies)
        role = random.choice(domain["roles"])
        product = random.choice(PRODUCTS)

        posting = {
            "id": str(uuid.uuid4()),
            "company": company,
            "role_title": role,
            "domain": domain_name,
            "location": random.choice(LOCATIONS),
            "mode": random.choice(MODES),
            "duration_weeks": random.choice([8, 10, 12, 16, 24]),
            "stipend_inr_per_month": random.choice(
                [8000, 10000, 12000, 15000, 18000, 20000, 25000, 30000]
            ),
            "min_education": random.choice(EDUCATION_LEVELS),
            "required_skills": sorted(_pick_skills(domain["required"], 3, 5)),
            "preferred_skills": sorted(_pick_skills(domain["preferred"], 1, 3)),
            "description": domain["desc"].format(product=product),
        }
        postings.append(posting)

    return postings


def main() -> None:
    postings = generate_postings()
    OUTPUT_PATH.write_text(json.dumps(postings, indent=2), encoding="utf-8")
    print(f"Wrote {len(postings)} postings to {OUTPUT_PATH}")


if __name__ == "__main__":
    main()
