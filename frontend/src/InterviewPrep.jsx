import { useEffect, useRef, useState } from "react";
import { NavLink } from "react-router-dom";
import ReactMarkdown from "react-markdown";
import { api } from "./api";

// ---------------------------------------------------------------------------
// AI Interview Preparation Agent - dedicated navbar page/workspace.
//
// This is a SEPARATE assistant from the floating "AI Product Assistant"
// (see ChatAssistant.jsx / app/routers/chat.py). It has its own sessions,
// its own messages table, and its own backend endpoints under
// /interview-prep/*. It is never merged with the product assistant.
// ---------------------------------------------------------------------------

const QUICK_PROMPTS = [
  { label: "Which role fits me?", text: "Based on my resume, which role or internship should I apply for, and why?" },
  { label: "Strongest skills", text: "What are my strongest technical skills based on my resume?" },
  { label: "Technical questions", text: "Generate technical interview questions for the role that best fits my resume." },
  { label: "HR questions", text: "Generate common HR/behavioral interview questions for this role, with answer guidance." },
  { label: "Prep roadmap", text: "Create a personalized interview preparation roadmap and topics to prepare for this role." },
  { label: "Learning path", text: "Suggest a personalized learning path and resources to strengthen my weak areas." }
];

function ContextBanner({ context, loading }) {
  if (loading) {
    return (
      <div className="context-banner">
        <span className="spinner" />
        <div><strong>Checking your resume context...</strong></div>
      </div>
    );
  }

  if (!context || !context.resume_loaded) {
    return (
      <div className="context-banner missing">
        <span className="context-dot" />
        <div>
          <strong>No resume context loaded</strong>
          <p>Upload and parse a resume to get personalized role recommendations and interview prep. You can still ask general questions.</p>
        </div>
        <NavLink className="secondary-button" to="/resume">Upload resume →</NavLink>
      </div>
    );
  }

  return (
    <div className="context-banner loaded">
      <span className="context-dot on" />
      <div>
        <strong>Resume context loaded — {context.name || "Candidate"}</strong>
        <p>{context.current_job_title || "Candidate profile"} · {context.filename}</p>
        {context.top_skills?.length > 0 && (
          <div className="tag-cloud" style={{ marginTop: 8 }}>
            {context.top_skills.map((s) => <span key={s}>{s}</span>)}
          </div>
        )}
      </div>
    </div>
  );
}

function getActiveResumeId() {
  try {
    return (
      JSON.parse(
        localStorage.getItem("activeInterviewPrepResume")
      )?.resume_id || null
    );
  } catch {
    return null;
  }
}

export default function InterviewPreparationPage() {
  const [context, setContext] = useState(null);
  const [contextLoading, setContextLoading] = useState(true);

  const [sessions, setSessions] = useState([]);
  const [activeId, setActiveId] = useState(null);
  const [activeSession, setActiveSession] = useState(null);
  const [messages, setMessages] = useState([]);
  const [input, setInput] = useState("");
  const [sending, setSending] = useState(false);
  const [loadingMessages, setLoadingMessages] = useState(false);
  const [error, setError] = useState("");

  const [uploadingDoc, setUploadingDoc] = useState(false);
  const [docError, setDocError] = useState("");

  const scrollRef = useRef(null);
  const fileInputRef = useRef(null);

  useEffect(() => {
    const saved = localStorage.getItem("activeInterviewPrepResume");

    let resumeId = null;

    if (saved) {
      try {
        resumeId = JSON.parse(saved)?.resume_id || null;
      } catch {
        resumeId = null;
      }
    }

    api.getInterviewPrepContext(resumeId)
      .then(setContext)
      .catch(() => {})
      .finally(() => setContextLoading(false));
  }, []);

  function loadSessions(selectId) {
    api.listInterviewPrepSessions()
      .then((rows) => {
        setSessions(rows);
        if (selectId) {
          setActiveId(selectId);
        } else if (!activeId && rows.length > 0) {
          setActiveId(rows[0].id);
        }
      })
      .catch((e) => setError(e.message));
  }

  useEffect(() => { loadSessions(); }, []); // eslint-disable-line react-hooks/exhaustive-deps

  useEffect(() => {
    setActiveSession(sessions.find((s) => s.id === activeId) || null);
  }, [sessions, activeId]);

  useEffect(() => {
    if (!activeId) { setMessages([]); return; }
    setLoadingMessages(true);
    api.getInterviewPrepMessages(activeId)
      .then(setMessages)
      .catch((e) => setError(e.message))
      .finally(() => setLoadingMessages(false));
  }, [activeId]);

  useEffect(() => {
    if (scrollRef.current) scrollRef.current.scrollTop = scrollRef.current.scrollHeight;
  }, [messages, sending]);

  async function startNewSession() {
    setError("");
    try {
      const session = await api.createInterviewPrepSession(null, getActiveResumeId());
      setSessions((prev) => [session, ...prev]);
      setActiveId(session.id);
      setMessages([]);
    } catch (e) {
      setError(e.message);
    }
  }

  async function deleteSession(sessionId) {
    if (!window.confirm("Delete this preparation session?")) return;
    setError("");
    try {
      await api.deleteInterviewPrepSession(sessionId);
      setSessions((prev) => prev.filter((s) => s.id !== sessionId));
      if (activeId === sessionId) {
        setActiveId(null);
        setMessages([]);
      }
    } catch (e) {
      setError(e.message || "Failed to delete the session.");
    }
  }

  async function sendText(text) {
    const trimmed = (text || "").trim();
    if (!trimmed || sending) return;

    let sessionId = activeId;
    setError("");

    try {
      if (!sessionId) {
        const session = await api.createInterviewPrepSession(null, getActiveResumeId());
        setSessions((prev) => [session, ...prev]);
        sessionId = session.id;
        setActiveId(sessionId);
      }

      setInput("");
      setSending(true);
      const optimisticUser = { id: `pending-${Date.now()}`, role: "user", message: trimmed, created_at: new Date().toISOString() };
      setMessages((prev) => [...prev, optimisticUser]);

      const result = await api.sendInterviewPrepMessage(sessionId, trimmed);

      setMessages((prev) => [
        ...prev.filter((m) => m.id !== optimisticUser.id),
        result.user_message,
        result.assistant_message
      ]);
      loadSessions(sessionId);
    } catch (e) {
      setError(e.message || "The Interview Preparation Agent could not respond. Please try again.");
    } finally {
      setSending(false);
    }
  }

  function handleKeyDown(e) {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      sendText(input);
    }
  }

  async function handleDocumentPick(file) {
    if (!file) return;
    const valid = /\.(pdf|docx)$/i.test(file.name);
    if (!valid) {
      setDocError("Please choose a PDF or DOCX file.");
      return;
    }
    setDocError("");
    setUploadingDoc(true);
    try {
      let sessionId = activeId;
      if (!sessionId) {
        const session = await api.createInterviewPrepSession(null, getActiveResumeId());
        setSessions((prev) => [session, ...prev]);
        sessionId = session.id;
        setActiveId(sessionId);
      }
      const result = await api.uploadInterviewPrepDocument(sessionId, file);
      setSessions((prev) => prev.map((s) => (s.id === sessionId ? { ...s, document_filename: result.filename, has_document: true } : s)));
      setActiveSession((prev) => (prev ? { ...prev, document_filename: result.filename, has_document: true } : prev));
    } catch (e) {
      setDocError(e.message || "Could not read that document.");
    } finally {
      setUploadingDoc(false);
      if (fileInputRef.current) fileInputRef.current.value = "";
    }
  }

  return (
    <div>
      <div className="page-header">
        <span className="eyebrow">AI INTERVIEW PREPARATION AGENT</span>
        <h1>Ace your next interview with confidence.</h1>
        <p>Get role-specific technical and HR questions, personalized answer guidance, and a smart preparation roadmap based on your resume and uploaded documents.</p>
      </div>

      <ContextBanner context={context} loading={contextLoading} />

      {error && <div className="form-message error">{error}</div>}

      <div className="chat-layout">
        <div className="chat-sidebar">
          <button className="primary-button full" onClick={startNewSession}>+ New preparation</button>

          <label className="doc-upload-chip" title="Upload a PDF or DOCX for document-based Q&A">
            <input
              ref={fileInputRef}
              type="file"
              accept=".pdf,.docx"
              style={{ display: "none" }}
              onChange={(e) => handleDocumentPick(e.target.files?.[0])}
              disabled={uploadingDoc}
            />
            {uploadingDoc ? "Uploading document..." : "📎 Upload PDF/DOCX for Q&A"}
          </label>
          {docError && <p className="form-message error" style={{ fontSize: 11 }}>{docError}</p>}

          {sessions.map((s) => (
            <div key={s.id} className={`chat-session-item ${s.id === activeId ? "active" : ""}`}>
              <button className="chat-session-title" onClick={() => setActiveId(s.id)}>
                {s.has_document ? "📎 " : ""}{s.title}
              </button>
              <button
                className="chat-session-delete"
                onClick={(e) => { e.stopPropagation(); deleteSession(s.id); }}
                title="Delete session"
                aria-label={`Delete session: ${s.title}`}
              >
                🗑️
              </button>
            </div>
          ))}
          {sessions.length === 0 && <p className="muted" style={{ padding: "8px 12px", fontSize: 11 }}>No previous sessions yet.</p>}
        </div>

        <div className="chat-panel">
          <div className="chat-header">
            <div>
              <h3>Interview Preparation Agent</h3>
              <p>
                {activeSession?.document_filename
                  ? `Using your resume + "${activeSession.document_filename}" as context`
                  : "Grounded in your parsed resume · remembers this session's context"}
              </p>
            </div>
          </div>

          <div className="quick-prompts">
            {QUICK_PROMPTS.map((q) => (
              <button key={q.label} className="quick-prompt-chip" onClick={() => sendText(q.text)} disabled={sending}>
                {q.label}
              </button>
            ))}
          </div>

          <div className="chat-messages" ref={scrollRef}>
            {loadingMessages ? (
              <div className="chat-empty"><span className="spinner" /></div>
            ) : messages.length === 0 ? (
              <div className="chat-empty">
                <h2 style={{ fontSize: 16, color: "var(--text)" }}>Your interview prep starts here</h2>
                <p>Explore roles that match your resume, practice targeted technical and HR questions, or get personalized guidance to strengthen your preparation.</p>
              </div>
            ) : (
              messages.map((m) => (
                <div className={`chat-bubble-row ${m.role}`} key={m.id}>
                  <div>
                    <div className="chat-bubble">
                      {m.role === "assistant" ? <ReactMarkdown>{m.message}</ReactMarkdown> : m.message}
                    </div>
                  </div>
                </div>
              ))
            )}
            {sending && (
              <div className="chat-bubble-row assistant">
                <div className="chat-bubble chat-typing"><span /><span /><span /></div>
              </div>
            )}
          </div>

          <div className="chat-input-row">
            <textarea
              placeholder="Ask about roles, questions, roadmap, or your uploaded document..."
              value={input}
              onChange={(e) => setInput(e.target.value)}
              onKeyDown={handleKeyDown}
              disabled={sending}
            />
            <button className="primary-button" onClick={() => sendText(input)} disabled={sending || !input.trim()}>
              {sending ? "Sending..." : "Send"}
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}
