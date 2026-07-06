import { useState } from "react";
import { moveToIndex, moveToPosition } from "../utils/reorderList";
import "../styles/IssueList.css";

let issueIdCounter = 0;
function createIssueItem(text) {
  issueIdCounter += 1;
  return { id: `issue-${issueIdCounter}`, text: text.trim() };
}

/**
 * Participant issue card UI: type and press Enter to add, drag or set position to rank.
 */
export default function IssueCardForm({
  issues,
  onChange,
  onSubmit,
  submitting,
  error,
  alreadyAnswered,
}) {
  const [draft, setDraft] = useState("");
  const [dragIndex, setDragIndex] = useState(null);
  const [dragOverIndex, setDragOverIndex] = useState(null);
  const [positionDrafts, setPositionDrafts] = useState({});

  if (alreadyAnswered) {
    return (
      <p className="resource-note">
        Your ranked issues were submitted. Waiting for the organizer to advance.
      </p>
    );
  }

  const displayPosition = (index, id) =>
    positionDrafts[id] !== undefined ? positionDrafts[id] : String(index + 1);

  const applyReorder = (reordered) => {
    onChange(reordered);
  };

  const commitPosition = (index, id, rawValue) => {
    setPositionDrafts((prev) => {
      const next = { ...prev };
      delete next[id];
      return next;
    });
    applyReorder(moveToPosition(issues, index, rawValue));
  };

  const handleDrop = (dropIndex) => {
    if (dragIndex === null || dragIndex === dropIndex) {
      setDragIndex(null);
      setDragOverIndex(null);
      return;
    }
    applyReorder(moveToIndex(issues, dragIndex, dropIndex));
    setDragIndex(null);
    setDragOverIndex(null);
  };

  const addDraftIssue = () => {
    const text = draft.trim();
    if (!text) return;
    onChange([...issues, createIssueItem(text)]);
    setDraft("");
  };

  const handleInputKeyDown = (e) => {
    if (e.key === "Enter") {
      e.preventDefault();
      addDraftIssue();
    }
  };

  const handleFormSubmit = (e) => {
    e.preventDefault();
    if (!issues.length && draft.trim()) {
      onSubmit([createIssueItem(draft)]);
      setDraft("");
      return;
    }
    onSubmit(issues);
  };

  return (
    <form onSubmit={handleFormSubmit} className="resource-form">
      <p className="issue-list-hint">
        Type an issue and press <strong>Enter</strong> to add it. Drag the handle or
        change the position number to rank by importance (1 = most important). Entering a
        number larger than the list length moves the issue to last.
      </p>

      {issues.length === 0 ? (
        <p className="issue-list-empty">No issues added yet.</p>
      ) : (
        <ul className="issue-list" aria-label="Your issues ranked by importance">
          {issues.map((issue, index) => {
            const isDragging = dragIndex === index;
            const isDragOver = dragOverIndex === index && dragIndex !== index;
            return (
              <li
                key={issue.id}
                className={`issue-list-item${isDragging ? " issue-list-item--dragging" : ""}${
                  isDragOver ? " issue-list-item--drag-over" : ""
                }`}
                onDragOver={(e) => {
                  e.preventDefault();
                  setDragOverIndex(index);
                }}
                onDragLeave={() => {
                  if (dragOverIndex === index) setDragOverIndex(null);
                }}
                onDrop={(e) => {
                  e.preventDefault();
                  handleDrop(index);
                }}
              >
                <button
                  type="button"
                  className="issue-list-item__drag"
                  draggable
                  aria-label={`Drag issue ${index + 1}`}
                  onDragStart={(e) => {
                    setDragIndex(index);
                    e.dataTransfer.effectAllowed = "move";
                  }}
                  onDragEnd={() => {
                    setDragIndex(null);
                    setDragOverIndex(null);
                  }}
                >
                  ⋮⋮
                </button>
                <input
                  type="number"
                  min={1}
                  max={issues.length}
                  className="issue-list-item__position"
                  aria-label={`Position for issue ${index + 1}`}
                  value={displayPosition(index, issue.id)}
                  onChange={(e) =>
                    setPositionDrafts((prev) => ({
                      ...prev,
                      [issue.id]: e.target.value,
                    }))
                  }
                  onBlur={(e) => commitPosition(index, issue.id, e.target.value)}
                  onKeyDown={(e) => {
                    if (e.key === "Enter") {
                      e.preventDefault();
                      commitPosition(index, issue.id, e.currentTarget.value);
                    }
                  }}
                />
                <span className="issue-list-item__text">{issue.text}</span>
                <button
                  type="button"
                  className="issue-list-item__remove"
                  aria-label="Remove issue"
                  onClick={() => onChange(issues.filter((item) => item.id !== issue.id))}
                >
                  ×
                </button>
              </li>
            );
          })}
        </ul>
      )}

      <input
        type="text"
        className="issue-list-input"
        placeholder="Type an issue and press Enter…"
        value={draft}
        onChange={(e) => setDraft(e.target.value)}
        onKeyDown={handleInputKeyDown}
      />

      {error && <p className="landing-code-error">{error}</p>}
      <button
        type="submit"
        className="landing-code-button"
        disabled={submitting || (issues.length === 0 && !draft.trim())}
      >
        {submitting ? "Submitting..." : "Submit ranked issues"}
      </button>
    </form>
  );
}
