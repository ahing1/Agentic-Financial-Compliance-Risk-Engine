"use client";

import { useState } from "react";

interface FilingInputProps {
  onSubmit: (ticker: string, filingType: string) => void;
  isLoading: boolean;
}

export default function FilingInput({ onSubmit, isLoading }: FilingInputProps) {
  const [ticker, setTicker] = useState("");
  const [filingType, setFilingType] = useState("10-K");

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    const cleaned = ticker.trim().toUpperCase();
    if (!cleaned) return;
    onSubmit(cleaned, filingType);
  };

  return (
    <form onSubmit={handleSubmit} className="flex items-end gap-3">
      <div className="flex-1">
        <label
          htmlFor="ticker"
          className="block text-sm font-medium text-gray-700 mb-1"
        >
          Company Ticker
        </label>
        <input
          id="ticker"
          type="text"
          value={ticker}
          onChange={(e) => setTicker(e.target.value.toUpperCase())}
          placeholder="AAPL"
          maxLength={10}
          disabled={isLoading}
          className="w-full px-3 py-2 border border-gray-300 rounded-md
                     focus:outline-none focus:ring-2 focus:ring-blue-500
                     disabled:bg-gray-100 disabled:cursor-not-allowed"
        />
      </div>

      <div>
        <label
          htmlFor="filingType"
          className="block text-sm font-medium text-gray-700 mb-1"
        >
          Filing Type
        </label>
        <select
          id="filingType"
          value={filingType}
          onChange={(e) => setFilingType(e.target.value)}
          disabled={isLoading}
          className="px-3 py-2 border border-gray-300 rounded-md
                     focus:outline-none focus:ring-2 focus:ring-blue-500"
        >
          <option value="10-K">10-K (Annual)</option>
          <option value="10-Q">10-Q (Quarterly)</option>
        </select>
      </div>

      <button
        type="submit"
        disabled={isLoading || !ticker.trim()}
        className="px-6 py-2 bg-blue-600 text-white rounded-md font-medium
                   hover:bg-blue-700 disabled:bg-gray-400
                   disabled:cursor-not-allowed transition-colors"
      >
        {isLoading ? "Submitting..." : "Analyze"}
      </button>
    </form>
  );
}