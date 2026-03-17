"use client";

import { useState, useEffect } from "react";
import { getFilingHistory } from "@/lib/api";
import type { FilingHistoryItem, FilingHistoryResponse } from "@/lib/types";

interface FilingHistoryProps {
  onSelectFiling: (filingId: string) => void;
  refreshTrigger?: number; // Increment to force a refetch after new analysis
}

const PAGE_SIZE = 10;

export default function FilingHistory({
  onSelectFiling,
  refreshTrigger = 0,
}: FilingHistoryProps) {
  const [data, setData] = useState<FilingHistoryResponse | null>(null);
  const [page, setPage] = useState(1);
  const [tickerFilter, setTickerFilter] = useState("");
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;

    async function fetchHistory() {
      setLoading(true);
      setError(null);

      try {
        const result = await getFilingHistory(
          page,
          PAGE_SIZE,
          tickerFilter || undefined
        );
        if (!cancelled) setData(result);
      } catch (err) {
        if (!cancelled) {
          setError(err instanceof Error ? err.message : "Failed to load history");
        }
      } finally {
        if (!cancelled) setLoading(false);
      }
    }

    fetchHistory();
    return () => { cancelled = true; };
  }, [page, tickerFilter, refreshTrigger]);

  const totalPages = data ? Math.ceil(data.total / PAGE_SIZE) : 0;

  return (
    <div>
      {/* Header + filter */}
      <div className="flex items-center justify-between mb-3">
        <h3 className="text-lg font-medium text-gray-900">Filing History</h3>
        <input
          type="text"
          placeholder="Filter by ticker..."
          value={tickerFilter}
          onChange={(e) => {
            setTickerFilter(e.target.value.toUpperCase());
            setPage(1); // Reset to page 1 when filter changes
          }}
          className="px-3 py-1.5 text-sm border border-gray-300 rounded-md
                     focus:outline-none focus:ring-2 focus:ring-blue-500 w-40"
        />
      </div>

      {/* Error state */}
      {error && (
        <p className="text-sm text-red-600 py-4">{error}</p>
      )}

      {/* Loading state */}
      {loading && !data && (
        <p className="text-sm text-gray-500 py-4">Loading history...</p>
      )}

      {/* Empty state */}
      {data && data.filings.length === 0 && (
        <p className="text-sm text-gray-500 py-8 text-center">
          No analyses found.
          {tickerFilter && " Try clearing the filter."}
        </p>
      )}

      {/* Table */}
      {data && data.filings.length > 0 && (
        <>
          <div className="border border-gray-200 rounded-lg overflow-hidden">
            <table className="w-full text-sm">
              <thead className="bg-gray-50">
                <tr>
                  <th className="text-left px-4 py-2.5 font-medium text-gray-600">
                    Ticker
                  </th>
                  <th className="text-left px-4 py-2.5 font-medium text-gray-600">
                    Company
                  </th>
                  <th className="text-left px-4 py-2.5 font-medium text-gray-600">
                    Type
                  </th>
                  <th className="text-left px-4 py-2.5 font-medium text-gray-600">
                    Filing Date
                  </th>
                  <th className="text-left px-4 py-2.5 font-medium text-gray-600">
                    Risk Score
                  </th>
                  <th className="text-left px-4 py-2.5 font-medium text-gray-600">
                    Status
                  </th>
                </tr>
              </thead>
              <tbody className="divide-y divide-gray-100">
                {data.filings.map((filing) => (
                  <tr
                    key={filing.filing_id}
                    onClick={() => onSelectFiling(filing.filing_id)}
                    className="hover:bg-blue-50 cursor-pointer transition-colors"
                  >
                    <td className="px-4 py-3 font-medium text-gray-900">
                      {filing.ticker}
                    </td>
                    <td className="px-4 py-3 text-gray-600">
                      {filing.company}
                    </td>
                    <td className="px-4 py-3 text-gray-600">
                      {filing.filing_type}
                    </td>
                    <td className="px-4 py-3 text-gray-600">
                      {new Date(filing.filing_date).toLocaleDateString()}
                    </td>
                    <td className="px-4 py-3">
                      {filing.risk_score !== null ? (
                        <span
                          className={`font-medium ${
                            filing.risk_score >= 7
                              ? "text-red-600"
                              : filing.risk_score >= 4
                              ? "text-amber-600"
                              : "text-green-600"
                          }`}
                        >
                          {filing.risk_score}
                        </span>
                      ) : (
                        <span className="text-gray-400">—</span>
                      )}
                    </td>
                    <td className="px-4 py-3">
                      <StatusBadge status={filing.status} />
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>

          {/* Pagination */}
          {totalPages > 1 && (
            <div className="flex items-center justify-between mt-3">
              <span className="text-xs text-gray-500">
                {data.total} total · Page {page} of {totalPages}
              </span>
              <div className="flex gap-2">
                <button
                  onClick={() => setPage((p) => Math.max(1, p - 1))}
                  disabled={page === 1}
                  className="px-3 py-1 text-sm border border-gray-300 rounded
                             hover:bg-gray-50 disabled:opacity-40
                             disabled:cursor-not-allowed"
                >
                  Previous
                </button>
                <button
                  onClick={() => setPage((p) => Math.min(totalPages, p + 1))}
                  disabled={page === totalPages}
                  className="px-3 py-1 text-sm border border-gray-300 rounded
                             hover:bg-gray-50 disabled:opacity-40
                             disabled:cursor-not-allowed"
                >
                  Next
                </button>
              </div>
            </div>
          )}
        </>
      )}
    </div>
  );
}

/** Small helper component for status badges */
function StatusBadge({ status }: { status: string }) {
  const styles: Record<string, string> = {
    completed: "bg-green-100 text-green-800",
    needs_review: "bg-amber-100 text-amber-800",
    failed: "bg-red-100 text-red-800",
    processing: "bg-blue-100 text-blue-800",
    pending: "bg-gray-100 text-gray-800",
  };

  return (
    <span
      className={`text-xs font-medium px-2 py-0.5 rounded-full ${
        styles[status] || styles.pending
      }`}
    >
      {status}
    </span>
  );
}