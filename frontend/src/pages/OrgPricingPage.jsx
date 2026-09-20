import { useEffect, useState } from "react";
import { Link, useNavigate, useSearchParams } from "react-router-dom";
import api from "../api";
import CreateOrganizationLink from "../components/CreateOrganizationLink";
import MarketingLayout from "../components/MarketingLayout";
import SiteLogo from "../components/SiteLogo";
import { ensureValidSession } from "../auth";
import {
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
      "Create your organization, invite your community, and use core communiBetter tools at no cost.",
    features: [
      "Organization profile and messaging",
      "Public calendar events",
      "Community board: 5 posts per month",
      "View previous meetings and surveys",
    ],
    cta: "free",
  },
  {
    id: PAID_PLAN_LEVELS.STARTER,
    name: "Starter",
    price: "$19.99/month",
    description:
      "Starter plan for organizations to explore community management tools and surveys.",
    features: [
      "3 interactive meetings per month",
      "50 attendees per meeting",
      "500 survey responses per month",
      "1 AI-processed meeting per month",
    ],
    buttonLabel: "Choose Starter",
    cta: "paid",
  },
  {
    id: PAID_PLAN_LEVELS.BASIC,
    name: "Basic",
    price: "$49.99/month",
    description:
      "Dashboard tools and community engagement features for smaller organizations.",
    features: [
      "10 interactive meetings per month",
      "200 attendees per meeting",
      "2,000 survey responses per month",
      "3 AI-processed meetings per month",
    ],
    buttonLabel: "Choose Basic",
    cta: "paid",
  },
  {
    id: PAID_PLAN_LEVELS.COMMUNITY,
    name: "Community",
    price: "$125/month",
    description:
      "Higher meeting, survey, participation, and reporting capacity for active local organizations.",
    features: [
      "30 interactive meetings per month",
      "1,000 attendees per meeting",
      "15,000 survey responses per month",
      "10 AI-processed meetings per month",
    ],
    buttonLabel: "Choose Community",
    cta: "paid",
  },
  {
    id: PAID_PLAN_LEVELS.COMMUNITY_PLUS,
    name: "Community Plus",
    price: "$300/month",
    description:
      "High-capacity engagement tools for elected offices, regional organizations, and larger communities.",
    features: [
      "Unlimited interactive meetings*",
      "5,000 attendees per meeting",
      "75,000 survey responses per month",
      "30 AI-processed meetings per month",
    ],
    buttonLabel: "Choose Community Plus",
    cta: "paid",
  },
];

function registerThenCreateOrg(navigate, planId) {
  const to = createOrganizationPath(planId ? { plan: planId } : {});
  const qIndex = to.indexOf("?");
  const pathname = qIndex >= 0 ? to.slice(0, qIndex) : to;
  const search = qIndex >= 0 ? to.slice(qIndex) : "";
  navigate("/register", {
    state: { from: { pathname, search } },
  });
}

export default function OrgPricingPage() {
  const navigate = useNavigate();
  const [searchParams, setSearchParams] = useSearchParams();
  const [orgs, setOrgs] = useState(null);
  const [paypalNotice, setPaypalNotice] = useState("");

  useEffect(() => {
    if (searchParams.get("paypal") !== "cancelled") return;
    setPaypalNotice(
      "PayPal checkout was cancelled. No payment was processed."
    );
    const next = new URLSearchParams(searchParams);
    next.delete("paypal");
    setSearchParams(next, { replace: true });
  }, [searchParams, setSearchParams]);

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
    if (!ensureValidSession()) {
      registerThenCreateOrg(navigate, planId);
      return;
    }
    const list = orgs || [];
    if (list.length === 0) {
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
          {paypalNotice ? (
            <p className="org-pricing-paypal-notice" role="status">
              {paypalNotice}
            </p>
          ) : null}
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
                {plan.features?.length ? (
                  <ul className="org-pricing-features">
                    {plan.features.map((item) => (
                      <li key={item}>{item}</li>
                    ))}
                  </ul>
                ) : null}
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
          *Unlimited features remain subject to reasonable-use protections.
          Already manage an organization?{" "}
          <Link to="/dashboard">Go to your dashboard</Link>
          {" · "}
          <CreateOrganizationLink>Create another organization</CreateOrganizationLink>
        </p>
      </div>
    </MarketingLayout>
  );
}
