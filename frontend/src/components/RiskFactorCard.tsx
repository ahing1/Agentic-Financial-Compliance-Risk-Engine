import type { RiskFactor } from "@/lib/types";

interface RiskFactorCardProps {
  riskFactor: RiskFactor;
  index: number;
}

const SEVERITY_STYLES: Record<string, { border: string; badge: string; label: string }> = {
  high: {
    border: "border-l-red-500",
    badge: "bg-red-100 text-red-800",
    label: "High",
  },
  medium: {
    border: "border-l-amber-500",
    badge: "bg-amber-100 text-amber-800",
    label: "Medium",
  },
  low: {
    border: "border-l-green-500",
    badge: "bg-green-100 text-green-800",
    label: "Low",
  },
};

export default function RiskFactorCard({ riskFactor, index }: RiskFactorCardProps) {
  const style = SEVERITY_STYLES[riskFactor.severity] || SEVERITY_STYLES.medium;

  return (
    <div
      className={`border border-gray-200 rounded-lg p-4 border-l-4 ${style.border}`}
    >
      {/* Header: index + severity badge */}
      <div className="flex items-center justify-between mb-2">
        <span className="text-sm font-medium text-gray-500">
          Risk Factor #{index + 1}
        </span>
        <span
          className={`text-xs font-semibold px-2.5 py-0.5 rounded-full ${style.badge}`}
        >
          {style.label}
        </span>
      </div>

      {/* Risk description */}
      <p className="text-gray-900 mb-3">{riskFactor.factor}</p>

      {/* Citation — the source text from the filing */}
      <div className="bg-gray-50 rounded p-3 border border-gray-100">
        <p className="text-xs font-medium text-gray-500 mb-1">Citation</p>
        <p className="text-sm text-gray-700 italic leading-relaxed">
          &ldquo;{riskFactor.citation}&rdquo;
        </p>
      </div>

      {/* Source chunk indicator */}
      {riskFactor.source_chunk_id && (
        <p className="text-xs text-gray-400 mt-2">
          Source: chunk {riskFactor.source_chunk_id.slice(0, 8)}...
        </p>
      )}
    </div>
  );
}