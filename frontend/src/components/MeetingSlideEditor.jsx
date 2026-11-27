import { memo, useCallback, useEffect, useRef, useState } from "react";
import api from "../api";
import TagPicker, { TagChips, resolveTags } from "./TagPicker";

const QUESTION_SLIDE_TYPES = ["standard", "issue_card", "political_issue_card"];

export function isQuestionSlide(slide) {
  return QUESTION_SLIDE_TYPES.includes(slide?.slide_type);
}

export function emptyContentSlide() {
  return {
    clientId: newClientId("slide"),
    slide_type: "content",
    title: "",
    prompt: "",
    question_format: "",
    choices: "",
    fields: [],
    body: "",
    banner_url: "",
    video_url: "",
    tag_ids: [],
    tags: [],
  };
}

function newClientId(prefix = "id") {
  return `${prefix}_${Math.random().toString(36).slice(2, 10)}`;
}

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

function cloneSlide(slide) {
  return {
    ...slide,
    choices: slide.choices,
    fields: (slide.fields || []).map((field) => ({ ...field, options: field.options })),
  };
}

/** Parse comma-separated choices; accepts string drafts or string arrays. */
export function parseChoiceList(value) {
  if (Array.isArray(value)) {
    return value.map((item) => String(item).trim()).filter(Boolean);
  }
  return String(value || "")
    .split(",")
    .map((item) => item.trim())
    .filter(Boolean);
}

function choiceListInputValue(value) {
  if (typeof value === "string") return value;
  if (Array.isArray(value)) return value.join(", ");
  return "";
}

export function emptyStandardSlide() {
  return {
    clientId: newClientId("slide"),
    slide_type: "standard",
    title: "",
    prompt: "",
    question_format: "text",
    choices: "",
    fields: [],
    tag_ids: [],
    tags: [],
  };
}

export function emptyIssueSlide(slideType) {
  return {
    clientId: newClientId("slide"),
    slide_type: slideType,
    title: "",
    prompt:
      slideType === "political_issue_card"
        ? "Describe a policy issue that matters to you."
        : "Share a concern or suggestion.",
    question_format: "",
    choices: "",
    fields: [],
    tag_ids: [],
    tags: [],
  };
}

export function emptyParticipantInfoSlide() {
  return {
    clientId: newClientId("slide"),
    slide_type: "participant_info",
    title: "About you",
    prompt: "",
    question_format: "",
    choices: "",
    fields: [
      {
        clientId: newClientId("field"),
        key: "zip_code",
        label: "Zip Code",
        required: false,
        field_type: "text",
        options: "",
      },
    ],
  };
}

export function slideFromApi(slide) {
  return {
    id: slide.id,
    clientId: newClientId("slide"),
    order: slide.order,
    slide_type: slide.slide_type,
    title: slide.title || "",
    prompt: slide.prompt || "",
    question_format: slide.question_format || "text",
    choices: Array.isArray(slide.choices) ? slide.choices.join(", ") : "",
    tag_ids: Array.isArray(slide.tag_ids) ? slide.tag_ids : [],
    tags: Array.isArray(slide.tags) ? slide.tags : [],
    added_live: !!slide.added_live,
    is_disclosure: !!slide.config?.disclosure,
    body: slide.content?.body || slide.config?.body || "",
    banner_url: slide.content?.banner_url || slide.config?.banner_url || "",
    video_url: slide.content?.video_url || slide.config?.video_url || "",
    fields: Array.isArray(slide.participant_fields)
      ? slide.participant_fields.map((field) => ({
          clientId: newClientId("field"),
          key: field.key || "",
          label: field.label || "",
          required: !!field.required,
          field_type: field.field_type || "text",
          options: Array.isArray(field.options) ? field.options.join(", ") : "",
        }))
      : [],
  };
}

/** Generate field keys from labels — call when organizer clicks Done on a slide. */
export function commitParticipantFieldKeys(slide) {
  if (slide.slide_type !== "participant_info") return slide;
  const used = new Set();
  return {
    ...slide,
    fields: (slide.fields || []).map((field) => {
      const label = (field.label || "").trim();
      if (!label) {
        return { ...field, key: "" };
      }
      const key = fieldKeyFromLabel(label, used);
      used.add(key);
      return { ...field, key, label };
    }),
  };
}

export function participantInfoSlideNeedsFieldKeys(slide) {
  if (slide.slide_type !== "participant_info") return false;
  return (slide.fields || []).some(
    (field) => (field.label || "").trim() && !(field.key || "").trim()
  );
}

export function validateSlidesForSave(slides, expandedIndex = null) {
  if (expandedIndex !== null) {
    return `Slide ${expandedIndex + 1}: click Done to finish editing before saving.`;
  }

  for (let index = 0; index < slides.length; index += 1) {
    const slide = slides[index];
    const label = `Slide ${index + 1}`;

    if (slide.slide_type === "participant_info") {
      // No fields is fine: the slide still shows the disclosure text.
      if (participantInfoSlideNeedsFieldKeys(slide)) {
        return `${label}: click Done on the demographic slide to generate field keys before saving.`;
      }
      for (const field of slide.fields) {
        if (!field.label.trim()) {
          return `${label}: each demographic question needs a label.`;
        }
        if (
          ["single_select", "multi_select"].includes(field.field_type) &&
          parseChoiceList(field.options).length < 2
        ) {
          return `${label}: "${field.label}" needs at least two choices.`;
        }
      }
    }

    if (slide.slide_type === "standard") {
      if (!slide.prompt.trim() && !slide.title.trim()) {
        return `${label}: add a prompt or title.`;
      }
      if (
        ["single_choice", "multi_choice"].includes(slide.question_format) &&
        parseChoiceList(slide.choices).length < 2
      ) {
        return `${label}: choice questions need at least two options.`;
      }
    }

    if (
      slide.slide_type === "issue_card" ||
      slide.slide_type === "political_issue_card"
    ) {
      if (!slide.prompt.trim() && !slide.title.trim()) {
        return `${label}: add a prompt or title.`;
      }
    }

    if (slide.slide_type === "content") {
      if (
        !(slide.body || "").trim() &&
        !(slide.banner_url || "").trim() &&
        !(slide.video_url || "").trim() &&
        !(slide.title || "").trim()
      ) {
        return `${label}: add text, a banner image URL, or a YouTube/Vimeo link.`;
      }
    }
  }
  return "";
}

export function slideToPayload(slide, order) {
  const usedKeys = new Set();
  const fields =
    slide.slide_type === "participant_info"
      ? (slide.fields || [])
          .filter((field) => (field.label || "").trim())
          .map((field) => {
            const label = field.label.trim();
            const key = (field.key || "").trim();
            usedKeys.add(key);
            const fieldType = field.field_type || "text";
            return {
              key,
              label,
              required: !!field.required,
              field_type: fieldType,
              options: ["single_select", "multi_select"].includes(fieldType)
                ? parseChoiceList(field.options)
                : [],
            };
          })
      : [];

  return {
    ...(slide.id ? { id: slide.id } : {}),
    order,
    slide_type: slide.slide_type,
    title: (slide.title || "").trim(),
    prompt: (slide.prompt || "").trim(),
    question_format: slide.slide_type === "standard" ? slide.question_format : "",
    choices:
      slide.slide_type === "standard" &&
      ["single_choice", "multi_choice"].includes(slide.question_format)
        ? parseChoiceList(slide.choices)
        : [],
    fields,
    ...(slide.slide_type === "content"
      ? {
          body: (slide.body || "").trim(),
          banner_url: (slide.banner_url || "").trim(),
          video_url: (slide.video_url || "").trim(),
        }
      : {}),
    ...(isQuestionSlide(slide)
      ? { tag_ids: (slide.tag_ids || []).map(Number), tag_scope: "all" }
      : {}),
  };
}

export function slideTypeLabel(slideType) {
  const labels = {
    standard: "Standard question",
    participant_info: "Participant info",
    content: "Content (banner / video / text)",
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
  if (slide.slide_type === "content") {
    const bits = [];
    if (slide.banner_url) bits.push("banner");
    if (slide.video_url) bits.push("video");
    if ((slide.body || "").trim()) bits.push("text");
    return bits.length ? bits.join(" · ") : "Empty content";
  }
  if (
    slide.slide_type === "standard" &&
    ["single_choice", "multi_choice"].includes(slide.question_format)
  ) {
    const choices = parseChoiceList(slide.choices);
    if (!choices.length) return prompt || "Choice question (no options yet)";
    return `${prompt || "Choice question"} · Options: ${choices.join(", ")}`;
  }
  return prompt || "(No prompt yet)";
}

/**
 * Self-contained question row — label/options live here so typing does not
 * re-render sibling questions or the parent slide editor.
 */
const ParticipantQuestionBlock = memo(function ParticipantQuestionBlock({
  index,
  fieldIndex,
  field,
  onRemove,
  onMetaChange,
  registerQuestionRef,
}) {
  const [label, setLabel] = useState(field.label || "");
  const [options, setOptions] = useState(choiceListInputValue(field.options));

  useEffect(() => {
    if (!field.clientId) return undefined;
    registerQuestionRef(field.clientId, {
      getField: () => ({
        clientId: field.clientId,
        key: field.key,
        label,
        options,
        field_type: field.field_type,
        required: field.required,
      }),
    });
    return () => registerQuestionRef(field.clientId, null);
  }, [
    field.clientId,
    field.field_type,
    field.key,
    field.required,
    label,
    options,
    registerQuestionRef,
  ]);

  return (
    <div className="dashboard-question-block">
      <div className="dashboard-question-header">
        <strong>Question {index + 1}</strong>
        <button type="button" className="dashboard-link-btn" onClick={() => onRemove(fieldIndex)}>
          Remove
        </button>
      </div>
      <div className="dashboard-field">
        <label>Question</label>
        <input
          value={label}
          onChange={(e) => setLabel(e.target.value)}
          placeholder="e.g. Neighborhood, Age range, Comments"
        />
      </div>
      {field.key ? (
        <div className="dashboard-field">
          <label>Field key</label>
          <input value={field.key} readOnly />
        </div>
      ) : null}
      <div className="dashboard-field">
        <label>Answer type</label>
        <select
          value={field.field_type}
          onChange={(e) => onMetaChange(fieldIndex, { field_type: e.target.value })}
        >
          <option value="text">Free text (short)</option>
          <option value="textarea">Free form (long answer)</option>
          <option value="single_select">Single choice</option>
          <option value="multi_select">Multiple choice</option>
        </select>
      </div>
      {["single_select", "multi_select"].includes(field.field_type) && (
        <div className="dashboard-field">
          <label>Choices (comma-separated)</label>
          <input
            value={options}
            onChange={(e) => setOptions(e.target.value)}
            placeholder="Option A, Option B, Option C"
          />
        </div>
      )}
      <div className="dashboard-field dashboard-field--row">
        <label>
          <input
            type="checkbox"
            checked={!!field.required}
            onChange={(e) => onMetaChange(fieldIndex, { required: e.target.checked })}
          />{" "}
          Required
        </label>
      </div>
    </div>
  );
}, (prev, next) =>
  prev.fieldIndex === next.fieldIndex &&
  prev.field.clientId === next.field.clientId &&
  prev.field.field_type === next.field.field_type &&
  prev.field.required === next.field.required &&
  prev.field.key === next.field.key);

export default function MeetingSlideEditor({
  slide,
  order,
  expanded,
  onToggleExpand,
  onChange,
  onDelete,
  canDelete = true,
  orgSlug = "",
  meetingId = null,
}) {
  const [draft, setDraft] = useState(() => cloneSlide(slide));
  const [titleDraft, setTitleDraft] = useState(slide.title || "");
  const [promptDraft, setPromptDraft] = useState(slide.prompt || "");
  const [choicesDraft, setChoicesDraft] = useState(choiceListInputValue(slide.choices));
  const wasExpandedRef = useRef(expanded);
  const questionRefs = useRef({});

  useEffect(() => {
    const wasExpanded = wasExpandedRef.current;
    if (expanded && !wasExpanded) {
      setDraft(cloneSlide(slide));
      setTitleDraft(slide.title || "");
      setPromptDraft(slide.prompt || "");
      setChoicesDraft(choiceListInputValue(slide.choices));
      questionRefs.current = {};
    } else if (!expanded && wasExpanded) {
      setDraft(cloneSlide(slide));
      setTitleDraft(slide.title || "");
      setPromptDraft(slide.prompt || "");
      setChoicesDraft(choiceListInputValue(slide.choices));
      questionRefs.current = {};
    }
    wasExpandedRef.current = expanded;
    // Only re-init draft when expand/collapse toggles, not on every slide prop change.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [expanded]);

  const updateDraftFieldMeta = useCallback((fieldIndex, patch) => {
    setDraft((current) => ({
      ...current,
      fields: current.fields.map((field, index) => {
        if (index !== fieldIndex) return field;
        return { ...field, ...patch };
      }),
    }));
  }, []);

  const registerQuestionRef = useCallback((clientId, instance) => {
    if (instance) {
      questionRefs.current[clientId] = instance;
    } else {
      delete questionRefs.current[clientId];
    }
  }, []);

  const handleRemoveField = useCallback((fieldIndex) => {
    setDraft((current) => {
      const removed = current.fields[fieldIndex];
      if (removed?.clientId) {
        delete questionRefs.current[removed.clientId];
      }
      return {
        ...current,
        fields: current.fields.filter((_, index) => index !== fieldIndex),
      };
    });
  }, []);

  const addField = () => {
    setDraft((current) => ({
      ...current,
      fields: [
        ...current.fields,
        {
          clientId: newClientId("field"),
          key: "",
          label: "",
          required: false,
          field_type: "text",
          options: "",
        },
      ],
    }));
  };

  const collectDraft = () => {
    const fields = draft.fields.map((field) => {
      const captured = questionRefs.current[field.clientId]?.getField();
      return captured || field;
    });
    return {
      ...draft,
      title: titleDraft,
      prompt: promptDraft,
      choices: choicesDraft,
      fields,
    };
  };

  const changeSlideType = (slideType) => {
    const preserved = {
      id: draft.id,
      order: draft.order,
      clientId: draft.clientId || newClientId("slide"),
    };
    if (slideType === "participant_info") {
      setDraft({ ...emptyParticipantInfoSlide(), ...preserved });
    } else if (slideType === "content") {
      setDraft({ ...emptyContentSlide(), ...preserved });
    } else if (slideType === "issue_card") {
      setDraft({ ...emptyIssueSlide("issue_card"), ...preserved });
    } else if (slideType === "political_issue_card") {
      setDraft({ ...emptyIssueSlide("political_issue_card"), ...preserved });
    } else {
      setDraft({ ...emptyStandardSlide(), ...preserved });
    }
    setTitleDraft("");
    setPromptDraft("");
    setChoicesDraft("");
    questionRefs.current = {};
  };

  const finishEditing = () => {
    if (expanded) {
      const merged = collectDraft();
      const committed =
        merged.slide_type === "participant_info"
          ? commitParticipantFieldKeys(merged)
          : merged;
      if (isQuestionSlide(committed) && orgSlug) {
        committed.tags = resolveTags(orgSlug, committed.tag_ids || []);
      }
      if (isQuestionSlide(committed) && orgSlug && committed.id && meetingId) {
        api
          .put(
            `/api/organizations/${orgSlug}/meetings/${meetingId}/slides/${committed.id}/tags/`,
            { tag_ids: committed.tag_ids || [], scope: "all" }
          )
          .catch(() => {});
      }
      onChange(committed);
      onToggleExpand();
      return;
    }
    setDraft(cloneSlide(slide));
    setTitleDraft(slide.title || "");
    setPromptDraft(slide.prompt || "");
    setChoicesDraft(choiceListInputValue(slide.choices));
    questionRefs.current = {};
    onToggleExpand();
  };

  const needsKeys =
    slide.slide_type === "participant_info" && participantInfoSlideNeedsFieldKeys(slide);

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
          {!expanded && needsKeys && (
            <p className="dashboard-error">Field keys not generated — click Edit, then Done.</p>
          )}
          {!expanded && isQuestionSlide(slide) && slide.tags?.length > 0 && (
            <p className="dashboard-meta">
              <TagChips tags={slide.tags} small />
            </p>
          )}
          {!expanded && slide.added_live && (
            <p className="dashboard-meta">Added live during a meeting</p>
          )}
          {slide.slide_type === "participant_info" && (
            <p className="dashboard-meta">
              Always shown first. Includes the automatic disclosure about sharing and
              anonymity, plus any demographic questions you add.
            </p>
          )}
        </div>
        <div className="meeting-slide-actions">
          <button type="button" className="dashboard-btn" onClick={finishEditing}>
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
              value={draft.slide_type}
              onChange={(e) => changeSlideType(e.target.value)}
            >
              <option value="standard">Standard question</option>
              <option value="content">Content (banner / video / text)</option>
              <option value="participant_info">Participant info</option>
              <option value="issue_card">Issue card</option>
              <option value="political_issue_card">Political issue card</option>
            </select>
          </div>

          <div className="dashboard-field">
            <label>Title (optional)</label>
            <input
              value={titleDraft}
              onChange={(e) => setTitleDraft(e.target.value)}
              placeholder={
                draft.slide_type === "participant_info"
                  ? "About you"
                  : draft.slide_type === "content"
                    ? "Optional heading"
                    : "Optional heading"
              }
            />
          </div>

          {draft.slide_type === "content" && (
            <>
              <div className="dashboard-field">
                <label>Text (links become clickable)</label>
                <textarea
                  value={draft.body || ""}
                  onChange={(e) =>
                    setDraft((current) => ({ ...current, body: e.target.value }))
                  }
                  rows={4}
                  placeholder="Introduce the candidate, agenda, or instructions…"
                />
              </div>
              <div className="dashboard-field">
                <label>Banner image URL</label>
                <input
                  value={draft.banner_url || ""}
                  onChange={(e) =>
                    setDraft((current) => ({ ...current, banner_url: e.target.value }))
                  }
                  placeholder="https://…"
                />
              </div>
              <div className="dashboard-field">
                <label>Video URL (YouTube or Vimeo)</label>
                <input
                  value={draft.video_url || ""}
                  onChange={(e) =>
                    setDraft((current) => ({ ...current, video_url: e.target.value }))
                  }
                  placeholder="https://www.youtube.com/watch?v=…"
                />
              </div>
            </>
          )}

          {draft.slide_type !== "participant_info" && draft.slide_type !== "content" && (
            <div className="dashboard-field">
              <label>Prompt</label>
              <textarea
                value={promptDraft}
                onChange={(e) => setPromptDraft(e.target.value)}
                required={draft.slide_type === "standard"}
              />
            </div>
          )}

          {draft.slide_type === "standard" && (
            <>
              <div className="dashboard-field">
                <label>Format</label>
                <select
                  value={draft.question_format}
                  onChange={(e) =>
                    setDraft((current) => ({ ...current, question_format: e.target.value }))
                  }
                >
                  <option value="text">Free text</option>
                  <option value="single_choice">Single choice</option>
                  <option value="multi_choice">Multiple choice</option>
                </select>
              </div>
              {["single_choice", "multi_choice"].includes(draft.question_format) && (
                <div className="dashboard-field">
                  <label>Choices (comma-separated)</label>
                  <input
                    value={choicesDraft}
                    onChange={(e) => setChoicesDraft(e.target.value)}
                    placeholder="Option A, Option B, Option C"
                  />
                </div>
              )}
            </>
          )}

          {isQuestionSlide(draft) && orgSlug && (
            <div className="dashboard-field">
              <label>Report tags</label>
              <TagPicker
                orgSlug={orgSlug}
                value={draft.tag_ids || []}
                questionText={promptDraft || titleDraft}
                onChange={(ids) => setDraft((current) => ({ ...current, tag_ids: ids }))}
              />
              <p className="dashboard-meta">
                Tags group answers for reports (e.g. all “concern” questions this quarter). You
                can add or change them any time, even after the meeting.
              </p>
            </div>
          )}

          {draft.slide_type === "participant_info" && (
            <div className="meeting-participant-fields">
              <p className="dashboard-meta">
                Participants see a disclosure at the top of this slide, generated from your
                sharing and anonymity settings. Demographic questions below are optional.
              </p>
              <div className="dashboard-section-header">
                <h3>Demographic questions</h3>
                <button type="button" className="dashboard-btn" onClick={addField}>
                  + Add question
                </button>
              </div>
              <p className="dashboard-meta">
                Type your questions freely, then click Done — field keys are generated then,
                and the meeting cannot be saved until they exist.
              </p>
              {draft.fields.length === 0 ? (
                <p className="dashboard-empty">
                  No demographic questions — participants just read the disclosure and continue.
                </p>
              ) : (
                draft.fields.map((field, fieldIndex) => (
                  <ParticipantQuestionBlock
                    key={field.clientId || `field-${fieldIndex}`}
                    index={fieldIndex}
                    fieldIndex={fieldIndex}
                    field={field}
                    onRemove={handleRemoveField}
                    onMetaChange={updateDraftFieldMeta}
                    registerQuestionRef={registerQuestionRef}
                  />
                ))
              )}
            </div>
          )}
        </div>
      )}
    </div>
  );
}
