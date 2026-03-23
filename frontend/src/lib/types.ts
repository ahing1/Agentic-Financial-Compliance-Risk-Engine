export interface JobResponse { 
    job_id: string;
    filing_id: string;
    status: string;
    message: string;
}

export interface JobStatusResponse {
    job_id: string;
    status: "pending" | "processing" | "completed" | "failed" | "needs_review";
    current_step: string | null;
    started_at: string | null;
    completed_at: string | null;
    error: string | null;
}

export interface ProgressUpdate {
    step: string;
    message: string;
    progress: string;
}

export interface RiskFactor {
    id: string;
    factor: string;
    severity: "high" | "medium" | "low";
    citation: string;
    source_chunk_id: string | null;
}

export interface Report {
    report_id: string;
    filing_id: string;
    ticker: string;
    company: string;
    filing_type: string;
    filing_date: string;
    risk_score: number;
    summary: string;
    risk_factors: RiskFactor[];
    created_at: string;
}

export interface FilingHistoryItem {
  filing_id: string;
  ticker: string;
  company: string;
  filing_type: string;
  filing_date: string;
  status: string;
  risk_score: number | null;
  created_at: string;
}

export interface FilingHistoryResponse {
  filings: FilingHistoryItem[];
  total: number;
  page: number;
  page_size: number;
}

export interface HealthResponse {
  status: string;
  database: string;
  redis: string;
}

export interface LoginRequest {
  email: string;
  password: string;
}

export interface RegisterRequest {
  email: string;
  password: string;
}

export interface TokenResponse {
  access_token: string;
  token_type: string;
  user_id: string;
  email: string;
}

export interface RegisterResponse {
  user_id: string;
  email: string;
  message: string;
}

export type DashboardView = "idle" | "processing" | "viewing_report";