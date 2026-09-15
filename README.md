\# CareerPilot



\### AI-Powered Internship Matching and Career Preparation Platform



CareerPilot is an AI-powered career companion designed to help students discover relevant internship opportunities, understand their skill profile, improve applications, and prepare for interviews from a single platform.



The system combines resume parsing, semantic search, vector-based internship retrieval, AI-assisted analysis, application tracking, cover-letter generation, and interview preparation to create a personalized career workflow.



\---



\## Overview



Finding the right internship often requires students to search across multiple platforms, repeatedly modify their resumes, identify missing skills, prepare for interviews, and track applications separately.



CareerPilot brings these activities together into one platform.



A student can:



\- Create and manage a career profile

\- Upload a PDF or DOCX resume

\- Extract structured information from the resume

\- Discover internships using semantic matching

\- View personalized internship matches

\- Identify relevant skill gaps

\- Generate tailored cover letters

\- Track internship applications

\- Prepare for interviews using a dedicated AI preparation agent

\- Interact with an AI career assistant

\- Maintain multiple parsed resumes and reuse them for career workflows



\---



\## Key Features



\### 1. Resume Intelligence



Upload a PDF or DOCX resume and convert it into structured career information.



The resume workflow can extract information such as:



\- Personal details

\- Professional summary

\- Technical skills

\- Education

\- Work experience

\- Projects

\- Certifications

\- Languages

\- Achievements



Parsed resume information can then be used by the matching and career-preparation workflows.



\---



\### 2. Internship Discovery



CareerPilot provides an internship catalog that can be searched and filtered by users.



Users can explore opportunities based on information such as:



\- Role

\- Company

\- Domain

\- Location

\- Work mode

\- Required skills

\- Internship duration



\---



\### 3. AI-Powered Internship Matching



CareerPilot uses semantic vector search to identify internships that best match a student's resume.



The matching pipeline combines:



\- Resume information

\- Technical skills

\- Education

\- Experience

\- Semantic similarity

\- Location

\- Internship requirements



FAISS is used for vector retrieval, while sentence-transformer embeddings are used to represent resume and internship information.



\---



\### 4. Skill Gap Analysis



CareerPilot helps students understand the difference between their current skills and the skills expected for a target role.



The analysis can be used to identify:



\- Existing skills

\- Missing skills

\- Areas for improvement

\- Priority learning areas



This helps students create a more focused preparation plan.



\---



\### 5. Cover Letter Generation



CareerPilot can generate a personalized cover letter based on the student's resume/profile and a selected internship opportunity.



This helps users create application-specific content instead of relying on a generic cover letter.



\---



\### 6. Interview Preparation Agent



The Interview Preparation Agent provides role-focused interview preparation.



It can help students with:



\- Technical interview questions

\- HR questions

\- Role-specific preparation

\- Answer guidance

\- Interview strategies

\- Preparation roadmaps

\- Learning topics



The active resume can be used as context so that preparation is relevant to the student's own background.



\---



\### 7. AI Career Assistant



CareerPilot includes an AI-powered conversational assistant that provides guidance related to the platform and career workflow.



The assistant uses retrieval-augmented generation (RAG) with the application's product knowledge base.



It supports:



\- Conversational sessions

\- Chat history

\- New conversations

\- Message persistence

\- Product-related questions

\- Career workflow guidance



\---



\### 8. Application Tracking



Students can apply to internships directly from the platform and view their application history.



The application tracker stores information such as:



\- Internship

\- Company

\- Application date

\- Application status



\---



\### 9. Career Profile



Students can maintain a dedicated career profile containing information such as:



\- Personal details

\- Skills

\- Education

\- Experience

\- Target roles

\- Preferred domains

\- Preferred locations

\- Work-mode preferences

\- Professional links

\- Profile photo



\---



\## System Workflow



```text

&#x20;                ┌─────────────────────┐

&#x20;                │    Student Profile   │

&#x20;                └──────────┬──────────┘

&#x20;                           │

&#x20;                           ▼

&#x20;                ┌─────────────────────┐

&#x20;                │    Resume Upload    │

&#x20;                └──────────┬──────────┘

&#x20;                           │

&#x20;                           ▼

&#x20;                ┌─────────────────────┐

&#x20;                │   Resume Parsing    │

&#x20;                │  PDF / DOCX → Data  │

&#x20;                └──────────┬──────────┘

&#x20;                           │

&#x20;                           ▼

&#x20;                ┌─────────────────────┐

&#x20;                │ Semantic Embeddings │

&#x20;                │  SentenceTransform  │

&#x20;                └──────────┬──────────┘

&#x20;                           │

&#x20;                           ▼

&#x20;                ┌─────────────────────┐

&#x20;                │   FAISS Retrieval   │

&#x20;                │ Internship Matching │

&#x20;                └──────────┬──────────┘

&#x20;                           │

&#x20;                           ▼

&#x20;                ┌─────────────────────┐

&#x20;                │ Personalized Roles  │

&#x20;                └──────────┬──────────┘

&#x20;                           │

&#x20;             ┌─────────────┼─────────────┐

&#x20;             ▼             ▼             ▼

&#x20;      Cover Letters   Skill Analysis   Interview Prep

&#x20;             │             │             │

&#x20;             └─────────────┼─────────────┘

&#x20;                           ▼

&#x20;                ┌─────────────────────┐

&#x20;                │ Application Tracker│

&#x20;                └─────────────────────┘

Technology Stack

Frontend

React

JavaScript

Vite

React Router

CSS

Lucide React

Backend

Python

FastAPI

SQLAlchemy

Pydantic

JWT Authentication

Database

PostgreSQL

AI / Machine Learning

Groq

LangChain

Sentence Transformers

Hugging Face

FAISS

Retrieval-Augmented Generation (RAG)

Document Processing

PyMuPDF

python-docx

Architecture

&#x20;                        CareerPilot

&#x20;                             │

&#x20;            ┌────────────────┴────────────────┐

&#x20;            │                                 │

&#x20;            ▼                                 ▼

&#x20;     React / Vite Frontend              FastAPI Backend

&#x20;            │                                 │

&#x20;            │                         ┌───────┼────────┐

&#x20;            │                         │       │        │

&#x20;            │                         ▼       ▼        ▼

&#x20;            │                     PostgreSQL FAISS    Groq

&#x20;            │                             │       │

&#x20;            │                             │       ▼

&#x20;            │                             │   AI / RAG

&#x20;            │                             │

&#x20;            └─────────────────────────────┘

Project Structure

AI\_Career\_Pilot/

│

├── app/

│   ├── models/

│   ├── routes/

│   ├── services/

│   ├── data/

│   ├── main.py

│   └── config.py

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

│   ├── package.json

│   └── vite.config.js

│

├── docs/

├── screenshots of app/

├── requirements.txt

├── .env.example

├── postman\_collection.json

├── rag\_test\_results.txt

└── test\_matching\_scenarios.py

Requirements



Make sure the following are installed:



Python 3.12+

Node.js

npm

PostgreSQL

Installation

1\. Clone the repository

git clone https://github.com/Manishachoudhary24/AI-Career-Companion-Agent-for-Internship-Matching-and-Interview-Preparation.git

cd AI-Career-Companion-Agent-for-Internship-Matching-and-Interview-Preparation

2\. Backend Setup



Create a Python virtual environment:



Windows

python -m venv venv



Activate it:



.\\venv\\Scripts\\Activate.ps1



Install the dependencies:



pip install -r requirements.txt

3\. PostgreSQL Setup



Create a PostgreSQL database for the project.



Example:



Database Name:

ai\_career\_companion



The application uses the DATABASE\_URL environment variable to connect to PostgreSQL.



4\. Environment Configuration



Create a .env file in the project root.



You can start from:



.env.example



Example configuration:



DATABASE\_URL=postgresql://postgres:YOUR\_PASSWORD@localhost:5432/ai\_career\_companion



JWT\_SECRET\_KEY=change\_this\_to\_a\_long\_random\_secret\_string

JWT\_ALGORITHM=HS256



ACCESS\_TOKEN\_EXPIRE\_MINUTES=60

RESET\_TOKEN\_EXPIRE\_MINUTES=30



GROQ\_API\_KEY=your\_groq\_api\_key

GROQ\_MODEL=your\_groq\_model



LLM\_TEMPERATURE=0.0

LLM\_TIMEOUT\_SECONDS=60



MAX\_UPLOAD\_MB=10



UPLOAD\_DIR=uploads

PARSED\_DIR=parsed



EMBEDDING\_MODEL=sentence-transformers/all-MiniLM-L6-v2



INTERNSHIP\_DATA\_PATH=app/data/internships.json

INTERNSHIP\_INDEX\_DIR=app/data/faiss\_internship\_index

AUTO\_BUILD\_INTERNSHIP\_INDEX=true



PRODUCT\_KNOWLEDGE\_DOC\_PATH=app/data/product\_knowledge/product\_knowledge.md

PRODUCT\_KNOWLEDGE\_INDEX\_DIR=app/data/faiss\_product\_knowledge

AUTO\_BUILD\_PRODUCT\_KNOWLEDGE\_INDEX=true



CHAT\_HISTORY\_LIMIT=12

CHAT\_RAG\_TOP\_K=4



APP\_ENV=development

LOG\_LEVEL=INFO



CORS\_ORIGINS=\*



Never commit your .env file or expose your API keys publicly.



5\. Start the Backend



From the project root:



python -m uvicorn app.main:app --reload



The backend should be available at:



http://127.0.0.1:8000



API documentation:



http://127.0.0.1:8000/docs

6\. Frontend Setup



Open another terminal.



Move to the frontend directory:



cd frontend



Install frontend dependencies:



npm install



Start the development server:



npm run dev



The frontend should be available at:



http://localhost:5173

Application Flow

Register / Login

&#x20;      │

&#x20;      ▼

Career Profile

&#x20;      │

&#x20;      ▼

Upload Resume

&#x20;      │

&#x20;      ▼

AI Resume Parsing

&#x20;      │

&#x20;      ▼

Personalized Internship Matching

&#x20;      │

&#x20;      ├──────────────► Skill Gap Analysis

&#x20;      │

&#x20;      ├──────────────► Cover Letter Generation

&#x20;      │

&#x20;      ├──────────────► Interview Preparation Agent

&#x20;      │

&#x20;      └──────────────► Application Tracking

&#x20;                            

&#x20;                     AI Career Assistant

&#x20;                             │

&#x20;                             ▼

&#x20;                      Career Guidance

API Modules



The backend provides functionality for:



Authentication

User registration and login

Password management

Career profile management

Resume upload and parsing

Parsed resume management

Internship retrieval

Internship matching

Internship applications

Cover-letter generation

AI chat sessions

AI chat messages

Interview preparation sessions

Interview preparation document upload

AI Matching Pipeline



CareerPilot uses a semantic matching pipeline rather than relying only on keyword matching.



Resume

&#x20; │

&#x20; ▼

Resume Parsing

&#x20; │

&#x20; ▼

Structured Career Data

&#x20; │

&#x20; ▼

Text Embeddings

&#x20; │

&#x20; ▼

FAISS Vector Search

&#x20; │

&#x20; ▼

Candidate Internship Retrieval

&#x20; │

&#x20; ▼

Additional Matching Factors

&#x20; │

&#x20; ├── Skills

&#x20; ├── Education

&#x20; ├── Experience

&#x20; └── Location

&#x20; │

&#x20; ▼

Ranked Internship Results

RAG Assistant



The AI assistant uses a retrieval-based architecture.



User Question

&#x20;     │

&#x20;     ▼

Embedding / Retrieval

&#x20;     │

&#x20;     ▼

Product Knowledge Vector Store

&#x20;     │

&#x20;     ▼

Relevant Context

&#x20;     │

&#x20;     ▼

Groq LLM

&#x20;     │

&#x20;     ▼

AI Response



This allows the assistant to use relevant application knowledge when responding to supported product-related questions.



Security



The application includes:



JWT-based authentication

Password hashing

Authenticated API requests

Protected user-specific resources

Environment-based secret configuration



Sensitive values such as API keys and database passwords should always remain in .env.



Testing



The repository includes resources for testing the matching functionality:



test\_matching\_scenarios.py

rag\_test\_results.txt



API endpoints can also be tested using the included:



postman\_collection.json

Future Enhancements



Potential future improvements include:



Real-time internship data ingestion

More advanced recommendation models

Improved skill-gap learning roadmaps

Interview performance analytics

Application reminders and notifications

More comprehensive ATS analysis

Role-specific learning recommendations

Deployment to a production cloud environment

Project Goals



CareerPilot is designed around a simple goal:



Help students move from a resume to a realistic career opportunity with less friction.



Instead of treating resume building, opportunity discovery, skill development, applications, and interview preparation as separate tasks, CareerPilot connects them into one workflow.



License



This project is licensed under the MIT License.



Author



Manisha Choudhary



AI-powered Career Platform for Internship Discovery, Matching and Interview Preparation.

