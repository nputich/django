function fieldKeyFromLabel(label, existingKeys) {
  const base = label
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, "_")
    .replace(/^_|_$/g, "")
    .slice(0, 50);
  let key = base || "field";
  let n = 2;
  while (existingKeys.has(key)) {
    key = `${base}_${n}`;
    n += 1;
  }
  return key;
}

export function emptyStandardSlide() {
  return {
    slide_type: "standard",
    title: "",
    prompt: "",
    question_format: "text",
    choices: [],
    fields: [],
  };
}

export function emptyIssueSlide(slideType) {
  return {
    slide_type: slideType,
    title: "",
    prompt:
      slideType === "political_issue_card"
        ? "Describe a policy issue that matters to you."
        : "Share a concern or suggestion.",
    question_format: "",
    choices: [],
    fields: [],
  };
}

export function emptyParticipantInfoSlide() {
  return {
    slide_type: "participant_info",
    title: "About you",
    prompt: "",
    question_format: "",
    choices: [],
    fields: [
      {
        key: "zip_code",
        label: "Zip Code",
        required: false,
        field_type: "text",
        options: [],
      },
    ],
  };
}

export function slideFromApi(slide) {
  return {
    id: slide.id,
    order: slide.order,
    slide_type: slide.slide_type,
    title: slide.title || "",
    prompt: slide.prompt || "",
    question_format: slide.question_format || "text",
    choices: Array.isArray(slide.choices) ? [...slide.choices] : [],
    fields: Array.isArray(slide.participant_fields)
      ? slide.participant_fields.map((field) => ({
          key: field.key || "",
          label: field.label || "",
          required: !!field.required,
          field_type: field.field_type || "text",
          options: Array.isArray(field.options) ? [...field.options] : [],
        }))
      : [],
  };
}

export function slideToPayload(slide, order) {
  return {
    order,
    slide_type: slide.slide_type,
    title: slide.title.trim(),
    prompt: slide.prompt.trim(),
    question_format: slide.slide_type === "standard" ? slide.question_format : "",
    choices:
      slide.slide_type === "standard" &&
      ["single_choice", "multi_choice"].includes(slide.question_format)
        ? slide.choices.filter(Boolean)
        : [],
    fields: slide.slide_type === "participant_info" ? slide.fields : [],
  };
}

export function slideTypeLabel(slideType) {
  const labels = {
    standard: "Standard question",
    participant_info: "Participant info",
    issue_card: "Issue card",
    political_issue_card: "Political issue",
  };
  return labels[slideType] || slideType.replace(/_/g, " ");
}

export function questionFormatLabel(format) {
  const labels = {
    text: "Free text",
    single_choice: "Single choice",
    multi_choice: "Multiple choice",
  };
  return labels[format] || format;
}

export function slideSummary(slide) {
  const prompt = slide.prompt || slide.title;
  if (slide.slide_type === "participant_info") {
    const count = slide.fields?.length || 0;
    return count
      ? `${count} participant question${count === 1 ? "" : "s"}`
      : "No participant questions";
  }
  if (
    slide.slide_type === "standard" &&
    ["single_choice", "multi_choice"].includes(slide.question_format)
  ) {
    const choices = slide.choices || [];
    if (!choices.length) return prompt || "Choice question (no options yet)";
    return `${prompt || "Choice question"} · Options: ${choices.join(", ")}`;
  }
  return prompt || "(No prompt yet)";
}

export default function MeetingSlideEditor({
  slide,
  order,
  expanded,
  onToggleExpand,
  onChange,
  onDelete,
  canDelete = true,
}) {
  const update = (field, value) => {
    onChange({ ...slide, [field]: value });
  };

  const updateField = (fieldIndex, key, value) => {
    const fields = slide.fields.map((field, index) =>
      index === fieldIndex ? { ...field, [key]: value } : field
    );
    if (key === "label") {
      const existingKeys = new Set(
        fields.filter((_, index) => index !== fieldIndex).map((field) => field.key)
      );
      fields[fieldIndex] = {
        ...fields[fieldIndex],
        key: fieldKeyFromLabel(String(value), existingKeys),
      };
    }
    update("fields", fields);
  };

  const addField = () => {
    const existingKeys = new Set(slide.fields.map((field) => field.key));
    const label = `Question ${slide.fields.length + 1}`;
    update("fields", [
      ...slide.fields,
      {
        key: fieldKeyFromLabel(label, existingKeys),
        label,
        required: false,
        field_type: "text",
        options: [],
      },
    ]);
  };

  const removeField = (fieldIndex) => {
    update(
      "fields",
      slide.fields.filter((_, index) => index !== fieldIndex)
    );
  };

  return (
    <div className="dashboard-card meeting-slide-editor">
      <div className="dashboard-card-header">
        <div>
          <strong>
            Slide {order} · {slideTypeLabel(slide.slide_type)}
          </strong>
          {!expanded && (
            <p className="dashboard-meta meeting-slide-summary">{slideSummary(slide)}</p>
          )}
          {!expanded &&
            slide.slide_type === "standard" &&
            slide.question_format &&
            slide.question_format !== "text" && (
              <p className="dashboard-meta">{questionFormatLabel(slide.question_format)}</p>
            )}
        </div>
        <div className="meeting-slide-actions">
          <button type="button" className="dashboard-btn" onClick={onToggleExpand}>
            {expanded ? "Done" : "Edit"}
          </button>
          {canDelete && (
            <button type="button" className="dashboard-link-btn" onClick={onDelete}>
              Delete
            </button>
          )}
        </div>
      </div>

      {expanded && (
        <div className="meeting-slide-editor-body">
          <div className="dashboard-field">
            <label>Slide type</label>
            <select
              value={slide.slide_type}
              onChange={(e) => {
                const slideType = e.target.value;
                const preserved = { id: slide.id, order: slide.order };
                if (slideType === "participant_info") {
                  onChange({ ...emptyParticipantInfoSlide(), ...preserved });
                  return;
                }
                if (slideType === "issue_card") {
                  onChange({ ...emptyIssueSlide("issue_card"), ...preserved });
                  return;
                }
                if (slideType === "political_issue_card") {
                  onChange({ ...emptyIssueSlide("political_issue_card"), ...preserved });
                  return;
                }
                onChange({ ...emptyStandardSlide(), ...preserved });
              }}
            >
              <option value="standard">Standard question</option>
              <option value="participant_info">Participant info</option>
              <option value="issue_card">Issue card</option>
              <option value="political_issue_card">Political issue card</option>
            </select>
          </div>

          <div className="dashboard-field">
            <label>Title (optional)</label>
            <input
              value={slide.title}
              onChange={(e) => update("title", e.target.value)}
              placeholder={
                slide.slide_type === "participant_info" ? "About you" : "Optional heading"
              }
            />
          </div>

          {slide.slide_type !== "participant_info" && (
            <div className="dashboard-field">
              <label>Prompt</label>
              <textarea
                value={slide.prompt}
                onChange={(e) => update("prompt", e.target.value)}
                required={slide.slide_type === "standard"}
              />
            </div>
          )}

          {slide.slide_type === "standard" && (
            <>
              <div className="dashboard-field">
                <label>Format</label>
                <select
                  value={slide.question_format}
                  onChange={(e) => update("question_format", e.target.value)}
                >
                  <option value="text">Free text</option>
                  <option value="single_choice">Single choice</option>
                  <option value="multi_choice">Multiple choice</option>
                </select>
              </div>
              {["single_choice", "multi_choice"].includes(slide.question_format) && (
                <div className="dashboard-field">
                  <label>Choices (comma-separated)</label>
                  <input
                    value={slide.choices.join(", ")}
                    onChange={(e) =>
                      update(
                        "choices",
                        e.target.value
                          .split(",")
                          .map((value) => value.trim())
                          .filter(Boolean)
                      )
                    }
                    placeholder="Option A, Option B, Option C"
                  />
                </div>
              )}
            </>
          )}

          {slide.slide_type === "participant_info" && (
            <div className="meeting-participant-fields">
              <div className="dashboard-section-header">
                <h3>Participant questions</h3>
                <button type="button" className="dashboard-btn" onClick={addField}>
                  + Add question
                </button>
              </div>
              {slide.fields.length === 0 ? (
                <p className="dashboard-empty">No participant questions yet.</p>
              ) : (
                slide.fields.map((field, fieldIndex) => (
                  <div key={field.key || fieldIndex} className="dashboard-question-block">
                    <div className="dashboard-question-header">
                      <strong>Question {fieldIndex + 1}</strong>
                      <button
                        type="button"
                        className="dashboard-link-btn"
                        onClick={() => removeField(fieldIndex)}
                      >
                        Remove
                      </button>
                    </div>
                    <div className="dashboard-field">
                      <label>Label</label>
                      <input
                        value={field.label}
                        onChange={(e) => updateField(fieldIndex, "label", e.target.value)}
                        required
                      />
                    </div>
                    <div className="dashboard-field">
                      <label>Field key</label>
                      <input value={field.key} readOnly />
                    </div>
                    <div className="dashboard-field">
                      <label>Answer type</label>
                      <select
                        value={field.field_type}
                        onChange={(e) => updateField(fieldIndex, "field_type", e.target.value)}
                      >
                        <option value="text">Text</option>
                        <option value="single_select">Single select</option>
                        <option value="multi_select">Multi select</option>
                      </select>
                    </div>
                    {["single_select", "multi_select"].includes(field.field_type) && (
                      <div className="dashboard-field">
                        <label>Options (comma-separated)</label>
                        <input
                          value={(field.options || []).join(", ")}
                          onChange={(e) =>
                            updateField(
                              fieldIndex,
                              "options",
                              e.target.value
                                .split(",")
                                .map((value) => value.trim())
                                .filter(Boolean)
                            )
                          }
                          placeholder="Option A, Option B, Option C"
                        />
                      </div>
                    )}
                    <div className="dashboard-field dashboard-field--row">
                      <label>
                        <input
                          type="checkbox"
                          checked={!!field.required}
                          onChange={(e) =>
                            updateField(fieldIndex, "required", e.target.checked)
                          }
                        />{" "}
                        Required
                      </label>
                    </div>
                  </div>
                ))
              )}
            </div>
          )}
        </div>
      )}
    </div>
  );
}
