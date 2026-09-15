const API_BASE = (import.meta.env.VITE_API_BASE_URL || "http://127.0.0.1:8000").replace(/\/$/, "");

export function getToken() {
  return localStorage.getItem("ai_access_token");
}

export function setToken(token) {
  localStorage.setItem("ai_access_token", token);
}

export function clearSession() {
  localStorage.removeItem("ai_access_token");
  localStorage.removeItem("ai_user");
  localStorage.removeItem("ai_resume");
}

async function request(path, options = {}) {
  const { auth = false, ...fetchOptions } = options;
  const headers = new Headers(fetchOptions.headers || {});

  if (auth) {
    const token = getToken();
    if (token) headers.set("Authorization", `Bearer ${token}`);
  }

  if (fetchOptions.body && !(fetchOptions.body instanceof FormData) && !headers.has("Content-Type")) {
    headers.set("Content-Type", "application/json");
  }

  const response = await fetch(`${API_BASE}${path}`, {
    ...fetchOptions,
    headers
  });

  let data = null;
  const contentType = response.headers.get("content-type") || "";
  if (contentType.includes("application/json")) {
    data = await response.json();
  } else {
    data = await response.text();
  }

  if (!response.ok) {
    const message =
      data?.detail ||
      data?.message ||
      (Array.isArray(data?.detail) ? data.detail.map((x) => x.msg).join(", ") : null) ||
      `Request failed with status ${response.status}`;
    const error = new Error(message);
    error.status = response.status;
    throw error;
  }

  return data;
}

export const api = {
  register: (payload) =>
    request("/register", {
      method: "POST",
      body: JSON.stringify(payload)
    }),

  login: async (email, password) => {
    // FastAPI's OAuth2PasswordRequestForm expects x-www-form-urlencoded.
    const body = new URLSearchParams();
    body.set("username", email);
    body.set("password", password);

    return request("/login", {
      method: "POST",
      headers: { "Content-Type": "application/x-www-form-urlencoded" },
      body
    });
  },

  logout: () => request("/logout", { method: "POST", auth: true }),

  forgotPassword: (email) =>
    request("/forgot-password", {
      method: "POST",
      body: JSON.stringify({ email })
    }),

  resetPassword: (token, new_password) =>
    request("/reset-password", {
      method: "POST",
      body: JSON.stringify({ token, new_password })
    }),

  changePassword: (current_password, new_password) =>
    request("/change-password", {
      method: "POST",
      auth: true,
      body: JSON.stringify({ current_password, new_password })
    }),

  getProfile: () => request("/profile", { auth: true }),

  updateProfile: (payload) =>
    request("/profile", {
      method: "PUT",
      auth: true,
      body: JSON.stringify(payload)
    }),

  uploadResume: (file) => {
    const form = new FormData();
    form.append("file", file);
    return request("/upload-resume", {
      method: "POST",
      auth: true,
      body: form
    });
  },

  getInternships: () => request("/internships/"),

  matchInternships: (resumeId, k = 5) =>
    request(`/internships/match/${resumeId}?k=${k}`, { auth: true }),

  getCareerProfile: () => request("/career-profile", { auth: true }),
  updateCareerProfile: (payload) => request("/career-profile", { method: "PUT", auth: true, body: JSON.stringify(payload) }),
  uploadProfilePhoto: (file) => { const form = new FormData(); form.append("file", file); return request("/profile/photo", { method: "POST", auth: true, body: form }); },
  getCoverLetters: () => request("/cover-letters", { auth: true }),
  generateCoverLetter: (resumeId, internshipId) => request("/cover-letter/generate", { method: "POST", auth: true, body: JSON.stringify({ resume_id: resumeId, internship_id: internshipId }) }),

  // ---- Parsed Resumes ----
  getParsedResumes: () => request("/parsed-resumes", { auth: true }),
  reparseResume: (resumeId) => request(`/parsed-resumes/${resumeId}/reparse`, { method: "POST", auth: true }),
  deleteParsedResume: (resumeId) =>
  request(`/parsed-resumes/${resumeId}`, {
    method: "DELETE",
    auth: true,
  }),

  // ---- Applied Internships (in-app apply, no external redirect) ----
  applyToInternship: (internshipId) => request(`/internships/${internshipId}/apply`, { method: "POST", auth: true }),
  getAppliedInternships: () => request("/internships/applied/me", { auth: true }),

  // ---- AI Assistant (RAG chatbot) ----
  createChatSession: (title) => request("/chat/sessions", { method: "POST", auth: true, body: JSON.stringify(title ? { title } : {}) }),
  listChatSessions: () => request("/chat/sessions", { auth: true }),
  deleteChatSession: (sessionId) => request(`/chat/sessions/${sessionId}`, { method: "DELETE", auth: true }),
  getChatMessages: (sessionId) => request(`/chat/sessions/${sessionId}/messages`, { auth: true }),
  sendChatMessage: (sessionId, message) => request(`/chat/sessions/${sessionId}/messages`, { method: "POST", auth: true, body: JSON.stringify({ message }) }),

  // ---- AI Interview Preparation Agent (separate from the AI Assistant above) ----
  getInterviewPrepContext: (resumeId) =>
  request(
    `/interview-prep/context${resumeId ? `?resume_id=${encodeURIComponent(resumeId)}` : ""}`,
    { auth: true }
  ),
  createInterviewPrepSession: (title, resumeId) =>
    request("/interview-prep/sessions", {
      method: "POST",
      auth: true,
      body: JSON.stringify({
        ...(title ? { title } : {}),
        ...(resumeId ? { resume_id: resumeId } : {}),
      }),
    }), 
  listInterviewPrepSessions: () => request("/interview-prep/sessions", { auth: true }),
  deleteInterviewPrepSession: (sessionId) => request(`/interview-prep/sessions/${sessionId}`, { method: "DELETE", auth: true }),
  getInterviewPrepMessages: (sessionId) => request(`/interview-prep/sessions/${sessionId}/messages`, { auth: true }),
  sendInterviewPrepMessage: (sessionId, message) => request(`/interview-prep/sessions/${sessionId}/messages`, { method: "POST", auth: true, body: JSON.stringify({ message }) }),
  uploadInterviewPrepDocument: (sessionId, file) => { const form = new FormData(); form.append("file", file); return request(`/interview-prep/sessions/${sessionId}/document`, { method: "POST", auth: true, body: form }); },

  health: () => request("/health"),
  baseUrl: () => API_BASE
};