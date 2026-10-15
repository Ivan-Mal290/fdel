const API = "/api";

const TEXT = {
  email_taken: "This email is already registered",
  invalid_credentials: "Invalid email or password",
  invalid_token: "Session expired, please sign in again",
  unauthorized: "Please sign in",
  file_too_large: "File is larger than 100 MB",
  file_type_blocked: "This file type is not allowed",
  quota_exceeded: "Not enough free storage",
  unsupported_expiration: "You can only choose 5, 10, or 15 minutes",
  unsupported_share_mode: "Choose link or code sharing",
  share_password_invalid: "Share password must be 4 to 72 characters",
  invalid_share_password: "Invalid code or password",
  file_not_found: "File not found",
  file_expired: "Retention period has expired",
  rate_limited: "Too many requests, try again later",
  validation_error: "Please check the information you entered",
  rate_limit_unavailable: "Service temporarily unavailable",
  network: "Cannot reach the server",
};

export const PUBLIC_ORIGIN = import.meta.env.VITE_API_ORIGIN || window.location.origin;

export function errorText(error) {
  if (error?.code === "validation_error") {
    const locations = (error.details || []).map((item) => (item.loc || []).join("."));
    if (locations.some((loc) => loc.includes("password"))) {
      return "Password must be 8 to 72 characters";
    }
    if (locations.some((loc) => loc.includes("email"))) {
      return "Enter a valid email";
    }
  }
  return TEXT[error?.code] || "Something went wrong";
}

export function getAccessToken() {
  return localStorage.getItem("access_token");
}

export function setSession(tokens) {
  localStorage.setItem("access_token", tokens.access_token);
  localStorage.setItem("refresh_token", tokens.refresh_token);
}

export function clearSession() {
  localStorage.removeItem("access_token");
  localStorage.removeItem("refresh_token");
}

export async function logout() {
  const refreshToken = localStorage.getItem("refresh_token");
  try {
    if (refreshToken) {
      await fetch(`${API}/auth/logout`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ refresh_token: refreshToken }),
      });
    }
  } catch {
    // The browser session is cleared either way.
  } finally {
    clearSession();
  }
}

function networkError() {
  const error = new Error("Failed to fetch");
  error.code = "network";
  return error;
}

async function parseError(response) {
  let body = null;
  try {
    body = await response.json();
  } catch {
    body = null;
  }
  const error = new Error(body?.message || "Request failed");
  error.status = response.status;
  error.code = body?.code || "request_failed";
  error.details = body?.details;
  return error;
}

async function raw(path, options = {}) {
  const headers = new Headers(options.headers || {});
  const token = getAccessToken();
  if (token && !headers.has("Authorization")) {
    headers.set("Authorization", `Bearer ${token}`);
  }
  if (options.json !== undefined) {
    headers.set("Content-Type", "application/json");
  }
  try {
    return await fetch(`${API}${path}`, {
      method: options.method || "GET",
      headers,
      body: options.json !== undefined ? JSON.stringify(options.json) : options.body,
    });
  } catch {
    throw networkError();
  }
}

let refreshPromise = null;

async function tryRefresh() {
  if (!refreshPromise) {
    refreshPromise = refreshSession().finally(() => {
      refreshPromise = null;
    });
  }
  return refreshPromise;
}

async function refreshSession() {
  const refreshToken = localStorage.getItem("refresh_token");
  if (!refreshToken) return false;
  let response;
  try {
    response = await fetch(`${API}/auth/refresh`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ refresh_token: refreshToken }),
    });
  } catch {
    return false;
  }
  if (!response.ok) {
    clearSession();
    return false;
  }
  setSession(await response.json());
  return true;
}

export async function api(path, options = {}) {
  let response = await raw(path, options);
  if (response.status === 401 && !options.skipAuthRetry && localStorage.getItem("refresh_token")) {
    const refreshed = await tryRefresh();
    if (refreshed) {
      response = await raw(path, options);
    }
  }
  if (!response.ok) {
    throw await parseError(response);
  }
  if (response.status === 204) return null;
  return response.json();
}

export function register(email, password) {
  return api("/auth/register", { method: "POST", json: { email, password }, skipAuthRetry: true });
}

export function login(email, password) {
  return api("/auth/login", { method: "POST", json: { email, password }, skipAuthRetry: true });
}

export function fetchMe() {
  return api("/users/me");
}

export function fetchStorage() {
  return api("/users/me/storage");
}

export function fetchFiles(page) {
  return api(`/files?page=${page}&limit=20`);
}

export function fetchHistory(page) {
  return api(`/files/history?page=${page}&limit=20`);
}

export function uploadFile(file, expiresIn, shareMode = "link", sharePassword = "") {
  const body = new FormData();
  body.append("file", file);
  body.append("expires_in", String(expiresIn));
  body.append("share_mode", shareMode);
  if (shareMode === "code") {
    body.append("share_password", sharePassword);
  }
  return api("/files", { method: "POST", body });
}

export async function downloadByCode(code, password) {
  const response = await raw("/d/code", {
    method: "POST",
    json: { code, password },
    skipAuthRetry: true,
  });
  if (!response.ok) {
    throw await parseError(response);
  }
  const blob = await response.blob();
  const disposition = response.headers.get("content-disposition") || "";
  const match = /filename\*?=(?:UTF-8''|")?([^\";]+)/i.exec(disposition);
  const filename = match ? decodeURIComponent(match[1].replace(/"/g, "")) : "download";
  const objectUrl = URL.createObjectURL(blob);
  const anchor = document.createElement("a");
  anchor.href = objectUrl;
  anchor.download = filename;
  document.body.appendChild(anchor);
  anchor.click();
  anchor.remove();
  URL.revokeObjectURL(objectUrl);
}

export function deleteFile(id) {
  return api(`/files/${id}`, { method: "DELETE" });
}
