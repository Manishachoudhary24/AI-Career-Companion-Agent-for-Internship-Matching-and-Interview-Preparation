# AI Career Companion - Product Knowledge Document

This document is the single source of truth for the AI Assistant chatbot.
It describes the AI Career Companion application exactly as implemented -
no invented features, technologies, or workflows. Each `##` section below
is treated as one retrievable chunk by the Retrieval-Augmented Generation
(RAG) pipeline, and its heading is shown to users as the "source" of an
answer.

## Product Overview

AI Career Companion is an AI-powered internship and career-preparation
web application. It helps students and early-career job seekers go from a
raw resume to a set of concrete next steps: a structured understanding of
their own background, a shortlist of internships that genuinely fit their
skills, a tailored cover letter, and a persistent career profile they
control. The problem it solves is that manually reading dozens of
internship postings and hand-tailoring applications to each one is slow
and error-prone; this product automates the matching and drafting work
while keeping the user in control of their own profile data. The primary
target users are students and recent graduates searching for internships.
The main objectives of the product are: (1) turn an uploaded resume into
structured, usable data, (2) let the user maintain their own permanent
career profile independently of any one resume, (3) recommend internships
ranked by genuine skill fit using semantic search, (4) let users apply to
internships without leaving the app, and (5) help users understand and
use the product itself through a built-in AI Assistant.

## Authentication

Users register with a full name, email, password, and optional phone
number, and log in with email + password. The backend issues a JWT access
token (python-jose) on login; the frontend stores it in the browser and
attaches it as a Bearer token on every protected request. Logging out
revokes the current token by recording its JWT id (jti) in a
token-blacklist table, so a logged-out token cannot be reused even if the
browser still has a copy. A forgot-password / reset-password flow issues a
short-lived reset token. Passwords are hashed with bcrypt (never stored in
plain text). Every protected API endpoint depends on `get_current_user`,
which decodes the JWT, checks the blacklist, and loads the active user
from the database - so ownership of chat sessions, applications, resumes,
and profile data is always verified on the backend, not just hidden in the
UI.

## Dashboard

The Dashboard is the landing page after login. It shows a personalized
greeting, a shortcut to upload or analyze a resume, quick stats (indexed
internship count, the matching engine used, the embedding model, and the
LLM provider), a four-step "resume to opportunity" workflow explainer, and
- if a resume has already been parsed in the current browser session - a
mini card linking straight to that resume's matches.

## Resume Upload

Users upload a resume as a PDF or DOCX file (up to 10 MB) from the Resume
page, by dragging a file onto the dropzone or browsing for one. The file
is stored on disk under the backend's `uploads/` directory with a
generated UUID filename, and a `resumes` database row is created holding
the original filename, file type, storage path, and the extracted raw
text, linked to the uploading user.

## Resume Parsing

Parsing is a hybrid pipeline combining two independent extraction passes
that are then merged into one structured record:

1. Text extraction - PyMuPDF for PDF files, python-docx for DOCX files -
   produces the resume's raw text.
2. Regex extraction - fast, deterministic pattern matching pulls out
   fields that have a reliable format: email addresses, phone numbers, and
   profile links (LinkedIn, GitHub, portfolio, Twitter).
3. LLM extraction - the raw resume text is sent to Groq's LLM API (via
   LangChain's Groq integration) with a prompt asking for a structured
   JSON extraction of everything else: professional summary, skills,
   education, work experience, internships, projects, certifications,
   publications, achievements, languages, and total years of experience.
4. Merge - the regex output and the LLM output are merged into one
   `ParsedResumeData` record, with the regex result treated as the source
   of truth for structured contact fields and the LLM result treated as
   the source of truth for everything contextual.

The resume, the regex JSON, the LLM JSON, and the final merged JSON are
all stored in the database (in the `resumes` and `parsed_resumes` tables),
so the raw inputs to a parse remain inspectable even after merging.

## Parsed Resumes

The Parsed Resumes page lists every resume a user has uploaded, most
recent first, showing the filename, the upload date/time, and the
internal resume ID, so a user can tell multiple uploads apart. Each entry
has a "Reuse" action, which sets that resume as the active resume for
internship matching and cover-letter generation, and a "Parse again"
action, which re-runs the same hybrid Regex + LLM pipeline against the
already-stored file (no re-upload needed) and creates a fresh parsed
result. This feature reuses the existing `resumes` / `parsed_resumes`
database tables - it does not introduce a second resume storage system.

## Career Profile

The Career Profile is a separate concept from a parsed resume: it is a
permanent, user-managed record of someone's career information, stored in
its own `user_profiles` table as a JSON document per user. It is not
auto-populated from an uploaded resume and is never silently overwritten
by resume parsing - the user must explicitly type in or edit their own
personal details, skills, education, experience, projects, and
achievements. This keeps "what my resume said last time I parsed it" and
"what I say about my career today" as two independent, non-conflicting
sources of truth.

## Personal Details

A free-text section of the Career Profile covering full name, email,
phone number, address, LinkedIn, GitHub, and portfolio website. Saving
this section also updates the corresponding fields on the user's account
record where applicable (name and phone number).

## Skills

A simple list of skill tags the user adds to and removes from directly.
Skills are stored as plain strings in the Career Profile's JSON document.

## Education

A list of education entries (degree, institution, field of study, start
and end dates, grade, location) that the user adds, edits, and deletes
directly on the Career Profile page.

## Experience

A list of work/internship experience entries the user maintains manually.
This section intentionally uses the same flexible entry shape the resume
parser produces (job title, company, dates, responsibilities), so
experience the user typed in and experience they once accepted from a
resume look and behave the same way, without the profile auto-merging new
resume data on top of it later.

## Projects

A list of project entries (name, description, technologies used) the user
adds, edits, and deletes on the Career Profile page.

## Achievements

A list of achievement/award entries (name, description) the user adds,
edits, and deletes on the Career Profile page.

## Custom Profile Sections

If the built-in sections (personal details, education, skills, experience,
projects, achievements) don't cover something a user wants on their
profile, the "+ Add section" button lets them create an arbitrarily
titled section with free-text content (for example "Certifications",
"Publications", or "Volunteering"). Custom sections are stored alongside
the built-in ones in the same profile JSON document and are fully
editable and deletable.

## Profile Photo

Users upload a profile photo (PNG, JPG, JPEG, or WEBP) from the Career
Profile page. Before saving, the frontend shows an interactive circular
cropper (react-easy-crop) with pan and zoom controls; only the cropped
region is uploaded, as a JPEG. The photo is stored on disk under
`profile_photos/`, keyed by user ID, and served back via a dedicated
`/profile/photo/{user_id}` endpoint.

## Internship Listing

The Internships page shows the full synthetic internship catalog (role
title, company, domain, location, mode, duration, stipend, required and
preferred skills, and a description), loaded from a JSON dataset on the
backend. It supports free-text search and filtering by domain. Browsing
the catalog does not require a parsed resume.

## Internship Matching

Internship matching is a Retrieval-Augmented Generation pipeline built on
a FAISS vector index. Every internship posting is embedded (using a local
sentence-transformers model, `all-MiniLM-L6-v2`, so no external API call
or cost is needed for embedding) and stored in a FAISS index at
`app/data/faiss_internship_index/`. When a user requests matches, their
most recently, successfully parsed resume is used as the query: its
skills, education, and project data are flattened into a query profile,
embedded with the same model, and compared against the internship index
using vector similarity search. Results are then re-ranked with a
weighted composite score (skill overlap, semantic similarity, education
fit, and location fit), and each match reports a match percentage, a match
label (Perfect / Strong / Partial / Weak Match), the matched skills, and
the skill gaps. If Groq is configured, a short natural-language summary of
the match set is also generated. If a user has multiple parsed resumes,
matching always uses the latest one - the manually maintained Career
Profile is not used as the matching input, so a user editing their profile
does not change their internship matches.

## Applied Internships

Clicking "Apply Now" on an internship does not redirect to Google or any
external site. Instead, the backend records an application - user ID,
internship ID, role title, company, applied date, and status - in the
`applied_internships` table, and the button switches from "Apply Now" to
"Applied". A unique constraint on (user, internship) prevents duplicate
applications: re-clicking Apply on an already-applied internship simply
confirms it's already applied rather than creating a second record. The
Applied Internships page lists every internship a user has applied to,
most recent first.

## Cover Letter Generation

From the Cover Letter page, a user picks one of their parsed resumes and
one internship posting. The backend sends only the parsed resume's
structured data and the selected internship's data to Groq's LLM, with an
explicit instruction not to invent skills, experience, dates, or company
facts, and asks for a complete, ready-to-send cover letter. The generated
letter is stored in the `cover_letters` table.

## Cover Letter History

Every generated cover letter is saved and listed on the Career Profile
page (role, company, and date), so a user can revisit past letters
without regenerating them.

## AI Assistant

The AI Assistant is an in-app chatbot reachable from the sidebar. It is a
Product Assistant, not a general-purpose chatbot: its job is to help users
understand and use AI Career Companion itself (what each feature does,
how resume parsing and internship matching work, how to apply to an
internship, and so on). It answers using Retrieval-Augmented Generation
over this Product Knowledge Document plus the recent conversation history
of the current chat session, and it is explicitly instructed not to
invent product facts it cannot find in either source. Users can start new
chat sessions, see a list of previous sessions, and continue any of them;
each session keeps its own message history, and one user's sessions are
never visible to another user.

## System Architecture

The overall request flow is: User -> React (Vite) frontend -> FastAPI
backend -> a service layer (resume parsing, internship matching, career
profile, cover-letter generation, and the AI Assistant's RAG pipeline) ->
PostgreSQL (via SQLAlchemy) for persistence, with Groq's LLM API called
for any generative step (resume field extraction, cover letters, match
summaries, and chatbot answers) and FAISS vector search used for both
internship matching and the AI Assistant's document retrieval.

## Internship Matching FAISS Index

`app/services/internship_index.py` builds and queries a FAISS index of
internship postings, embedded with a local Hugging Face sentence-
transformers model. It is rebuilt automatically on first startup if
missing, or manually via `python -m app.services.internship_index`.

## Product Knowledge FAISS Index

A second, separate FAISS index - stored at
`app/data/faiss_product_knowledge/`, entirely independent of the
internship-matching index above - holds the embedded chunks of this
Product Knowledge Document. It is built by chunking this document by
section, embedding each chunk with the same local sentence-transformers
model used for internship matching, and is what the AI Assistant searches
before every answer. Keeping the two indices separate means rebuilding
one (for example, after this document is edited) never touches or
corrupts the other.

## RAG Flow for the AI Assistant

1. This Product Knowledge Document is split into chunks (one per `##`
   section).
2. Each chunk is embedded and stored in the Product Knowledge FAISS index.
3. When a user asks a question, the question is embedded with the same
   model.
4. The most relevant chunks are retrieved from the FAISS index by vector
   similarity.
5. The current chat session's recent message history is retrieved from
   the database.
6. A prompt combining the system instructions, the retrieved chunks, the
   recent conversation history, and the current question is sent to
   Groq's LLM.
7. The LLM's answer is returned to the user, saved to the database, and
   (where practical) shown alongside the names of the knowledge-document
   sections it drew on.

## Conversation Memory

Within a chat session, the AI Assistant resolves references to earlier
turns (for example, understanding "it" or "that" from the previous
message) because the recent message history for that session is included
in every prompt sent to the LLM, alongside the retrieved documentation
context.

## Conversation Storage

Chat sessions and messages are stored in the same PostgreSQL database as
everything else, in two tables: `chat_sessions` (id, user, title, created
and updated timestamps) and `chat_messages` (id, session, user, role -
user or assistant -, message text, cited sources, and timestamp). No
separate database is used for chat data.

## User and Session Isolation

Every chat session belongs to exactly one user, and every chat API
endpoint checks that the requesting user owns the session before
returning or appending to it. A user can never retrieve another user's
sessions or messages, and each session's conversation memory only ever
includes messages from that same session.

## Technology Stack

Frontend: React with Vite as the build tool and dev server, React Router
for client-side routing, and `react-easy-crop` for the profile-photo
cropper - chosen for a fast development loop and a component model well
suited to a multi-page authenticated app.

Backend: FastAPI, chosen for its speed, automatic OpenAPI/Swagger docs,
and native async support; SQLAlchemy as the ORM against PostgreSQL for
durable, relational storage of users, resumes, profiles, applications and
chat data.

Authentication: JWT access tokens (python-jose) with bcrypt password
hashing (passlib/bcrypt), chosen for a stateless, scalable auth model with
a revocation list for logout.

Resume parsing: PyMuPDF (PDF) and python-docx (DOCX) for text extraction,
plain Python regular expressions for deterministic contact-field
extraction, and LangChain's Groq integration for LLM-based structured
extraction of everything else - a hybrid approach chosen because regex is
reliable for well-formatted fields but cannot understand free-form resume
prose, which the LLM handles well.

Internship matching and AI Assistant retrieval: FAISS for fast vector
similarity search, and a local Hugging Face sentence-transformers model
(`all-MiniLM-L6-v2`) for embeddings, chosen so semantic search runs
locally with no per-query API cost - the same embedding approach is reused
for the AI Assistant's Product Knowledge Document index rather than
introducing a second vector database.

LLM: Groq's LLM API (used both directly via the `groq` Python SDK and via
LangChain's Groq integration), chosen for low-latency inference. The same
Groq API key and model configuration (`GROQ_API_KEY`, `GROQ_MODEL`) is
reused for resume extraction, cover-letter generation, match summaries,
and the AI Assistant - there is no second, separate LLM configuration.

## How to Use the Product: Register and Log In

Open the app, choose "Create one" on the login page, fill in full name,
email, phone number, and a password with at least one letter and one
digit, and submit. After registering, log in with the same email and
password to receive a session.

## How to Use the Product: Upload and Parse a Resume

Go to the Resume page, drag a PDF or DOCX file onto the dropzone (or click
to browse), then click "Parse resume & continue". The parsed result
appears on the same page once processing finishes.

## How to Use the Product: View a Parsed Resume

Open the Parsed Resumes page from the sidebar to see every resume ever
uploaded, with filename, upload date, and resume ID. Use "Reuse" to make
an older resume active again, or "Parse again" to re-run extraction on it.

## How to Use the Product: Maintain the Career Profile

Open the Profile page from the sidebar. Edit personal details and click
"Save changes"; use each section's add/edit/delete controls for education,
skills, experience, projects, and achievements; use "+ Add section" for
anything not already covered.

## How to Use the Product: Check Internship Matches

Upload and parse a resume first, then open "My Matches" to see internships
ranked against that resume, with a match percentage, matched skills, and
skill gaps for each one.

## How to Use the Product: Apply to an Internship

From the Internships page or My Matches page, click "Apply Now" on a
posting. The button switches to "Applied" immediately, and the
application appears on the Applied Internships page - no external site is
opened.

## How to Use the Product: Generate a Cover Letter

Open the Cover Letter page, choose a parsed resume and an internship, then
click "Generate Cover Letter". The letter can be copied, and is also saved
to Cover Letter history on the Profile page.

## How to Use the Product: Use the AI Assistant

Open "AI Assistant" from the sidebar, click "+ New Chat" (or continue a
previous chat from the list), and type a question about the product - for
example how resume parsing works or how to apply to an internship. The
assistant answers using this Product Knowledge Document and the current
chat's history.
