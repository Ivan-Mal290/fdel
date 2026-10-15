# File Sharing

Temporary file sharing service with a FastAPI backend and a simple React frontend.

Registered users can upload files, choose how long they stay available (5, 10, or 15 minutes), and share them either with a public link or with an 8-character code plus password. Expired files are removed from disk, stay in history as metadata, and no longer count toward storage quota.

## Features

- JWT auth: register, login, refresh, logout
- Upload with per-file limit **100 MB** and per-user active quota **500 MB**
- Share modes:
  - **Unique link** — landing page for recipients, download starts after they press Download
  - **Code + password** — 8-character alphanumeric code; recipient enters code and password on the Download page
- Active files list, manual delete, history (removed + expired)
- Redis rate limiting on public downloads (default **50 req/min** per IP)
- Light / dark theme toggle in the UI
- Blocked executable/installer extensions: `exe`, `msi`, `bat`, `cmd`, `com`, `scr`, `ps1`, `dmg`, `pkg`, `app`

## Stack

- Python 3.12+ / FastAPI / SQLAlchemy 2 / Alembic / PostgreSQL / Redis / JWT
- React + Vite frontend
- pytest for API tests

## Requirements

- Python 3.12+
- Node.js 18+
- PostgreSQL
- Redis

## Setup

### 1. Configure

From the repository root:

```bash
cp .env.example .env
```

Set a long `JWT_SECRET`. The example `DATABASE_URL` has no username, so PostgreSQL uses the current OS user. If that role cannot connect, put your PostgreSQL role in the URL.

### 2. Database

Create the app database:

```bash
createdb fdel
```

### 3. Backend

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
alembic upgrade head
```

### 4. Frontend

```bash
cd frontend
npm install
cd ..
```

## Run

Start Redis and PostgreSQL, then in two terminals:

**API**

```bash
source .venv/bin/activate
uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload
```

**UI**

```bash
cd frontend
npm run dev
```

- App: http://127.0.0.1:5173  
- API docs: http://127.0.0.1:8000/docs  

The Vite dev server proxies `/api` and share links under `/d/` to the backend.

### Behind nginx

nginx serves the built UI and proxies the API on a single port, `8080`. It runs from the repository with its own config, so the Homebrew config is not touched and `sudo` is not needed.

```bash
brew install nginx

cd frontend
npm run build
cd ..

mkdir -p tmp/nginx
nginx -p "$PWD/" -c "$PWD/deploy/nginx/nginx.conf" -t
nginx -p "$PWD/" -c "$PWD/deploy/nginx/nginx.conf"
```

Keep the API running on `127.0.0.1:8000`, then open http://localhost:8080.

| Path | Goes to |
|------|---------|
| `/api/...` | API, with the `/api` prefix removed |
| `/d/...` | API: link landing pages and downloads |
| everything else | `frontend/dist`, falling back to `index.html` |

Reload after editing the config, or stop nginx:

```bash
nginx -p "$PWD/" -c "$PWD/deploy/nginx/nginx.conf" -s reload
nginx -p "$PWD/" -c "$PWD/deploy/nginx/nginx.conf" -s stop
```

Rebuild the UI with `npm run build` after frontend changes. Logs are in `tmp/nginx/`.

nginx sends the client address in `X-Forwarded-For`, and uvicorn trusts it from `127.0.0.1` by default. Without that header, every visitor would share one download rate limit.

## API overview

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| `POST` | `/auth/register` | no | Create account, return tokens |
| `POST` | `/auth/login` | no | Login |
| `POST` | `/auth/refresh` | no | Rotate refresh token |
| `POST` | `/auth/logout` | no | Revoke the current refresh token |
| `GET` | `/users/me` | yes | Current user |
| `GET` | `/users/me/storage` | yes | Quota usage |
| `POST` | `/files` | yes | Upload (`file`, `expires_in`, `share_mode`, optional `share_password`) |
| `GET` | `/files` | yes | List active files |
| `GET` | `/files/history` | yes | Removed / expired history |
| `GET` | `/files/{id}` | yes | Own file metadata |
| `DELETE` | `/files/{id}` | yes | Delete own file |
| `GET` | `/d/{token}` | no | Link landing page |
| `GET` | `/d/{token}/download` | no | Download by link |
| `GET` | `/d/{token}/info` | no | Link metadata JSON |
| `POST` | `/d/code` | no | Download by code + password |

Upload form fields:

- `expires_in`: `5`, `10`, or `15` (default `15` if omitted)
- `share_mode`: `link` or `code`
- `share_password`: required when `share_mode=code` (4–72 characters)

`GET /files` and `GET /files/history` accept `page` (default `1`) and `limit` (default `20`, maximum `100`).

Downloading by code (`POST /d/code`) does not require an account. The same is true for link landing pages and link downloads.

Common error responses:

| Status | When |
|--------|------|
| `404` | The file belongs to someone else, was deleted, or the token or code is unknown |
| `410` | The file has expired |
| `429` | The client exceeded the public download rate limit |

Errors use JSON `{ "code", "message" }`, except the link landing page, which returns an HTML error page with the same status code.

## Configuration

| Variable | Meaning | Default in example |
|----------|---------|-------------------|
| `DATABASE_URL` | PostgreSQL URL | `postgresql+psycopg://localhost:5432/fdel` |
| `REDIS_URL` | Redis URL | `redis://localhost:6379/0` |
| `JWT_SECRET` | Signing secret (≥ 32 bytes recommended) | — |
| `ACCESS_TOKEN_EXPIRE_MINUTES` | Access token lifetime | `15` |
| `REFRESH_TOKEN_EXPIRE_MINUTES` | Refresh token lifetime | `10080` (7 days) |
| `STORAGE_PATH` | Local file storage directory | `./storage` |
| `MAX_FILE_SIZE` | Max single file size (bytes) | `104857600` (100 MB) |
| `USER_STORAGE_LIMIT` | Active storage per user (bytes) | `524288000` (500 MB) |
| `DOWNLOAD_RATE_LIMIT` | Public download requests per window | `50` |
| `DOWNLOAD_RATE_WINDOW_SECONDS` | Rate-limit window | `60` |
| `PUBLIC_BASE_URL` | Stored in config, not used when building share links | `http://127.0.0.1:8000` |
| `CORS_ORIGINS` | Allowed frontend origins | Vite localhost ports |

The UI turns a download path such as `/d/...` into an absolute link. It uses `VITE_API_ORIGIN` when that variable is set, and the address the site is opened on otherwise.

## Tests

Tests use a separate database `fdel_test` and Redis DB `15`, so they do not touch your main `fdel` data. If `TEST_DATABASE_URL` is unset, the PostgreSQL role is the current OS user.

```bash
createdb fdel_test
source .venv/bin/activate
pip install -r requirements.txt
pytest -v
```

Optional overrides:

```bash
TEST_DATABASE_URL=postgresql+psycopg://USER@localhost:5432/fdel_test \
TEST_REDIS_URL=redis://localhost:6379/15 \
pytest -v
```

Covered scenarios include registration/login/refresh, uploads, quota, blocked types, link and code sharing, foreign-file access, expiration/history, and download rate limiting.

## Project layout

```text
app/                 FastAPI application
alembic/             DB migrations
deploy/nginx/        nginx config for running behind a reverse proxy
frontend/            React + Vite UI
storage/             Uploaded files (gitignored contents)
tests/               pytest suite
```

## Notes

- Physical filenames on disk are UUIDs; original names are stored in PostgreSQL.
- Expired files are deleted from disk but kept in history with name, size, and upload date.
- Manually deleted files also remain in history as **Removed**.
- **Log out** revokes the refresh token for this browser. Shared links and codes keep working. The access token stays valid until it expires, which is 15 minutes by default.
- Docker / S3 / background workers are out of scope for this version.
