import { useState } from "react";
import { errorText, fetchMe, login, register, setSession } from "./api.js";
import ThemeToggle from "./ThemeToggle.jsx";

export default function AuthScreen({ onSuccess, onOpenDownload, theme, onToggleTheme }) {
  const [mode, setMode] = useState("login");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const [pending, setPending] = useState(false);

  async function onSubmit(event) {
    event.preventDefault();
    setError("");
    setPending(true);
    try {
      const tokens = mode === "register" ? await register(email, password) : await login(email, password);
      setSession(tokens);
      onSuccess(await fetchMe());
    } catch (err) {
      setError(errorText(err));
    } finally {
      setPending(false);
    }
  }

  return (
    <main className="screen">
      {theme && onToggleTheme ? (
        <div className="screen-theme">
          <ThemeToggle theme={theme} onToggle={onToggleTheme} />
        </div>
      ) : null}
      <section className="auth-card">
        <p className="eyebrow">File Sharing</p>
        <h1>{mode === "register" ? "Register" : "Log in"}</h1>
        <p className="muted">Temporary file sharing with a link or an 8-character code.</p>
        <form onSubmit={onSubmit} className="stack">
          <label>
            Email
            <input
              type="email"
              autoComplete="email"
              value={email}
              onChange={(event) => setEmail(event.target.value)}
              required
            />
          </label>
          <label>
            Password
            <input
              type="password"
              autoComplete={mode === "register" ? "new-password" : "current-password"}
              value={password}
              onChange={(event) => setPassword(event.target.value)}
              minLength={8}
              required
            />
          </label>
          {error ? (
            <p className="error" role="alert">
              {error}
            </p>
          ) : null}
          <button type="submit" disabled={pending}>
            {pending ? "Please wait…" : mode === "register" ? "Create account" : "Log in"}
          </button>
        </form>
        <button
          type="button"
          className="text-button"
          onClick={() => {
            setMode(mode === "login" ? "register" : "login");
            setError("");
          }}
        >
          {mode === "login" ? "No account? Register" : "Already have an account? Log in"}
        </button>
        {onOpenDownload ? (
          <button type="button" className="text-button" onClick={onOpenDownload}>
            Have a code? Download a file
          </button>
        ) : null}
      </section>
    </main>
  );
}
