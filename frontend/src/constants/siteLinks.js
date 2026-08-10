export const YOUTUBE = "https://www.youtube.com/@communib";
export const DONATE = "https://www.paypal.com/ncp/payment/YQWJCEH54LKU8";

export const NAV_LINKS = [
  { to: "/", label: "Home", icon: "home" },
  { to: "/enter-code", label: "Enter Community Code" },
  { to: "/communities", label: "Explore Communities" },
  { to: "/org", label: "Organization Accounts Pricing" },
  { to: "/knowledge-center", label: "Knowledge Center" },
  { to: DONATE, label: "Donate", external: true, primary: true },
  // Nested Product dropdown (retired):
  // {
  //   label: "Product",
  //   children: [
  //     // { to: "/demo", label: "Demo" },
  //     { to: "/org", label: "Organization Accounts" },
  //     { to: "/communities", label: "Explore Communities" },
  //   ],
  // },
];

export const FOOTER_LINKS = [
  { to: "/about", label: "About Us" },
  { to: "/contact", label: "Contact Us" },
  { to: "/careers", label: "Careers" },
  { to: "/privacy", label: "Privacy Policy" },
  { to: "/terms", label: "Terms of Service" },
  { to: YOUTUBE, label: "YouTube", external: true, icon: "youtube" },
];

export const UNDER_CONSTRUCTION_ROUTES = [
  "/pricing",
  "/product",
  "/demo",
  "/blog",
  "/org",
  "/privacy",
  "/terms",
  "/careers",
];
