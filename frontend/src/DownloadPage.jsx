import { useState } from "react";
import { downloadByCode, errorText } from "./api.js";

export default function DownloadPage() {
  const [code, setCode] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const [pending, setPending] = useState(false);

  async function onSubmit(event) {
    event.preventDefault();
    setError("");
    setNotice("");
    setPending(true);
    try {
      await downloadByCode(code.trim().toUpperCase(), password);
      setNotice("Download started");
    } catch (err) {
      setError(errorText(err));
    } finally {
      setPending(false);
    }
  }

  return (
    <section className="card">
      <h2>Download</h2>
      <p className="muted">Enter the 8-character code and the password from the person who shared the file.</p>
      <form onSubmit={onSubmit} className="stack">
        <label>
          Code
          <input
            value={code}
            onChange={(event) =>
              setCode(event.target.value.replace(/[^a-zA-Z0-9]/g, "").slice(0, 8).toUpperCase())
            }
            placeholder="A1B2C3D4"
            maxLength={8}
            autoCapitalize="characters"
            autoCorrect="off"
            spellCheck={false}
            required
          />
        </label>
        <label>
          Password
          <input
            type="password"
            value={password}
            onChange={(event) => setPassword(event.target.value)}
            minLength={4}
            required
          />
        </label>
        {error ? (
          <p className="error" role="alert">
            {error}
          </p>
        ) : null}
        {notice ? <p className="ok">{notice}</p> : null}
        <button type="submit" disabled={pending || code.length !== 8}>
          {pending ? "Downloading…" : "Download file"}
        </button>
      </form>
    </section>
  );
}
