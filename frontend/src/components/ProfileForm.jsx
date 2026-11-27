import { useEffect, useState } from "react";
import api from "../api";
import FieldVisibilityIcon from "./FieldVisibilityIcon";
import "../styles/Board.css";

function requirementLabel(required) {
  return required ? "required" : "optional";
}

export default function ProfileForm({
  initial,
  onSaved,
  submitLabel = "Save profile",
  showPicture = true,
  requireRequiredFields = false,
}) {
  const [username, setUsername] = useState(initial?.username || "");
  const [firstName, setFirstName] = useState(initial?.first_name || "");
  const [lastName, setLastName] = useState(initial?.last_name || "");
  const [city, setCity] = useState(initial?.city || "");
  const [state, setState] = useState(initial?.state || "");
  const [zipCode, setZipCode] = useState(initial?.zip_code || "");
  const [phone, setPhone] = useState(initial?.phone || "");
  const [contactEmail, setContactEmail] = useState(initial?.contact_email || "");
  const [pictureFile, setPictureFile] = useState(null);
  const [picturePreview, setPicturePreview] = useState(
    initial?.profile_picture_url || ""
  );
  const [clearPicture, setClearPicture] = useState(false);
  const [visibility, setVisibility] = useState(() => {
    const map = {};
    for (const f of initial?.fields || []) {
      map[f.key] = f.visibility?.value || "private";
    }
    return map;
  });
  const [error, setError] = useState("");
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    setUsername(initial?.username || "");
    setFirstName(initial?.first_name || "");
    setLastName(initial?.last_name || "");
    setCity(initial?.city || "");
    setState(initial?.state || "");
    setZipCode(initial?.zip_code || "");
    setPhone(initial?.phone || "");
    setContactEmail(initial?.contact_email || "");
    setPicturePreview(initial?.profile_picture_url || "");
    setPictureFile(null);
    setClearPicture(false);
    const map = {};
    for (const f of initial?.fields || []) {
      map[f.key] = f.visibility?.value || "private";
    }
    setVisibility(map);
  }, [initial]);

  const setVis = (key, value) => {
    setVisibility((prev) => ({ ...prev, [key]: value }));
  };

  const visLabel = (key) => {
    const opt = (initial?.visibility_options || []).find(
      (o) => o.value === visibility[key]
    );
    return opt?.label || visibility[key] || "Visibility";
  };

  const handlePictureChange = (e) => {
    const file = e.target.files?.[0];
    if (!file) return;
    setPictureFile(file);
    setClearPicture(false);
    setPicturePreview(URL.createObjectURL(file));
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    setError("");

    if (requireRequiredFields && !username.trim()) {
      setError("Username is required.");
      return;
    }

    setSaving(true);
    try {
      const formData = new FormData();
      formData.append("username", username.trim());
      formData.append("first_name", firstName.trim());
      formData.append("last_name", lastName.trim());
      formData.append("city", city.trim());
      formData.append("state", state.trim());
      formData.append("zip_code", zipCode.trim());
      formData.append("phone", phone.trim());
      formData.append("contact_email", contactEmail.trim());
      formData.append("field_visibility", JSON.stringify(visibility));
      if (pictureFile) {
        formData.append("profile_picture", pictureFile);
      }
      if (clearPicture) {
        formData.append("clear_profile_picture", "true");
      }

      const res = await api.patch("/api/me/profile/", formData, {
        headers: { "Content-Type": undefined },
      });
      if (onSaved) {
        await onSaved(res.data);
      }
    } catch (err) {
      const data = err.response?.data;
      if (typeof data === "object" && data !== null) {
        const firstKey = Object.keys(data)[0];
        const val = data[firstKey];
        setError(
          Array.isArray(val)
            ? `${firstKey}: ${val[0]}`
            : data.detail || "Could not save profile."
        );
      } else {
        setError("Could not save profile.");
      }
    } finally {
      setSaving(false);
    }
  };

  const FieldLabel = ({
    htmlFor,
    children,
    fieldKey,
    required,
    showVisibility = true,
  }) => (
    <div className="field-label-row">
      <label htmlFor={htmlFor}>
        {children}{" "}
        <span className="dashboard-meta">({requirementLabel(required)})</span>
      </label>
      {showVisibility ? (
        <FieldVisibilityIcon
          value={visibility[fieldKey] || "private"}
          label={visLabel(fieldKey)}
          onChange={(v) => setVis(fieldKey, v)}
        />
      ) : null}
    </div>
  );

  return (
    <form className="dashboard-form profile-form" onSubmit={handleSubmit}>
      {showPicture && (
        <div className="profile-form-row">
          {picturePreview && !clearPicture ? (
            <img src={picturePreview} alt="" className="profile-form-preview" />
          ) : (
            <div className="profile-form-preview profile-form-preview--empty">
              No photo
            </div>
          )}
          <div className="dashboard-field">
            <FieldLabel
              htmlFor="profile-picture"
              fieldKey="profile_picture"
              required={false}
            >
              Profile picture
            </FieldLabel>
            <input
              id="profile-picture"
              type="file"
              accept="image/*"
              onChange={handlePictureChange}
            />
            {picturePreview && !clearPicture && (
              <button
                type="button"
                className="dashboard-link-btn"
                onClick={() => {
                  setClearPicture(true);
                  setPictureFile(null);
                  setPicturePreview("");
                }}
              >
                Remove photo
              </button>
            )}
          </div>
        </div>
      )}

      <div className="profile-form-grid">
        <div className="dashboard-field">
          <FieldLabel
            htmlFor="profile-username"
            fieldKey="username"
            required
            showVisibility={false}
          >
            Username
          </FieldLabel>
          <input
            id="profile-username"
            value={username}
            onChange={(e) => setUsername(e.target.value)}
            required={requireRequiredFields}
            autoComplete="username"
          />
        </div>
        {initial?.communibetter_id && (
          <div className="dashboard-field">
            <label>CommuniBetter ID</label>
            <input
              value={initial.communibetter_id}
              readOnly
              aria-readonly="true"
            />
            <small className="dashboard-meta">
              Stable ID for messaging and cards. It never changes.
            </small>
          </div>
        )}
      </div>

      <div className="profile-form-grid">
        <div className="dashboard-field">
          <FieldLabel
            htmlFor="profile-first-name"
            fieldKey="first_name"
            required={false}
          >
            First name
          </FieldLabel>
          <input
            id="profile-first-name"
            value={firstName}
            onChange={(e) => setFirstName(e.target.value)}
            autoComplete="given-name"
          />
        </div>
        <div className="dashboard-field">
          <FieldLabel
            htmlFor="profile-last-name"
            fieldKey="last_name"
            required={false}
          >
            Last name
          </FieldLabel>
          <input
            id="profile-last-name"
            value={lastName}
            onChange={(e) => setLastName(e.target.value)}
            autoComplete="family-name"
          />
        </div>
      </div>

      <div className="profile-form-grid profile-form-grid--location">
        <div className="dashboard-field">
          <FieldLabel htmlFor="profile-city" fieldKey="city" required={false}>
            City
          </FieldLabel>
          <input
            id="profile-city"
            value={city}
            onChange={(e) => setCity(e.target.value)}
          />
        </div>
        <div className="dashboard-field">
          <FieldLabel htmlFor="profile-state" fieldKey="state" required={false}>
            State
          </FieldLabel>
          <input
            id="profile-state"
            value={state}
            onChange={(e) => setState(e.target.value)}
          />
        </div>
        <div className="dashboard-field">
          <FieldLabel htmlFor="profile-zip" fieldKey="zip_code" required={false}>
            ZIP
          </FieldLabel>
          <input
            id="profile-zip"
            value={zipCode}
            onChange={(e) => setZipCode(e.target.value)}
            autoComplete="postal-code"
          />
        </div>
      </div>

      <div className="profile-form-grid">
        <div className="dashboard-field">
          <FieldLabel htmlFor="profile-phone" fieldKey="phone" required={false}>
            Telephone
          </FieldLabel>
          <input
            id="profile-phone"
            type="tel"
            value={phone}
            onChange={(e) => setPhone(e.target.value)}
          />
        </div>
        <div className="dashboard-field">
          <FieldLabel
            htmlFor="profile-email"
            fieldKey="contact_email"
            required={false}
          >
            Email
          </FieldLabel>
          <input
            id="profile-email"
            type="email"
            value={contactEmail}
            onChange={(e) => setContactEmail(e.target.value)}
          />
        </div>
      </div>

      <p className="dashboard-meta field-visibility-legend">
        Click the icon beside a field to set visibility: Public → Share with org
        admins → Private. Username is always public.
      </p>

      {error && <p className="dashboard-error">{error}</p>}

      <button
        type="submit"
        className="dashboard-btn dashboard-btn--primary"
        disabled={saving}
      >
        {saving ? "Saving..." : submitLabel}
      </button>
    </form>
  );
}
