import { Link } from "react-router-dom";
import MarketingLayout from "../components/MarketingLayout";
import SiteLogo from "../components/SiteLogo";
import "../styles/Landing.css";
import "../styles/About.css";

const BELIEFS = [
  {
    title: "Every Voice Matters",
    body: "Good ideas can come from anyone. We believe participation should be simple, accessible, and welcoming.",
  },
  {
    title: "Transparency Builds Trust",
    body: "Communities thrive when people understand how decisions are made and have opportunities to contribute.",
  },
  {
    title: "Technology Should Bring People Together",
    body: "Technology should reduce barriers to communication instead of creating them. We build tools that encourage collaboration rather than division.",
  },
  {
    title: "Common Ground Exists",
    body: "People often agree on more than they realize. Our goal is to help communities discover areas of agreement while respectfully understanding different perspectives.",
  },
];

const CAPABILITIES = [
  "Conduct interactive meetings and community discussions",
  "Collect surveys and public feedback",
  "Organize and prioritize issues submitted by participants",
  "Generate AI-powered summaries and reports",
  "Understand community priorities through meaningful analytics",
  "Build stronger communication between leaders and members",
];

const COMMUNITIES = [
  "Local governments",
  "Neighborhood associations",
  "Nonprofits",
  "Schools and universities",
  "Businesses",
  "Community groups",
  "Faith organizations",
  "Professional associations",
  "Clubs",
  "Advocacy organizations",
];

export default function AboutPage() {
  return (
    <MarketingLayout mainClassName="landing-main about-page">
      <header className="landing-hero about-hero">
        <SiteLogo />
        <h1 className="about-title">About Us</h1>
        <p className="about-lead">
          <strong>Better Communities Start Here</strong>
        </p>
        <p className="about-intro">
          CommuniB was created with a simple belief: every community makes better
          decisions when more people can participate, understand one another, and
          work toward common goals.
        </p>
        <p className="about-intro">
          Whether you&apos;re part of a neighborhood, nonprofit, business, school,
          government agency, club, or advocacy organization, CommuniB provides the
          tools to bring people together, gather meaningful feedback, and transform
          ideas into action.
        </p>
        <p className="about-intro about-intro--emphasis">
          Our mission is to help communities communicate more effectively, discover
          consensus, and make informed decisions.
        </p>
      </header>

      <section className="about-section">
        <h2>Our Vision</h2>
        <p>
          We envision a world where every organization has access to clear,
          organized, and constructive community input.
        </p>
        <p>
          Too often, valuable ideas are lost in long meetings, scattered emails,
          social media discussions, or surveys that fail to capture what matters
          most. CommuniB helps organize those conversations into information that
          leaders and community members can actually use.
        </p>
        <p>
          By combining modern collaboration tools with artificial intelligence, we
          make it easier to identify major issues, summarize discussions, recognize
          shared priorities, and help communities move forward together.
        </p>
      </section>

      <section className="about-section">
        <h2>What We Believe</h2>
        <ul className="about-beliefs">
          {BELIEFS.map((belief) => (
            <li key={belief.title}>
              <h3>{belief.title}</h3>
              <p>{belief.body}</p>
            </li>
          ))}
        </ul>
      </section>

      <section className="about-section">
        <h2>What CommuniB Does</h2>
        <p>CommuniB provides organizations with tools to:</p>
        <ul className="about-list">
          {CAPABILITIES.map((item) => (
            <li key={item}>{item}</li>
          ))}
        </ul>
        <p>
          Whether you&apos;re planning a town hall, managing a nonprofit, gathering
          employee feedback, or engaging members of a local organization, CommuniB
          helps turn participation into actionable insights.
        </p>
      </section>

      <section className="about-section">
        <h2>Designed for Every Community</h2>
        <p>
          CommuniB is built to support organizations of every size, including:
        </p>
        <ul className="about-list about-list--columns">
          {COMMUNITIES.map((item) => (
            <li key={item}>{item}</li>
          ))}
        </ul>
        <p>
          Our platform is designed to be flexible because every community has
          different goals, members, and ways of working together.
        </p>
      </section>

      <section className="about-section">
        <h2>Powered by AI, Guided by People</h2>
        <p>
          Artificial intelligence can help organize information, identify themes,
          and summarize discussions. People remain at the center of every decision.
        </p>
        <p>
          CommuniB uses AI to reduce administrative work and help participants and
          leaders better understand community conversations. This allows more time
          to focus on solving problems together.
        </p>
      </section>

      <section className="about-section">
        <h2>Building Stronger Communities</h2>
        <p>Our long-term vision extends beyond meetings and surveys.</p>
        <p>
          We believe communities benefit from better access to information, stronger
          communication, greater participation, and deeper understanding. By helping
          organizations listen more effectively and members engage more meaningfully,
          we hope to strengthen the relationships that make communities successful.
        </p>
        <p>
          When people are informed, heard, and connected, better decisions become
          possible.
        </p>
      </section>

      <section className="about-section about-section--cta">
        <h2>Join Us</h2>
        <p>
          Whether you&apos;re leading an organization or looking for a better way to
          participate in your community, CommuniB is here to help.
        </p>
        <p>
          Together, we can build communities that are more informed, more engaged,
          and better equipped to shape their future.
        </p>
        <div className="about-actions">
          <Link to="/contact" className="about-btn about-btn--primary">
            Contact us
          </Link>
          <Link to="/pricing" className="about-btn">
            View pricing
          </Link>
          <Link to="/enter-code" className="about-btn">
            Enter a community code
          </Link>
        </div>
      </section>

      <p className="about-back">
        <Link to="/">← Back to home</Link>
      </p>
    </MarketingLayout>
  );
}
