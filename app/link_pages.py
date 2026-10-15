from __future__ import annotations

import html
from datetime import datetime, timezone


def format_bytes(value: int) -> str:
    if value < 1024:
        return f"{value} B"
    if value < 1024 * 1024:
        return f"{value / 1024:.1f} KB"
    return f"{value / (1024 * 1024):.1f} MB"


def to_iso_z(value: datetime) -> str:
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


def _shell(title: str, body: str, script: str = "") -> str:
    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>{html.escape(title)}</title>
  <style>
    :root {{
      color-scheme: light;
      --bg: #f3efe6;
      --card: #fffcf7;
      --ink: #1f1a17;
      --muted: #6f655c;
      --line: #e3d9cc;
      --accent: #1f6b4a;
      --accent-ink: #f3fff8;
      --danger: #9d2c2c;
      font-family: "Avenir Next", "Segoe UI", sans-serif;
      line-height: 1.5;
      font-size: 18px;
    }}
    * {{ box-sizing: border-box; }}
    body {{
      margin: 0;
      min-height: 100vh;
      display: grid;
      place-items: center;
      padding: 2rem 1.5rem;
      background: var(--bg);
      color: var(--ink);
    }}
    .card {{
      width: min(560px, 100%);
      background: var(--card);
      border: 1px solid var(--line);
      border-radius: 22px;
      box-shadow: 0 18px 44px rgba(70, 48, 24, 0.07);
      padding: 2rem 2.1rem 2.15rem;
    }}
    .eyebrow {{
      margin: 0 0 0.45rem;
      text-transform: uppercase;
      letter-spacing: 0.08em;
      font-size: 0.82rem;
      color: var(--muted);
    }}
    h1 {{
      margin: 0;
      font-size: 1.85rem;
      letter-spacing: -0.02em;
      line-height: 1.25;
      overflow-wrap: anywhere;
    }}
    p {{ margin: 0.7rem 0 0; color: var(--muted); font-size: 1.05rem; }}
    .file {{
      margin-top: 1.4rem;
      padding: 1.15rem 1.2rem;
      border: 1px solid var(--line);
      border-radius: 16px;
      background: white;
    }}
    .file strong {{
      display: block;
      color: var(--ink);
      font-size: 1.15rem;
      overflow-wrap: anywhere;
    }}
    .file p {{ margin-top: 0.45rem; font-size: 1rem; }}
    .actions {{ margin-top: 1.5rem; }}
    a.button, .button {{
      display: inline-block;
      border: 0;
      border-radius: 999px;
      padding: 0.95rem 1.55rem;
      background: var(--accent);
      color: var(--accent-ink);
      text-decoration: none;
      cursor: pointer;
      font: inherit;
      font-size: 1.05rem;
    }}
    .error {{ color: var(--danger); }}
  </style>
</head>
<body>
  <main class="card">
    {body}
  </main>
  {script}
</body>
</html>"""


def render_link_landing(
    *,
    sender_email: str,
    filename: str,
    size: int,
    expires_at: datetime,
    download_path: str,
) -> str:
    sender = html.escape(sender_email)
    name = html.escape(filename)
    size_text = html.escape(format_bytes(size))
    expires_iso = html.escape(to_iso_z(expires_at))
    href = html.escape(download_path)
    body = f"""
    <p class="eyebrow">File Sharing</p>
    <h1>{sender} sent you a file</h1>
    <p>Open the file only if you trust the sender. Download starts after you press the button.</p>
    <div class="file">
      <strong>{name}</strong>
      <p>{size_text} · available until <span data-expires="{expires_iso}">…</span></p>
    </div>
    <div class="actions">
      <a class="button" href="{href}">Download</a>
    </div>
    """
    script = """
<script>
  (function () {
    var node = document.querySelector("[data-expires]");
    if (!node) return;
    var value = node.getAttribute("data-expires");
    var date = new Date(value);
    if (Number.isNaN(date.getTime())) return;
    node.textContent = date.toLocaleString("en-US", {
      day: "2-digit",
      month: "short",
      hour: "2-digit",
      minute: "2-digit",
    });
  })();
</script>
"""
    return _shell(f"{filename} · File Sharing", body, script)


def render_link_error(*, title: str, message: str) -> str:
    body = f"""
    <p class="eyebrow">File Sharing</p>
    <h1>{html.escape(title)}</h1>
    <p class="error">{html.escape(message)}</p>
    """
    return _shell(title, body)
