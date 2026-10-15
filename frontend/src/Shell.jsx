import AccountMenu from "./AccountMenu.jsx";
import DownloadPage from "./DownloadPage.jsx";
import ThemeToggle from "./ThemeToggle.jsx";
import UploadPage from "./UploadPage.jsx";

export default function Shell({ user, page, theme, onToggleTheme, onNavigate, onLogout }) {
  return (
    <main className="page">
      <header className="top">
        <div>
          <p className="eyebrow">File Sharing</p>
          <h1>{page === "download" ? "Download" : "Upload"}</h1>
          <p className="muted">{user.email}</p>
        </div>
        <div className="header-actions">
          <ThemeToggle theme={theme} onToggle={onToggleTheme} />
          <AccountMenu page={page} onNavigate={onNavigate} onLogout={onLogout} />
        </div>
      </header>
      {page === "download" ? <DownloadPage /> : <UploadPage />}
    </main>
  );
}
