const ICONS = {
  public: (
    <svg width="18" height="18" viewBox="0 0 24 24" fill="none" aria-hidden>
      <path
        d="M2 12s3.5-7 10-7 10 7 10 7-3.5 7-10 7S2 12 2 12z"
        stroke="currentColor"
        strokeWidth="2"
      />
      <circle cx="12" cy="12" r="3" stroke="currentColor" strokeWidth="2" />
    </svg>
  ),
  org_admins: (
    <svg width="18" height="18" viewBox="0 0 24 24" fill="none" aria-hidden>
      <path
        d="M3 21V8l9-5 9 5v13"
        stroke="currentColor"
        strokeWidth="2"
        strokeLinejoin="round"
      />
      <path d="M9 21v-8h6v8" stroke="currentColor" strokeWidth="2" />
    </svg>
  ),
  private: (
    <svg width="18" height="18" viewBox="0 0 24 24" fill="none" aria-hidden>
      <rect
        x="5"
        y="11"
        width="14"
        height="10"
        rx="2"
        stroke="currentColor"
        strokeWidth="2"
      />
      <path
        d="M8 11V8a4 4 0 018 0v3"
        stroke="currentColor"
        strokeWidth="2"
      />
    </svg>
  ),
};

const ORDER = ["public", "org_admins", "private"];

/**
 * Cycles: Public → Share with org admins → Private.
 */
export default function FieldVisibilityIcon({
  value = "private",
  label,
  onChange,
  disabled = false,
}) {
  const current = ORDER.includes(value) ? value : "private";
  const title = label || current;

  const cycle = () => {
    if (disabled || !onChange) return;
    const idx = ORDER.indexOf(current);
    onChange(ORDER[(idx + 1) % ORDER.length]);
  };

  return (
    <button
      type="button"
      className={`field-visibility-btn field-visibility-btn--${current}`}
      onClick={cycle}
      title={title}
      aria-label={title}
      disabled={disabled}
    >
      {ICONS[current]}
    </button>
  );
}

export { ORDER as FIELD_VISIBILITY_ORDER };
