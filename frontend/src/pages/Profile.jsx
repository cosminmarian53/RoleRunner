import {
  FileText,
  GraduationCap,
  Briefcase,
  FolderGit2,
  Plus,
  Save,
  Trash2,
  Upload,
  User,
  Sparkles,
  LoaderCircle,
} from "lucide-react";
import { useEffect, useState } from "react";

import { useApi } from "../hooks/useApi";
import { api } from "../lib/api";

const emptyProfile = {
  personal_info: {
    name: "",
    title: "",
    email: "",
    phone: "",
    linkedin: "",
    github: "",
    portfolio: "",
    location: "",
    extra_links: {},
  },
  summary: "",
  skills: {},
  experience: [],
  education: [],
  certifications: [],
  projects: [],
  languages: [],
  achievements: [],
};

function ListEditor({ title, icon: Icon, items, fields, onChange }) {
  const add = () =>
    onChange([
      ...items,
      Object.fromEntries(fields.map(([key]) => [key, key === "bullets" ? [] : ""])),
    ]);

  return (
    <section className="p-6 rounded-2xl bg-[#111622] border border-slate-800 shadow-md space-y-4">
      <div className="flex items-center justify-between pb-3 border-b border-slate-800">
        <h2 className="text-base font-bold text-white flex items-center gap-2">
          {Icon && <Icon size={18} className="text-indigo-400" />} {title}
        </h2>
        <button
          type="button"
          onClick={add}
          className="inline-flex items-center gap-1.5 px-3 py-1.5 text-xs font-bold text-indigo-300 bg-indigo-500/10 hover:bg-indigo-500/20 border border-indigo-500/20 rounded-xl transition"
        >
          <Plus size={14} /> Add {title}
        </button>
      </div>

      {!items.length && (
        <p className="text-xs text-slate-500 py-2 italic">No {title.toLowerCase()} entries added yet.</p>
      )}

      <div className="space-y-4">
        {items.map((item, index) => (
          <div
            key={`${title}-${index}`}
            className="p-4 rounded-xl bg-slate-900/90 border border-slate-800 space-y-3 relative group"
          >
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
              {fields.map(([key, label]) => (
                <div key={key} className={key === "bullets" || key === "description" ? "sm:col-span-2" : ""}>
                  <label className="block text-[11px] font-semibold text-slate-400 mb-1">{label}</label>
                  <input
                    type="text"
                    value={key === "bullets" ? (item[key] || []).join(" | ") : item[key] || ""}
                    onChange={(e) =>
                      onChange(
                        items.map((entry, pos) =>
                          pos === index
                            ? {
                                ...entry,
                                [key]:
                                  key === "bullets"
                                    ? e.target.value.split("|").map((v) => v.trim()).filter(Boolean)
                                    : e.target.value,
                              }
                            : entry
                        )
                      )
                    }
                    placeholder={key === "bullets" ? "Accomplishment 1 | Accomplishment 2" : ""}
                    className="w-full px-3 py-2 bg-slate-950 border border-slate-700 rounded-lg text-xs text-slate-200 focus:outline-none focus:border-indigo-500"
                  />
                </div>
              ))}
            </div>

            <div className="flex justify-end pt-1">
              <button
                type="button"
                onClick={() => onChange(items.filter((_, pos) => pos !== index))}
                className="text-xs text-rose-400 hover:text-rose-300 flex items-center gap-1 font-semibold transition"
              >
                <Trash2 size={13} /> Remove
              </button>
            </div>
          </div>
        ))}
      </div>
    </section>
  );
}

export default function Profile() {
  const current = useApi("/profile");
  const [profile, setProfile] = useState(emptyProfile);
  const [skillsText, setSkillsText] = useState("");
  const [notice, setNotice] = useState("");
  const [busy, setBusy] = useState(false);
  const [uploadBusy, setUploadBusy] = useState(false);

  useEffect(() => {
    if (current.data) {
      setProfile({
        ...emptyProfile,
        ...current.data,
        personal_info: { ...emptyProfile.personal_info, ...current.data.personal_info },
      });
      setSkillsText(
        Object.entries(current.data.skills || {})
          .map(([category, values]) => `${category}: ${values.join(", ")}`)
          .join("\n")
      );
    }
  }, [current.data]);

  const setPersonal = (key, value) =>
    setProfile((prev) => ({
      ...prev,
      personal_info: { ...prev.personal_info, [key]: value },
    }));

  const parseSkills = () =>
    Object.fromEntries(
      skillsText
        .split("\n")
        .map((line) => line.split(":"))
        .filter(([, values]) => values)
        .map(([category, values]) => [
          category.trim(),
          values.split(",").map((v) => v.trim()).filter(Boolean),
        ])
    );

  const handleSave = async (e) => {
    e.preventDefault();
    setBusy(true);
    setNotice("");

    try {
      const saved = await api("/profile", {
        method: "POST",
        body: JSON.stringify({ ...profile, skills: parseSkills() }),
      });
      setProfile({
        ...emptyProfile,
        ...saved,
        personal_info: { ...emptyProfile.personal_info, ...saved.personal_info },
      });
      setNotice("Profile saved successfully.");
      setTimeout(() => setNotice(""), 3000);
    } catch (err) {
      setNotice(err.message || "Failed to save profile.");
    } finally {
      setBusy(false);
    }
  };

  const handleUploadResume = async (e) => {
    const file = e.target.files?.[0];
    if (!file) return;

    setUploadBusy(true);
    setNotice("");

    const formData = new FormData();
    formData.append("file", file);

    try {
      const res = await api("/profile/upload", {
        method: "POST",
        body: formData,
      });
      setProfile({
        ...emptyProfile,
        ...res,
        personal_info: { ...emptyProfile.personal_info, ...res.personal_info },
      });
      setSkillsText(
        Object.entries(res.skills || {})
          .map(([cat, vals]) => `${cat}: ${vals.join(", ")}`)
          .join("\n")
      );
      setNotice("Resume parsed and saved into profile!");
      setTimeout(() => setNotice(""), 4000);
    } catch (err) {
      setNotice(err.message || "Failed to parse resume.");
    } finally {
      setUploadBusy(false);
    }
  };

  return (
    <div className="page max-w-5xl mx-auto px-4 sm:px-6 lg:px-8 py-8 space-y-8">
      {/* Header & Resume Upload CTA */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div>
          <div className="inline-flex items-center gap-2 px-3 py-1 rounded-full bg-indigo-500/10 border border-indigo-500/20 text-indigo-400 text-xs font-semibold">
            <User size={14} /> Master Candidate Record
          </div>
          <h1 className="text-3xl font-extrabold text-white tracking-tight mt-1">Master Profile</h1>
          <p className="text-slate-400 text-sm">
            Used as the source of truth for dynamic ATS scoring and instant CV tailoring across all roles.
          </p>
        </div>

        {/* Upload Resume Button */}
        <div>
          <label className="inline-flex items-center gap-2 px-4 py-2.5 text-xs font-bold text-white bg-indigo-600 hover:bg-indigo-500 rounded-xl shadow-lg shadow-indigo-600/25 cursor-pointer transition">
            {uploadBusy ? <LoaderCircle size={15} className="animate-spin" /> : <Upload size={15} />}
            <span>Upload Resume (PDF / Word)</span>
            <input
              type="file"
              accept=".pdf,.docx,.txt"
              onChange={handleUploadResume}
              className="hidden"
            />
          </label>
        </div>
      </div>

      {notice && (
        <div className="p-4 rounded-xl bg-indigo-500/10 border border-indigo-500/30 text-indigo-300 text-xs font-semibold flex items-center gap-2">
          <Sparkles size={16} /> {notice}
        </div>
      )}

      <form onSubmit={handleSave} className="space-y-6">
        {/* Personal & Contact Information */}
        <section className="p-6 rounded-2xl bg-[#111622] border border-slate-800 shadow-md space-y-4">
          <div className="flex items-center justify-between pb-3 border-b border-slate-800">
            <h2 className="text-base font-bold text-white flex items-center gap-2">
              <User size={18} className="text-indigo-400" /> Contact & Identity
            </h2>
          </div>

          <div className="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-3 gap-4">
            <div>
              <label className="block text-xs font-semibold text-slate-300 mb-1">Full Name</label>
              <input
                required
                type="text"
                value={profile.personal_info.name}
                onChange={(e) => setPersonal("name", e.target.value)}
                placeholder="Jane Doe"
                className="w-full px-3 py-2 bg-slate-900 border border-slate-700 rounded-xl text-xs text-slate-100 focus:outline-none focus:border-indigo-500"
              />
            </div>

            <div>
              <label className="block text-xs font-semibold text-slate-300 mb-1">Primary Role Title</label>
              <input
                type="text"
                value={profile.personal_info.title || ""}
                onChange={(e) => setPersonal("title", e.target.value)}
                placeholder="e.g. Senior Marketing Director"
                className="w-full px-3 py-2 bg-slate-900 border border-slate-700 rounded-xl text-xs text-slate-100 focus:outline-none focus:border-indigo-500"
              />
            </div>

            <div>
              <label className="block text-xs font-semibold text-slate-300 mb-1">Email</label>
              <input
                type="email"
                value={profile.personal_info.email}
                onChange={(e) => setPersonal("email", e.target.value)}
                placeholder="jane@example.com"
                className="w-full px-3 py-2 bg-slate-900 border border-slate-700 rounded-xl text-xs text-slate-100 focus:outline-none focus:border-indigo-500"
              />
            </div>

            <div>
              <label className="block text-xs font-semibold text-slate-300 mb-1">Phone</label>
              <input
                type="text"
                value={profile.personal_info.phone}
                onChange={(e) => setPersonal("phone", e.target.value)}
                placeholder="+1 (555) 019-2831"
                className="w-full px-3 py-2 bg-slate-900 border border-slate-700 rounded-xl text-xs text-slate-100 focus:outline-none focus:border-indigo-500"
              />
            </div>

            <div>
              <label className="block text-xs font-semibold text-slate-300 mb-1">Location</label>
              <input
                type="text"
                value={profile.personal_info.location}
                onChange={(e) => setPersonal("location", e.target.value)}
                placeholder="New York, NY (Remote)"
                className="w-full px-3 py-2 bg-slate-900 border border-slate-700 rounded-xl text-xs text-slate-100 focus:outline-none focus:border-indigo-500"
              />
            </div>

            <div>
              <label className="block text-xs font-semibold text-slate-300 mb-1">LinkedIn Profile</label>
              <input
                type="text"
                value={profile.personal_info.linkedin}
                onChange={(e) => setPersonal("linkedin", e.target.value)}
                placeholder="linkedin.com/in/janedoe"
                className="w-full px-3 py-2 bg-slate-900 border border-slate-700 rounded-xl text-xs text-slate-100 focus:outline-none focus:border-indigo-500"
              />
            </div>
          </div>
        </section>

        {/* Master Summary */}
        <section className="p-6 rounded-2xl bg-[#111622] border border-slate-800 shadow-md space-y-3">
          <h2 className="text-base font-bold text-white flex items-center gap-2">
            <FileText size={18} className="text-indigo-400" /> Master Executive Summary
          </h2>
          <textarea
            rows={4}
            value={profile.summary}
            onChange={(e) => setProfile({ ...profile, summary: e.target.value })}
            placeholder="High-impact career overview summarizing key competencies, track record, and leadership scope..."
            className="w-full px-3.5 py-2.5 bg-slate-900 border border-slate-700 rounded-xl text-xs text-slate-100 focus:outline-none focus:border-indigo-500 leading-relaxed"
          />
        </section>

        {/* Skills Categories */}
        <section className="p-6 rounded-2xl bg-[#111622] border border-slate-800 shadow-md space-y-3">
          <div className="flex items-center justify-between">
            <h2 className="text-base font-bold text-white flex items-center gap-2">
              <Sparkles size={18} className="text-indigo-400" /> Skills & Domain Expertise
            </h2>
            <span className="text-[11px] text-slate-400 font-mono">Category: Skill 1, Skill 2</span>
          </div>
          <textarea
            rows={5}
            value={skillsText}
            onChange={(e) => setSkillsText(e.target.value)}
            placeholder="Core Skills: Strategic Planning, Project Management, Team Leadership&#10;Tools: Excel, Salesforce, Tableau, Figma"
            className="w-full px-3.5 py-2.5 bg-slate-900 border border-slate-700 rounded-xl text-xs text-slate-100 font-mono focus:outline-none focus:border-indigo-500 leading-relaxed"
          />
        </section>

        {/* Work Experience */}
        <ListEditor
          title="Work Experience"
          icon={Briefcase}
          items={profile.experience}
          fields={[
            ["title", "Job Title / Role"],
            ["company", "Company / Organization"],
            ["location", "Location"],
            ["start_date", "Start Date"],
            ["end_date", "End Date"],
            ["bullets", "Key Bullet Points (Separate with | )"],
          ]}
          onChange={(items) => setProfile({ ...profile, experience: items })}
        />

        {/* Education */}
        <ListEditor
          title="Education"
          icon={GraduationCap}
          items={profile.education}
          fields={[
            ["degree", "Degree / Diploma"],
            ["institution", "University / Institution"],
            ["year", "Graduation Year"],
          ]}
          onChange={(items) => setProfile({ ...profile, education: items })}
        />

        {/* Projects / Key Initiatives */}
        <ListEditor
          title="Projects & Key Initiatives"
          icon={FolderGit2}
          items={profile.projects}
          fields={[
            ["name", "Project Name / Initiative"],
            ["description", "Impact & Description"],
            ["technologies", "Tools / Methodologies (Pipe separated)"],
          ]}
          onChange={(items) => setProfile({ ...profile, projects: items })}
        />

        {/* Save Bar */}
        <div className="flex justify-end pt-4">
          <button
            type="submit"
            disabled={busy}
            className="inline-flex items-center gap-2 px-8 py-3 text-sm font-bold text-white bg-gradient-to-r from-indigo-600 to-violet-600 hover:from-indigo-500 hover:to-violet-500 rounded-xl shadow-lg shadow-indigo-600/30 transition active:scale-[0.98]"
          >
            {busy ? <LoaderCircle size={18} className="animate-spin" /> : <Save size={18} />}
            Save Master Profile
          </button>
        </div>
      </form>
    </div>
  );
}
