"use client";

import React from "react";
import type { ClosingRankRow, PaginatedResponse } from "@/lib/api";

interface ClosingRankGridProps {
  data: PaginatedResponse<ClosingRankRow> | null;
  loading: boolean;
  error: string | null;
  page: number;
  onPageChange: (page: number) => void;
  onRowClick: (row: ClosingRankRow) => void;
}

// Placeholder columns for future data (greyed out / disabled)
const PLACEHOLDER_COLS = ["CR R2", "CR R3", "CR R4", "Fee", "Stipend", "Bond", "Beds"];

export default function ClosingRankGrid({
  data,
  loading,
  error,
  page,
  onPageChange,
  onRowClick,
}: ClosingRankGridProps) {
  if (loading && !data) {
    return (
      <div className="flex items-center justify-center py-32">
        <div className="w-8 h-8 border-2 border-brand-500 border-t-transparent rounded-full animate-spin" />
      </div>
    );
  }

  if (error) {
    return (
      <div className="flex flex-col items-center justify-center py-32 gap-2 text-red-500">
        <svg className="w-8 h-8" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2}
            d="M12 9v2m0 4h.01M10.29 3.86L1.82 18a2 2 0 001.71 3h16.94a2 2 0 001.71-3L13.71 3.86a2 2 0 00-3.42 0z" />
        </svg>
        <p className="text-sm">{error}</p>
      </div>
    );
  }

  if (!data || data.data.length === 0) {
    return (
      <div className="flex flex-col items-center justify-center py-32 gap-2 text-slate-400">
        <svg className="w-10 h-10" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5}
            d="M9.75 17L9 20l-1 1h8l-1-1-.75-3M3 13h18M5 17h14a2 2 0 002-2V5a2 2 0 00-2-2H5a2 2 0 00-2 2v10a2 2 0 002 2z" />
        </svg>
        <p className="text-sm">No records found. Adjust your filters.</p>
      </div>
    );
  }

  return (
    <div className="flex flex-col h-full">
      {/* Result count */}
      <div className="px-4 py-2 text-sm text-slate-500 border-b border-slate-200 bg-white flex items-center justify-between">
        <span>
          Showing{" "}
          <span className="font-medium text-slate-700">
            {(page - 1) * data.page_size + 1}–
            {Math.min(page * data.page_size, data.total)}
          </span>{" "}
          of{" "}
          <span className="font-medium text-slate-700">
            {data.total.toLocaleString()}
          </span>{" "}
          groups
        </span>
        {loading && (
          <div className="w-4 h-4 border-2 border-brand-500 border-t-transparent rounded-full animate-spin" />
        )}
      </div>

      {/* Table */}
      <div className="flex-1 overflow-auto">
        <table className="w-full text-sm">
          <thead className="sticky top-0 z-10 bg-slate-100 border-b-2 border-slate-300">
            <tr>
              <th className="th">Quota</th>
              <th className="th">Category</th>
              <th className="th">State</th>
              <th className="th min-w-[200px]">Institute</th>
              <th className="th min-w-[180px]">Course</th>
              <th className="th text-right font-bold text-brand-700">
                CR 2025 R1
              </th>
              <th className="th text-center text-slate-300">#</th>
              {PLACEHOLDER_COLS.map((col) => (
                <th key={col} className="th text-center text-slate-300 text-xs opacity-50">
                  {col}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {data.data.map((row) => (
              <GridRow
                key={row.group_id}
                row={row}
                onClick={() => onRowClick(row)}
              />
            ))}
          </tbody>
        </table>
      </div>

      {/* Pagination */}
      {data.pages > 1 && (
        <div className="border-t border-slate-200 bg-white px-4 py-3 flex items-center justify-between">
          <button
            onClick={() => onPageChange(page - 1)}
            disabled={page <= 1}
            className="btn-page"
          >
            Previous
          </button>
          <PaginationNumbers current={page} total={data.pages} onChange={onPageChange} />
          <button
            onClick={() => onPageChange(page + 1)}
            disabled={page >= data.pages}
            className="btn-page"
          >
            Next
          </button>
        </div>
      )}

      <style jsx>{`
        .th {
          padding: 0.5rem 0.75rem;
          text-align: left;
          font-size: 0.75rem;
          font-weight: 600;
          color: #475569;
          text-transform: uppercase;
          letter-spacing: 0.05em;
          white-space: nowrap;
        }
        .btn-page {
          padding: 0.375rem 0.75rem;
          font-size: 0.875rem;
          border: 1px solid #cbd5e1;
          border-radius: 0.375rem;
          background: white;
          color: #475569;
          cursor: pointer;
          transition: background 0.1s;
        }
        .btn-page:disabled {
          opacity: 0.4;
          cursor: not-allowed;
        }
        .btn-page:not(:disabled):hover {
          background: #f1f5f9;
        }
      `}</style>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Grid row
// ---------------------------------------------------------------------------
interface GridRowProps {
  row: ClosingRankRow;
  onClick: () => void;
}

function GridRow({ row, onClick }: GridRowProps) {
  const catColors: Record<string, string> = {
    GN: "bg-green-100 text-green-700",
    EW: "bg-yellow-100 text-yellow-700",
    BC: "bg-orange-100 text-orange-700",
    SC: "bg-purple-100 text-purple-700",
    ST: "bg-red-100 text-red-700",
  };
  const catBase = row.allotted_category_norm?.split("-")[0] ?? "";
  const catColor = catColors[catBase] ?? "bg-slate-100 text-slate-600";

  return (
    <tr className="border-b border-slate-100 hover:bg-blue-50/30 transition-colors">
      {/* Quota */}
      <td className="td">
        {row.quota_norm ? (
          <span className="px-1.5 py-0.5 text-xs rounded bg-blue-100 text-blue-700 font-mono font-semibold">
            {row.quota_norm}
          </span>
        ) : (
          <span className="text-slate-300">—</span>
        )}
      </td>

      {/* Category */}
      <td className="td">
        {row.allotted_category_norm ? (
          <span className={`px-1.5 py-0.5 text-xs rounded font-medium ${catColor}`}>
            {row.allotted_category_norm}
          </span>
        ) : (
          <span className="text-slate-300">—</span>
        )}
      </td>

      {/* State */}
      <td className="td text-slate-500 text-xs whitespace-nowrap">
        {row.state ?? "—"}
      </td>

      {/* Institute */}
      <td className="td font-medium text-slate-800 max-w-[280px]">
        <span className="line-clamp-2" title={row.institute_name ?? ""}>
          {row.institute_name ?? "—"}
        </span>
      </td>

      {/* Course */}
      <td className="td text-slate-700 max-w-[240px]">
        <span className="line-clamp-2" title={row.course_norm ?? ""}>
          {row.course_norm ?? "—"}
        </span>
      </td>

      {/* Closing Rank — clickable */}
      <td className="td text-right">
        <button
          onClick={onClick}
          className="font-mono font-bold text-brand-600 hover:text-brand-800 hover:underline
                     focus:outline-none focus:ring-2 focus:ring-brand-400 rounded px-1"
          title="Click to view all allotments up to this closing rank"
        >
          {row.closing_rank?.toLocaleString() ?? "—"}
        </button>
      </td>

      {/* Count */}
      <td className="td text-center text-xs text-slate-400">{row.allotment_count}</td>

      {/* Placeholder future columns */}
      {PLACEHOLDER_COLS.map((col) => (
        <td key={col} className="td text-center text-slate-200 text-xs">
          —
        </td>
      ))}

      <style jsx>{`
        .td {
          padding: 0.5rem 0.75rem;
          vertical-align: middle;
        }
      `}</style>
    </tr>
  );
}

// ---------------------------------------------------------------------------
// Pagination numbers
// ---------------------------------------------------------------------------
function PaginationNumbers({
  current,
  total,
  onChange,
}: {
  current: number;
  total: number;
  onChange: (p: number) => void;
}) {
  const pages: (number | "...")[] = [];

  if (total <= 7) {
    for (let i = 1; i <= total; i++) pages.push(i);
  } else {
    pages.push(1);
    if (current > 3) pages.push("...");
    for (let i = Math.max(2, current - 1); i <= Math.min(total - 1, current + 1); i++) {
      pages.push(i);
    }
    if (current < total - 2) pages.push("...");
    pages.push(total);
  }

  return (
    <div className="flex items-center gap-1 text-sm">
      {pages.map((p, i) =>
        p === "..." ? (
          <span key={`ellipsis-${i}`} className="px-2 text-slate-400">
            …
          </span>
        ) : (
          <button
            key={p}
            onClick={() => onChange(p as number)}
            className={`w-8 h-8 rounded text-sm transition-colors ${
              p === current
                ? "bg-brand-600 text-white font-semibold"
                : "hover:bg-slate-100 text-slate-600"
            }`}
          >
            {p}
          </button>
        )
      )}
    </div>
  );
}
