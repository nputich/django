import privacyContent from "./content/legal/privacy-policy.md?raw";
import termsContent from "./content/legal/terms-of-service.md?raw";

/** Full legal documents linked from the site footer and registration flows. */
export const LEGAL_DOCUMENTS = {
  privacy: {
    path: "/privacy",
    title: "Privacy Policy",
    content: privacyContent,
    related: { path: "/terms", label: "Terms of Service" },
  },
  terms: {
    path: "/terms",
    title: "Terms of Service",
    content: termsContent,
    related: { path: "/privacy", label: "Privacy Policy" },
  },
};

export function getLegalDocumentByPath(pathname) {
  return Object.values(LEGAL_DOCUMENTS).find((doc) => doc.path === pathname) ?? null;
}
