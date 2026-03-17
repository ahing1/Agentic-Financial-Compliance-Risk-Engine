"use client";

import { useState, useEffect } from "react";
import { getReport } from "@/lib/api";
import RiskFactorCard from "./RiskFactorCard";
import type { Report } from "@/lib/types";

interface ReportViewProps {
  filingId: string;
  onBack: () => void;
}

export default function ReportView({ filingId, onBack }: ReportViewProps) {
  const [report, setReport] = useState<Report | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;

    async function fetchReport(retriesLeft = 3) {
      setLoading(true);
      setError(null);

      try {
        const data = await getReport(filingId);
        if (!cancelled) setReport(data);
      } catch (err) {
        // The report may not be committed yet when the SSE "complete"
        // event fires — retry a few times before giving up.
        if (!cancelled && retriesLeft > 0) {
          await new Promise((r) => setTimeout(r, 2000));
          if (!cancelled) return fetchReport(retriesLeft - 1);
        }
        if (!cancelled) {
          setError(err instanceof Error ? err.message : "Failed to load report");
        }
      } finally {
        if (!cancelled) setLoading(false);
      }
    }

    fetchReport();

    // Cleanup: if filingId changes before the fetch completes,
    // don't update state with stale data from the old request.
    return () => {
      cancelled = true;
    };
  }, [filingId]);

  if (loading) {
    return (
      <div className="flex items-center justify-center py-12 text-gray-500">
        <span className="animate-spin mr-2">⏳</span>
        Loading report...
      </div>
    );
  }

  if (error) {
    return (
      <div className="text-center py-12">
        <p className="text-red-600 mb-4">{error}</p>
        <button
          onClick={onBack}
          className="text-blue-600 hover:text-blue-800 text-sm"
        >
          ← Back to dashboard
        </button>
      </div>
    );
  }

  if (!report) return null;

  // Sort risk factors: high first, then medium, then low
  const sortedRisks = [...report.risk_factors].sort((a, b) => {
    const order = { high: 0, medium: 1, low: 2 };
    return (order[a.severity] ?? 1) - (order[b.severity] ?? 1);
  });

  // Count by severity for the summary bar
  const severityCounts = report.risk_factors.reduce(
    (acc, rf) => {
      acc[rf.severity] = (acc[rf.severity] || 0) + 1;
      return acc;
    },
    {} as Record<string, number>
  );

  return (
    <div className="space-y-6">
      {/* Header with back button */}
      <div className="flex items-center justify-between">
        <button
          onClick={onBack}
          className="text-sm text-gray-500 hover:text-gray-700"
        >
          ← Back to dashboard
        </button>
        <span className="text-xs text-gray-400">
          Report: {report.report_id.slice(0, 8)}...
        </span>
      </div>

      {/* Company info + risk score */}
      <div className="bg-white border border-gray-200 rounded-lg p-6">
        <div className="flex items-start justify-between">
          <div>
            <h2 className="text-xl font-semibold text-gray-900">
              {report.company}
            </h2>
            <p className="text-sm text-gray-500 mt-1">
              {report.ticker} · {report.filing_type} · Filed{" "}
              {new Date(report.filing_date).toLocaleDateString()}
            </p>
          </div>

          {/* Risk score circle */}
          {report.risk_score !== null && (
            <div
              className={`flex items-center justify-center w-16 h-16 rounded-full border-4
                ${report.risk_score >= 7
                  ? "border-red-500 text-red-700"
                  : report.risk_score >= 4
                  ? "border-amber-500 text-amber-700"
                  : "border-green-500 text-green-700"
                }
              `}
            >
              <span className="text-lg font-bold">{report.risk_score}</span>
            </div>
          )}
        </div>

        {/* Summary */}
        <p className="text-gray-700 mt-4 leading-relaxed">{report.summary}</p>

        {/* Severity counts */}
        <div className="flex gap-4 mt-4">
          {severityCounts.high && (
            <span className="text-xs bg-red-100 text-red-800 px-2 py-1 rounded-full">
              {severityCounts.high} high
            </span>
          )}
          {severityCounts.medium && (
            <span className="text-xs bg-amber-100 text-amber-800 px-2 py-1 rounded-full">
              {severityCounts.medium} medium
            </span>
          )}
          {severityCounts.low && (
            <span className="text-xs bg-green-100 text-green-800 px-2 py-1 rounded-full">
              {severityCounts.low} low
            </span>
          )}
        </div>
      </div>

      {/* Risk factors list */}
      <div>
        <h3 className="text-lg font-medium text-gray-900 mb-3">
          Risk Factors ({report.risk_factors.length})
        </h3>
        <div className="space-y-3">
          {sortedRisks.map((rf, i) => (
            <RiskFactorCard key={rf.id} riskFactor={rf} index={i} />
          ))}
        </div>
      </div>

      {/* Analysis metadata */}
      <p className="text-xs text-gray-400 text-center">
        Analyzed {new Date(report.created_at).toLocaleString()}
      </p>
    </div>
  );
}