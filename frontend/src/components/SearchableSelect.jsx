import { useEffect, useId, useMemo, useRef, useState } from "react";

/**
 * Mobile-friendly combobox: closed control shows the selection;
 * opening reveals a search field at the top of the option list.
 */
export default function SearchableSelect({
  label,
  placeholder = "Search…",
  value = null,
  options = [],
  onChange,
  disabled = false,
  loading = false,
  clearable = true,
  emptyMessage = "No matches",
  getOptionLabel = (o) => o?.name ?? "",
  getOptionKey = (o) => o?.id ?? o?.slug ?? getOptionLabel(o),
  /** Called when the open search query changes (for remote filtering). */
  onSearch = null,
  /** Keep a fixed option pinned to the top (not filtered out when empty). */
  pinnedOptions = [],
}) {
  const listId = useId();
  const [open, setOpen] = useState(false);
  const [query, setQuery] = useState("");
  const rootRef = useRef(null);
  const searchRef = useRef(null);

  const displayLabel = value ? getOptionLabel(value) : "";

  useEffect(() => {
    const onDoc = (event) => {
      if (!rootRef.current?.contains(event.target)) {
        setOpen(false);
        setQuery("");
      }
    };
    document.addEventListener("mousedown", onDoc);
    return () => document.removeEventListener("mousedown", onDoc);
  }, []);

  useEffect(() => {
    if (!open) return;
    setQuery("");
    requestAnimationFrame(() => searchRef.current?.focus());
    onSearch?.("");
    // Only re-run when the panel opens.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [open]);

  useEffect(() => {
    if (open && onSearch) onSearch(query);
  }, [query, open, onSearch]);

  const filtered = useMemo(() => {
    const q = query.trim().toLowerCase();
    const pinnedKeys = new Set(pinnedOptions.map(getOptionKey));
    const rest = options.filter((opt) => !pinnedKeys.has(getOptionKey(opt)));
    if (!q) return [...pinnedOptions, ...rest];
    const match = (opt) => getOptionLabel(opt).toLowerCase().includes(q);
    // Always filter locally for instant feedback; remote onSearch may refine options.
    return [...pinnedOptions.filter(match), ...rest.filter(match)];
  }, [options, query, getOptionLabel, getOptionKey, pinnedOptions]);

  const handleSelect = (opt) => {
    onChange?.(opt);
    setOpen(false);
    setQuery("");
  };

  const handleClear = (event) => {
    event.stopPropagation();
    onChange?.(null);
    setQuery("");
    setOpen(true);
  };

  return (
    <div className={`searchable-select${open ? " is-open" : ""}`} ref={rootRef}>
      {label && (
        <span className="searchable-select-label" id={`${listId}-label`}>
          {label}
        </span>
      )}
      <div className="searchable-select-control">
        <button
          type="button"
          className={`searchable-select-trigger${
            clearable && value ? " has-clear" : ""
          }`}
          disabled={disabled}
          aria-haspopup="listbox"
          aria-expanded={open}
          aria-labelledby={label ? `${listId}-label` : undefined}
          onClick={() => !disabled && setOpen((v) => !v)}
        >
          <span
            className={`searchable-select-value${
              displayLabel ? "" : " searchable-select-placeholder"
            }`}
          >
            {displayLabel || placeholder}
          </span>
          <span className="searchable-select-chevron" aria-hidden="true" />
        </button>
        {clearable && value && !disabled && (
          <button
            type="button"
            className="searchable-select-clear"
            onClick={handleClear}
            aria-label="Clear selection"
          >
            ×
          </button>
        )}
      </div>
      {open && !disabled && (
        <div className="searchable-select-panel" role="presentation">
          <input
            ref={searchRef}
            id={`${listId}-input`}
            type="search"
            className="searchable-select-search"
            placeholder={placeholder}
            value={query}
            autoComplete="off"
            enterKeyHint="search"
            aria-controls={`${listId}-list`}
            aria-autocomplete="list"
            onChange={(e) => setQuery(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === "Escape") {
                setOpen(false);
                setQuery("");
              }
            }}
          />
          <ul
            className="searchable-select-list"
            id={`${listId}-list`}
            role="listbox"
            aria-labelledby={label ? `${listId}-label` : undefined}
          >
            {loading && (
              <li className="searchable-select-empty">Loading…</li>
            )}
            {!loading && filtered.length === 0 && (
              <li className="searchable-select-empty">{emptyMessage}</li>
            )}
            {!loading &&
              filtered.map((opt) => (
                <li key={String(getOptionKey(opt))}>
                  <button
                    type="button"
                    className={`searchable-select-option${
                      value && getOptionKey(value) === getOptionKey(opt)
                        ? " is-selected"
                        : ""
                    }`}
                    role="option"
                    aria-selected={
                      Boolean(value) && getOptionKey(value) === getOptionKey(opt)
                    }
                    onClick={() => handleSelect(opt)}
                  >
                    {getOptionLabel(opt)}
                  </button>
                </li>
              ))}
          </ul>
        </div>
      )}
    </div>
  );
}
