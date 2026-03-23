"use client";

import { useState, useCallback } from "react";
import { submitFiling } from "@/lib/api";
import { useSSE } from "@/hooks/useSSE";
import { useAuth } from "@/hooks/useAuth";
import AuthForm from "@/components/AuthForm";
import FilingInput from "@/components/FilingInput";
import AgentFeed from "@/components/AgentFeed";
import ReportView from "@/components/ReportView";
import FilingHistory from "@/components/FilingHistory";
import type { DashboardView } from "@/lib/types";

export default function DashboardPage() {
  // --- Auth ---
  const {
    isLoggedIn,
    userEmail,
    loginError,
    registerError,
    isLoading: authLoading,
    login,
    register,
    logout,
  } = useAuth();

  // --- View state ---
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

  if (view === "processing" && isFinished && activeFilingId) {
    const lastMessage = messages[messages.length - 1];
    if (lastMessage?.step === "complete") {
      setTimeout(() => {
        setView("viewing_report");
        setRefreshTrigger((prev) => prev + 1);
      }, 1000);
    }
  }

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

  // --- Show login form if not authenticated ---
  if (!isLoggedIn) {
    return (
      <AuthForm
        onLogin={login}
        onRegister={register}
        loginError={loginError}
        registerError={registerError}
        isLoading={authLoading}
      />
    );
  }

  // --- Authenticated: show dashboard ---
  return (
    <div className="space-y-8">
      {/* User info bar */}
      <div className="flex items-center justify-between text-sm text-gray-500">
        <span>Logged in as {userEmail}</span>
        <button
          onClick={logout}
          className="text-gray-500 hover:text-gray-700"
        >
          Sign out
        </button>
      </div>

      <section>
        <FilingInput
          onSubmit={handleSubmit}
          isLoading={isSubmitting || view === "processing"}
        />
        {submitError && (
          <p className="text-sm text-red-600 mt-2">{submitError}</p>
        )}
      </section>

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