import { useEffect, useState } from "react";
import { clearSession, fetchMe, getAccessToken, logout } from "./api.js";
import AuthScreen from "./AuthScreen.jsx";
import DownloadPage from "./DownloadPage.jsx";
import Shell from "./Shell.jsx";
import ThemeToggle from "./ThemeToggle.jsx";
import { applyTheme, getStoredTheme, setStoredTheme } from "./theme.js";

export default function App() {
  const [user, setUser] = useState(null);
  const [page, setPage] = useState("upload");
  const [booting, setBooting] = useState(true);
  const [theme, setTheme] = useState(() => getStoredTheme());

  useEffect(() => {
    applyTheme(theme);
  }, [theme]);

  useEffect(() => {
    let cancelled = false;
    async function boot() {
      if (!getAccessToken() && !localStorage.getItem("refresh_token")) {
        if (!cancelled) setBooting(false);
        return;
      }
      try {
        const me = await fetchMe();
        if (!cancelled) {
          setUser(me);
          setPage("upload");
        }
      } catch {
        clearSession();
      } finally {
        if (!cancelled) setBooting(false);
      }
    }
    boot();
    return () => {
      cancelled = true;
    };
  }, []);

  function changeTheme(next) {
    setStoredTheme(next);
    setTheme(next);
  }

  if (booting) {
    return (
      <main className="screen">
        <p className="muted">Loading…</p>
      </main>
    );
  }

  if (!user) {
    if (page === "download") {
      return (
        <main className="page">
          <header className="top">
            <div>
              <p className="eyebrow">File Sharing</p>
              <h1>Download</h1>
            </div>
            <div className="header-actions">
              <ThemeToggle theme={theme} onToggle={changeTheme} />
              <button type="button" className="ghost" onClick={() => setPage("auth")}>
                Log in
              </button>
            </div>
          </header>
          <DownloadPage />
        </main>
      );
    }
    return (
      <AuthScreen
        theme={theme}
        onToggleTheme={changeTheme}
        onSuccess={(me) => {
          setUser(me);
          setPage("upload");
        }}
        onOpenDownload={() => setPage("download")}
      />
    );
  }

  return (
    <Shell
      user={user}
      page={page}
      theme={theme}
      onToggleTheme={changeTheme}
      onNavigate={setPage}
      onLogout={() => {
        void logout();
        setUser(null);
        setPage("auth");
      }}
    />
  );
}
