import { useState } from "react";
import { Navigate, Route, Routes, useNavigate } from "react-router-dom";

import AppShell from "./components/AppShell";
import Applications from "./pages/Applications";
import Auth from "./pages/Auth";
import CVBuilder from "./pages/CVBuilder";
import Dashboard from "./pages/Dashboard";
import JobSearch from "./pages/JobSearch";
import Landing from "./pages/Landing";
import Profile from "./pages/Profile";

export default function App() {
  const [_localSession, setLocalSession] = useState(() => sessionStorage.getItem("rolerunner-session") === "local");
  const navigate = useNavigate();

  const continueLocally = () => {
    sessionStorage.setItem("rolerunner-session", "local");
    setLocalSession(true);
    navigate("/dashboard");
  };

  return (
    <Routes>
      {/* Public Landing Page */}
      <Route path="/" element={<Landing onLaunch={continueLocally} />} />

      {/* Auth Gate */}
      <Route
        path="/auth"
        element={<Auth onContinue={continueLocally} />}
      />

      {/* App Workspace */}
      <Route element={<AppShell />}>
        <Route path="dashboard" element={<Dashboard />} />
        <Route path="profile" element={<Profile />} />
        <Route path="jobs" element={<JobSearch />} />
        <Route path="cv" element={<CVBuilder />} />
        <Route path="applications" element={<Applications />} />
      </Route>

      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
  );
}
