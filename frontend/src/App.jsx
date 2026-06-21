import React from "react";
import { BrowserRouter, Routes, Route, Navigate } from "react-router-dom";
import Root from "./components/Root";
import Register from "./pages/Register";
import NotFound from "./pages/NotFound";
import EnterCode from "./pages/EnterCode";
import ContactPage from "./pages/ContactPage";
import UnderConstruction from "./pages/UnderConstruction";
import SurveyPage from "./pages/SurveyPage";
import OrgHubPage from "./pages/OrgHubPage";
import MeetingPage from "./pages/MeetingPage";
import DashboardHome from "./pages/DashboardHome";
import OrgDashboard from "./pages/OrgDashboard";
import CreateSurvey from "./pages/CreateSurvey";
import CreateMeeting from "./pages/CreateMeeting";
import ProtectedRoute from "./components/ProtectedRoute";
import { clearAuth } from "./auth";
import { UNDER_CONSTRUCTION_ROUTES } from "./constants/siteLinks";

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
        <Route path="/contact" element={<ContactPage />} />
        {UNDER_CONSTRUCTION_ROUTES.map((path) => (
          <Route key={path} path={path} element={<UnderConstruction />} />
        ))}
        <Route path="/s/:id" element={<SurveyPage />} />
        <Route path="/m/:id" element={<MeetingPage />} />
        <Route path="/org/:slug/hub" element={<OrgHubPage />} />
        <Route
          path="/dashboard"
          element={
            <ProtectedRoute>
              <DashboardHome />
            </ProtectedRoute>
          }
        />
        <Route
          path="/dashboard/:slug"
          element={
            <ProtectedRoute>
              <OrgDashboard />
            </ProtectedRoute>
          }
        />
        <Route
          path="/dashboard/:slug/surveys/new"
          element={
            <ProtectedRoute>
              <CreateSurvey />
            </ProtectedRoute>
          }
        />
        <Route
          path="/dashboard/:slug/meetings/new"
          element={
            <ProtectedRoute>
              <CreateMeeting />
            </ProtectedRoute>
          }
        />
        <Route path="*" element={<NotFound />} />
      </Routes>
    </BrowserRouter>
  );
}

export default App;