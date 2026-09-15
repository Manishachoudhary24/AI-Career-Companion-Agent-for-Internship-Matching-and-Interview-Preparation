# CareerPilot – AI Career Companion for Internship Matching & Interview Preparation

CareerPilot is an AI-powered career assistance platform designed to help students discover suitable internships, analyze their resumes, identify skill gaps, prepare for interviews, and manage their internship applications.

The platform combines **Resume Intelligence, Semantic Search, FAISS-based Matching, AI-powered Analysis, RAG-based Career Assistance, and Interview Preparation** into a single application.

---

## Features

### 1. Resume Management

- Upload your resume in a supported format.
- Store and manage uploaded resumes.
- Extract important information from the resume.
- Identify skills, education, projects, and experience.
- Use extracted resume information for further career recommendations.

### 2. Resume Parsing & Skill Extraction

CareerPilot analyzes the uploaded resume and extracts relevant information such as:

- Technical skills
- Soft skills
- Education
- Work experience
- Projects
- Certifications
- Other relevant career information

The extracted information is used by other modules for personalized recommendations.

### 3. Internship Discovery

The platform provides an internship knowledge base where users can explore available internship opportunities based on their interests and profile.

Users can:

- Browse internships
- View internship details
- Explore suitable opportunities
- Track applied internships

### 4. AI Internship Matching

CareerPilot uses semantic search and vector similarity to match a student's resume with relevant internship opportunities.

The matching pipeline uses:

```text
Resume
   ↓
Resume Parsing
   ↓
Skill & Experience Extraction
   ↓
Text Embedding
   ↓
FAISS Vector Search
   ↓
Internship Matching
   ↓
Compatibility Score
```

### 5. Skill Gap Analysis

CareerPilot compares the user's existing skills with the requirements of suitable internship roles.

It helps identify:

- Existing skills
- Missing skills
- Recommended technologies
- Learning areas
- Skills required for specific roles

### 6. Cover Letter Generation

Users can generate personalized cover letters based on:

- Resume information
- Internship/job role
- Skills
- Experience
- Projects
- Role requirements

### 7. Interview Preparation Agent

The Interview Preparation Agent helps students prepare for interviews using their resume and selected career role.

It provides:

- Role-specific interview questions
- Technical questions
- HR questions
- Answer guidance
- Interview preparation strategies
- Learning roadmaps
- Recommended preparation topics

The preparation agent can also use uploaded documents as additional context.

### 8. AI Career Assistant

CareerPilot includes an AI-powered career assistant that helps students with internship and career-related queries.

The assistant can provide guidance related to:

- Career roles
- Internship preparation
- Resume improvement
- Skills
- Interview preparation
- Learning paths
- Career planning

The assistant uses relevant career knowledge through a retrieval-based approach.

### 9. Application Tracking

Students can track their internship applications and monitor their application journey.

Application information can include:

- Internship
- Company
- Application status
- Application date
- Other relevant details

### 10. Career Profile

Users can maintain their career profile containing information such as:

- Personal details
- Education
- Skills
- Projects
- Experience
- Career interests

---

# Application Workflow

```text
               ┌─────────────────────┐
               │       Student       │
               └──────────┬──────────┘
                          │
                          ▼
               ┌─────────────────────┐
               │   Upload Resume     │
               └──────────┬──────────┘
                          │
                          ▼
               ┌─────────────────────┐
               │   Resume Parsing    │
               └──────────┬──────────┘
                          │
                          ▼
             ┌───────────────────────────┐
             │ Skill / Experience        │
             │ Extraction                │
             └────────────┬──────────────┘
                          │
              ┌───────────┴───────────┐
              │                       │
              ▼                       ▼
   ┌─────────────────────┐   ┌─────────────────────┐
   │ Internship Matching │   │ Skill Gap Analysis  │
   └──────────┬──────────┘   └──────────┬──────────┘
              │                         │
              ▼                         ▼
   ┌─────────────────────┐   ┌─────────────────────┐
   │ Recommended         │   │ Skill Improvement   │
   │ Internships         │   │ Roadmap             │
   └──────────┬──────────┘   └─────────────────────┘
              │
              ▼
   ┌─────────────────────┐
   │ Application Tracker │
   └──────────┬──────────┘
              │
              ▼
   ┌─────────────────────┐
   │ Interview Preparation│
   │ Agent               │
   └──────────┬──────────┘
              │
              ▼
   ┌─────────────────────┐
   │ Career Readiness    │
   └─────────────────────┘
```

---

# System Architecture

```text
┌──────────────────────────────────────────────┐
│                Frontend                      │
│        React + Vite + CSS + Lucide          │
└──────────────────────┬───────────────────────┘
                       │
                       │ HTTP / REST API
                       ▼
┌──────────────────────────────────────────────┐
│                FastAPI Backend                │
│                                              │
│  Authentication                              │
│  Resume Management                           │
│  Internship Management                       │
│  Matching                                    │
│  Skill Gap Analysis                          │
│  Interview Preparation                       │
│  AI Career Assistant                         │
└───────────────┬───────────────┬──────────────┘
                │               │
                ▼               ▼
      ┌─────────────────┐   ┌─────────────────┐
      │   PostgreSQL    │   │   FAISS Index   │
      │   Database      │   │ Vector Search   │
      └─────────────────┘   └────────┬────────┘
                                     │
                                     ▼
                           ┌──────────────────┐
                           │ Embedding Model  │
                           │     MiniLM       │
                           └────────┬─────────┘
                                    │
                                    ▼
                           ┌──────────────────┐
                           │   Groq LLM       │
                           │ AI Generation    │
                           └──────────────────┘
```

---

# Technology Stack

## Frontend

- React
- Vite
- JavaScript
- CSS
- React Router
- Lucide React

## Backend

- Python
- FastAPI
- SQLAlchemy

## Database

- PostgreSQL

## AI & Machine Learning

- Groq
- Large Language Model
- Sentence Transformers
- MiniLM
- FAISS

## Retrieval

- FAISS Vector Database
- Semantic Search
- Retrieval-Augmented Generation (RAG)

## Development Tools

- Visual Studio Code
- Git
- GitHub
- Python Virtual Environment
- PostgreSQL / pgAdmin

---

# AI Matching Pipeline

CareerPilot uses semantic matching instead of relying only on exact keyword matching.

```text
Resume Text
     ↓
Text Processing
     ↓
Sentence Embeddings
     ↓
MiniLM
     ↓
FAISS Vector Index
     ↓
Similarity Search
     ↓
Relevant Internship Results
     ↓
AI Analysis
     ↓
Personalized Recommendations
```

This approach helps identify opportunities based on the semantic similarity between the student's profile and internship requirements.

---

# RAG-Based Career Assistant

The Career Assistant uses a retrieval-based approach to provide relevant career guidance.

```text
User Query
    ↓
Query Processing
    ↓
Vector Search
    ↓
Relevant Knowledge Retrieval
    ↓
Context Construction
    ↓
LLM
    ↓
AI Response
```

The knowledge base can contain career and internship preparation resources such as:

- Resume improvement
- ATS guidance
- Internship preparation
- Skill development
- DSA learning
- Interview preparation

---

# Project Structure

```text
AI_Career_pilot/
│
├── app/
│   ├── main.py
│   ├── models/
│   ├── routes/
│   ├── services/
│   ├── schemas/
│   └── ...
│
├── frontend/
│   ├── src/
│   │   ├── App.jsx
│   │   ├── api.js
│   │   ├── CareerFeatures.jsx
│   │   ├── ChatAssistant.jsx
│   │   ├── InterviewPrep.jsx
│   │   ├── styles.css
│   │   └── ...
│   │
│   ├── package.json
│   └── vite.config.js
│
├── docs/
├── screenshots/
├── requirements.txt
├── .env.example
└── README.md
```

---

# Installation & Setup

## Prerequisites

Make sure the following are installed:

- Python 3.12+
- Node.js
- npm
- PostgreSQL
- Git

---

# 1. Clone the Repository

```bash
git clone https://github.com/Manishachoudhary24/AI-Career-Companion-Agent-for-Internship-Matching-and-Interview-Preparation.git
```

Go to the project directory:

```bash
cd AI-Career-Companion-Agent-for-Internship-Matching-and-Interview-Preparation
```

---

# 2. Create Python Virtual Environment

Windows:

```powershell
python -m venv .venv
```

Activate it:

```powershell
.venv\Scripts\Activate.ps1
```

---

# 3. Install Backend Dependencies

```powershell
pip install -r requirements.txt
```

---

# 4. Configure Environment Variables

Create a `.env` file based on `.env.example`.

Example:

```env
DATABASE_URL=postgresql://postgres:postgres@localhost:5432/ai_career_companion_new

GROQ_API_KEY=your_groq_api_key_here

GROQ_MODEL=openai/gpt-oss-20b
```

Do not commit your actual API keys to GitHub.

---

# 5. Setup PostgreSQL

Create the required PostgreSQL database.

Example:

```sql
CREATE DATABASE ai_career_companion_new;
```

Make sure the PostgreSQL service is running before starting the backend.

---

# 6. Start the Backend

From the project root:

```powershell
uvicorn app.main:app --reload
```

The FastAPI backend will normally run at:

```text
http://127.0.0.1:8000
```

API documentation is available at:

```text
http://127.0.0.1:8000/docs
```

---

# 7. Install Frontend Dependencies

Open another terminal and go to the frontend directory:

```powershell
cd frontend
```

Install packages:

```powershell
npm install
```

---

# 8. Start the Frontend

```powershell
npm run dev
```

Vite will display the local development URL, normally:

```text
http://localhost:5173
```

Open that URL in your browser.

---

# Environment Variables

The application uses environment variables for configuration.

Example:

```env
DATABASE_URL=postgresql://postgres:postgres@localhost:5432/your_database

GROQ_API_KEY=your_api_key

GROQ_MODEL=openai/gpt-oss-20b
```

### Security

Never upload:

```text
.env
```

to GitHub when it contains real credentials.

Use:

```text
.env.example
```

for sharing configuration templates.

---

# API Modules

The backend provides APIs for major application modules including:

```text
Authentication
    ↓
Resume Management
    ↓
Resume Parsing
    ↓
Internship Management
    ↓
Internship Matching
    ↓
Skill Gap Analysis
    ↓
Interview Preparation
    ↓
AI Career Assistant
    ↓
Application Tracking
```

FastAPI automatically provides interactive API documentation through:

```text
/docs
```

---

# Main User Journey

```text
Register / Login
       ↓
Create Career Profile
       ↓
Upload Resume
       ↓
Resume Analysis
       ↓
View Extracted Skills
       ↓
Explore Recommended Internships
       ↓
Check Skill Gaps
       ↓
Improve Resume / Generate Cover Letter
       ↓
Track Applications
       ↓
Prepare for Interviews
       ↓
Use AI Career Assistant
```

---

# Key Objectives

CareerPilot aims to:

- Simplify internship discovery for students.
- Analyze resumes using AI.
- Match students with relevant internship opportunities.
- Identify missing skills for desired roles.
- Generate personalized career guidance.
- Improve interview preparation.
- Help students manage internship applications.
- Provide an integrated career preparation platform.

---

# Future Enhancements

Possible future improvements include:

- Real-time internship data integration
- Advanced recommendation algorithms
- Job application automation
- More detailed compatibility scoring
- Interview performance analysis
- Voice-based interview practice
- More AI-powered career insights
- Mobile application
- Personalized learning recommendations
- Advanced analytics dashboard

---

# Why CareerPilot?

Students often use multiple platforms for:

```text
Resume Building
      +
Internship Search
      +
Skill Development
      +
Interview Preparation
      +
Application Tracking
```

CareerPilot brings these activities together into one platform.

The goal is to create a more personalized and AI-assisted internship preparation journey for students.

---

# Project Status

CareerPilot is developed as an AI-powered internship matching and interview preparation platform using modern web development, semantic search, vector retrieval, and generative AI technologies.

---

# Author

**Manisha Choudhary**


---

# License

This project is licensed under the MIT License.


