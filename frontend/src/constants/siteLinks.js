export const YOUTUBE = "https://www.youtube.com/@communib";
export const DONATE = "https://www.paypal.com/ncp/payment/YQWJCEH54LKU8";

export const NAV_LINKS = [
  { to: "/", label: "Home" },
  { to: "/enter-code", label: "Code search" },
  { to: "/product", label: "Product" },
  { to: "/demo", label: "Demo" },
  { to: "/pricing", label: "Pricing" },
  { to: "/about", label: "About us" },
  { to: "/blog", label: "Blog" },
  { to: "/org", label: "Organizations" },
  { to: "/contact", label: "Contact" },
  { to: YOUTUBE, label: "YouTube", external: true },
  { to: DONATE, label: "Donate", external: true, primary: true },
];

export const FOOTER_LINKS = [
  { to: "/privacy", label: "Privacy Policy" },
  { to: "/terms", label: "Terms and Conditions" },
  { to: "/careers", label: "Careers" },
];

export const UNDER_CONSTRUCTION_ROUTES = [
  "/about",
  "/pricing",
  "/contact",
  "/product",
  "/demo",
  "/blog",
  "/org",
  "/privacy",
  "/terms",
  "/careers",
  "/search-another-way",
];
