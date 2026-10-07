import { useEffect, useState } from "react";
import api from "../api";

function formatSubs(n) {
  if (n == null) return "—";
  if (n >= 1_000_000) return `${(n / 1_000_000).toFixed(1)}M`;
  if (n >= 1_000) return `${(n / 1_000).toFixed(1)}K`;
  return String(n);
}

function ChannelEditor({ channel, onSaved }) {
  const [state, setState] = useState(channel.state || "");
  const [zip, setZip] = useState(channel.zip_code || "");
  const [tags, setTags] = useState(
    Array.isArray(channel.tags) ? channel.tags.join(", ") : ""
  );
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState("");

  useEffect(() => {
    setState(channel.state || "");
    setZip(channel.zip_code || "");
    setTags(Array.isArray(channel.tags) ? channel.tags.join(", ") : "");
  }, [channel]);

  const save = async (e) => {
    e.preventDefault();
    setSaving(true);
    setError("");
    try {
      const res = await api.patch(
        `/api/me/youtube/channels/${encodeURIComponent(channel.channel_id)}/`,
        {
          state,
          zip_code: zip,
          tags: tags
            .split(",")
            .map((t) => t.trim())
            .filter(Boolean),
        }
      );
      onSaved(res.data);
    } catch (err) {
      setError(err.response?.data?.detail || "Could not save channel.");
    } finally {
      setSaving(false);
    }
  };

  return (
    <form className="dashboard-form map-search-channel-editor" onSubmit={save}>
      <h3>
        {channel.title || channel.channel_id}{" "}
        <span className="dashboard-meta">
          {formatSubs(channel.subscriber_count)} subscribers ·{" "}
          {formatSubs(channel.video_count)} videos
        </span>
      </h3>
      {channel.url && (
        <p className="dashboard-meta">
          <a href={channel.url} target="_blank" rel="noopener noreferrer">
            Open on YouTube
          </a>
          {channel.located ? " · on Map Search" : " · add state to appear on maps"}
        </p>
      )}
      <div className="profile-form-grid">
        <div className="dashboard-field">
          <label htmlFor={`yt-state-${channel.channel_id}`}>State</label>
          <input
            id={`yt-state-${channel.channel_id}`}
            value={state}
            onChange={(e) => setState(e.target.value)}
            placeholder="NC"
          />
        </div>
        <div className="dashboard-field">
          <label htmlFor={`yt-zip-${channel.channel_id}`}>ZIP</label>
          <input
            id={`yt-zip-${channel.channel_id}`}
            value={zip}
            onChange={(e) => setZip(e.target.value)}
            placeholder="27284"
          />
        </div>
      </div>
      <div className="dashboard-field">
        <label htmlFor={`yt-tags-${channel.channel_id}`}>Tags</label>
        <input
          id={`yt-tags-${channel.channel_id}`}
          value={tags}
          onChange={(e) => setTags(e.target.value)}
          placeholder="gaming, news, outdoor (comma-separated)"
        />
        <p className="dashboard-meta">
          Create your own tags for this channel. Used in Map Search filters.
        </p>
      </div>
      {error && <p className="dashboard-error">{error}</p>}
      <button
        type="submit"
        className="dashboard-btn dashboard-btn--primary"
        disabled={saving}
      >
        {saving ? "Saving…" : "Save channel"}
      </button>
    </form>
  );
}

export default function YouTubeChannelsSection() {
  const [channels, setChannels] = useState([]);
  const [configured, setConfigured] = useState(false);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");

  const load = async () => {
    const res = await api.get("/api/me/youtube/");
    setChannels(res.data.channels || []);
    setConfigured(Boolean(res.data.youtube_oauth_configured));
  };

  useEffect(() => {
    let cancelled = false;
    (async () => {
      setLoading(true);
      try {
        await load();
        const params = new URLSearchParams(window.location.search);
        const yt = params.get("youtube");
        if (yt === "connected") {
          setNotice("YouTube account connected. Set state, ZIP, and tags for each channel.");
        } else if (yt === "error") {
          setError("YouTube connection failed. Try again.");
        }
      } catch {
        if (!cancelled) setError("Could not load YouTube channels.");
      } finally {
        if (!cancelled) setLoading(false);
      }
    })();
    return () => {
      cancelled = true;
    };
  }, []);

  const connect = async () => {
    setError("");
    try {
      const res = await api.get("/api/me/youtube/start/");
      if (res.data.authorize_url) {
        window.location.href = res.data.authorize_url;
      }
    } catch (err) {
      if (err.response?.status === 503) {
        try {
          await api.post("/api/me/youtube/dev-stub/", {
            channel_id: "UC_LOCAL_STUB",
            title: "Local test channel",
            subscriber_count: 1000,
          });
          await load();
          setNotice("Local stub channel added (OAuth not configured).");
          return;
        } catch {
          /* fall through */
        }
      }
      setError(
        err.response?.data?.detail || "YouTube connection is not available yet."
      );
    }
  };

  const refresh = async () => {
    setError("");
    setNotice("");
    try {
      const res = await api.post("/api/me/youtube/refresh/");
      setChannels(res.data.channels || []);
      setNotice(
        res.data.cached
          ? res.data.detail || "Showing cached stats."
          : "Subscriber and video counts refreshed."
      );
    } catch (err) {
      const data = err.response?.data;
      if (data?.channels) setChannels(data.channels);
      setError(data?.detail || "Could not refresh (rate limited).");
    }
  };

  const onChannelSaved = (updated) => {
    setChannels((prev) =>
      prev.map((c) => (c.channel_id === updated.channel_id ? updated : c))
    );
    setNotice("Channel saved.");
  };

  if (loading) {
    return <p className="dashboard-empty">Loading YouTube channels…</p>;
  }

  return (
    <div className="youtube-account-section">
      <p className="dashboard-meta">
        Connect your YouTube account here. Set state, ZIP, and your own tags on
        each channel — Map Search reads this when you are a member of a map-enabled
        organization.
      </p>
      {notice && <div className="dashboard-success">{notice}</div>}
      {error && <p className="dashboard-error">{error}</p>}
      <div className="map-search-profile-actions" style={{ marginBottom: "1rem" }}>
        <button type="button" className="dashboard-btn dashboard-btn--primary" onClick={connect}>
          {channels.length ? "Reconnect YouTube" : "Sign in with YouTube"}
        </button>
        {channels.length > 0 && (
          <button type="button" className="dashboard-btn" onClick={refresh}>
            Refresh subscriber / video counts
          </button>
        )}
      </div>
      {!configured && (
        <p className="dashboard-meta">
          OAuth is not configured in this environment; a local stub may be used.
        </p>
      )}
      {channels.length === 0 ? (
        <p className="dashboard-empty">No channels connected yet.</p>
      ) : (
        channels.map((ch) => (
          <div key={ch.channel_id} className="dashboard-card" style={{ marginTop: "1rem" }}>
            <ChannelEditor channel={ch} onSaved={onChannelSaved} />
          </div>
        ))
      )}
    </div>
  );
}
