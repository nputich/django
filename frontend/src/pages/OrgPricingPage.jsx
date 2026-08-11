import { useEffect, useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import api from "../api";
import CreateOrganizationLink from "../components/CreateOrganizationLink";
import MarketingLayout from "../components/MarketingLayout";
import SiteLogo from "../components/SiteLogo";
import { ensureValidSession } from "../auth";
import {
  CREATE_ORGANIZATION_PATH,
  PAID_PLAN_LEVELS,
  createOrganizationPath,
} from "../constants/orgCreation";
import "../styles/Landing.css";
import "../styles/OrgPricing.css";

const PLANS = [
  {
    id: "FREE",
    name: "Free Organization",
    price: "$0",
    description:
      "Create your organization, invite your community, and use core CommuniB tools at no cost.",
    cta: "free",
  },
  {
    id: PAID_PLAN_LEVELS.BASIC,
    name: "Basic",
    price: "$49.99/month",
    description:
      "Dashboard tools and community engagement features for smaller organizations.",
    buttonLabel: "Choose Basic",
    cta: "paid",
  },
  {
    id: PAID_PLAN_LEVELS.COMMUNITY,
    name: "Community",
    price: "$125/month",
    description:
      "Higher meeting, survey, participation, and reporting capacity for active local organizations.",
    buttonLabel: "Choose Community",
    cta: "paid",
  },
  {
    id: PAID_PLAN_LEVELS.COMMUNITY_PLUS,
    name: "Community Plus",
    price: "$300/month",
    description:
      "High-capacity engagement tools for elected offices, regional organizations, and larger communities.",
    buttonLabel: "Choose Community Plus",
    cta: "paid",
  },
];

export default function OrgPricingPage() {
  const navigate = useNavigate();
  const [orgs, setOrgs] = useState(null);

  useEffect(() => {
    if (!ensureValidSession()) {
      setOrgs([]);
      return;
    }
    api
      .get("/api/me/organizations/")
      .then((res) => setOrgs(res.data.organizations ?? []))
      .catch(() => setOrgs([]));
  }, []);

  const handlePaidPlan = (planId) => {
    const list = orgs || [];
    if (!ensureValidSession() || list.length === 0) {
      navigate(createOrganizationPath({ plan: planId }));
      return;
    }
    if (list.length === 1) {
      navigate(`/dashboard/${list[0].slug}/billing`, {
        state: { intendedPlan: planId },
      });
      return;
    }
    navigate("/dashboard/billing", { state: { intendedPlan: planId } });
  };

  return (
    <MarketingLayout mainClassName="landing-main">
      <section className="landing-hero">
        <SiteLogo />
      </section>

      <div className="org-pricing-page">
        <header className="org-pricing-header">
          <h1 className="org-pricing-title">Organization Accounts</h1>
          <p className="org-pricing-lead">
            Start free, then choose a plan that fits your community when you are
            ready.
          </p>
        </header>

        <ul className="org-pricing-list">
          {PLANS.map((plan) => (
            <li
              key={plan.id}
              className={`org-pricing-card${
                plan.id === "FREE" ? " org-pricing-card--free" : ""
              }`}
            >
              <div className="org-pricing-copy">
                <h2 className="org-pricing-name">{plan.name}</h2>
                <p className="org-pricing-price">{plan.price}</p>
                <p className="org-pricing-desc">{plan.description}</p>
              </div>
              {plan.cta === "free" ? (
                <CreateOrganizationLink
                  asButton
                  className="create-org-link create-org-link--button"
                >
                  Create an Organization
                </CreateOrganizationLink>
              ) : (
                <button
                  type="button"
                  className="org-pricing-btn"
                  onClick={() => handlePaidPlan(plan.id)}
                >
                  {plan.buttonLabel}
                </button>
              )}
            </li>
          ))}
        </ul>

        <p className="org-pricing-footnote">
          Already manage an organization?{" "}
          <Link to="/dashboard">Go to your dashboard</Link>
          {" · "}
          <Link to={CREATE_ORGANIZATION_PATH}>Create another organization</Link>
        </p>
      </div>
    </MarketingLayout>
  );
}
