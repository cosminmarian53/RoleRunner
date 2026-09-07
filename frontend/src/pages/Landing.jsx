import {
  ArrowRight,
  CheckCircle2,
  ChevronRight,
  FileCheck,
  FileText,
  Globe,
  Layers,
  MessageSquare,
  ShieldCheck,
  Sparkles,
  Star,
  Target,
  Zap,
} from "lucide-react";
import { useState } from "react";
import FeedbackModal from "../components/FeedbackModal";

export default function Landing({ onLaunch }) {
  const [feedbackOpen, setFeedbackOpen] = useState(false);
  const [activeCareerTab, setActiveCareerTab] = useState("marketing");

  const careerPreviews = {
    marketing: {
      role: "Senior Growth Marketing Manager",
      company: "Stripe",
      location: "Remote (Global)",
      score: "9.4",
      scoreTier: "high",
      tags: ["B2B SaaS", "User Acquisition", "SQL", "SEO & Paid Ads", "A/B Testing"],
      summary: "Spearheaded multivariant acquisition funnels driving 140% YoY ARR expansion across European markets.",
    },
    healthcare: {
      role: "Lead Clinical Operations Specialist",
      company: "BioHealth Innovations",
      location: "Boston, MA (Hybrid)",
      score: "9.2",
      scoreTier: "high",
      tags: ["Clinical Protocol", "Regulatory Compliance", "Team Leadership", "Data Auditing", "GCP"],
      summary: "Coordinated Phase III clinical trials across 12 medical centers ensuring 100% FDA regulatory adherence.",
    },
    software: {
      role: "Staff Security Engineer",
      company: "Cloudflare",
      location: "Remote (US/EU)",
      score: "9.6",
      scoreTier: "high",
      tags: ["AppSec", "Rust", "Vulnerability Research", "CI/CD Security", "Distributed Systems"],
      summary: "Engineered automated invariant verification pipelines identifying zero-day memory flaws in edge services.",
    },
    finance: {
      role: "Director of Financial Strategy",
      company: "Apex Global Capital",
      location: "London, UK",
      score: "9.1",
      scoreTier: "high",
      tags: ["Financial Modeling", "M&A Diligence", "Capital Allocation", "Forecasting", "Executive Advisory"],
      summary: "Advised board on $450M acquisition strategy optimizing cash reserves and debt structure.",
    },
  };

  const preview = careerPreviews[activeCareerTab];

  return (
    <div className="min-h-screen bg-[#0b0f19] text-slate-100 font-sans selection:bg-indigo-500/30 selection:text-indigo-200">
      {/* Background Ambient Glows */}
      <div className="fixed inset-0 overflow-hidden pointer-events-none z-0">
        <div className="absolute -top-40 left-1/2 -translate-x-1/2 w-[1000px] h-[500px] bg-gradient-to-b from-indigo-600/15 via-purple-600/10 to-transparent blur-[140px]" />
        <div className="absolute top-1/3 -left-40 w-[600px] h-[600px] bg-blue-600/10 blur-[160px]" />
        <div className="absolute bottom-10 -right-40 w-[600px] h-[600px] bg-emerald-600/10 blur-[160px]" />
      </div>

      {/* Top Floating Glass Navigation */}
      <header className="sticky top-0 z-40 backdrop-blur-md bg-[#0b0f19]/80 border-b border-slate-800/60">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 h-18 flex items-center justify-between">
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 rounded-xl bg-gradient-to-tr from-indigo-600 to-violet-500 flex items-center justify-center shadow-lg shadow-indigo-500/25 border border-indigo-400/30">
              <Zap size={22} className="text-white" />
            </div>
            <div>
              <div className="flex items-center gap-2">
                <span className="text-xl font-extrabold tracking-tight bg-gradient-to-r from-white via-slate-200 to-slate-400 bg-clip-text text-transparent">
                  RoleRunner
                </span>
                <span className="text-[10px] uppercase font-bold tracking-widest px-2 py-0.5 rounded-full bg-indigo-500/10 border border-indigo-500/20 text-indigo-400">
                  Universal v2.0
                </span>
              </div>
              <p className="text-[11px] text-slate-400 hidden sm:block">Autonomous Career & ATS Match Orchestrator</p>
            </div>
          </div>

          <nav className="hidden md:flex items-center gap-8 text-sm font-medium text-slate-300">
            <a href="#features" className="hover:text-white transition">Features</a>
            <a href="#how-it-works" className="hover:text-white transition">How it Works</a>
            <a href="#demo" className="hover:text-white transition">Interactive Demo</a>
            <button
              onClick={() => setFeedbackOpen(true)}
              className="hover:text-white transition flex items-center gap-1.5 text-slate-300"
            >
              <MessageSquare size={14} /> Feedback
            </button>
          </nav>

          <div className="flex items-center gap-3">
            <button
              onClick={onLaunch}
              className="inline-flex items-center gap-2 px-5 py-2.5 text-sm font-semibold text-white bg-gradient-to-r from-indigo-600 to-violet-600 hover:from-indigo-500 hover:to-violet-500 rounded-xl shadow-lg shadow-indigo-600/30 hover:shadow-indigo-600/50 transition active:scale-[0.98]"
            >
              Launch Workspace <ArrowRight size={16} />
            </button>
          </div>
        </div>
      </header>

      {/* Hero Section */}
      <section className="relative z-10 pt-20 pb-16 sm:pt-28 sm:pb-24 px-4 sm:px-6 lg:px-8 max-w-7xl mx-auto text-center">
        {/* Pill Tag */}
        <div className="inline-flex items-center gap-2 px-3.5 py-1.5 rounded-full bg-slate-800/80 border border-slate-700/80 text-xs font-semibold text-indigo-300 mb-8 backdrop-blur-sm shadow-inner">
          <Sparkles size={14} className="text-indigo-400 animate-pulse" />
          <span>Job-Agnostic Intelligence for Healthcare, Tech, Marketing, Finance & More</span>
        </div>

        {/* Main Headline */}
        <h1 className="text-4xl sm:text-6xl lg:text-7xl font-extrabold tracking-tight text-white max-w-5xl mx-auto leading-[1.12]">
          Land your dream role. <br />
          <span className="bg-gradient-to-r from-indigo-400 via-purple-300 to-cyan-300 bg-clip-text text-transparent">
            Autopilot your job search.
          </span>
        </h1>

        {/* Subhead */}
        <p className="mt-6 text-lg sm:text-xl text-slate-300 max-w-3xl mx-auto leading-relaxed">
          RoleRunner searches live opportunities across Google, Remotive, and verified career pages.
          It computes genuine ATS relevance scores from your profile and generates perfectly tailored CVs in seconds.
        </p>

        {/* Hero CTAs */}
        <div className="mt-10 flex flex-col sm:flex-row items-center justify-center gap-4">
          <button
            onClick={onLaunch}
            className="w-full sm:w-auto inline-flex items-center justify-center gap-2.5 px-8 py-4 text-base font-bold text-white bg-gradient-to-r from-indigo-600 to-violet-600 hover:from-indigo-500 hover:to-violet-500 rounded-xl shadow-xl shadow-indigo-600/35 transition active:scale-[0.98]"
          >
            Start Finding Jobs <ArrowRight size={18} />
          </button>
          <a
            href="#demo"
            className="w-full sm:w-auto inline-flex items-center justify-center gap-2 px-7 py-4 text-base font-semibold text-slate-200 bg-slate-800/80 hover:bg-slate-700/80 border border-slate-700 rounded-xl transition"
          >
            Explore Live Demo
          </a>
        </div>

        {/* Trust Badges */}
        <div className="mt-14 pt-8 border-t border-slate-800/80 max-w-4xl mx-auto grid grid-cols-2 md:grid-cols-4 gap-6 text-slate-400 text-xs font-semibold">
          <div className="flex items-center justify-center gap-2">
            <CheckCircle2 size={16} className="text-emerald-400" />
            <span>Zero API Keys Required</span>
          </div>
          <div className="flex items-center justify-center gap-2">
            <Target size={16} className="text-indigo-400" />
            <span>0.0–10.0 ATS Relevance Scale</span>
          </div>
          <div className="flex items-center justify-center gap-2">
            <FileCheck size={16} className="text-cyan-400" />
            <span>PDF, DOCX & Markdown Export</span>
          </div>
          <div className="flex items-center justify-center gap-2">
            <ShieldCheck size={16} className="text-purple-400" />
            <span>100% Private & Tenant-Isolated</span>
          </div>
        </div>
      </section>

      {/* Interactive Live Demo Preview Card */}
      <section id="demo" className="relative z-10 py-16 px-4 sm:px-6 lg:px-8 max-w-6xl mx-auto">
        <div className="text-center mb-8">
          <p className="text-xs uppercase font-bold tracking-widest text-indigo-400 mb-2">Interactive Preview</p>
          <h2 className="text-3xl font-extrabold text-white">Universal Career Intelligence in Action</h2>
          <p className="text-slate-400 text-sm mt-2 max-w-xl mx-auto">
            Select a career path below to see how RoleRunner scores real listings and tailors your application materials.
          </p>

          {/* Career Switcher Tabs */}
          <div className="mt-6 inline-flex flex-wrap items-center justify-center gap-2 p-1.5 rounded-2xl bg-slate-900/90 border border-slate-800">
            {[
              { id: "marketing", label: "💼 Marketing & Growth" },
              { id: "healthcare", label: "🩺 Healthcare & Clinical" },
              { id: "software", label: "💻 Tech & Security" },
              { id: "finance", label: "📈 Finance & Strategy" },
            ].map((tab) => (
              <button
                key={tab.id}
                onClick={() => setActiveCareerTab(tab.id)}
                className={`px-4 py-2 text-xs sm:text-sm font-semibold rounded-xl transition ${
                  activeCareerTab === tab.id
                    ? "bg-indigo-600 text-white shadow-md shadow-indigo-600/30"
                    : "text-slate-400 hover:text-slate-200"
                }`}
              >
                {tab.label}
              </button>
            ))}
          </div>
        </div>

        {/* Live Mockup Box */}
        <div className="rounded-2xl border border-slate-700/60 bg-gradient-to-b from-[#131926] to-[#0d121c] p-6 sm:p-8 shadow-2xl shadow-black/60">
          <div className="grid grid-cols-1 lg:grid-cols-12 gap-8 items-start">
            {/* Left: Job Match Card */}
            <div className="lg:col-span-7 space-y-4">
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-2 text-xs font-semibold text-slate-400">
                  <span className="px-2.5 py-1 rounded-md bg-indigo-500/10 border border-indigo-500/20 text-indigo-300">
                    Live Crawled Opportunity
                  </span>
                  <span>• Verified 2h ago</span>
                </div>
                <div className="flex items-center gap-2 px-3 py-1 rounded-full bg-emerald-500/10 border border-emerald-500/30 text-emerald-400 text-sm font-bold">
                  <Star size={14} className="fill-emerald-400" /> {preview.score} / 10 Strong Match
                </div>
              </div>

              <div>
                <h3 className="text-2xl font-bold text-white">{preview.role}</h3>
                <p className="text-slate-300 text-sm font-medium mt-1">
                  {preview.company} • <span className="text-slate-400">{preview.location}</span>
                </p>
              </div>

              <div className="p-4 rounded-xl bg-slate-900/80 border border-slate-800 text-sm text-slate-300 leading-relaxed">
                <p className="font-semibold text-slate-200 mb-1">Tailored Candidate Match Summary:</p>
                <p>{preview.summary}</p>
              </div>

              <div>
                <p className="text-xs font-semibold text-slate-400 mb-2">Matched Candidate Keywords & Skills:</p>
                <div className="flex flex-wrap gap-2">
                  {preview.tags.map((tag, i) => (
                    <span
                      key={i}
                      className="px-2.5 py-1 text-xs font-medium rounded-lg bg-indigo-950/60 border border-indigo-800/40 text-indigo-200"
                    >
                      ✓ {tag}
                    </span>
                  ))}
                </div>
              </div>
            </div>

            {/* Right: Instant Tailored Output Preview */}
            <div className="lg:col-span-5 rounded-xl border border-slate-700/80 bg-slate-900/90 p-5 space-y-4 shadow-inner">
              <div className="flex items-center justify-between border-b border-slate-800 pb-3">
                <div className="flex items-center gap-2 text-xs font-bold text-slate-200">
                  <FileText size={16} className="text-indigo-400" />
                  <span>Tailored CV Snapshot</span>
                </div>
                <span className="text-[11px] text-emerald-400 font-semibold">ATS Optimized</span>
              </div>

              <div className="space-y-2 text-xs text-slate-300 font-mono bg-black/30 p-3 rounded-lg border border-slate-800/60">
                <p className="text-slate-100 font-bold"># Candidate Name</p>
                <p className="text-indigo-300">**{preview.role}**</p>
                <p className="text-slate-400">email@example.com • +1 (555) 019-2831</p>
                <p className="text-slate-300 pt-1 text-[11px] leading-tight">
                  ## Core Skills & Competencies
                  <br />- {preview.tags.slice(0, 3).join(", ")}
                </p>
              </div>

              <div className="pt-2">
                <button
                  onClick={onLaunch}
                  className="w-full inline-flex items-center justify-center gap-2 py-2.5 px-4 text-xs font-bold text-white bg-indigo-600 hover:bg-indigo-500 rounded-lg shadow-md transition"
                >
                  Generate Your Own Tailored CV <ArrowRight size={14} />
                </button>
              </div>
            </div>
          </div>
        </div>
      </section>

      {/* How It Works Section */}
      <section id="how-it-works" className="relative z-10 py-20 px-4 sm:px-6 lg:px-8 max-w-7xl mx-auto">
        <div className="text-center max-w-3xl mx-auto mb-16">
          <p className="text-xs uppercase font-bold tracking-widest text-indigo-400 mb-2">Simple 3-Step Process</p>
          <h2 className="text-3xl sm:text-4xl font-extrabold text-white">How RoleRunner Accelerates Your Search</h2>
          <p className="text-slate-400 text-base mt-3">
            From raw resume ingestion to scored listings and tailored application exports in 60 seconds.
          </p>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-3 gap-8">
          {/* Step 1 */}
          <div className="relative rounded-2xl border border-slate-800 bg-[#111622] p-8 space-y-4 hover:border-slate-700 transition">
            <div className="w-12 h-12 rounded-xl bg-indigo-500/10 border border-indigo-500/20 text-indigo-400 flex items-center justify-center font-bold text-lg">
              01
            </div>
            <h3 className="text-xl font-bold text-white">Import Your Profile</h3>
            <p className="text-slate-400 text-sm leading-relaxed">
              Upload your resume in PDF, DOCX, or text. Our layout-aware engine converts your career history into structured Markdown while preserving all contact links.
            </p>
          </div>

          {/* Step 2 */}
          <div className="relative rounded-2xl border border-slate-800 bg-[#111622] p-8 space-y-4 hover:border-slate-700 transition">
            <div className="w-12 h-12 rounded-xl bg-violet-500/10 border border-violet-500/20 text-violet-400 flex items-center justify-center font-bold text-lg">
              02
            </div>
            <h3 className="text-xl font-bold text-white">Multi-Engine Discovery & Scoring</h3>
            <p className="text-slate-400 text-sm leading-relaxed">
              Scout live listings across Google, Remotive, Jobicy, and company career portals. Every job is scored on a 0.0 to 10.0 scale directly against your master skills.
            </p>
          </div>

          {/* Step 3 */}
          <div className="relative rounded-2xl border border-slate-800 bg-[#111622] p-8 space-y-4 hover:border-slate-700 transition">
            <div className="w-12 h-12 rounded-xl bg-cyan-500/10 border border-cyan-500/20 text-cyan-400 flex items-center justify-center font-bold text-lg">
              03
            </div>
            <h3 className="text-xl font-bold text-white">Tailor & Track Applications</h3>
            <p className="text-slate-400 text-sm leading-relaxed">
              Generate custom-tailored ATS resumes in Markdown, PDF, and DOCX. Track your interview pipeline, status changes, and deadlines in one unified dashboard.
            </p>
          </div>
        </div>
      </section>

      {/* Core Features Grid */}
      <section id="features" className="relative z-10 py-20 px-4 sm:px-6 lg:px-8 max-w-7xl mx-auto border-t border-slate-800/80">
        <div className="text-center max-w-3xl mx-auto mb-16">
          <p className="text-xs uppercase font-bold tracking-widest text-indigo-400 mb-2">Platform Capabilities</p>
          <h2 className="text-3xl sm:text-4xl font-extrabold text-white">Engineered for High Precision Matching</h2>
          <p className="text-slate-400 text-base mt-3">
            State-of-the-art tools designed to give you an unfair advantage in the modern job market.
          </p>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
          <div className="p-6 rounded-2xl bg-slate-900/60 border border-slate-800 space-y-3">
            <div className="p-2.5 w-fit rounded-xl bg-blue-500/10 text-blue-400 border border-blue-500/20">
              <Globe size={22} />
            </div>
            <h4 className="text-lg font-bold text-white">Parallel Multi-Feed Search</h4>
            <p className="text-slate-400 text-sm leading-relaxed">
              Aggregates job feeds concurrently from Remotive, Jobicy, Arbeitnow, and Google with schema.org JSON-LD parsing for exact locations and dates.
            </p>
          </div>

          <div className="p-6 rounded-2xl bg-slate-900/60 border border-slate-800 space-y-3">
            <div className="p-2.5 w-fit rounded-xl bg-emerald-500/10 text-emerald-400 border border-emerald-500/20">
              <Target size={22} />
            </div>
            <h4 className="text-lg font-bold text-white">Dynamic Profile Scorer</h4>
            <p className="text-slate-400 text-sm leading-relaxed">
              Evaluates true skill density, multi-word domain concepts, and title alignment on a transparent 0.0 to 10.0 scale without blackbox biases.
            </p>
          </div>

          <div className="p-6 rounded-2xl bg-slate-900/60 border border-slate-800 space-y-3">
            <div className="p-2.5 w-fit rounded-xl bg-purple-500/10 text-purple-400 border border-purple-500/20">
              <FileCheck size={22} />
            </div>
            <h4 className="text-lg font-bold text-white">PDF & Annotation Extraction</h4>
            <p className="text-slate-400 text-sm leading-relaxed">
              Reads embedded PDF hyperlink annotations (/Annots) so contact links (LinkedIn, GitHub, email) are 100% captured even from icon-only resumes.
            </p>
          </div>

          <div className="p-6 rounded-2xl bg-slate-900/60 border border-slate-800 space-y-3">
            <div className="p-2.5 w-fit rounded-xl bg-amber-500/10 text-amber-400 border border-amber-500/20">
              <Sparkles size={22} />
            </div>
            <h4 className="text-lg font-bold text-white">Instant CV Tailoring</h4>
            <p className="text-slate-400 text-sm leading-relaxed">
              Highlights the exact competencies and project achievements that recruiters and ATS scanners look for, exported in high-res PDF and Word.
            </p>
          </div>

          <div className="p-6 rounded-2xl bg-slate-900/60 border border-slate-800 space-y-3">
            <div className="p-2.5 w-fit rounded-xl bg-rose-500/10 text-rose-400 border border-rose-500/20">
              <Layers size={22} />
            </div>
            <h4 className="text-lg font-bold text-white">Full Application Tracker</h4>
            <p className="text-slate-400 text-sm leading-relaxed">
              Organize your pipeline across Applied, Interviewing, Offered, and Archived states with timeline notes and direct job URLs.
            </p>
          </div>

          <div className="p-6 rounded-2xl bg-slate-900/60 border border-slate-800 space-y-3">
            <div className="p-2.5 w-fit rounded-xl bg-cyan-500/10 text-cyan-400 border border-cyan-500/20">
              <ShieldCheck size={22} />
            </div>
            <h4 className="text-lg font-bold text-white">Private & Secure Multi-Tenancy</h4>
            <p className="text-slate-400 text-sm leading-relaxed">
              Isolated user data, tenant-scoped PostgreSQL queries, zero credential leaks, and strictly GDPR compliant document storage.
            </p>
          </div>
        </div>
      </section>

      {/* Feedback Banner CTA */}
      <section className="relative z-10 py-16 px-4 sm:px-6 lg:px-8 max-w-5xl mx-auto">
        <div className="rounded-3xl border border-indigo-500/30 bg-gradient-to-r from-indigo-950/60 via-purple-950/40 to-slate-900/80 p-8 sm:p-12 text-center space-y-6 shadow-2xl">
          <div className="inline-flex items-center gap-2 p-2 rounded-xl bg-indigo-500/20 text-indigo-300 border border-indigo-500/30 text-xs font-semibold">
            <MessageSquare size={16} /> Direct Beta Feedback Loop
          </div>
          <h2 className="text-3xl sm:text-4xl font-extrabold text-white">
            Help Us Build the Ultimate Job Search Engine
          </h2>
          <p className="text-slate-300 text-base max-w-2xl mx-auto leading-relaxed">
            Have a suggestion, found an issue, or want a specific career board integrated? We read every submission and iterate daily.
          </p>
          <div className="flex flex-wrap items-center justify-center gap-4 pt-2">
            <button
              onClick={() => setFeedbackOpen(true)}
              className="inline-flex items-center gap-2 px-6 py-3.5 text-sm font-bold text-white bg-indigo-600 hover:bg-indigo-500 rounded-xl shadow-lg transition"
            >
              <MessageSquare size={16} /> Give Product Feedback
            </button>
            <button
              onClick={onLaunch}
              className="inline-flex items-center gap-2 px-6 py-3.5 text-sm font-semibold text-slate-200 bg-slate-800 hover:bg-slate-700 border border-slate-700 rounded-xl transition"
            >
              Open Workspace <ChevronRight size={16} />
            </button>
          </div>
        </div>
      </section>

      {/* Footer */}
      <footer className="relative z-10 border-t border-slate-800/80 py-12 px-4 sm:px-6 lg:px-8 max-w-7xl mx-auto text-slate-400 text-sm">
        <div className="flex flex-col sm:flex-row items-center justify-between gap-6">
          <div className="flex items-center gap-2.5">
            <div className="w-8 h-8 rounded-lg bg-indigo-600 flex items-center justify-center text-white">
              <Zap size={18} />
            </div>
            <span className="font-bold text-white text-base">RoleRunner</span>
            <span className="text-xs text-slate-500 ml-2">© {new Date().getFullYear()} RoleRunner. All rights reserved.</span>
          </div>

          <div className="flex items-center gap-6 text-xs font-medium">
            <button onClick={() => setFeedbackOpen(true)} className="hover:text-slate-200 transition">Feedback</button>
            <a href="#features" className="hover:text-slate-200 transition">Features</a>
            <a href="#demo" className="hover:text-slate-200 transition">Demo</a>
            <button onClick={onLaunch} className="hover:text-slate-200 transition text-indigo-400 font-bold">Launch App</button>
          </div>
        </div>
      </footer>

      {/* Global Feedback Modal */}
      <FeedbackModal isOpen={feedbackOpen} onClose={() => setFeedbackOpen(false)} />
    </div>
  );
}
