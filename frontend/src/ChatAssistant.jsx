import { useEffect, useRef, useState } from "react";
import ReactMarkdown from "react-markdown";
import { api } from "./api";

// ---------------------------------------------------------------------------
// Shared logic for the AI Assistant (RAG chatbot).
// This hook owns all session/message state and API calls. It is unchanged
// from the original AIAssistantPage implementation — only extracted so the
// same behavior can power either a full page or the floating widget.
// ---------------------------------------------------------------------------
function useChatAssistant() {
  const [sessions, setSessions] = useState([]);
  const [activeId, setActiveId] = useState(null);
  const [messages, setMessages] = useState([]);
  const [input, setInput] = useState("");
  const [sending, setSending] = useState(false);
  const [loadingMessages, setLoadingMessages] = useState(false);
  const [error, setError] = useState("");
  const scrollRef = useRef(null);

  function loadSessions(selectId) {
    api.listChatSessions()
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

  useEffect(() => { loadSessions(); }, []);

  useEffect(() => {
    if (!activeId) { setMessages([]); return; }
    setLoadingMessages(true);
    api.getChatMessages(activeId)
      .then(setMessages)
      .catch((e) => setError(e.message))
      .finally(() => setLoadingMessages(false));
  }, [activeId]);

  useEffect(() => {
    if (scrollRef.current) scrollRef.current.scrollTop = scrollRef.current.scrollHeight;
  }, [messages, sending]);

  async function startNewChat() {
    setError("");
    try {
      const session = await api.createChatSession();
      setSessions((prev) => [session, ...prev]);
      setActiveId(session.id);
      setMessages([]);
    } catch (e) {
      setError(e.message);
    }
  }

  async function deleteChat(sessionId) {
    if (!window.confirm("Are you sure you want to delete this chat?")) return;

    setError("");

    try {
      await api.deleteChatSession(sessionId);

      setSessions((prev) => prev.filter((s) => s.id !== sessionId));

      if (activeId === sessionId) {
        setActiveId(null);
        setMessages([]);
      }
    } catch (e) {
      setError(e.message || "Failed to delete the chat.");
    }
  }

  async function send() {
    const text = input.trim();
    if (!text || sending) return;

    let sessionId = activeId;
    setError("");

    try {
      if (!sessionId) {
        const session = await api.createChatSession();
        setSessions((prev) => [session, ...prev]);
        sessionId = session.id;
        setActiveId(sessionId);
      }

      setInput("");
      setSending(true);
      // Optimistically show the user's message immediately.
      const optimisticUser = { id: `pending-${Date.now()}`, role: "user", message: text, created_at: new Date().toISOString() };
      setMessages((prev) => [...prev, optimisticUser]);

      const result = await api.sendChatMessage(sessionId, text);

      setMessages((prev) => [
        ...prev.filter((m) => m.id !== optimisticUser.id),
        result.user_message,
        result.assistant_message
      ]);
      loadSessions(sessionId);
    } catch (e) {
      setError(e.message || "The AI Assistant could not respond. Please try again.");
    } finally {
      setSending(false);
    }
  }

  function handleKeyDown(e) {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      send();
    }
  }

  return {
    sessions, activeId, setActiveId, messages, input, setInput,
    sending, loadingMessages, error, scrollRef,
    startNewChat, deleteChat, send, handleKeyDown
  };
}

// ---------------------------------------------------------------------------
// Original full-page presentation. Kept intact and unused by the router by
// default now that the assistant is presented as a floating widget, but left
// in place in case a dedicated page is ever needed again.
// ---------------------------------------------------------------------------
export function AIAssistantPage() {
  const {
    sessions, activeId, setActiveId, messages, input, setInput,
    sending, loadingMessages, error, scrollRef,
    startNewChat, deleteChat, send, handleKeyDown
  } = useChatAssistant();

  return (
    <div>
      <div className="page-header">
        <span className="eyebrow">AI PRODUCT ASSISTANT</span>
        <h1>Ask about AI Career Companion.</h1>
        <p>A RAG-grounded assistant that answers from the product's own knowledge base — how features work, how to use them, and what powers them under the hood.</p>
      </div>

      {error && <div className="form-message error">{error}</div>}

      <div className="chat-layout">
        <div className="chat-sidebar">
          <button className="primary-button full" onClick={startNewChat}>+ New Chat</button>
          {sessions.map((s) => (
            <div
              key={s.id}
              className={`chat-session-item ${s.id === activeId ? "active" : ""}`}
            >
              <button
                className="chat-session-title"
                onClick={() => setActiveId(s.id)}
              >
                {s.title}
              </button>

              <button
                className="chat-session-delete"
                onClick={(e) => {
                  e.stopPropagation();
                  deleteChat(s.id);
                }}
                title="Delete chat"
                aria-label={`Delete chat: ${s.title}`}
              >
                🗑️
              </button>
            </div>
          ))}
          {sessions.length === 0 && <p className="muted" style={{ padding: "8px 12px", fontSize: 11 }}>No previous chats yet.</p>}
        </div>

        <div className="chat-panel">
          <div className="chat-header">
            <div>
              <h3>AI Assistant</h3>
              <p>Grounded in the Product Knowledge Document · remembers this chat's context</p>
            </div>
          </div>

          <div className="chat-messages" ref={scrollRef}>
            {loadingMessages ? (
              <div className="chat-empty"><span className="spinner" /></div>
            ) : messages.length === 0 ? (
              <div className="chat-empty">
                <h2 style={{ fontSize: 16, color: "var(--text)" }}>Ask me anything about the product</h2>
                <p>Try: "How does internship matching work?" or "How do I add experience to my profile?"</p>
              </div>
            ) : (
              messages.map((m) => (
                <div className={`chat-bubble-row ${m.role}`} key={m.id}>
                  <div>
                    <div className="chat-bubble">
                      {m.role === "assistant" ? (
                        <ReactMarkdown>
                          {m.message}
                        </ReactMarkdown>
                      ) : (
                        m.message
                      )}
                      {m.sources && m.sources.length > 0 && (
                        <div className="chat-sources">
                          <strong>Sources</strong>
                          {m.sources.map((s) => <div key={s}>Product Knowledge Document — {s}</div>)}
                        </div>
                      )}
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
              placeholder="Ask a question about AI Career Companion..."
              value={input}
              onChange={(e) => setInput(e.target.value)}
              onKeyDown={handleKeyDown}
              disabled={sending}
            />
            <button className="primary-button" onClick={send} disabled={sending || !input.trim()}>
              {sending ? "Sending..." : "Send"}
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Floating chatbot widget: a small fixed button (bottom-left) that opens a
// compact popup above it. Same underlying functionality as AIAssistantPage,
// presented like a typical real-world website support chatbot.
// ---------------------------------------------------------------------------
export function AIAssistantWidget() {
  const {
    sessions, activeId, setActiveId, messages, input, setInput,
    sending, loadingMessages, error, scrollRef,
    startNewChat, deleteChat, send, handleKeyDown
  } = useChatAssistant();

  const [open, setOpen] = useState(false);
  const [historyOpen, setHistoryOpen] = useState(false);

  function toggleOpen() {
    setOpen((v) => !v);
    setHistoryOpen(false);
  }

  return (
    <>
      <button
        type="button"
        className="chatbot-fab"
        onClick={toggleOpen}
        aria-label={open ? "Close AI Assistant chat" : "Open AI Assistant chat"}
        aria-expanded={open}
        title="AI Assistant"
      >
        💬
      </button>

      {open && (
        <div className="chatbot-popup" role="dialog" aria-label="AI Assistant chat">
          <div className="chatbot-popup-header">
            <div className="chatbot-popup-header-title">
              <span className="chatbot-popup-dot" />
              <div>
                <h3>AI Assistant</h3>
                <p>Grounded in the Product Knowledge Document</p>
              </div>
            </div>
            <div className="chatbot-popup-header-actions">
              <button
                type="button"
                className="chatbot-icon-button"
                onClick={() => setHistoryOpen((v) => !v)}
                title="Chat history"
                aria-label="Show chat history"
                aria-expanded={historyOpen}
              >
                🕘
              </button>
              <button
                type="button"
                className="chatbot-icon-button"
                onClick={startNewChat}
                title="New chat"
                aria-label="Start a new chat"
              >
                +
              </button>
              <button
                type="button"
                className="chatbot-icon-button"
                onClick={() => setOpen(false)}
                title="Minimize"
                aria-label="Minimize AI Assistant chat"
              >
                −
              </button>
            </div>
          </div>

          {historyOpen && (
            <div className="chatbot-history-panel">
              {sessions.length === 0 ? (
                <p className="muted" style={{ padding: "10px 12px", fontSize: 11 }}>No previous chats yet.</p>
              ) : (
                sessions.map((s) => (
                  <div
                    key={s.id}
                    className={`chat-session-item ${s.id === activeId ? "active" : ""}`}
                  >
                    <button
                      className="chat-session-title"
                      onClick={() => {
                        setActiveId(s.id);
                        setHistoryOpen(false);
                      }}
                    >
                      {s.title}
                    </button>
                    <button
                      className="chat-session-delete"
                      onClick={(e) => {
                        e.stopPropagation();
                        deleteChat(s.id);
                      }}
                      title="Delete chat"
                      aria-label={`Delete chat: ${s.title}`}
                    >
                      🗑️
                    </button>
                  </div>
                ))
              )}
            </div>
          )}

          {error && <div className="form-message error chatbot-error">{error}</div>}

          <div className="chat-messages chatbot-messages" ref={scrollRef}>
            {loadingMessages ? (
              <div className="chat-empty"><span className="spinner" /></div>
            ) : messages.length === 0 ? (
              <div className="chat-empty">
                <h2 style={{ fontSize: 14, color: "var(--text)" }}>Ask me anything about the product</h2>
                <p>Try: "How does internship matching work?"</p>
              </div>
            ) : (
              messages.map((m) => (
                <div className={`chat-bubble-row ${m.role}`} key={m.id}>
                  <div>
                    <div className="chat-bubble">
                      {m.role === "assistant" ? (
                        <ReactMarkdown>
                          {m.message}
                        </ReactMarkdown>
                      ) : (
                        m.message
                      )}
                      {m.sources && m.sources.length > 0 && (
                        <div className="chat-sources">
                          <strong>Sources</strong>
                          {m.sources.map((s) => <div key={s}>Product Knowledge Document — {s}</div>)}
                        </div>
                      )}
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

          <div className="chat-input-row chatbot-input-row">
            <textarea
              placeholder="Ask a question..."
              value={input}
              onChange={(e) => setInput(e.target.value)}
              onKeyDown={handleKeyDown}
              disabled={sending}
            />
            <button className="primary-button" onClick={send} disabled={sending || !input.trim()}>
              {sending ? "..." : "Send"}
            </button>
          </div>
        </div>
      )}
    </>
  );
}
