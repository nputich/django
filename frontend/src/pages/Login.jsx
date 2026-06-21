import CodeLookup from "../components/CodeLookup";
import MarketingLayout from "../components/MarketingLayout";
import SiteLogo from "../components/SiteLogo";
import "../styles/Landing.css";
import "../styles/CodeResults.css";

function Login() {
  return (
    <MarketingLayout mainClassName="landing-main landing-main--home">
      <section className="landing-hero">
        <SiteLogo />
      </section>
      <CodeLookup />
    </MarketingLayout>
  );
}

export default Login;
