import { useEffect, useRef, useState } from "react";
import { NavLink } from "react-router-dom";
import ReactMarkdown from "react-markdown";
import { api } from "./api";

// ---------------------------------------------------------------------------
// AI Interview Preparation Agent
// Uses the parsed resume saved by the main Resume page.
// ---------------------------------------------------------------------------

const QUICK_PROMPTS = [
  {
    label: "Which role fits me?",
    text: "Based on my resume, which role or internship should I apply for, and why?"
  },
  {
    label: "Strongest skills",
    text: "What are my strongest technical skills based on my resume?"
  },
  {
    label: "Technical questions",
    text: "Generate technical interview questions for the role that best fits my resume."
  },
  {
    label: "HR questions",
    text: "Generate common HR/behavioral interview questions for this role, with answer guidance."
  },
  {
    label: "Prep roadmap",
    text: "Create a personalized interview preparation roadmap and topics to prepare for this role."
  },
  {
    label: "Learning path",
    text: "Suggest a personalized learning path and resources to strengthen my weak areas."
  }
];

function ContextBanner({ context, loading }) {
  if (loading) {
    return (
      <div className="context-banner">
        <span className="spinner" />
        <div>
          <strong>Checking your resume context...</strong>
        </div>
      </div>
    );
  }

  if (!context || !context.resume_loaded) {
    return (
      <div className="context-banner missing">
        <span className="context-dot" />

        <div>
          <strong>No resume context loaded</strong>

          <p>
            Upload and parse a resume to get personalized role
            recommendations and interview preparation.
          </p>
        </div>

        <NavLink className="secondary-button" to="/resume">
          Upload resume →
        </NavLink>
      </div>
    );
  }

  return (
    <div className="context-banner loaded">
      <span className="context-dot on" />

      <div>
        <strong>
          Resume context loaded — {context.name || "Candidate"}
        </strong>

        <p>
          {context.current_job_title || "Candidate profile"} ·{" "}
          {context.filename}
        </p>

        {context.top_skills?.length > 0 && (
          <div className="tag-cloud" style={{ marginTop: 8 }}>
            {context.top_skills.map((skill) => (
              <span key={skill}>{skill}</span>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}

/*
 * IMPORTANT:
 *
 * ResumePage stores the successfully parsed resume in:
 *
 *     localStorage["ai_resume"]
 *
 * The old Preparation Agent was looking only for:
 *
 *     localStorage["activeInterviewPrepResume"]
 *
 * which was never being created.
 *
 * We now use ai_resume as the primary source.
 *
 * The old key is kept as a fallback so existing sessions/workflows
 * do not break.
 */
function getActiveResumeId() {
  try {
    // First use the resume selected specifically for interview preparation,
    // if one exists.
    const activePrepResume = localStorage.getItem(
      "activeInterviewPrepResume"
    );

    if (activePrepResume) {
      const parsed = JSON.parse(activePrepResume);

      if (parsed?.resume_id) {
        return parsed.resume_id;
      }

      if (parsed?.id) {
        return parsed.id;
      }
    }

    // Main source used by the Resume page.
    const savedResume = localStorage.getItem("ai_resume");

    if (savedResume) {
      const parsed = JSON.parse(savedResume);

      if (parsed?.resume_id) {
        return parsed.resume_id;
      }

      if (parsed?.id) {
        return parsed.id;
      }
    }

    return null;
  } catch (error) {
    console.error("Could not read saved resume:", error);
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

  // -------------------------------------------------------------------------
  // Load resume context
  // -------------------------------------------------------------------------

  useEffect(() => {
    const resumeId = getActiveResumeId();

    console.log("Interview Prep resume ID:", resumeId);

    api
      .getInterviewPrepContext(resumeId)
      .then((result) => {
        console.log("Interview Prep context:", result);
        setContext(result);
      })
      .catch((error) => {
        console.error("Interview Prep context error:", error);
        setError(error.message || "Could not load resume context.");
      })
      .finally(() => {
        setContextLoading(false);
      });
  }, []);

  // -------------------------------------------------------------------------
  // Load sessions
  // -------------------------------------------------------------------------

  function loadSessions(selectId) {
    api
      .listInterviewPrepSessions()
      .then((rows) => {
        setSessions(rows);

        if (selectId) {
          setActiveId(selectId);
        } else if (!activeId && rows.length > 0) {
          setActiveId(rows[0].id);
        }
      })
      .catch((error) => {
        setError(error.message || "Could not load preparation sessions.");
      });
  }

  useEffect(() => {
    loadSessions();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  // -------------------------------------------------------------------------
  // Active session
  // -------------------------------------------------------------------------

  useEffect(() => {
    setActiveSession(
      sessions.find((session) => session.id === activeId) || null
    );
  }, [sessions, activeId]);

  // -------------------------------------------------------------------------
  // Load messages
  // -------------------------------------------------------------------------

  useEffect(() => {
    if (!activeId) {
      setMessages([]);
      return;
    }

    setLoadingMessages(true);

    api
      .getInterviewPrepMessages(activeId)
      .then((rows) => {
        setMessages(rows);
      })
      .catch((error) => {
        setError(error.message || "Could not load messages.");
      })
      .finally(() => {
        setLoadingMessages(false);
      });
  }, [activeId]);

  // -------------------------------------------------------------------------
  // Scroll chat
  // -------------------------------------------------------------------------

  useEffect(() => {
    if (scrollRef.current) {
      scrollRef.current.scrollTop = scrollRef.current.scrollHeight;
    }
  }, [messages, sending]);

  // -------------------------------------------------------------------------
  // Start new preparation session
  // -------------------------------------------------------------------------

  async function startNewSession() {
    setError("");

    const resumeId = getActiveResumeId();

    if (!resumeId) {
      setError(
        "No parsed resume was found. Please upload and parse your resume first."
      );
      return;
    }

    try {
      console.log("Creating Interview Prep session with resume:", resumeId);

      const session = await api.createInterviewPrepSession(
        null,
        resumeId
      );

      setSessions((previous) => [session, ...previous]);
      setActiveId(session.id);
      setMessages([]);
    } catch (error) {
      console.error("Could not create Interview Prep session:", error);

      setError(
        error.message || "Could not create a preparation session."
      );
    }
  }

  // -------------------------------------------------------------------------
  // Delete session
  // -------------------------------------------------------------------------

  async function deleteSession(sessionId) {
    if (!window.confirm("Delete this preparation session?")) {
      return;
    }

    setError("");

    try {
      await api.deleteInterviewPrepSession(sessionId);

      setSessions((previous) =>
        previous.filter((session) => session.id !== sessionId)
      );

      if (activeId === sessionId) {
        setActiveId(null);
        setMessages([]);
      }
    } catch (error) {
      setError(
        error.message || "Failed to delete the session."
      );
    }
  }

  // -------------------------------------------------------------------------
  // Send message
  // -------------------------------------------------------------------------

  async function sendText(text) {
    const trimmed = (text || "").trim();

    if (!trimmed || sending) {
      return;
    }

    let sessionId = activeId;

    setError("");

    try {
      // If there is no session, create one automatically.
      if (!sessionId) {
        const resumeId = getActiveResumeId();

        if (!resumeId) {
          setError(
            "No parsed resume was found. Please upload and parse your resume first."
          );
          return;
        }

        console.log(
          "Creating automatic Interview Prep session with resume:",
          resumeId
        );

        const session = await api.createInterviewPrepSession(
          null,
          resumeId
        );

        setSessions((previous) => [session, ...previous]);

        sessionId = session.id;
        setActiveId(sessionId);
      }

      setInput("");
      setSending(true);

      const optimisticUser = {
        id: `pending-${Date.now()}`,
        role: "user",
        message: trimmed,
        created_at: new Date().toISOString()
      };

      setMessages((previous) => [
        ...previous,
        optimisticUser
      ]);

      const result = await api.sendInterviewPrepMessage(
        sessionId,
        trimmed
      );

      setMessages((previous) => [
        ...previous.filter(
          (message) => message.id !== optimisticUser.id
        ),
        result.user_message,
        result.assistant_message
      ]);

      loadSessions(sessionId);
    } catch (error) {
      console.error(
        "Interview Preparation Agent error:",
        error
      );

      setError(
        error.message ||
          "The Interview Preparation Agent could not respond. Please try again."
      );
    } finally {
      setSending(false);
    }
  }

  // -------------------------------------------------------------------------
  // Keyboard
  // -------------------------------------------------------------------------

  function handleKeyDown(event) {
    if (event.key === "Enter" && !event.shiftKey) {
      event.preventDefault();
      sendText(input);
    }
  }

  // -------------------------------------------------------------------------
  // Document upload
  // -------------------------------------------------------------------------

  async function handleDocumentPick(file) {
    if (!file) {
      return;
    }

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
        const resumeId = getActiveResumeId();

        if (!resumeId) {
          setDocError(
            "Please upload and parse your resume before uploading a document."
          );
          return;
        }

        const session = await api.createInterviewPrepSession(
          null,
          resumeId
        );

        setSessions((previous) => [
          session,
          ...previous
        ]);

        sessionId = session.id;
        setActiveId(sessionId);
      }

      const result =
        await api.uploadInterviewPrepDocument(
          sessionId,
          file
        );

      setSessions((previous) =>
        previous.map((session) =>
          session.id === sessionId
            ? {
                ...session,
                document_filename: result.filename,
                has_document: true
              }
            : session
        )
      );

      setActiveSession((previous) =>
        previous
          ? {
              ...previous,
              document_filename: result.filename,
              has_document: true
            }
          : previous
      );
    } catch (error) {
      console.error(
        "Interview Prep document upload error:",
        error
      );

      setDocError(
        error.message || "Could not read that document."
      );
    } finally {
      setUploadingDoc(false);

      if (fileInputRef.current) {
        fileInputRef.current.value = "";
      }
    }
  }

  // -------------------------------------------------------------------------
  // UI
  // -------------------------------------------------------------------------

  return (
    <div>
      <div className="page-header">
        <span className="eyebrow">
          AI INTERVIEW PREPARATION AGENT
        </span>

        <h1>Ace your next interview with confidence.</h1>

        <p>
          Get role-specific technical and HR questions,
          personalized answer guidance, and a smart
          preparation roadmap based on your resume and
          uploaded documents.
        </p>
      </div>

      <ContextBanner
        context={context}
        loading={contextLoading}
      />

      {error && (
        <div className="form-message error">
          {error}
        </div>
      )}

      <div className="chat-layout">
        {/* -----------------------------------------------------------------
            SIDEBAR
        ------------------------------------------------------------------ */}

        <div className="chat-sidebar">
          <button
            className="primary-button full"
            onClick={startNewSession}
          >
            + New preparation
          </button>

          <label
            className="doc-upload-chip"
            title="Upload a PDF or DOCX for document-based Q&A"
          >
            <input
              ref={fileInputRef}
              type="file"
              accept=".pdf,.docx"
              style={{ display: "none" }}
              onChange={(event) =>
                handleDocumentPick(
                  event.target.files?.[0]
                )
              }
              disabled={uploadingDoc}
            />

            {uploadingDoc
              ? "Uploading document..."
              : "📎 Upload PDF/DOCX for Q&A"}
          </label>

          {docError && (
            <p
              className="form-message error"
              style={{ fontSize: 11 }}
            >
              {docError}
            </p>
          )}

          {sessions.map((session) => (
            <div
              key={session.id}
              className={`chat-session-item ${
                session.id === activeId
                  ? "active"
                  : ""
              }`}
            >
              <button
                className="chat-session-title"
                onClick={() =>
                  setActiveId(session.id)
                }
              >
                {session.has_document
                  ? "📎 "
                  : ""}
                {session.title}
              </button>

              <button
                className="chat-session-delete"
                onClick={(event) => {
                  event.stopPropagation();
                  deleteSession(session.id);
                }}
                title="Delete session"
                aria-label={`Delete session: ${session.title}`}
              >
                🗑️
              </button>
            </div>
          ))}

          {sessions.length === 0 && (
            <p
              className="muted"
              style={{
                padding: "8px 12px",
                fontSize: 11
              }}
            >
              No previous sessions yet.
            </p>
          )}
        </div>

        {/* -----------------------------------------------------------------
            CHAT PANEL
        ------------------------------------------------------------------ */}

        <div className="chat-panel">
          <div className="chat-header">
            <div>
              <h3>
                Interview Preparation Agent
              </h3>

              <p>
                {activeSession?.document_filename
                  ? `Using your resume + "${activeSession.document_filename}" as context`
                  : "Grounded in your parsed resume · remembers this session's context"}
              </p>
            </div>
          </div>

          <div className="quick-prompts">
            {QUICK_PROMPTS.map((prompt) => (
              <button
                key={prompt.label}
                className="quick-prompt-chip"
                onClick={() =>
                  sendText(prompt.text)
                }
                disabled={sending}
              >
                {prompt.label}
              </button>
            ))}
          </div>

          <div
            className="chat-messages"
            ref={scrollRef}
          >
            {loadingMessages ? (
              <div className="chat-empty">
                <span className="spinner" />
              </div>
            ) : messages.length === 0 ? (
              <div className="chat-empty">
                <h2
                  style={{
                    fontSize: 16,
                    color: "var(--text)"
                  }}
                >
                  Your interview prep starts here
                </h2>

                <p>
                  Explore roles that match your
                  resume, practice targeted technical
                  and HR questions, or get personalized
                  guidance to strengthen your
                  preparation.
                </p>
              </div>
            ) : (
              messages.map((message) => (
                <div
                  className={`chat-bubble-row ${message.role}`}
                  key={message.id}
                >
                  <div>
                    <div className="chat-bubble">
                      {message.role === "assistant" ? (
                        <ReactMarkdown>
                          {message.message}
                        </ReactMarkdown>
                      ) : (
                        message.message
                      )}
                    </div>
                  </div>
                </div>
              ))
            )}

            {sending && (
              <div className="chat-bubble-row assistant">
                <div className="chat-bubble chat-typing">
                  <span />
                  <span />
                  <span />
                </div>
              </div>
            )}
          </div>

          <div className="chat-input-row">
            <textarea
              placeholder="Ask about roles, questions, roadmap, or your uploaded document..."
              value={input}
              onChange={(event) =>
                setInput(event.target.value)
              }
              onKeyDown={handleKeyDown}
              disabled={sending}
            />

            <button
              className="primary-button"
              onClick={() => sendText(input)}
              disabled={
                sending || !input.trim()
              }
            >
              {sending ? "Sending..." : "Send"}
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}
