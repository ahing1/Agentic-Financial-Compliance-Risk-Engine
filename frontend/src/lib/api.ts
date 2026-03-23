import type {
  JobResponse,
  JobStatusResponse,
  Report,
  FilingHistoryResponse,
  HealthResponse,
  LoginRequest,
  RegisterRequest,
  TokenResponse,
  RegisterResponse,
} from "./types";

const API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

let authToken: string | null = null;

export function setToken(token: string | null) {
  authToken = token;
}

export function getToken(): string | null {
  return authToken;
}

export function isAuthenticated(): boolean {
  return authToken !== null;
}

export function logout() {
  authToken = null;
}

async function apiFetch<T>(
  path: string,
  options?: RequestInit
): Promise<T> {
  const url = `${API_BASE}${path}`;

  const headers: Record<string, string> = {
    "Content-Type": "application/json",
    ...((options?.headers as Record<string, string>) || {}),
  };

  // Add auth token if available
  if (authToken) {
    headers["Authorization"] = `Bearer ${authToken}`;
  }

  const response = await fetch(url, {
    ...options,
    headers,
  });

  // Handle 401 — token expired or invalid
  if (response.status === 401) {
    // If we had a token, it's expired/invalid — clear it
    // If we didn't (e.g. login attempt), let the error fall through
    // to the generic handler so the backend's message is shown
    if (authToken) {
      authToken = null;
      throw new Error("Session expired. Please log in again.");
    }
  }

  if (!response.ok) {
    let detail = `API error: ${response.status}`;
    try {
      const errorBody = await response.json();
      if (Array.isArray(errorBody.detail)) {
        detail = errorBody.detail.map((e: { msg?: string }) => {
          const msg = e.msg || JSON.stringify(e);
          return msg.replace(/^Value error, /i, "");
        }).join("; ");
      } else {
        detail = errorBody.detail || detail;
      }
    } catch {
      detail = `${response.status}: ${response.statusText}`;
    }
    throw new Error(detail);
  }

  return response.json() as Promise<T>;
}

export async function register(
  email: string,
  password: string
): Promise<RegisterResponse> {
  return apiFetch<RegisterResponse>("/auth/register", {
    method: "POST",
    body: JSON.stringify({ email, password }),
  });
}

export async function login(
  email: string,
  password: string
): Promise<TokenResponse> {
  const result = await apiFetch<TokenResponse>("/auth/login", {
    method: "POST",
    body: JSON.stringify({ email, password }),
  });

  // Store the token for subsequent requests
  authToken = result.access_token;
  return result;
}

export async function submitFiling(
  ticker: string,
  filingType: string = "10-K"
): Promise<JobResponse> {
  return apiFetch<JobResponse>("/filings/analyze", {
    method: "POST",
    body: JSON.stringify({ ticker, filing_type: filingType }),
  });
}

export async function getFilingStatus(
  filingId: string
): Promise<JobStatusResponse> {
  return apiFetch<JobStatusResponse>(`/filings/${filingId}/status`);
}

export async function getReport(filingId: string): Promise<Report> {
  return apiFetch<Report>(`/filings/${filingId}/report`);
}

export async function getFilingHistory(
  page: number = 1,
  pageSize: number = 20,
  ticker?: string
): Promise<FilingHistoryResponse> {
  const params = new URLSearchParams({
    page: String(page),
    page_size: String(pageSize),
  });
  if (ticker) params.set("ticker", ticker);
  return apiFetch<FilingHistoryResponse>(`/filings/history?${params}`);
}

export async function getHealth(): Promise<HealthResponse> {
  return apiFetch<HealthResponse>("/health");
}

export function getStreamUrl(jobId: string): string {
  const token = authToken ? `?token=${authToken}` : "";
  return `${API_BASE}/stream/${jobId}${token}`;
}