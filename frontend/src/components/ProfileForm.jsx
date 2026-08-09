import { useEffect, useState } from "react";
import api from "../api";
import "../styles/Board.css";

export default function ProfileForm({
  initial,
  onSaved,
  submitLabel = "Save profile",
  showPicture = true,
  requireRequiredFields = false,
}) {
  const [username, setUsername] = useState(initial?.username || "");
  const [displayName, setDisplayName] = useState(initial?.display_name || "");
  const [city, setCity] = useState(initial?.city || "");
  const [state, setState] = useState(initial?.state || "");
  const [phone, setPhone] = useState(initial?.phone || "");
  const [contactEmail, setContactEmail] = useState(initial?.contact_email || "");
  const [pictureFile, setPictureFile] = useState(null);
  const [picturePreview, setPicturePreview] = useState(initial?.profile_picture_url || "");
  const [clearPicture, setClearPicture] = useState(false);
  const [error, setError] = useState("");
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    setUsername(initial?.username || "");
    setDisplayName(initial?.display_name || "");
    setCity(initial?.city || "");
    setState(initial?.state || "");
    setPhone(initial?.phone || "");
    setContactEmail(initial?.contact_email || "");
    setPicturePreview(initial?.profile_picture_url || "");
    setPictureFile(null);
    setClearPicture(false);
  }, [initial]);

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

    if (requireRequiredFields) {
      if (!displayName.trim()) {
        setError("Name is required.");
        return;
      }
      if (!username.trim()) {
        setError("Username is required.");
        return;
      }
    }

    setSaving(true);
    try {
      const formData = new FormData();
      formData.append("username", username.trim());
      formData.append("display_name", displayName.trim());
      formData.append("city", city.trim());
      formData.append("state", state.trim());
      formData.append("phone", phone.trim());
      formData.append("contact_email", contactEmail.trim());
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
            <label htmlFor="profile-picture">Profile picture (optional)</label>
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
          <label htmlFor="profile-name">Name *</label>
          <input
            id="profile-name"
            value={displayName}
            onChange={(e) => setDisplayName(e.target.value)}
            required={requireRequiredFields}
          />
        </div>
        <div className="dashboard-field">
          <label htmlFor="profile-username">Username *</label>
          <input
            id="profile-username"
            value={username}
            onChange={(e) => setUsername(e.target.value)}
            required={requireRequiredFields}
            autoComplete="username"
          />
        </div>
      </div>

      <div className="profile-form-grid profile-form-grid--location">
        <div className="dashboard-field">
          <label htmlFor="profile-city">City</label>
          <input
            id="profile-city"
            value={city}
            onChange={(e) => setCity(e.target.value)}
          />
        </div>
        <div className="dashboard-field">
          <label htmlFor="profile-state">State</label>
          <input
            id="profile-state"
            value={state}
            onChange={(e) => setState(e.target.value)}
          />
        </div>
      </div>

      <div className="profile-form-grid">
        <div className="dashboard-field">
          <label htmlFor="profile-phone">Telephone</label>
          <input
            id="profile-phone"
            type="tel"
            value={phone}
            onChange={(e) => setPhone(e.target.value)}
          />
        </div>
        <div className="dashboard-field">
          <label htmlFor="profile-email">Email</label>
          <input
            id="profile-email"
            type="email"
            value={contactEmail}
            onChange={(e) => setContactEmail(e.target.value)}
          />
        </div>
      </div>

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
