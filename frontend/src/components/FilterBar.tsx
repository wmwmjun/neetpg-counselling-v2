"use client";

import React, { useCallback } from "react";
import type { MetadataResponse, ClosingRankFilters } from "@/lib/api";

interface FilterBarProps {
  filters: ClosingRankFilters;
  metadata: MetadataResponse | null;
  loading: boolean;
  onFilterChange: (updates: Partial<ClosingRankFilters>) => void;
  onClear: () => void;
}

const DEFAULT_FILTERS: ClosingRankFilters = {
  year: 2025,
  counselling_type: "AIQ",
  round: 1,
  quota_norm: "AI",
};

export default function FilterBar({
  filters,
  metadata,
  loading,
  onFilterChange,
  onClear,
}: FilterBarProps) {
  const handle = useCallback(
    (key: keyof ClosingRankFilters) =>
      (e: React.ChangeEvent<HTMLInputElement | HTMLSelectElement>) => {
        const val = e.target.value;
        if (key === "rank_min" || key === "rank_max" || key === "year" || key === "round") {
          onFilterChange({ [key]: val === "" ? undefined : Number(val) });
        } else {
          onFilterChange({ [key]: val === "" ? undefined : val });
        }
      },
    [onFilterChange]
  );

  return (
    <div className="sticky top-0 z-30 bg-white border-b border-slate-200 shadow-sm">
      {/* Header row */}
      <div className="flex items-center justify-between px-4 py-2 bg-brand-700 text-white">
        <div className="flex items-center gap-3">
          <span className="font-bold text-lg tracking-tight">NEET-PG Analytics</span>
          <span className="text-brand-100 text-sm">Closing Ranks</span>
        </div>
        <div className="flex items-center gap-2 text-sm text-brand-100">
          {/* Future: Year / Type / Round selectors */}
          <span className="px-2 py-0.5 bg-brand-600 rounded">
            {filters.counselling_type ?? "AIQ"} · Round {filters.round ?? 1} · {filters.year ?? 2025}
          </span>
        </div>
      </div>

      {/* Filter controls */}
      <div className="px-4 py-3 flex flex-wrap gap-3 items-end">
        {/* Quota */}
        <div className="flex flex-col gap-1">
          <label className="text-xs font-medium text-slate-500 uppercase tracking-wide">
            Quota
          </label>
          <select
            className="input-select"
            value={filters.quota_norm ?? "AI"}
            onChange={handle("quota_norm")}
          >
            <option value="">All</option>
            {(metadata?.quotas ?? ["AI"]).map((q) => (
              <option key={q} value={q}>
                {q}
              </option>
            ))}
          </select>
        </div>

        {/* Category */}
        <div className="flex flex-col gap-1">
          <label className="text-xs font-medium text-slate-500 uppercase tracking-wide">
            Category
          </label>
          <select
            className="input-select"
            value={filters.allotted_category_norm ?? ""}
            onChange={handle("allotted_category_norm")}
          >
            <option value="">All</option>
            {(metadata?.categories ?? []).map((c) => (
              <option key={c} value={c}>
                {c}
              </option>
            ))}
          </select>
        </div>

        {/* State */}
        <div className="flex flex-col gap-1">
          <label className="text-xs font-medium text-slate-500 uppercase tracking-wide">
            State
          </label>
          <select
            className="input-select"
            value={filters.state ?? ""}
            onChange={handle("state")}
          >
            <option value="">All</option>
            {(metadata?.states ?? []).map((s) => (
              <option key={s} value={s}>
                {s}
              </option>
            ))}
          </select>
        </div>

        {/* Course */}
        <div className="flex flex-col gap-1">
          <label className="text-xs font-medium text-slate-500 uppercase tracking-wide">
            Course
          </label>
          <select
            className="input-select w-52"
            value={filters.course_norm ?? ""}
            onChange={handle("course_norm")}
          >
            <option value="">All</option>
            {(metadata?.courses ?? []).map((c) => (
              <option key={c} value={c}>
                {c}
              </option>
            ))}
          </select>
        </div>

        {/* Rank range */}
        <div className="flex flex-col gap-1">
          <label className="text-xs font-medium text-slate-500 uppercase tracking-wide">
            Rank (from – to)
          </label>
          <div className="flex gap-1 items-center">
            <input
              type="number"
              min={1}
              placeholder="Min"
              className="input-text w-20"
              value={filters.rank_min ?? ""}
              onChange={handle("rank_min")}
            />
            <span className="text-slate-400 text-sm">–</span>
            <input
              type="number"
              min={1}
              placeholder="Max"
              className="input-text w-20"
              value={filters.rank_max ?? ""}
              onChange={handle("rank_max")}
            />
          </div>
        </div>

        {/* Search */}
        <div className="flex flex-col gap-1 flex-1 min-w-[180px]">
          <label className="text-xs font-medium text-slate-500 uppercase tracking-wide">
            Search
          </label>
          <input
            type="text"
            placeholder="Institute or course..."
            className="input-text w-full"
            value={filters.search ?? ""}
            onChange={handle("search")}
          />
        </div>

        {/* Sort */}
        <div className="flex flex-col gap-1">
          <label className="text-xs font-medium text-slate-500 uppercase tracking-wide">
            Sort by
          </label>
          <div className="flex gap-1">
            <select
              className="input-select"
              value={filters.sort_by ?? "institute_name"}
              onChange={handle("sort_by")}
            >
              <option value="institute_name">Institute</option>
              <option value="course_norm">Course</option>
              <option value="closing_rank">Closing Rank</option>
            </select>
            <select
              className="input-select"
              value={filters.sort_order ?? "asc"}
              onChange={handle("sort_order")}
            >
              <option value="asc">Asc</option>
              <option value="desc">Desc</option>
            </select>
          </div>
        </div>

        {/* Clear button */}
        <div className="flex flex-col gap-1">
          <label className="text-xs font-medium text-transparent uppercase tracking-wide select-none">
            &nbsp;
          </label>
          <button
            onClick={onClear}
            className="px-3 py-1.5 text-sm rounded border border-slate-300 bg-white hover:bg-slate-50
                       text-slate-600 font-medium transition-colors"
          >
            Clear filters
          </button>
        </div>

        {/* Loading indicator */}
        {loading && (
          <div className="flex items-end pb-1.5">
            <div className="w-4 h-4 border-2 border-brand-500 border-t-transparent rounded-full animate-spin" />
          </div>
        )}
      </div>

      {/* Future placeholders (year/type/round selectors - greyed out) */}
      <div className="px-4 pb-2 flex gap-2 text-xs text-slate-400">
        <span className="px-2 py-0.5 rounded bg-slate-100 cursor-not-allowed" title="Coming soon">
          Year selector (coming soon)
        </span>
        <span className="px-2 py-0.5 rounded bg-slate-100 cursor-not-allowed" title="Coming soon">
          State counselling (coming soon)
        </span>
        <span className="px-2 py-0.5 rounded bg-slate-100 cursor-not-allowed" title="Coming soon">
          Round selector (coming soon)
        </span>
      </div>

      <style jsx>{`
        .input-select {
          border: 1px solid #cbd5e1;
          border-radius: 0.375rem;
          padding: 0.25rem 0.5rem;
          font-size: 0.875rem;
          background: white;
          color: #1e293b;
          outline: none;
          height: 2rem;
        }
        .input-select:focus {
          border-color: #3b82f6;
          box-shadow: 0 0 0 2px rgba(59, 130, 246, 0.2);
        }
        .input-text {
          border: 1px solid #cbd5e1;
          border-radius: 0.375rem;
          padding: 0.25rem 0.5rem;
          font-size: 0.875rem;
          background: white;
          color: #1e293b;
          outline: none;
          height: 2rem;
        }
        .input-text:focus {
          border-color: #3b82f6;
          box-shadow: 0 0 0 2px rgba(59, 130, 246, 0.2);
        }
      `}</style>
    </div>
  );
}

export { DEFAULT_FILTERS };
