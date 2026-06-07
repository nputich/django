import React from "react";
import { BrowserRouter, Routes, Route, Navigate } from "react-router-dom";
import Root from "./components/Root";
import Register from "./pages/Register";
import NotFound from "./pages/NotFound";
import EnterCode from "./pages/EnterCode";
import UnderConstruction from "./pages/UnderConstruction";
import SurveyPage from "./pages/SurveyPage";
import OrgHubPage from "./pages/OrgHubPage";
import MeetingPage from "./pages/MeetingPage";
import { clearAuth } from "./auth";

function Logout() {
  clearAuth();
  return <Navigate to="/" replace />;
}

function App() {
  return (
    <BrowserRouter>
      <Routes>
        <Route path="/" element={<Root />} />
        <Route path="/app" element={<Navigate to="/" replace />} />
        <Route path="/login" element={<Navigate to="/" replace />} />
        <Route path="/register" element={<Register />} />
        <Route path="/logout" element={<Logout />} />
        <Route path="/enter-code" element={<EnterCode />} />
        <Route path="/search-another-way" element={<UnderConstruction />} />
        <Route path="/org" element={<UnderConstruction />} />
        <Route path="/s/:id" element={<SurveyPage />} />
        <Route path="/m/:id" element={<MeetingPage />} />
        <Route path="/org/:slug/hub" element={<OrgHubPage />} />
        <Route path="*" element={<NotFound />} />
      </Routes>
    </BrowserRouter>
  );
}

export default App;