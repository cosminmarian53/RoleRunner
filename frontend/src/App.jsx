import { useState } from "react";
import { Navigate, Route, Routes } from "react-router-dom";

import AppShell from "./components/AppShell";
import Applications from "./pages/Applications";
import Auth from "./pages/Auth";
import CVBuilder from "./pages/CVBuilder";
import Dashboard from "./pages/Dashboard";
import JobSearch from "./pages/JobSearch";
import Profile from "./pages/Profile";

export default function App() {
  const [localSession, setLocalSession] = useState(() => sessionStorage.getItem("rolerunner-session") === "local");

  const continueLocally = () => {
    sessionStorage.setItem("rolerunner-session", "local");
    setLocalSession(true);
  };

  if (!localSession) return <Auth onContinue={continueLocally} />;

  return (
    <Routes>
      <Route element={<AppShell />}>
        <Route index element={<Dashboard />} />
        <Route path="profile" element={<Profile />} />
        <Route path="jobs" element={<JobSearch />} />
        <Route path="cv" element={<CVBuilder />} />
        <Route path="applications" element={<Applications />} />
      </Route>
      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
  );
}
