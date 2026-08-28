import { Plus, Save, Trash2, Upload } from "lucide-react";
import { useEffect, useState } from "react";

import { useApi } from "../hooks/useApi";
import { api } from "../lib/api";

const emptyProfile = {
  personal_info: { name: "", email: "", phone: "", linkedin: "", github: "", portfolio: "", twitter: "", telegram: "", location: "", extra_links: {} },
  summary: "", skills: {}, experience: [], education: [], certifications: [], projects: [], languages: [], achievements: [],
};

function ListEditor({ title, items, fields, onChange }) {
  const add = () => onChange([...items, Object.fromEntries(fields.map(([key]) => [key, key === "bullets" ? [] : ""]))]);
  return (
    <section className="form-section">
      <div className="section-title"><h2>{title}</h2><button type="button" className="button secondary small" onClick={add}><Plus size={15} /> Add</button></div>
      {!items.length && <p className="empty compact">No entries added.</p>}
      {items.map((item, index) => (
        <div className="repeater" key={`${title}-${index}`}>
          <div className="field-grid">
            {fields.map(([key, label]) => <label key={key}>{label}<input value={key === "bullets" ? (item[key] || []).join(" | ") : item[key] || ""} onChange={(event) => onChange(items.map((entry, position) => position === index ? { ...entry, [key]: key === "bullets" ? event.target.value.split("|").map((v) => v.trim()).filter(Boolean) : event.target.value } : entry))} /></label>)}
          </div>
          <button type="button" className="icon-button danger" title={`Remove ${title} entry`} onClick={() => onChange(items.filter((_, position) => position !== index))}><Trash2 size={16} /></button>
        </div>
      ))}
    </section>
  );
}

export default function Profile() {
  const current = useApi("/profile");
  const [profile, setProfile] = useState(emptyProfile);
  const [skillsText, setSkillsText] = useState("");
  const [notice, setNotice] = useState("");
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    if (current.data) {
      setProfile({ ...emptyProfile, ...current.data, personal_info: { ...emptyProfile.personal_info, ...current.data.personal_info } });
      setSkillsText(Object.entries(current.data.skills || {}).map(([category, values]) => `${category}: ${values.join(", ")}`).join("\n"));
    }
  }, [current.data]);

  const setPersonal = (key, value) => setProfile((valueNow) => ({ ...valueNow, personal_info: { ...valueNow.personal_info, [key]: value } }));
  const parseSkills = () => Object.fromEntries(skillsText.split("\n").map((line) => line.split(":"))
    .filter(([, values]) => values).map(([category, values]) => [category.trim(), values.split(",").map((value) => value.trim()).filter(Boolean)]));

  const save = async (event) => {
    event.preventDefault(); setBusy(true); setNotice("");
    try {
      const saved = await api("/profile", { method: "POST", body: JSON.stringify({ ...profile, skills: parseSkills() }) });
      setProfile({ ...emptyProfile, ...saved, personal_info: { ...emptyProfile.personal_info, ...saved.personal_info } });
      setNotice("Profile saved.");
    }
    catch (error) { setNotice(error.message); }
    finally { setBusy(false); }
  };

  const upload = async (event) => {
    const file = event.target.files?.[0]; if (!file) return;
    const body = new FormData(); body.append("file", file); setBusy(true); setNotice("Extracting profile from CV...");
    try {
      const result = await api("/profile/upload", { method: "POST", body });
      const parsed = result.profile || result;
      setProfile({ ...emptyProfile, ...parsed, personal_info: { ...emptyProfile.personal_info, ...parsed.personal_info } });
      setSkillsText(Object.entries(parsed.skills || {}).map(([category, values]) => `${category}: ${values.join(", ")}`).join("\n"));
      setNotice("CV imported. Review and save your profile.");
    }
    catch (error) { setNotice(error.message); }
    finally { setBusy(false); event.target.value = ""; }
  };

  const remove = async () => {
    if (!window.confirm("Delete the saved profile?")) return;
    try { await api("/profile", { method: "DELETE" }); setProfile(emptyProfile); setSkillsText(""); setNotice("Profile deleted."); } catch (error) { setNotice(error.message); }
  };

  return (
    <div className="page"><div className="page-header"><div><p className="eyebrow">Candidate data</p><h1>Profile</h1><p>Maintain the complete source profile used for matching and CV generation.</p></div><label className="button secondary file-button"><Upload size={17} /> Import CV<input type="file" accept=".pdf,.docx,.txt" onChange={upload} /></label></div>
      <form className="panel profile-form" onSubmit={save}>
        <section className="form-section"><h2>Personal information</h2><div className="field-grid">{[["name","Full name"],["email","Email"],["phone","Phone"],["location","Location"],["linkedin","LinkedIn"],["github","GitHub"],["portfolio","Portfolio"]].map(([key,label]) => <label key={key}>{label}<input required={key === "name"} value={profile.personal_info[key]} onChange={(event) => setPersonal(key, event.target.value)} /></label>)}</div><label>Professional summary<textarea rows="4" value={profile.summary} onChange={(event) => setProfile({ ...profile, summary: event.target.value })} /></label></section>
        <section className="form-section"><h2>Skills</h2><label>One category per line<textarea rows="5" placeholder="Languages: Python, JavaScript\nSecurity: Slither, Echidna" value={skillsText} onChange={(event) => setSkillsText(event.target.value)} /></label></section>
        <ListEditor title="Experience" items={profile.experience} fields={[["company","Company"],["title","Title"],["duration","Duration"],["location","Location"],["bullets","Bullets (separate with |)"]]} onChange={(experience) => setProfile({ ...profile, experience })} />
        <ListEditor title="Education" items={profile.education} fields={[["institution","Institution"],["degree","Degree"],["year","Year"],["details","Details"]]} onChange={(education) => setProfile({ ...profile, education })} />
        <ListEditor title="Projects" items={profile.projects} fields={[["name","Project"],["tech","Technology"],["description","Description"]]} onChange={(projects) => setProfile({ ...profile, projects })} />
        <div className="form-actions"><button type="button" className="button danger-button" onClick={remove}><Trash2 size={17} /> Delete</button><span className="form-notice">{notice}</span><button className="button primary" disabled={busy}><Save size={17} /> Save profile</button></div>
      </form>
    </div>
  );
}
