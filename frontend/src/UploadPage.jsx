import { useEffect, useId, useRef, useState } from "react";
import {
  PUBLIC_ORIGIN,
  deleteFile,
  errorText,
  fetchFiles,
  fetchHistory,
  fetchStorage,
  uploadFile,
} from "./api.js";

function formatBytes(value) {
  if (value < 1024) return `${value} B`;
  if (value < 1024 * 1024) return `${(value / 1024).toFixed(1)} KB`;
  return `${(value / (1024 * 1024)).toFixed(1)} MB`;
}

function formatWhen(value) {
  return new Date(value).toLocaleString("en-US", {
    day: "2-digit",
    month: "short",
    hour: "2-digit",
    minute: "2-digit",
  });
}

function nextKey() {
  return `${Date.now()}-${Math.random().toString(36).slice(2, 8)}`;
}

export default function UploadPage() {
  const fileRef = useRef(null);
  const inputId = useId();
  const [expiresIn, setExpiresIn] = useState(15);
  const [shareMode, setShareMode] = useState("link");
  const [sharePassword, setSharePassword] = useState("");
  const [storage, setStorage] = useState(null);
  const [files, setFiles] = useState(null);
  const [history, setHistory] = useState(null);
  const [filePage, setFilePage] = useState(1);
  const [historyPage, setHistoryPage] = useState(1);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const [lastShares, setLastShares] = useState([]);
  const [uploading, setUploading] = useState(false);
  const [loading, setLoading] = useState(true);
  const [picked, setPicked] = useState([]);
  const [dragging, setDragging] = useState(false);

  async function reload(nextFilePage = filePage, nextHistoryPage = historyPage) {
    const [storageData, fileData, historyData] = await Promise.all([
      fetchStorage(),
      fetchFiles(nextFilePage),
      fetchHistory(nextHistoryPage),
    ]);
    setStorage(storageData);
    setFiles(fileData);
    setHistory(historyData);
  }

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    reload(filePage, historyPage)
      .catch((err) => {
        if (!cancelled) setError(errorText(err));
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [filePage, historyPage]);

  function addFiles(fileList) {
    const incoming = Array.from(fileList || []);
    if (!incoming.length) return;
    setPicked((current) => [
      ...current,
      ...incoming.map((file) => ({ key: nextKey(), file })),
    ]);
    if (fileRef.current) fileRef.current.value = "";
  }

  function removePicked(key) {
    setPicked((current) => current.filter((item) => item.key !== key));
  }

  function clearPicked() {
    setPicked([]);
    if (fileRef.current) fileRef.current.value = "";
  }

  async function onUpload(event) {
    event.preventDefault();
    if (!picked.length) {
      setError("Choose at least one file");
      return;
    }
    if (shareMode === "code" && sharePassword.trim().length < 4) {
      setError("Share password must be at least 4 characters");
      return;
    }
    setError("");
    setNotice("");
    setLastShares([]);
    setUploading(true);
    const uploaded = [];
    try {
      for (const item of picked) {
        uploaded.push(await uploadFile(item.file, expiresIn, shareMode, sharePassword));
      }
      clearPicked();
      setSharePassword("");
      if (filePage !== 1) {
        setFilePage(1);
      } else {
        await reload(1, historyPage);
      }
      setLastShares(uploaded);
      setNotice(
        uploaded.length === 1
          ? uploaded[0].share_mode === "code"
            ? "File uploaded — share the code and password"
            : "File uploaded — the link is ready"
          : `${uploaded.length} files uploaded`,
      );
    } catch (err) {
      if (uploaded.length) {
        setLastShares(uploaded);
        await reload().catch(() => {});
      }
      setError(errorText(err));
    } finally {
      setUploading(false);
    }
  }

  async function onDelete(id) {
    if (!window.confirm("Remove this file? Recipients will lose access.")) return;
    setError("");
    setNotice("");
    try {
      await deleteFile(id);
      await reload();
    } catch (err) {
      setError(errorText(err));
    }
  }

  async function copyText(value, okMessage) {
    try {
      await navigator.clipboard.writeText(value);
      setNotice(okMessage);
      setError("");
    } catch {
      setError("Could not copy");
    }
  }

  const usedRatio = storage && storage.limit_bytes > 0 ? Math.min(storage.used_bytes / storage.limit_bytes, 1) : 0;

  return (
    <>
      {error ? (
        <p className="error" role="alert">
          {error}
        </p>
      ) : null}
      {notice ? <p className="ok">{notice}</p> : null}

      {lastShares.length ? (
        <section className="card">
          <h2>Share details</h2>
          <div className="list">
            {lastShares.map((item) => {
              const link = item.download_url ? `${PUBLIC_ORIGIN}${item.download_url}` : null;
              return (
                <article className="item" key={item.id}>
                  <div>
                    <h3>{item.filename}</h3>
                    {link ? (
                      <div className="share-box">
                        <code>{link}</code>
                      </div>
                    ) : (
                      <p>
                        Code: <strong>{item.access_code}</strong>
                      </p>
                    )}
                  </div>
                  <div className="actions">
                    {link ? (
                      <button type="button" className="ghost" onClick={() => copyText(link, "Link copied")}>
                        Copy link
                      </button>
                    ) : (
                      <button
                        type="button"
                        className="ghost"
                        onClick={() => copyText(item.access_code, "Code copied")}
                      >
                        Copy code
                      </button>
                    )}
                  </div>
                </article>
              );
            })}
          </div>
          {lastShares[0]?.share_mode === "code" ? (
            <p className="muted">Tell recipients the password you set. They open Download and enter both.</p>
          ) : null}
        </section>
      ) : null}

      <section className="card">
        <div className="section-head">
          <h2>Storage</h2>
          <span className="muted">
            {storage ? `${formatBytes(storage.used_bytes)} of ${formatBytes(storage.limit_bytes)}` : "…"}
          </span>
        </div>
        <div className="bar" aria-hidden="true">
          <div style={{ width: `${usedRatio * 100}%` }} />
        </div>
        <p className="muted">Free {storage ? formatBytes(storage.available_bytes) : "…"}</p>
      </section>

      <section className="card">
        <h2>Upload</h2>
        <form onSubmit={onUpload} className="stack">
          <input
            id={inputId}
            ref={fileRef}
            className="file-input"
            type="file"
            multiple
            onChange={(event) => addFiles(event.target.files)}
          />
          <label
            htmlFor={inputId}
            className={dragging ? "dropzone dragging" : "dropzone"}
            onDragEnter={(event) => {
              event.preventDefault();
              setDragging(true);
            }}
            onDragOver={(event) => {
              event.preventDefault();
              setDragging(true);
            }}
            onDragLeave={(event) => {
              event.preventDefault();
              setDragging(false);
            }}
            onDrop={(event) => {
              event.preventDefault();
              setDragging(false);
              addFiles(event.dataTransfer.files);
            }}
          >
            <strong>Choose files</strong>
            <span>or drag and drop several files here</span>
          </label>

          {picked.length ? (
            <ul className="picked-list">
              {picked.map((item) => (
                <li key={item.key}>
                  <div>
                    <span className="picked-name">{item.file.name}</span>
                    <span className="muted">{formatBytes(item.file.size)}</span>
                  </div>
                  <button type="button" className="ghost" onClick={() => removePicked(item.key)}>
                    Remove
                  </button>
                </li>
              ))}
            </ul>
          ) : null}

          <label>
            Keep for
            <select value={expiresIn} onChange={(event) => setExpiresIn(Number(event.target.value))}>
              <option value={5}>5 minutes</option>
              <option value={10}>10 minutes</option>
              <option value={15}>15 minutes</option>
            </select>
          </label>

          <fieldset className="share-modes">
            <legend>How should recipients get the file?</legend>
            <label className="choice">
              <input
                type="radio"
                name="share_mode"
                checked={shareMode === "link"}
                onChange={() => setShareMode("link")}
              />
              Unique link
            </label>
            <label className="choice">
              <input
                type="radio"
                name="share_mode"
                checked={shareMode === "code"}
                onChange={() => setShareMode("code")}
              />
              8-character code and password
            </label>
          </fieldset>

          {shareMode === "code" ? (
            <label>
              Share password
              <input
                type="password"
                value={sharePassword}
                onChange={(event) => setSharePassword(event.target.value)}
                minLength={4}
                maxLength={72}
                autoComplete="new-password"
                required
              />
            </label>
          ) : null}

          <button type="submit" disabled={uploading || !picked.length}>
            {uploading
              ? "Uploading…"
              : picked.length > 1
                ? `Upload ${picked.length} files`
                : "Upload"}
          </button>
        </form>
        <p className="muted">Up to 100 MB each. Blocked types: exe, msi, bat, cmd, com, scr, ps1, dmg, pkg, and app.</p>
      </section>

      <section className="card">
        <div className="section-head">
          <h2>Active files</h2>
          <button type="button" className="ghost" onClick={() => reload().catch((err) => setError(errorText(err)))}>
            Refresh
          </button>
        </div>
        {loading && !files ? <p className="muted">Loading…</p> : null}
        {files && files.items.length === 0 ? <p className="muted">No active files.</p> : null}
        <div className="list">
          {files?.items.map((file) => {
            const link = file.download_url ? `${PUBLIC_ORIGIN}${file.download_url}` : null;
            return (
              <article className="item" key={file.id}>
                <div>
                  <h3>{file.filename}</h3>
                  <p className="muted">
                    {formatBytes(file.size)} · until {formatWhen(file.expires_at)} ·{" "}
                    {file.share_mode === "code" ? "code + password" : "link"}
                  </p>
                  {link ? (
                    <a href={link} target="_blank" rel="noreferrer">
                      {link}
                    </a>
                  ) : (
                    <p>
                      Code: <strong>{file.access_code}</strong>
                    </p>
                  )}
                </div>
                <div className="actions">
                  {link ? (
                    <button type="button" className="ghost" onClick={() => copyText(link, "Link copied")}>
                      Copy
                    </button>
                  ) : (
                    <button
                      type="button"
                      className="ghost"
                      onClick={() => copyText(file.access_code, "Code copied")}
                    >
                      Copy code
                    </button>
                  )}
                  <button type="button" className="danger" onClick={() => onDelete(file.id)}>
                    Delete
                  </button>
                </div>
              </article>
            );
          })}
        </div>
        <Pager page={files?.page || 1} limit={files?.limit || 20} total={files?.total || 0} onPage={setFilePage} />
      </section>

      <section className="card">
        <h2>History</h2>
        <p className="muted">Removed and expired files: name, size, and upload date.</p>
        {history && history.items.length === 0 ? <p className="muted">History is empty.</p> : null}
        <div className="list">
          {history?.items.map((item) => (
            <article className="item" key={item.id}>
              <div>
                <h3>{item.filename}</h3>
                <p className="muted">
                  {formatBytes(item.size)} · {formatWhen(item.created_at)}
                </p>
              </div>
              <span className={item.status === "deleted" ? "badge danger-badge" : "badge"}>
                {item.status === "deleted" ? "Removed" : "Expired"}
              </span>
            </article>
          ))}
        </div>
        <Pager
          page={history?.page || 1}
          limit={history?.limit || 20}
          total={history?.total || 0}
          onPage={setHistoryPage}
        />
      </section>
    </>
  );
}

function Pager({ page, limit, total, onPage }) {
  if (total <= limit) return null;
  const pages = Math.ceil(total / limit);
  return (
    <div className="pager">
      <button type="button" className="ghost" disabled={page <= 1} onClick={() => onPage(page - 1)}>
        Back
      </button>
      <span className="muted">
        {page} / {pages}
      </span>
      <button type="button" className="ghost" disabled={page >= pages} onClick={() => onPage(page + 1)}>
        Next
      </button>
    </div>
  );
}
