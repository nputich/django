import SiteHeader from "./SiteHeader";
import SiteFooter from "./SiteFooter";
import "../../styles/AppLayout.css";

function AppLayout({ children }) {
  return (
    <div className="app-layout">
      <SiteHeader />
      <main className="app-main">{children}</main>
      <SiteFooter />
    </div>
  );
}

export default AppLayout;
