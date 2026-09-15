import { useEffect, useState } from "react";
import { NavLink } from "react-router-dom";
import Cropper from "react-easy-crop";
import { api } from "./api";


export function CoverLetterPage({ resume }) {
  const [jobs, setJobs] = useState([]);
  const [selected, setSelected] = useState("");
  const [letter, setLetter] = useState(null);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    api.getInternships().then(setJobs).catch(e => setError(e.message));
    const id = new URLSearchParams(window.location.search).get("internship");
    if (id) setSelected(id);
  }, []);

  async function generate() {
    if (!resume?.resume_id) return setError("Upload and parse a resume first.");
    if (!selected) return setError("Select an internship first.");
    setLoading(true); setError("");
    try { setLetter(await api.generateCoverLetter(resume.resume_id, selected)); }
    catch (e) { setError(e.message); }
    finally { setLoading(false); }
  }

  return <div>
    <div className="page-header"><span className="eyebrow">AI COVER LETTER</span><h1>Generate a tailored cover letter.</h1>
      <p>Uses your parsed resume and the selected internship as the only source context.</p></div>
    {!resume?.resume_id ? <div className="empty-state"><h2>Upload a resume first</h2><p>The cover letter uses your parsed candidate data.</p><NavLink className="primary-button" to="/resume">Upload resume →</NavLink></div> :
      <div className="cover-letter-layout">
        <div className="settings-card">
          <h3>Select internship</h3>
          <select value={selected} onChange={e => setSelected(e.target.value)}>
            <option value="">Choose an opportunity...</option>
            {jobs.map(j => <option key={j.id} value={j.id}>{j.role_title} — {j.company}</option>)}
          </select>
          {error && <div className="form-message error">{error}</div>}
          <button className="primary-button full" onClick={generate} disabled={loading}>{loading ? "Generating..." : "Generate Cover Letter ✦"}</button>
          {letter && <button className="secondary-button" onClick={() => navigator.clipboard?.writeText(letter.content)}>Copy</button>}
        </div>
        <div className="settings-card letter-paper">
          {letter ? <><span className="eyebrow">{letter.internship_role} · {letter.company}</span><h3>Cover Letter</h3><div className="cover-letter-content">{letter.content}</div></> :
            <div className="empty-state compact"><h2>Your cover letter will appear here</h2><p>Select an internship and generate it.</p></div>}
        </div>
      </div>}
  </div>;
}



function createCroppedImage(imageSrc, pixelCrop) {
  return new Promise((resolve, reject) => {
    const image = new Image();

    image.onload = () => {
      const canvas = document.createElement("canvas");
      const ctx = canvas.getContext("2d");

      canvas.width = pixelCrop.width;
      canvas.height = pixelCrop.height;

      ctx.drawImage(
        image,
        pixelCrop.x,
        pixelCrop.y,
        pixelCrop.width,
        pixelCrop.height,
        0,
        0,
        pixelCrop.width,
        pixelCrop.height
      );

      canvas.toBlob(
        (blob) => {
          if (!blob) {
            reject(new Error("Could not crop image."));
            return;
          }

          resolve(
            new File(
              [blob],
              "profile-photo.jpg",
              { type: "image/jpeg" }
            )
          );
        },
        "image/jpeg",
        0.92
      );
    };

    image.onerror = () => {
      reject(new Error("Could not load selected image."));
    };

    image.src = imageSrc;
  });
}









export function CareerProfilePage({ user, onUserChange }) {
  const [p, setP] = useState(null), [letters, setLetters] = useState([]), [error, setError] = useState(""), [message, setMessage] = useState("");
  const [photoVersion, setPhotoVersion] = useState(Date.now());
  // Profile photo cropping state
  const [selectedImage, setSelectedImage] = useState(null);
  const [crop, setCrop] = useState({ x: 0, y: 0 });
  const [zoom, setZoom] = useState(1);
  const [croppedAreaPixels, setCroppedAreaPixels] = useState(null);
  const [cropping, setCropping] = useState(false);
  const [photoUploading, setPhotoUploading] = useState(false);

  useEffect(() => { Promise.all([api.getCareerProfile(), api.getCoverLetters()]).then(([a,b]) => { setP(a); setLetters(b); }).catch(e => setError(e.message)); }, []);
  if (!p) return <div className="loading-state">Loading your career profile...</div>;
  const pd = p.personal_details || {};
  const setPD = (k,v) => setP(x => ({...x, personal_details:{...(x.personal_details||{}),[k]:v}}));
  async function save(e) { e?.preventDefault?.(); try { const x=await api.updateCareerProfile(p); setP(x); setMessage("Profile updated."); onUserChange({...user,full_name:x.personal_details?.full_name||user.full_name,phone_number:x.personal_details?.phone_number||user.phone_number}); } catch(e){setError(e.message)} }
  async function saveField(field, value) {
    setError(""); setMessage("");
    try {
      const payload = { ...p, [field]: value };
      const x = await api.updateCareerProfile(payload);
      setP(x);
      setMessage("Profile updated.");
    } catch (e) {
      setError(e.message);
    }
  }
  function photo(e) {
    const f = e.target.files?.[0];

    if (!f) return;

    if (!f.type.startsWith("image/")) {
      setError("Please select an image file.");
      return;
    }

    setError("");
    setMessage("");

    const imageUrl = URL.createObjectURL(f);

    setSelectedImage(imageUrl);
    setCrop({ x: 0, y: 0 });
    setZoom(1);
    setCroppedAreaPixels(null);
    setCropping(true);

    // Allow selecting the same image again later.
    e.target.value = "";
  }

  function onCropComplete(_, croppedPixels) {
    setCroppedAreaPixels(croppedPixels);
  }

  async function saveCroppedPhoto() {
    if (!selectedImage || !croppedAreaPixels) {
      setError("Please select a crop area.");
      return;
    }

    setPhotoUploading(true);
    setError("");
    setMessage("");

    try {
      const croppedFile = await createCroppedImage(
        selectedImage,
        croppedAreaPixels
      );

      await api.uploadProfilePhoto(croppedFile);

      const updatedProfile = await api.getCareerProfile();

      setP(updatedProfile);
      setPhotoVersion(Date.now());
      setCropping(false);

      URL.revokeObjectURL(selectedImage);
      setSelectedImage(null);

      setMessage("Photo updated.");
    } catch (e) {
      setError(e.message || "Failed to update profile photo.");
    } finally {
      setPhotoUploading(false);
    }
  }

  function cancelPhotoCrop() {
    if (selectedImage) {
      URL.revokeObjectURL(selectedImage);
    }

    setSelectedImage(null);
    setCropping(false);
    setCrop({ x: 0, y: 0 });
    setZoom(1);
    setCroppedAreaPixels(null);
  }
  return <div>
    <div className="page-header"><span className="eyebrow">CAREER PROFILE</span><h1>Your professional profile.</h1><p>Manage your personal details and career information used by the AI Career Companion.</p></div>
    {error && <div className="form-message error">{error}</div>}{message && <div className="form-message success">{message}</div>}
    <div className="profile-hero-card">


      <div className="profile-photo-wrap">
        {p.photo_url ? (
          <img
            className="profile-photo"
            src={`${api.baseUrl()}${p.photo_url}?v=${photoVersion}`}
            alt="Profile"
          />
        ) : (
          <span className="large-avatar">
            {(pd.full_name || "U")[0].toUpperCase()}
          </span>
        )}

        <label className="secondary-button">
          Change photo
          <input
            hidden
            type="file"
            accept="image/*"
            onChange={photo}
          />
        </label>
      </div>
      <div><span className="eyebrow">CAREER COMPANION</span><h2>{pd.full_name||user.full_name}</h2><p>{pd.email||user.email}</p></div>
    </div>

    <div className="resume-disclaimer">
      <span>ⓘ</span>
      <span>This profile is entirely yours to manage — it is never auto-filled or overwritten by an uploaded resume. Resume parsing (see the Resume and Parsed Resumes pages) is used only for internship matching and cover letters.</span>
    </div>

    <div className="settings-grid">
      <div className="settings-card profile-wide"><h3>Personal details</h3><form onSubmit={save} className="form-stack"><div className="two-col">
        {["full_name","email","phone_number","address","linkedin","github","portfolio_website"].map(k=><label className="field" key={k}><span>{k.replaceAll("_"," ")}</span><input value={pd[k]||""} onChange={e=>setPD(k,e.target.value)}/></label>)}
      </div><button className="primary-button">Save changes</button></form></div>

      <SkillsEditor
        skills={p.skills || []}
        onSave={(skills) => saveField("skills", skills)}
      />

      <EditableListSection
        title="Education"
        items={p.education || []}
        onSave={(education) => saveField("education", education)}
        summary={(x) => x.degree || "New entry"}
        subSummary={(x) => x.institution || ""}
        fields={[
          { key: "degree", label: "Degree", type: "text" },
          { key: "institution", label: "Institution", type: "text" },
          { key: "field_of_study", label: "Field of study", type: "text" },
          { key: "location", label: "Location", type: "text" },
          { key: "start_date", label: "Start date", type: "text" },
          { key: "end_date", label: "End date", type: "text" },
          { key: "grade", label: "Grade / GPA", type: "text" }
        ]}
      />

      <EditableListSection
        title="Experience"
        items={p.experience || []}
        onSave={(experience) => saveField("experience", experience)}
        summary={(x) => x.job_title || "New role"}
        subSummary={(x) => x.company || ""}
        fields={[
          { key: "job_title", label: "Job title", type: "text" },
          { key: "company", label: "Company", type: "text" },
          { key: "location", label: "Location", type: "text" },
          { key: "start_date", label: "Start date", type: "text" },
          { key: "end_date", label: "End date", type: "text" },
          { key: "responsibilities", label: "Responsibilities", type: "textarea" }
        ]}
      />

      <EditableListSection
        title="Projects"
        items={p.projects || []}
        onSave={(projects) => saveField("projects", projects)}
        summary={(x) => x.name || "New project"}
        subSummary={(x) => x.technologies || ""}
        fields={[
          { key: "name", label: "Project name", type: "text" },
          { key: "technologies", label: "Technologies used", type: "text" },
          { key: "description", label: "Description", type: "textarea" }
        ]}
      />

      <EditableListSection
        title="Achievements"
        items={p.achievements || []}
        onSave={(achievements) => saveField("achievements", achievements)}
        summary={(x) => x.name || "New achievement"}
        fields={[
          { key: "name", label: "Achievement", type: "text" },
          { key: "description", label: "Description", type: "textarea" }
        ]}
      />

      <div className="settings-card"><h3>Resume</h3>{p.resume?<><strong>📄 {p.resume.filename}</strong><p>{p.resume.is_parsed ? "Parsed and available for matching and cover letters." : "Uploaded, not yet parsed."}</p><NavLink className="secondary-button" to="/resume">Manage resume</NavLink></>:<NavLink className="primary-button" to="/resume">Upload resume</NavLink>}</div>
      <div className="settings-card"><h3>Cover letters</h3>{letters.length?letters.map(x=><div className="profile-list-item" key={x.id}><strong>{x.internship_role}</strong><span>{x.company}</span><small>{new Date(x.created_at).toLocaleDateString()}</small></div>):<p className="muted">No cover letters generated yet.</p>}</div>
    </div>

    <CustomSectionsEditor
      sections={p.custom_sections || []}
      onSave={(custom_sections) => saveField("custom_sections", custom_sections)}
    />

    {cropping && selectedImage && (
      <div className="photo-crop-overlay">
        <div className="photo-crop-modal">

          <div className="photo-crop-header">
            <h3>Crop your profile photo</h3>
            <button
              type="button"
              className="photo-crop-close"
              onClick={cancelPhotoCrop}
              disabled={photoUploading}
            >
              ×
            </button>
          </div>

          <div className="photo-crop-area">
            <Cropper
              image={selectedImage}
              crop={crop}
              zoom={zoom}
              aspect={1}
              cropShape="round"
              showGrid={false}
              onCropChange={setCrop}
              onCropComplete={onCropComplete}
              onZoomChange={setZoom}
            />
          </div>

          <div className="photo-crop-controls">
            <span>Zoom</span>

            <input
              type="range"
              min={1}
              max={3}
              step={0.05}
              value={zoom}
              onChange={(e) => setZoom(Number(e.target.value))}
            />
          </div>

          <div className="photo-crop-actions">
            <button
              type="button"
              className="secondary-button"
              onClick={cancelPhotoCrop}
              disabled={photoUploading}
            >
              Cancel
            </button>

            <button
              type="button"
              className="primary-button"
              onClick={saveCroppedPhoto}
              disabled={photoUploading}
            >
              {photoUploading ? "Saving..." : "Crop & Save"}
            </button>
          </div>

        </div>
      </div>
    )}

  </div>;
}

function ProfilePanel({title,items=[],skills,main,sub}) {
  return <div className="settings-card"><h3>{title}</h3>{skills?<div className="skill-row">{skills.map(x=><span key={x}>{x}</span>)}</div>:items.length?items.map((x,i)=><div className="profile-list-item" key={i}><strong>{x[main]||x.title||"Item"}</strong><span>{x[sub]||""}</span></div>):<p className="muted">No data available.</p>}</div>;
}

// ---------------------------------------------------------------------
// User-managed Career Profile editors: skills tags, generic add/edit/
// delete list sections (education, experience, projects, achievements),
// and freeform custom sections. All persist by calling onSave(newValue)
// with the field's fully-updated value; the parent PUTs the whole
// profile and refreshes from the server response.
// ---------------------------------------------------------------------

function SkillsEditor({ skills, onSave }) {
  const [draft, setDraft] = useState(skills);
  const [input, setInput] = useState("");
  const dirty = JSON.stringify(draft) !== JSON.stringify(skills);

  useEffect(() => setDraft(skills), [skills]);

  function addSkill() {
    const value = input.trim();
    if (!value) return;
    if (draft.some((s) => s.toLowerCase() === value.toLowerCase())) { setInput(""); return; }
    setDraft([...draft, value]);
    setInput("");
  }

  function removeSkill(skill) {
    setDraft(draft.filter((s) => s !== skill));
  }

  return (
    <div className="settings-card">
      <h3>Skills</h3>
      <div className="skill-tag-input">
        {draft.map((s) => (
          <span className="skill-chip" key={s}>
            {s}
            <button type="button" onClick={() => removeSkill(s)} aria-label={`Remove ${s}`}>×</button>
          </span>
        ))}
        {draft.length === 0 && <p className="muted">No skills added yet.</p>}
      </div>
      <div className="add-item-row">
        <input
          placeholder="Add a skill and press Enter"
          value={input}
          onChange={(e) => setInput(e.target.value)}
          onKeyDown={(e) => { if (e.key === "Enter") { e.preventDefault(); addSkill(); } }}
        />
        <button type="button" className="secondary-button" onClick={addSkill}>Add</button>
      </div>
      {dirty && (
        <button type="button" className="primary-button full" style={{ marginTop: 12 }} onClick={() => onSave(draft)}>
          Save skills
        </button>
      )}
    </div>
  );
}

function EditableListSection({ title, items, onSave, fields, summary, subSummary }) {
  const [draft, setDraft] = useState(items);
  const dirty = JSON.stringify(draft) !== JSON.stringify(items);

  useEffect(() => setDraft(items), [items]);

  function addItem() {
    const blank = {};
    fields.forEach((f) => { blank[f.key] = ""; });
    setDraft([...draft, blank]);
  }

  function updateItem(index, key, value) {
    setDraft(draft.map((item, i) => (i === index ? { ...item, [key]: value } : item)));
  }

  function removeItem(index) {
    setDraft(draft.filter((_, i) => i !== index));
  }

  return (
    <div className="settings-card profile-wide">
      <div className="section-heading" style={{ marginBottom: 0 }}>
        <h3>{title}</h3>
      </div>

      <div className="editable-list">
        {draft.length === 0 && <p className="muted">No {title.toLowerCase()} added yet.</p>}
        {draft.map((item, i) => (
          <div className="editable-item" key={i}>
            <div className="editable-item-head">
              <span>{summary ? (summary(item) || `Entry ${i + 1}`) : `Entry ${i + 1}`}{subSummary && subSummary(item) ? ` · ${subSummary(item)}` : ""}</span>
              <button type="button" className="icon-button" onClick={() => removeItem(i)} aria-label="Remove entry">🗑</button>
            </div>
            <div className={`field-grid ${fields.length <= 1 ? "single" : ""}`}>
              {fields.map((f) => (
                <label className="field" key={f.key} style={f.type === "textarea" ? { gridColumn: "1 / -1" } : undefined}>
                  <span>{f.label}</span>
                  {f.type === "textarea" ? (
                    <textarea value={item[f.key] || ""} onChange={(e) => updateItem(i, f.key, e.target.value)} />
                  ) : (
                    <input value={item[f.key] || ""} onChange={(e) => updateItem(i, f.key, e.target.value)} />
                  )}
                </label>
              ))}
            </div>
          </div>
        ))}
      </div>

      <button type="button" className="section-add-button" onClick={addItem}>+ Add {title.toLowerCase().replace(/s$/, "")}</button>

      {dirty && (
        <button type="button" className="primary-button full" style={{ marginTop: 12 }} onClick={() => onSave(draft)}>
          Save {title.toLowerCase()}
        </button>
      )}
    </div>
  );
}

function CustomSectionsEditor({ sections, onSave }) {
  const [draft, setDraft] = useState(sections);
  const dirty = JSON.stringify(draft) !== JSON.stringify(sections);

  useEffect(() => setDraft(sections), [sections]);

  function addSection() {
    setDraft([...draft, { id: `sec_${Date.now()}`, title: "", content: "" }]);
  }

  function updateSection(index, key, value) {
    setDraft(draft.map((s, i) => (i === index ? { ...s, [key]: value } : s)));
  }

  function removeSection(index) {
    setDraft(draft.filter((_, i) => i !== index));
  }

  return (
    <div className="section-block">
      <div className="section-heading">
        <h2>Custom sections</h2>
        <button type="button" className="secondary-button" onClick={addSection}>+ Add section</button>
      </div>
      {draft.length === 0 && (
        <p className="muted">Add a custom section for anything not covered above — certifications, publications, volunteering, and more.</p>
      )}
      {draft.map((s, i) => (
        <div className="custom-section-card" key={s.id}>
          <div className="custom-section-title-row">
            <input
              placeholder="Section title (e.g. Certifications)"
              value={s.title}
              onChange={(e) => updateSection(i, "title", e.target.value)}
            />
            <button type="button" className="icon-button" onClick={() => removeSection(i)} aria-label="Remove section">🗑</button>
          </div>
          <textarea
            placeholder="Content..."
            value={s.content}
            onChange={(e) => updateSection(i, "content", e.target.value)}
            style={{ minHeight: 100 }}
          />
        </div>
      ))}
      {dirty && (
        <button type="button" className="primary-button" style={{ marginTop: 12 }} onClick={() => onSave(draft)}>
          Save custom sections
        </button>
      )}
    </div>
  );
}

// ---------------------------------------------------------------------
// Parsed Resumes page - lists every uploaded resume (separate concept
// from the Career Profile above), with Reuse / Parse again actions.
// ---------------------------------------------------------------------

export function ParsedResumesPage({ setResume }) {
  const [rows, setRows] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [busyId, setBusyId] = useState(null);
  const [message, setMessage] = useState("");

  function load() {
    setLoading(true);
    api.getParsedResumes().then(setRows).catch((e) => setError(e.message)).finally(() => setLoading(false));
  }

  useEffect(() => { load(); }, []);

  function reuse(row) {
    setResume && setResume({ resume_id: row.resume_id, filename: row.filename });

    localStorage.setItem(
      "activeInterviewPrepResume",
      JSON.stringify({
        resume_id: row.resume_id,
        filename: row.filename,
      })
    );

    setMessage(
      `"${row.filename}" is now the active resume for matching, cover letters, and interview preparation.`
    );
  }

  async function reparse(row) {
    setBusyId(row.resume_id);
    setError(""); setMessage("");
    try {
      const result = await api.reparseResume(row.resume_id);
      setMessage(`"${row.filename}" was re-parsed successfully.`);
      const activeResume = {
        resume_id: result.resume_id,
        filename: result.filename,
      };

      setResume && setResume(activeResume);

      localStorage.setItem(
        "activeInterviewPrepResume",
        JSON.stringify(activeResume)
      );

      load();
    } catch (e) {
      setError(e.message);
    } finally {
      setBusyId(null);
    }
  }

  async function deleteResume(row) {
    if (
      !window.confirm(
        `Delete "${row.filename}" permanently? This will remove its parsed resume data too.`
      )
    ) {
      return;
    }

    setBusyId(row.resume_id);
    setError("");
    setMessage("");

    try {
      await api.deleteParsedResume(row.resume_id);

      const saved = localStorage.getItem("activeInterviewPrepResume");

      if (saved) {
        try {
          if (JSON.parse(saved)?.resume_id === row.resume_id) {
            localStorage.removeItem("activeInterviewPrepResume");
          }
        } catch {}
      }

      setMessage(`"${row.filename}" was deleted successfully.`);
      load();
    } catch (e) {
      setError(e.message || "Failed to delete the resume.");
    } finally {
      setBusyId(null);
    }
  }

  return (
    <div>
      <div className="page-header">
        <span className="eyebrow">RESUME HISTORY</span>
        <h1>Parsed resumes.</h1>
        <p>Every resume you've uploaded, kept separately from your Career Profile. Reuse an older resume for matching, or re-run parsing on it.</p>
      </div>
      {error && <div className="form-message error">{error}</div>}
      {message && <div className="form-message success">{message}</div>}
      {loading ? (
        <div className="loading-state">Loading your resumes...</div>
      ) : rows.length === 0 ? (
        <div className="empty-state">
          <div className="empty-icon">▣</div>
          <h2>No resumes uploaded yet</h2>
          <p>Upload a resume to see it listed here.</p>
          <NavLink className="primary-button" to="/resume">Upload resume →</NavLink>
        </div>
      ) : (
        <div>
          {rows.map((r) => (
            <div className="parsed-resume-row" key={r.resume_id}>
              <div className="resume-icon">📄</div>
              <div className="parsed-resume-main">
                <h3>
                  {r.filename}
                  {r.is_latest && <span className="latest-pill">LATEST</span>}
                </h3>
                <p>
                  Uploaded {new Date(r.uploaded_at).toLocaleString()} · ID {r.resume_id.slice(0, 8)} · {r.is_parsed ? "Parsed" : "Not parsed"}
                </p>
              </div>
              <div className="parsed-resume-actions">
                <button className="secondary-button" onClick={() => reuse(r)}>Reuse</button>
                <button className="secondary-button" onClick={() => reparse(r)} disabled={busyId === r.resume_id}>
                  {busyId === r.resume_id ? "Parsing..." : "Parse again"}
                </button>
                <button
                  className="secondary-button"
                  onClick={() => deleteResume(r)}
                  disabled={busyId === r.resume_id}
                >
                  Delete
                </button>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}


