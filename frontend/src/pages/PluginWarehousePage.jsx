import { useEffect, useState } from "react";
import { Link, useParams } from "react-router-dom";
import api from "../api";
import AppHeader from "../components/AppHeader";
import "../styles/Dashboard.css";

export default function PluginWarehousePage() {
  const { slug } = useParams();
  const [plugins, setPlugins] = useState([]);
  const [canManage, setCanManage] = useState(false);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const [loading, setLoading] = useState(true);
  const [comments, setComments] = useState({});

  const base = slug ? `/api/organizations/${slug}/plugins/` : "/api/me/plugins/";
  const back = slug ? `/dashboard/${slug}` : "/dashboard";

  const load = () => {
    setLoading(true);
    api
      .get(base)
      .then((res) => {
        setPlugins(res.data.plugins ?? []);
        setCanManage(Boolean(res.data.can_manage));
      })
      .catch((err) => {
        setError(err.response?.data?.detail || "Could not load plugins.");
      })
      .finally(() => setLoading(false));
  };

  useEffect(() => {
    load();
  }, [base]);

  const addPlugin = async (key) => {
    setError("");
    setNotice("");
    try {
      const res = await api.post(base, { key, comment: comments[key] || "" });
      if (res.data.status === "pending") {
        setNotice(
          res.data.message ||
            "Request sent. A Communibetter state or national admin will review it."
        );
      } else if (res.data.status === "approved") {
        setNotice(res.data.message || "Plugin added.");
      }
      load();
    } catch (err) {
      setError(err.response?.data?.detail || "Could not add the plugin.");
    }
  };

  const removePlugin = async (key) => {
    setError("");
    try {
      await api.delete(`${base}${key}/`);
      load();
    } catch (err) {
      setError(err.response?.data?.detail || "Could not remove the plugin.");
    }
  };

  return (
    <div className="dashboard">
      <AppHeader />
      <main className="dashboard-main">
        <Link to={back} className="dashboard-back">
          Back
        </Link>
        <div className="dashboard-header">
          <h1>Plugin warehouse</h1>
          <p>
            {slug
              ? "Add a plugin for this organization. It stays separate from your personal plugins."
              : "Add a plugin for yourself. It stays separate from any organization you belong to."}
          </p>
        </div>
        {loading && <p className="dashboard-empty">Loading...</p>}
        {notice && <p className="dashboard-success">{notice}</p>}
        {error && <p className="dashboard-error">{error}</p>}
        {!loading &&
          plugins.map((plugin) => (
            <div className="dashboard-card" key={plugin.key}>
              <h2>{plugin.name}</h2>
              <p>{plugin.description}</p>
              {plugin.status === "pending" && (
                <p className="dashboard-success">
                  Request sent. A Communibetter state or national admin will review it.
                  {plugin.request_comment ? ` Your comment: ${plugin.request_comment}` : ""}
                </p>
              )}
              {plugin.status === "denied" && (
                <p>Denied. {plugin.decision_comment}</p>
              )}
              <div className="dashboard-actions">
                {plugin.status === "approved" && plugin.key === "nc_voter_powerquery" && (
                  <Link
                    to={slug ? `/dashboard/${slug}/plugins/nc-voter` : "/dashboard/plugins/nc-voter"}
                    className="dashboard-btn dashboard-btn--blue"
                  >
                    Open
                  </Link>
                )}
                {plugin.status === "approved" && plugin.key === "map_search" && slug && (
                  <Link
                    to={`/dashboard/${slug}/map-search`}
                    className="dashboard-btn dashboard-btn--blue"
                  >
                    Open
                  </Link>
                )}
                {plugin.installed && canManage && (
                  <button type="button" className="dashboard-btn" onClick={() => removePlugin(plugin.key)}>
                    Remove
                  </button>
                )}
                {canManage && plugin.requires_approval && plugin.status !== "approved" && (
                  <>
                    <textarea
                      rows={2}
                      placeholder="Comment for the reviewer"
                      value={comments[plugin.key] || ""}
                      onChange={(event) =>
                        setComments((current) => ({ ...current, [plugin.key]: event.target.value }))
                      }
                    />
                    <button
                      type="button"
                      className="dashboard-btn dashboard-btn--blue"
                      onClick={() => addPlugin(plugin.key)}
                    >
                      Request access
                    </button>
                  </>
                )}
                {canManage && !plugin.installed && !plugin.requires_approval && (
                  <button
                    type="button"
                    className="dashboard-btn dashboard-btn--blue"
                    onClick={() => addPlugin(plugin.key)}
                  >
                    Add Plugin
                  </button>
                )}
              </div>
            </div>
          ))}
      </main>
    </div>
  );
}
