import { useEffect, useRef, useState } from "react";
import { Link, useParams } from "react-router-dom";
import api from "../api";
import AppHeader from "../components/AppHeader";
import PluginAccessQueue from "../components/PluginAccessQueue";
import "../styles/Dashboard.css";

function downloadBlob(data, filename, type) {
  const blob = new Blob([data], { type });
  const url = URL.createObjectURL(blob);
  const link = document.createElement("a");
  link.href = url;
  link.download = filename;
  link.click();
  URL.revokeObjectURL(url);
}

export default function NcVoterPluginPage() {
  const { slug } = useParams();
  const root = slug
    ? `/api/organizations/${slug}/plugins/nc-voter`
    : "/api/me/plugins/nc-voter";
  const back = slug ? `/dashboard/${slug}/plugins` : "/dashboard/plugins";

  const [files, setFiles] = useState([]);
  const [canOfficial, setCanOfficial] = useState(false);
  const [error, setError] = useState("");
  const [accessNote, setAccessNote] = useState("");
  const [uploadNote, setUploadNote] = useState("");
  const [fileA, setFileA] = useState("");
  const [fileB, setFileB] = useState("");
  const [county, setCounty] = useState("");
  const [compare, setCompare] = useState(null);
  const [queryFile, setQueryFile] = useState("");
  const [queryName, setQueryName] = useState("");
  const [queryParty, setQueryParty] = useState("");
  const [rows, setRows] = useState([]);
  const [previews, setPreviews] = useState({});
  const [showViewer, setShowViewer] = useState(false);
  const [askKind, setAskKind] = useState(false);
  const [uploadLabel, setUploadLabel] = useState("");
  const fileInputRef = useRef(null);
  const officialRef = useRef(false);
  const labelRef = useRef("");
  const [previewFileId, setPreviewFileId] = useState("");
  const [listId, setListId] = useState("");
  const [match, setMatch] = useState(null);

  const choosePreviewFile = (fileId) => {
    setPreviewFileId(fileId);
    if (!fileId || previews[fileId]) return;
    api
      .get(`${root}/files/${fileId}/browse/?preview=1`)
      .then((res) => {
        setPreviews((current) => ({ ...current, [fileId]: res.data.rows || [] }));
      })
      .catch(() => {
        setPreviews((current) => ({ ...current, [fileId]: [] }));
        setError("Could not load a preview of that file.");
      });
  };

  const load = () => {
    api
      .get(`${root}/files/`)
      .then((res) => {
        setFiles(res.data.files ?? []);
        setCanOfficial(Boolean(res.data.can_submit_official));
        setAccessNote("");
      })
      .catch((err) => {
        const data = err.response?.data || {};
        if (data.status === "pending" || data.status === "denied") {
          setAccessNote(data.detail || "This plugin is waiting for approval.");
          setError("");
          return;
        }
        setError(data.detail || "Could not load voter files.");
      });
  };

  useEffect(() => {
    load();
  }, [root]);

  useEffect(() => {
    const processing = files.some((file) => file.status === "queued" || file.status === "parsing");
    if (!processing) return undefined;
    const timer = setInterval(load, 3000);
    return () => clearInterval(timer);
  }, [files, root]);

  const beginUpload = () => {
    setAskKind(true);
  };

  const pickUploadKind = (official) => {
    officialRef.current = official;
    labelRef.current = uploadLabel.trim();
    setAskKind(false);
    fileInputRef.current?.click();
  };

  const upload = async (event, source, official = false) => {
    const chosen = event.target.files?.[0];
    event.target.value = "";
    if (!chosen) return;
    const body = new FormData();
    body.append("file", chosen);
    body.append("label", labelRef.current);
    if (!official) body.append("source", source);
    setError("");
    setUploadNote("Uploading… 0%");
    try {
      const url = official ? "/api/plugins/nc-voter/official/" : `${root}/files/`;
      const res = await api.post(url, body, {
        onUploadProgress: (event) => {
          if (!event.total) return;
          const percent = Math.min(100, Math.round((event.loaded / event.total) * 100));
          setUploadNote(`Uploading… ${percent}%`);
        },
      });
      const stored = res.data.row_count ?? 0;
      const skipped = res.data.rows_skipped ?? 0;
      if (res.data.status === "ready") {
        setUploadNote(
          `Processing finished. ${stored} records stored, ${skipped} skipped.`
        );
      } else {
        setUploadNote(
          "Upload received. Processing continues on the server. You can leave this page and come back."
        );
      }
      load();
    } catch (err) {
      setUploadNote("");
      setError(err.response?.data?.detail || "Upload failed.");
    }
  };

  const runCompare = async () => {
    setError("");
    try {
      const res = await api.post(`${root}/compare/`, {
        file_a: Number(fileA),
        file_b: Number(fileB),
        county,
      });
      setCompare(res.data);
    } catch (err) {
      setError(err.response?.data?.detail || "Compare failed.");
    }
  };

  const runQuery = async () => {
    setError("");
    try {
      const res = await api.post(`${root}/files/${queryFile}/query/`, {
        name: queryName,
        county,
        party: queryParty,
        limit: 100,
      });
      setRows(res.data.rows ?? []);
    } catch (err) {
      setError(err.response?.data?.detail || "Query failed.");
    }
  };

  const exportQuery = async () => {
    const res = await api.post(
      `${root}/files/${queryFile}/export/`,
      { name: queryName, county, party: queryParty },
      { responseType: "blob" }
    );
    downloadBlob(res.data, "voter-query.csv", "text/csv");
  };

  const runMatch = async () => {
    setError("");
    try {
      const res = await api.post(`${root}/match/`, {
        file_id: Number(queryFile || fileA),
        list_id: Number(listId),
      });
      setMatch(res.data);
    } catch (err) {
      setError(err.response?.data?.detail || "List compare failed.");
    }
  };

  const downloadPackets = async () => {
    const res = await api.post(
      `${root}/county-packets/`,
      { file_a: Number(fileA), file_b: Number(fileB), missing_side: "only_in_a", county },
      { responseType: "blob" }
    );
    downloadBlob(res.data, "county-voter-packets.zip", "application/zip");
  };

  const ready = files.filter((file) => file.status === "ready");

  return (
    <div className="dashboard">
      <AppHeader />
      <main className="dashboard-main">
        <Link to={back} className="dashboard-back">
          Back to warehouse
        </Link>
        <div className="dashboard-header">
          <h1>NC Voter Record PowerQuery</h1>
          <p>Upload a North Carolina voter extract, or query the official file when one is on file.</p>
        </div>
        {accessNote && <p className="dashboard-success">{accessNote}</p>}
        {uploadNote && <p className="dashboard-success">{uploadNote}</p>}
        {error && <p className="dashboard-error">{error}</p>}

        <PluginAccessQueue slug={slug} />

        <section className="dashboard-card">
          <h2>Files</h2>
          <button type="button" className="dashboard-btn dashboard-btn--blue" onClick={beginUpload}>
            Upload voter file
          </button>{" "}
          <button type="button" className="dashboard-btn" disabled>
            Upload comparison list
          </button>
          <input
            ref={fileInputRef}
            type="file"
            accept=".txt,.tsv,.csv,.zip"
            hidden
            onChange={(event) => upload(event, "owner_upload", officialRef.current)}
          />
          {askKind && (
            <div>
              <p className="dashboard-meta">Name this file, then choose it.</p>
              <input
                placeholder="File name"
                value={uploadLabel}
                onChange={(event) => setUploadLabel(event.target.value)}
              />{" "}
              {canOfficial ? (
                <>
                  <p className="dashboard-meta">Is this the official Communibetter file, or your own unofficial file?</p>
                  <button type="button" className="dashboard-btn dashboard-btn--blue" onClick={() => pickUploadKind(true)}>
                    Official
                  </button>{" "}
                  <button type="button" className="dashboard-btn" onClick={() => pickUploadKind(false)}>
                    Unofficial
                  </button>{" "}
                </>
              ) : (
                <button type="button" className="dashboard-btn dashboard-btn--blue" onClick={() => pickUploadKind(false)}>
                  Choose file
                </button>
              )}{" "}
              <button type="button" className="dashboard-btn" onClick={() => setAskKind(false)}>
                Cancel
              </button>
              {canOfficial && (
                <p className="dashboard-meta">
                  A new official file replaces the current one. The previous file is kept for comparison. Older official files are deleted.
                </p>
              )}
            </div>
          )}
          <ul>
            {files.map((file) => (
              <li key={file.id}>
                {file.label || file.original_filename || "file"} · {file.source} · {file.status}
                {file.status === "queued" ? " · upload received, waiting to process" : ""}
                {file.status === "parsing"
                  ? ` · processing ${file.row_count || 0} stored, ${file.rows_skipped || 0} skipped`
                  : ""}
                {file.status === "ready"
                  ? ` · ${file.row_count || 0} stored, ${file.rows_skipped || 0} skipped`
                  : ""}
                {file.error ? ` · ${file.error}` : ""}
                {file.rows_skipped > 0 && file.skip_samples?.length ? (
                  <div className="dashboard-meta">{file.skip_samples.join(" · ")}</div>
                ) : null}
              </li>
            ))}
            {files.length === 0 && <li>No files yet.</li>}
          </ul>
          <button
            type="button"
            className="dashboard-btn dashboard-btn--blue"
            onClick={() => setShowViewer((open) => !open)}
            disabled={ready.length === 0}
          >
            {showViewer ? "Hide voter file" : "View voter file"}
          </button>
          {showViewer && (
            <div>
              <select value={previewFileId} onChange={(event) => choosePreviewFile(event.target.value)}>
                <option value="">Select a voter file</option>
                {ready.map((file) => (
                  <option key={file.id} value={file.id}>
                    {file.label || file.original_filename || `File ${file.id}`}
                  </option>
                ))}
              </select>
              {previewFileId && (
                <table>
                  <caption className="dashboard-meta">First stored records</caption>
                  <thead>
                    <tr>
                      <th>County</th>
                      <th>NCID</th>
                      <th>Name</th>
                      <th>Address</th>
                      <th>Status</th>
                      <th>Party</th>
                    </tr>
                  </thead>
                  <tbody>
                    {!previews[previewFileId] && (
                      <tr>
                        <td colSpan={6}>Loading preview…</td>
                      </tr>
                    )}
                    {previews[previewFileId]?.length === 0 && (
                      <tr>
                        <td colSpan={6}>No stored records to preview.</td>
                      </tr>
                    )}
                    {(previews[previewFileId] || []).map((row) => (
                      <tr key={row.ncid}>
                        <td>{row.county}</td>
                        <td>{row.ncid}</td>
                        <td>
                          {row.first_name} {row.last_name}
                        </td>
                        <td>{row.address}</td>
                        <td>{row.status}</td>
                        <td>{row.party}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              )}
            </div>
          )}
        </section>

        <section className="dashboard-card">
          <h2>Compare</h2>
          <select value={fileA} onChange={(event) => setFileA(event.target.value)}>
            <option value="">File A</option>
            {ready.map((file) => (
              <option key={file.id} value={file.id}>
                {file.id}: {file.label || file.original_filename}
              </option>
            ))}
          </select>{" "}
          <select value={fileB} onChange={(event) => setFileB(event.target.value)}>
            <option value="">File B</option>
            {ready.map((file) => (
              <option key={file.id} value={file.id}>
                {file.id}: {file.label || file.original_filename}
              </option>
            ))}
          </select>{" "}
          <input
            placeholder="County (optional)"
            value={county}
            onChange={(event) => setCounty(event.target.value)}
          />{" "}
          <button type="button" className="dashboard-btn dashboard-btn--blue" onClick={runCompare} disabled={!fileA || !fileB}>
            Compare
          </button>{" "}
          <button type="button" className="dashboard-btn" onClick={downloadPackets} disabled={!fileA || !fileB}>
            Download county packets
          </button>
          {compare && (
            <p>
              Only in A: {compare.only_in_a_count}. Only in B: {compare.only_in_b_count}. Changed:{" "}
              {compare.changed_count}.
            </p>
          )}
        </section>

        <section className="dashboard-card">
          <h2>Query</h2>
          <select value={queryFile} onChange={(event) => setQueryFile(event.target.value)}>
            <option value="">Choose a file</option>
            {ready.map((file) => (
              <option key={file.id} value={file.id}>
                {file.id}: {file.label || file.original_filename}
              </option>
            ))}
          </select>{" "}
          <input placeholder="Name" value={queryName} onChange={(event) => setQueryName(event.target.value)} />{" "}
          <input placeholder="Party" value={queryParty} onChange={(event) => setQueryParty(event.target.value)} />{" "}
          <button type="button" className="dashboard-btn dashboard-btn--blue" onClick={runQuery} disabled={!queryFile}>
            Run query
          </button>{" "}
          <button type="button" className="dashboard-btn" onClick={exportQuery} disabled={!queryFile}>
            Export CSV
          </button>
          {rows.length > 0 && (
            <table>
              <thead>
                <tr>
                  <th>County</th>
                  <th>NCID</th>
                  <th>Name</th>
                  <th>Address</th>
                  <th>Status</th>
                  <th>Party</th>
                </tr>
              </thead>
              <tbody>
                {rows.map((row) => (
                  <tr key={row.ncid}>
                    <td>{row.county}</td>
                    <td>{row.ncid}</td>
                    <td>
                      {row.first_name} {row.last_name}
                    </td>
                    <td>{row.address}</td>
                    <td>{row.status}</td>
                    <td>{row.party}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </section>

        <section className="dashboard-card">
          <h2>Compare against a list</h2>
          <select value="" disabled>
            <option value="">Comparison list</option>
          </select>{" "}
          <button type="button" className="dashboard-btn" disabled>
            Match list
          </button>
          {match && (
            <p>
              Matched {match.matched_count}. Unmatched {match.unmatched_count}. Ambiguous {match.ambiguous_count}.
            </p>
          )}
        </section>
      </main>
    </div>
  );
}
