"use client";

import React, { useEffect, useRef } from "react";
import type { DrillDownResponse } from "@/lib/api";

interface DrillDownModalProps {
  groupId: string | null;
  data: DrillDownResponse | null;
  loading: boolean;
  error: string | null;
  onClose: () => void;
}

export default function DrillDownModal({
  groupId,
  data,
  loading,
  error,
  onClose,
}: DrillDownModalProps) {
  const overlayRef = useRef<HTMLDivElement>(null);

  // Close on Escape
  useEffect(() => {
    const handler = (e: KeyboardEvent) => {
      if (e.key === "Escape") onClose();
    };
    document.addEventListener("keydown", handler);
    return () => document.removeEventListener("keydown", handler);
  }, [onClose]);

  // Trap focus within modal
  useEffect(() => {
    if (groupId) document.body.style.overflow = "hidden";
    return () => { document.body.style.overflow = ""; };
  }, [groupId]);

  if (!groupId) return null;

  const handleOverlayClick = (e: React.MouseEvent<HTMLDivElement>) => {
    if (e.target === overlayRef.current) onClose();
  };

  return (
    <div
      ref={overlayRef}
      onClick={handleOverlayClick}
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 backdrop-blur-sm p-4"
      role="dialog"
      aria-modal="true"
      aria-label="Allotments drill-down"
    >
      <div className="bg-white rounded-xl shadow-2xl w-full max-w-5xl flex flex-col max-h-[90vh]">
        {/* Modal header */}
        <div className="flex items-center justify-between px-6 py-4 border-b border-slate-200">
          <div>
            <h2 className="text-lg font-semibold text-slate-800">
              Allotments up to Closing Rank
            </h2>
            {data && (
              <p className="text-sm text-slate-500 mt-0.5">
                {data.allotment_count} allotment
                {data.allotment_count !== 1 ? "s" : ""} · Closing rank:{" "}
                <span className="font-semibold text-brand-600">
                  {data.closing_rank?.toLocaleString() ?? "—"}
                </span>{" "}
                · R{data.data[0]?.round ?? 1} – {new Date().getFullYear()}
              </p>
            )}
          </div>
          <button
            onClick={onClose}
            className="p-2 rounded-lg hover:bg-slate-100 text-slate-500 hover:text-slate-700 transition-colors"
            aria-label="Close modal"
          >
            <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
            </svg>
          </button>
        </div>

        {/* Modal body */}
        <div className="flex-1 overflow-auto modal-table-scroll">
          {loading && (
            <div className="flex items-center justify-center py-16">
              <div className="w-8 h-8 border-2 border-brand-500 border-t-transparent rounded-full animate-spin" />
            </div>
          )}

          {error && !loading && (
            <div className="flex items-center justify-center py-16 text-red-500">
              {error}
            </div>
          )}

          {!loading && !error && data && data.data.length === 0 && (
            <div className="flex items-center justify-center py-16 text-slate-400">
              No allotments found.
            </div>
          )}

          {!loading && !error && data && data.data.length > 0 && (
            <table className="w-full text-sm">
              <thead className="sticky top-0 bg-slate-50 border-b border-slate-200">
                <tr>
                  <th className="th-cell text-center w-16">Rank</th>
                  <th className="th-cell w-8">Rnd</th>
                  <th className="th-cell">State</th>
                  <th className="th-cell">Institute</th>
                  <th className="th-cell">Course</th>
                  <th className="th-cell w-16">Quota</th>
                  <th className="th-cell">Allotted Cat.</th>
                  <th className="th-cell">Candidate Cat.</th>
                  <th className="th-cell">Remarks</th>
                </tr>
              </thead>
              <tbody>
                {data.data.map((row, idx) => (
                  <tr
                    key={idx}
                    className={`border-b border-slate-100 hover:bg-blue-50/40 transition-colors
                      ${row.rank === data.closing_rank ? "bg-amber-50 font-medium" : ""}
                    `}
                  >
                    <td className="td-cell text-center font-mono font-semibold text-brand-700">
                      {row.rank?.toLocaleString() ?? "—"}
                    </td>
                    <td className="td-cell text-center">{row.round}</td>
                    <td className="td-cell text-slate-500">{row.state ?? "—"}</td>
                    <td className="td-cell font-medium">{row.institute_name ?? "—"}</td>
                    <td className="td-cell">{row.course_norm ?? "—"}</td>
                    <td className="td-cell text-center">
                      <QuotaBadge quota={row.quota_norm} />
                    </td>
                    <td className="td-cell">
                      <CategoryBadge category={row.allotted_category_norm} />
                    </td>
                    <td className="td-cell text-slate-500 text-xs">
                      {row.candidate_category_raw ?? "—"}
                    </td>
                    <td className="td-cell text-slate-400 text-xs max-w-[160px] truncate">
                      {row.remarks ?? ""}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </div>

        {/* Footer */}
        {data && (
          <div className="px-6 py-3 border-t border-slate-200 flex items-center justify-between text-xs text-slate-400">
            <span>
              Sorted by rank ascending · Highlighted row = closing rank
            </span>
            <button
              onClick={onClose}
              className="px-3 py-1.5 text-sm rounded bg-slate-100 hover:bg-slate-200 text-slate-600 transition-colors"
            >
              Close
            </button>
          </div>
        )}
      </div>

      <style jsx>{`
        .th-cell {
          padding: 0.5rem 0.75rem;
          text-align: left;
          font-size: 0.75rem;
          font-weight: 600;
          color: #64748b;
          text-transform: uppercase;
          letter-spacing: 0.05em;
          white-space: nowrap;
        }
        .td-cell {
          padding: 0.5rem 0.75rem;
          vertical-align: top;
        }
      `}</style>
    </div>
  );
}

function QuotaBadge({ quota }: { quota: string | null }) {
  if (!quota) return <span className="text-slate-400">—</span>;
  return (
    <span className="inline-block px-1.5 py-0.5 text-xs rounded bg-blue-100 text-blue-700 font-mono font-semibold">
      {quota}
    </span>
  );
}

function CategoryBadge({ category }: { category: string | null }) {
  if (!category) return <span className="text-slate-400">—</span>;
  const colorMap: Record<string, string> = {
    GN: "bg-green-100 text-green-700",
    EW: "bg-yellow-100 text-yellow-700",
    BC: "bg-orange-100 text-orange-700",
    SC: "bg-purple-100 text-purple-700",
    ST: "bg-red-100 text-red-700",
  };
  const base = category.split("-")[0];
  const color = colorMap[base] ?? "bg-slate-100 text-slate-600";
  return (
    <span className={`inline-block px-1.5 py-0.5 text-xs rounded font-medium ${color}`}>
      {category}
    </span>
  );
}
