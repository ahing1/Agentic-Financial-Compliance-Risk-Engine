"use client";

import { useState, useCallback, useEffect } from "react";
import { submitFiling } from "@/lib/api";
import { useSSE } from "@/hooks/useSSE";
import FilingInput from "@/components/FilingInput";
import AgentFeed from "@/components/AgentFeed";
import ReportView from "@/components/ReportView";
import FilingHistory from "@/components/FilingHistory";
import type { DashboardView } from "@/lib/types";

export default function DashboardPage() {
  const [view, setView] = useState<DashboardView>("idle");

  const [isSubmitting, setIsSubmitting] = useState(false);
  const [submitError, setSubmitError] = useState<string | null>(null);

  const [activeJobId, setActiveJobId] = useState<string | null>(null);
  const [activeFilingId, setActiveFilingId] = useState<string | null>(null);

  const [refreshTrigger, setRefreshTrigger] = useState(0);

  const { messages, progress, isFinished } = useSSE(
    view === "processing" ? activeJobId : null
  );

  const handleSubmit = useCallback(async (ticker: string, filingType: string) => {
    setIsSubmitting(true);
    setSubmitError(null);

    try {
      const result = await submitFiling(ticker, filingType);

      setActiveJobId(result.job_id);
      setActiveFilingId(result.filing_id);
      setView("processing");
    } catch (err) {
      setSubmitError(
        err instanceof Error ? err.message : "Failed to submit filing"
      );
    } finally {
      setIsSubmitting(false);
    }
  }, []);

  // When the agent finishes, transition to report view
  useEffect(() => {
    if (view !== "processing" || !isFinished || !activeFilingId) return;
    const lastMessage = messages[messages.length - 1];
    if (lastMessage?.step !== "complete") return;

    const timer = setTimeout(() => {
      setView("viewing_report");
      setRefreshTrigger((prev) => prev + 1);
    }, 1500);

    return () => clearTimeout(timer);
  }, [view, isFinished, activeFilingId, messages]);

  const handleSelectFiling = useCallback((filingId: string) => {
    setActiveFilingId(filingId);
    setActiveJobId(null);
    setView("viewing_report");
  }, []);

  const handleBack = useCallback(() => {
    setView("idle");
    setActiveJobId(null);
    setActiveFilingId(null);
  }, []);

  return (
    <div className="space-y-8">
      {/* Filing input — always visible, disabled during processing */}
      <section>
        <FilingInput
          onSubmit={handleSubmit}
          isLoading={isSubmitting || view === "processing"}
        />
        {submitError && (
          <p className="text-sm text-red-600 mt-2">{submitError}</p>
        )}
      </section>

      {/* Main content area — changes based on view state */}
      <section>
        {view === "processing" && (
          <AgentFeed
            messages={messages}
            progress={progress}
            isFinished={isFinished}
          />
        )}

        {view === "viewing_report" && activeFilingId && (
          <ReportView filingId={activeFilingId} onBack={handleBack} />
        )}
      </section>

      {/* Filing history — visible in idle and processing views */}
      {view !== "viewing_report" && (
        <section>
          <FilingHistory
            onSelectFiling={handleSelectFiling}
            refreshTrigger={refreshTrigger}
          />
        </section>
      )}
    </div>
  );
}