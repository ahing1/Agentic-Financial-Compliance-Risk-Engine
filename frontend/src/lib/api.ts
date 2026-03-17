import type {
  JobResponse,
  JobStatusResponse,
  Report,
  FilingHistoryResponse,
  HealthResponse,
} from "./types";

const API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

async function apiFetch<T>(
    path: string,
    options?: RequestInit
): Promise<T> {
    const url = `${API_BASE}${path}`

    const response = await fetch(url, {
        ...options,
        headers: {
            "Content-Type": "application/json",
            ...options?.headers
        }
    });
    if (!response.ok) {
    let detail = `API error: ${response.status}`;
    try {
      const errorBody = await response.json();
      detail = errorBody.detail || detail;
    } catch {
      detail = `${response.status}: ${response.statusText}`;
    }
    throw new Error(detail);
  }

  return response.json() as Promise<T>;
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
  return `${API_BASE}/stream/${jobId}`;
}