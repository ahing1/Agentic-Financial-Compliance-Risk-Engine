"use client";

import ProgressBar from "./ProgressBar";
import type { ProgressUpdate } from "@/lib/types";

interface AgentFeedProps {
  messages: ProgressUpdate[];
  progress: number;
  isFinished: boolean;
}

const STEP_ICONS: Record<string, string> = {
  started: "🚀",
  parsing: "📄",
  embedding: "🧮",
  retrieval: "🔍",
  analyzing: "🧠",
  comparing: "📊",
  verifying: "✅",
  complete: "🎉",
  error: "❌",
};

export default function AgentFeed({
  messages,
  progress,
  isFinished,
}: AgentFeedProps) {
  return (
    <div className="space-y-4">
      {/* Progress bar at the top */}
      <div>
        <div className="flex justify-between text-sm text-gray-600 mb-1">
          <span>Analysis Progress</span>
          <span>{progress}%</span>
        </div>
        <ProgressBar progress={progress} />
      </div>

      {/* Step timeline */}
      <div className="space-y-2 mt-4">
        {messages.map((msg, i) => (
          <div
            key={i}
            className={`flex items-start gap-3 p-3 rounded-lg border
              ${msg.step === "error"
                ? "border-red-200 bg-red-50"
                : msg.step === "complete"
                ? "border-green-200 bg-green-50"
                : "border-gray-200 bg-white"
              }
              ${i === messages.length - 1 && !isFinished
                ? "animate-pulse"
                : ""
              }
            `}
          >
            {/* Step icon */}
            <span className="text-xl flex-shrink-0 mt-0.5">
              {STEP_ICONS[msg.step] || "⚙️"}
            </span>

            {/* Step content */}
            <div className="flex-1 min-w-0">
              <div className="flex items-center gap-2">
                <span className="text-sm font-medium text-gray-900 capitalize">
                  {msg.step}
                </span>
                <span className="text-xs text-gray-400">
                  {msg.progress}%
                </span>
              </div>
              <p className="text-sm text-gray-600 mt-0.5">
                {msg.message}
              </p>
            </div>
          </div>
        ))}

        {/* Waiting indicator when no messages yet */}
        {messages.length === 0 && (
          <div className="flex items-center gap-3 p-3 text-gray-500">
            <span className="animate-spin">⏳</span>
            <span className="text-sm">Waiting for agent to start...</span>
          </div>
        )}
      </div>
    </div>
  );
}