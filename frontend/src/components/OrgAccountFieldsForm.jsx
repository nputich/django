import { useEffect, useState } from "react";
import api from "../api";
import FieldVisibilityIcon from "./FieldVisibilityIcon";
import "../styles/Board.css";

function requirementLabel(required) {
  return required ? "required" : "optional";
}

function fieldIsEmpty(value) {
  return value == null || String(value).trim() === "";
}

function initValues(fields) {
  const values = {};
  const visibility = {};
  for (const f of fields || []) {
    values[f.key] = f.value || "";
    visibility[f.key] = f.visibility?.value || "org_admins";
  }
  return { values, visibility };
}

function fieldsSignature(fields, showOnProfile) {
  return JSON.stringify({
    showOnProfile: Boolean(showOnProfile),
    fields: (fields || []).map((f) => [
      f.key,
      f.value ?? "",
      f.visibility?.value || "",
      f.personal_value ?? "",
    ]),
  });
}

function FieldBlock({
  field,
  slug,
  value,
  onChange,
  visibility,
  onVisibility,
  personalValue,
  onUsePersonal,
  onPicture,
  clearPicture,
  onClearPicture,
  showVisibility = true,
}) {
  if (!field) return null;
  const inputType =
    field.field_type === "email"
      ? "email"
      : field.field_type === "tel"
        ? "tel"
        : "text";
  const visLabel = field.visibility?.label || visibility || "Visibility";
  const showUsePersonal =
    Boolean(field.has_personal_value) &&
    Boolean(onUsePersonal) &&
    fieldIsEmpty(clearPicture ? "" : value);

  if (field.field_type === "image") {
    const preview = clearPicture ? "" : value;
    return (
      <div className="profile-form-row" key={field.key}>
        {preview ? (
          <img src={preview} alt="" className="profile-form-preview" />
        ) : (
          <div className="profile-form-preview profile-form-preview--empty">
            ?
          </div>
        )}
        <div className="dashboard-field">
          <div className="field-label-row">
            <label htmlFor={`org-${field.key}-${slug}`}>
              {field.label}{" "}
              <span className="dashboard-meta">
                ({requirementLabel(field.required)})
              </span>
            </label>
            {showVisibility ? (
              <FieldVisibilityIcon
                value={visibility}
                label={visLabel}
                onChange={onVisibility}
              />
            ) : null}
          </div>
          <input
            id={`org-${field.key}-${slug}`}
            type="file"
            accept="image/*"
            onChange={onPicture}
          />
          {preview && (
            <button
              type="button"
              className="dashboard-link-btn"
              onClick={onClearPicture}
            >
              Remove picture
            </button>
          )}
          {showUsePersonal && (
            <button
              type="button"
              className="dashboard-link-btn"
              onClick={onUsePersonal}
            >
              Use personal profile photo
            </button>
          )}
        </div>
      </div>
    );
  }

  return (
    <div className="dashboard-field" key={field.key}>
      <div className="field-label-row">
        <label htmlFor={`org-${field.key}-${slug}`}>
          {field.label}{" "}
          <span className="dashboard-meta">
            ({requirementLabel(field.required)})
          </span>
        </label>
        {showVisibility ? (
          <FieldVisibilityIcon
            value={visibility}
            label={visLabel}
            onChange={onVisibility}
          />
        ) : null}
      </div>
      <input
        id={`org-${field.key}-${slug}`}
        type={inputType}
        value={value || ""}
        onChange={(e) => onChange(e.target.value)}
        placeholder={
          showUsePersonal && personalValue
            ? `Personal: ${personalValue}`
            : undefined
        }
        autoComplete="off"
        required={field.required}
      />
      {field.help_text && (
        <small className="dashboard-meta">{field.help_text}</small>
      )}
      {showUsePersonal && (
        <button
          type="button"
          className="dashboard-link-btn"
          onClick={onUsePersonal}
        >
          Use personal ({String(personalValue).slice(0, 40)}
          {String(personalValue).length > 40 ? "…" : ""})
        </button>
      )}
    </div>
  );
}

/**
 * One form per organization: fields shared with that org when you join.
 */
export default function OrgAccountFieldsForm({ section, onSaved }) {
  const slug = section.organization_slug;
  const memberFields = section.member_fields || [];
  const serverSignature = fieldsSignature(
    memberFields,
    section.show_membership_on_profile
  );

  const [memberValues, setMemberValues] = useState(() => initValues(memberFields).values);
  const [memberVis, setMemberVis] = useState(() => initValues(memberFields).visibility);
  const [memberPictureFile, setMemberPictureFile] = useState(null);
  const [clearMemberPicture, setClearMemberPicture] = useState(false);
  const [usePersonalKeys, setUsePersonalKeys] = useState([]);
  const [showOnProfile, setShowOnProfile] = useState(
    Boolean(section.show_membership_on_profile)
  );
  const [error, setError] = useState("");
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    const next = initValues(memberFields);
    setMemberValues(next.values);
    setMemberVis(next.visibility);
    setMemberPictureFile(null);
    setClearMemberPicture(false);
    setUsePersonalKeys([]);
    setShowOnProfile(Boolean(section.show_membership_on_profile));
    // Only re-sync when server-backed values actually change (not on parent re-render).
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [serverSignature]);

  const markUsePersonal = (key, value) => {
    setUsePersonalKeys((prev) =>
      prev.includes(key) ? prev : [...prev, key]
    );
    setMemberValues((p) => ({ ...p, [key]: value }));
    if (key === "profile_picture") {
      setClearMemberPicture(false);
      setMemberPictureFile(null);
    }
  };

  const saveMember = async (e) => {
    e.preventDefault();
    setError("");
    if (!(memberValues.username || "").trim()) {
      setError("Username is required.");
      return;
    }
    setSaving(true);
    try {
      const formData = new FormData();
      for (const f of memberFields) {
        if (f.field_type === "image") continue;
        formData.append(f.key, (memberValues[f.key] || "").trim());
      }
      formData.append("field_visibility", JSON.stringify(memberVis));
      formData.append(
        "show_membership_on_profile",
        showOnProfile ? "true" : "false"
      );
      for (const key of usePersonalKeys) {
        formData.append("use_personal", key);
      }
      if (memberPictureFile) {
        formData.append("profile_picture", memberPictureFile);
      } else if (
        !clearMemberPicture &&
        usePersonalKeys.includes("profile_picture") &&
        (memberValues.profile_picture || "").trim()
      ) {
        // Persist the personal photo URL chosen via "Use personal profile photo".
        formData.append(
          "profile_picture",
          (memberValues.profile_picture || "").trim()
        );
      }
      if (clearMemberPicture) {
        formData.append("clear_profile_picture", "true");
      }
      const res = await api.patch(
        `/api/organizations/${slug}/member-profile/`,
        formData,
        { headers: { "Content-Type": undefined } }
      );
      setUsePersonalKeys([]);
      setMemberPictureFile(null);
      setClearMemberPicture(false);
      if (onSaved) await onSaved(res.data);
    } catch (err) {
      const data = err.response?.data;
      setError(
        data?.detail ||
          (typeof data === "object" && data
            ? Object.values(data)[0]?.[0] || "Could not save fields."
            : "Could not save fields.")
      );
    } finally {
      setSaving(false);
    }
  };

  if (memberFields.length === 0) return null;

  const memberByKey = Object.fromEntries(memberFields.map((f) => [f.key, f]));

  return (
    <div className="org-account-fields">
      <form className="dashboard-form profile-form" onSubmit={saveMember}>
        <p className="dashboard-meta org-fields-intro">
          Fields this organization requests when you join. Required and optional
          are labeled. Use personal copies from your CommuniBetter account.
        </p>

        <div className="dashboard-field org-membership-public-row">
          <label className="field-checkbox-label org-membership-public-label">
            <input
              type="checkbox"
              checked={showOnProfile}
              onChange={(e) => setShowOnProfile(e.target.checked)}
            />
            <span>Display membership publicly</span>
          </label>
        </div>

        <FieldBlock
          field={memberByKey.profile_picture}
          slug={slug}
          value={memberValues.profile_picture}
          visibility={memberVis.profile_picture}
          onVisibility={(v) =>
            setMemberVis((p) => ({ ...p, profile_picture: v }))
          }
          personalValue={memberByKey.profile_picture?.personal_value}
          onUsePersonal={() => {
            const pv = memberByKey.profile_picture?.personal_value;
            if (!pv) return;
            markUsePersonal("profile_picture", pv);
          }}
          onPicture={(e) => {
            const file = e.target.files?.[0];
            if (!file) return;
            setMemberPictureFile(file);
            setClearMemberPicture(false);
            setUsePersonalKeys((prev) =>
              prev.filter((k) => k !== "profile_picture")
            );
            setMemberValues((p) => ({
              ...p,
              profile_picture: URL.createObjectURL(file),
            }));
          }}
          clearPicture={clearMemberPicture}
          onClearPicture={() => {
            setClearMemberPicture(true);
            setMemberPictureFile(null);
            setUsePersonalKeys((prev) =>
              prev.filter((k) => k !== "profile_picture")
            );
            setMemberValues((p) => ({ ...p, profile_picture: "" }));
          }}
        />

        <div className="profile-form-grid">
          <FieldBlock
            field={memberByKey.username}
            slug={slug}
            value={memberValues.username}
            onChange={(v) => setMemberValues((p) => ({ ...p, username: v }))}
            visibility={memberVis.username}
            showVisibility={false}
            personalValue={memberByKey.username?.personal_value}
            onUsePersonal={() =>
              markUsePersonal(
                "username",
                memberByKey.username?.personal_value || ""
              )
            }
          />
        </div>

        <div className="profile-form-grid">
          {["first_name", "last_name"].map((key) => (
            <FieldBlock
              key={key}
              field={memberByKey[key]}
              slug={slug}
              value={memberValues[key]}
              onChange={(v) => setMemberValues((p) => ({ ...p, [key]: v }))}
              visibility={memberVis[key]}
              onVisibility={(v) => setMemberVis((p) => ({ ...p, [key]: v }))}
              personalValue={memberByKey[key]?.personal_value}
              onUsePersonal={() =>
                markUsePersonal(key, memberByKey[key]?.personal_value || "")
              }
            />
          ))}
        </div>

        <div className="profile-form-grid profile-form-grid--location">
          {["city", "state", "zip_code"].map((key) => (
            <FieldBlock
              key={key}
              field={memberByKey[key]}
              slug={slug}
              value={memberValues[key]}
              onChange={(v) => setMemberValues((p) => ({ ...p, [key]: v }))}
              visibility={memberVis[key]}
              onVisibility={(v) => setMemberVis((p) => ({ ...p, [key]: v }))}
              personalValue={memberByKey[key]?.personal_value}
              onUsePersonal={() =>
                markUsePersonal(key, memberByKey[key]?.personal_value || "")
              }
            />
          ))}
        </div>

        <div className="profile-form-grid">
          {["phone", "contact_email"].map((key) => (
            <FieldBlock
              key={key}
              field={memberByKey[key]}
              slug={slug}
              value={memberValues[key]}
              onChange={(v) => setMemberValues((p) => ({ ...p, [key]: v }))}
              visibility={memberVis[key]}
              onVisibility={(v) => setMemberVis((p) => ({ ...p, [key]: v }))}
              personalValue={memberByKey[key]?.personal_value}
              onUsePersonal={() =>
                markUsePersonal(key, memberByKey[key]?.personal_value || "")
              }
            />
          ))}
        </div>

        {error && <p className="dashboard-error">{error}</p>}

        <button
          type="submit"
          className="dashboard-btn dashboard-btn--primary"
          disabled={saving}
        >
          {saving ? "Saving…" : `Save fields for ${section.organization_name}`}
        </button>
      </form>
    </div>
  );
}
