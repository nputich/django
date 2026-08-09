import { useEffect, useId, useMemo, useRef, useState } from "react";

/**
 * Mobile-friendly searchable selector (combobox pattern).
 * Filters options as the user types; does not require exact prefix match.
 */
export default function SearchableSelect({
  label,
  placeholder = "Search…",
  value = null,
  options = [],
  onChange,
  disabled = false,
  loading = false,
  emptyMessage = "No matches",
  getOptionLabel = (o) => o?.name ?? "",
  getOptionKey = (o) => o?.id ?? o?.slug ?? getOptionLabel(o),
}) {
  const listId = useId();
  const [query, setQuery] = useState("");
  const [open, setOpen] = useState(false);
  const rootRef = useRef(null);

  useEffect(() => {
    if (value) {
      setQuery(getOptionLabel(value));
    }
  }, [value, getOptionLabel]);

  useEffect(() => {
    const onDoc = (event) => {
      if (!rootRef.current?.contains(event.target)) {
        setOpen(false);
        if (value) setQuery(getOptionLabel(value));
      }
    };
    document.addEventListener("mousedown", onDoc);
    return () => document.removeEventListener("mousedown", onDoc);
  }, [value, getOptionLabel]);

  const filtered = useMemo(() => {
    const q = query.trim().toLowerCase();
    if (!q) return options;
    return options.filter((opt) =>
      getOptionLabel(opt).toLowerCase().includes(q)
    );
  }, [options, query, getOptionLabel]);

  const handleSelect = (opt) => {
    onChange?.(opt);
    setQuery(getOptionLabel(opt));
    setOpen(false);
  };

  const handleClear = () => {
    onChange?.(null);
    setQuery("");
    setOpen(true);
  };

  return (
    <div className="searchable-select" ref={rootRef}>
      {label && (
        <label className="searchable-select-label" htmlFor={`${listId}-input`}>
          {label}
        </label>
      )}
      <div className="searchable-select-control">
        <input
          id={`${listId}-input`}
          type="search"
          className="searchable-select-input"
          placeholder={placeholder}
          value={query}
          disabled={disabled}
          autoComplete="off"
          aria-autocomplete="list"
          aria-expanded={open}
          aria-controls={`${listId}-list`}
          onChange={(e) => {
            setQuery(e.target.value);
            setOpen(true);
            if (value && e.target.value !== getOptionLabel(value)) {
              onChange?.(null);
            }
          }}
          onFocus={() => setOpen(true)}
        />
        {value && !disabled && (
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
        <ul
          className="searchable-select-list"
          id={`${listId}-list`}
          role="listbox"
        >
          {loading && <li className="searchable-select-empty">Loading…</li>}
          {!loading && filtered.length === 0 && (
            <li className="searchable-select-empty">{emptyMessage}</li>
          )}
          {!loading &&
            filtered.map((opt) => (
              <li key={getOptionKey(opt)}>
                <button
                  type="button"
                  className="searchable-select-option"
                  role="option"
                  onClick={() => handleSelect(opt)}
                >
                  {getOptionLabel(opt)}
                </button>
              </li>
            ))}
        </ul>
      )}
    </div>
  );
}
