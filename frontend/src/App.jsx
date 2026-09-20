import React from "react";
import { BrowserRouter, Routes, Route, Navigate, useLocation } from "react-router-dom";
import Root from "./components/Root";
import Register from "./pages/Register";
import NotFound from "./pages/NotFound";
import EnterCode from "./pages/EnterCode";
import CommunityDirectory from "./pages/CommunityDirectory";
import ContactPage from "./pages/ContactPage";
import AboutPage from "./pages/AboutPage";
import KnowledgeCenter from "./pages/KnowledgeCenter";
import KnowledgeCenterArticle from "./pages/KnowledgeCenterArticle";
import UnderConstruction from "./pages/UnderConstruction";
import SurveyPage from "./pages/SurveyPage";
import OrgHubPage from "./pages/OrgHubPage";
import OrgPricingPage from "./pages/OrgPricingPage";
import CreateOrganization from "./pages/CreateOrganization";
import MeetingPage from "./pages/MeetingPage";
import MeetingDetailsPage from "./pages/MeetingDetailsPage";
import MeetingResultsPage from "./pages/MeetingResultsPage";
import MeetingSummaryPage from "./pages/MeetingSummaryPage";
import MeetingHostPage from "./pages/MeetingHostPage";
import DashboardHome from "./pages/DashboardHome";
import OrgDashboard from "./pages/OrgDashboard";
import OrgBilling from "./pages/OrgBilling";
import BillingEntry from "./pages/BillingEntry";
import OrgOwnershipSettings from "./pages/OrgOwnershipSettings";
import OrgBoardSettings from "./pages/OrgBoardSettings";
import OrgRelationshipsSettings from "./pages/OrgRelationshipsSettings";
import OrgUmbrellaPortal from "./pages/OrgUmbrellaPortal";
import OrgReportsPage from "./pages/OrgReportsPage";
import OrgSharedMeetingsPage from "./pages/OrgSharedMeetingsPage";
import OrgDocumentsPage from "./pages/OrgDocumentsPage";
import PersonalBoardSettings from "./pages/PersonalBoardSettings";
import OrgDirectoryPlacement from "./pages/OrgDirectoryPlacement";
import CreateSurvey from "./pages/CreateSurvey";
import CreateMeeting from "./pages/CreateMeeting";
import EditSurvey from "./pages/EditSurvey";
import EditMeeting from "./pages/EditMeeting";
import CompleteProfile from "./pages/CompleteProfile";
import AccountSettings from "./pages/AccountSettings";
import OrgBoardPage from "./pages/OrgBoardPage";
import PersonalInboxPage from "./pages/PersonalInboxPage";
import OrgInboxPage from "./pages/OrgInboxPage";
import PublicProfilePage from "./pages/PublicProfilePage";
import ProtectedRoute from "./components/ProtectedRoute";
import { clearAuth } from "./auth";
import { UNDER_CONSTRUCTION_ROUTES } from "./constants/siteLinks";

function Logout() {
  clearAuth();
  return <Navigate to="/" replace />;
}

/** Preserve ?paypal=cancelled (and other query) when aliasing /pricing → /org. */
function PricingRedirect() {
  const { search } = useLocation();
  return <Navigate to={`/org${search}`} replace />;
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
        <Route path="/communities/*" element={<CommunityDirectory />} />
        <Route path="/explore-communities" element={<Navigate to="/communities" replace />} />
        <Route path="/search-another-way" element={<Navigate to="/communities" replace />} />
        <Route path="/contact" element={<ContactPage />} />
        <Route path="/about" element={<AboutPage />} />
        <Route path="/knowledge-center" element={<KnowledgeCenter />} />
        <Route
          path="/knowledge-center/:urlSlug"
          element={<KnowledgeCenterArticle />}
        />
        <Route path="/org" element={<OrgPricingPage />} />
        <Route path="/pricing" element={<PricingRedirect />} />
        {UNDER_CONSTRUCTION_ROUTES.map((path) => (
          <Route key={path} path={path} element={<UnderConstruction />} />
        ))}
        <Route path="/s/:id" element={<SurveyPage />} />
        <Route path="/m/:id" element={<MeetingPage />} />
        <Route path="/m/:id/details" element={<MeetingDetailsPage />} />
        <Route path="/m/:id/results" element={<MeetingResultsPage />} />
        <Route path="/m/:id/summary" element={<MeetingSummaryPage />} />
        <Route path="/org/create" element={<CreateOrganization />} />
        <Route path="/org/:slug/hub" element={<OrgHubPage />} />
        <Route path="/org/:slug/board" element={<OrgBoardPage />} />
        <Route path="/u/:username" element={<PublicProfilePage />} />
        <Route
          path="/complete-profile"
          element={
            <ProtectedRoute skipProfileCheck>
              <CompleteProfile />
            </ProtectedRoute>
          }
        />
        <Route
          path="/account"
          element={
            <ProtectedRoute>
              <AccountSettings />
            </ProtectedRoute>
          }
        />
        <Route
          path="/dashboard"
          element={
            <ProtectedRoute>
              <DashboardHome />
            </ProtectedRoute>
          }
        />
        <Route
          path="/dashboard/inbox"
          element={
            <ProtectedRoute>
              <PersonalInboxPage />
            </ProtectedRoute>
          }
        />
        <Route
          path="/dashboard/board-settings"
          element={
            <ProtectedRoute>
              <PersonalBoardSettings />
            </ProtectedRoute>
          }
        />
        <Route
          path="/dashboard/billing"
          element={
            <ProtectedRoute>
              <BillingEntry />
            </ProtectedRoute>
          }
        />
        <Route
          path="/dashboard/:slug/inbox"
          element={
            <ProtectedRoute>
              <OrgInboxPage />
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
          path="/dashboard/:slug/billing"
          element={
            <ProtectedRoute>
              <OrgBilling />
            </ProtectedRoute>
          }
        />
        <Route
          path="/dashboard/:slug/settings"
          element={
            <ProtectedRoute>
              <OrgOwnershipSettings />
            </ProtectedRoute>
          }
        />
        <Route
          path="/dashboard/:slug/board-settings"
          element={
            <ProtectedRoute>
              <OrgBoardSettings />
            </ProtectedRoute>
          }
        />
        <Route
          path="/dashboard/:slug/umbrella"
          element={
            <ProtectedRoute>
              <OrgUmbrellaPortal />
            </ProtectedRoute>
          }
        />
        <Route
          path="/dashboard/:slug/reports"
          element={
            <ProtectedRoute>
              <OrgReportsPage />
            </ProtectedRoute>
          }
        />
        <Route
          path="/dashboard/:slug/shared-with-us"
          element={
            <ProtectedRoute>
              <OrgSharedMeetingsPage />
            </ProtectedRoute>
          }
        />
        <Route
          path="/dashboard/:slug/documents"
          element={
            <ProtectedRoute>
              <OrgDocumentsPage />
            </ProtectedRoute>
          }
        />
        <Route
          path="/dashboard/:slug/relationships"
          element={
            <ProtectedRoute>
              <OrgRelationshipsSettings />
            </ProtectedRoute>
          }
        />
        <Route
          path="/dashboard/:slug/directory"
          element={
            <ProtectedRoute>
              <OrgDirectoryPlacement />
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
          path="/dashboard/:slug/surveys/:id/edit"
          element={
            <ProtectedRoute>
              <EditSurvey />
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
        <Route
          path="/dashboard/:slug/meetings/:id/edit"
          element={
            <ProtectedRoute>
              <EditMeeting />
            </ProtectedRoute>
          }
        />
        <Route
          path="/dashboard/:slug/meetings/:id/host"
          element={
            <ProtectedRoute>
              <MeetingHostPage />
            </ProtectedRoute>
          }
        />
        <Route path="*" element={<NotFound />} />
      </Routes>
    </BrowserRouter>
  );
}

export default App;