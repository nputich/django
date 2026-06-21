import { Link, useLocation } from "react-router-dom";
import MarketingLayout from "../components/MarketingLayout";
import SiteLogo from "../components/SiteLogo";
import "../styles/Landing.css";
import "../styles/EnterCode.css";

const DEFAULT = {
  title: "Under construction",
  body: "This page is still under construction. Please check back later.",
  back: { to: "/", label: "← Back to home" },
};

const MESSAGES = {
  "/about": {
    title: "About us",
    body: "Learn more about communiB and our mission. This page is coming soon.",
    back: { to: "/", label: "← Back to home" },
  },
  "/pricing": {
    title: "Pricing",
    body: "Plans and pricing for organizations are not available yet. Please check back later.",
    back: { to: "/", label: "← Back to home" },
  },
  "/contact": {
    title: "Contact",
    body: "Our contact page is under construction. Please check back soon.",
    back: { to: "/", label: "← Back to home" },
  },
  "/product": {
    title: "Product",
    body: "Product details and features are coming soon.",
    back: { to: "/", label: "← Back to home" },
  },
  "/demo": {
    title: "Demo",
    body: "A live product demo is not available yet. Please check back later.",
    back: { to: "/", label: "← Back to home" },
  },
  "/blog": {
    title: "Blog",
    body: "News and updates from communiB will appear here soon.",
    back: { to: "/", label: "← Back to home" },
  },
  "/org": {
    title: "Organizations",
    body: "Organization sign-up and management are not available yet. Please check back later.",
    back: { to: "/", label: "← Back to home" },
  },
  "/privacy": {
    title: "Privacy Policy",
    body: "Our privacy policy is being finalized. Please check back soon.",
    back: { to: "/", label: "← Back to home" },
  },
  "/terms": {
    title: "Terms and Conditions",
    body: "Terms and conditions are being finalized. Please check back soon.",
    back: { to: "/", label: "← Back to home" },
  },
  "/careers": {
    title: "Careers",
    body: "We're not hiring yet, but we'd love to hear from you. Check back later.",
    back: { to: "/", label: "← Back to home" },
  },
  "/search-another-way": {
    title: "Coming soon",
    body: "This feature is still under construction. Please check back later.",
    back: { to: "/enter-code", label: "← Back to Enter a code" },
  },
};

export default function UnderConstruction() {
  const { pathname } = useLocation();
  const content = MESSAGES[pathname] ?? DEFAULT;

  return (
    <MarketingLayout mainClassName="landing-main enter-code-page">
      <SiteLogo variant="compact" />
      <h1 className="enter-code-title">{content.title}</h1>
      <p className="enter-code-subtitle">{content.body}</p>
      <p className="enter-code-alt">
        <Link to={content.back.to}>{content.back.label}</Link>
        {" · "}
        <Link to="/">Home</Link>
      </p>
    </MarketingLayout>
  );
}
