import CodeLookup from "../components/CodeLookup";
import FavoriteCommunities from "../components/FavoriteCommunities";
import MarketingLayout from "../components/MarketingLayout";
import SiteLogo from "../components/SiteLogo";
import { ensureValidSession } from "../auth";
import "../styles/Landing.css";
import "../styles/CodeResults.css";
import "../styles/EnterCode.css";

/** Home and Enter Community Code share this layout. */
function Login() {
  const signedIn = ensureValidSession();
  return (
    <MarketingLayout mainClassName="landing-main landing-main--home">
      <section className="landing-hero">
        <SiteLogo withTagline />
      </section>
      {signedIn && <FavoriteCommunities />}
      <CodeLookup />
    </MarketingLayout>
  );
}

export default Login;
