"use client";
import React from "react";
import type { ClosingRankRow, PaginatedResponse } from "@/lib/api";
import type { DisplayedFields } from "./FilterModal";

interface Props {
  data: PaginatedResponse<ClosingRankRow> | null;
  loading: boolean;
  error: string | null;
  page: number;
  pageSize: number;
  displayedFields: DisplayedFields;
  onPageChange: (p: number) => void;
  onRowClick: (row: ClosingRankRow) => void;
}

const CAT_CLASS: Record<string, string> = {
  GN: "badge-GN", EW: "badge-EW", BC: "badge-BC", SC: "badge-SC", ST: "badge-ST",
};

export default function ClosingRankGrid({
  data, loading, error, page, pageSize, displayedFields, onPageChange, onRowClick,
}: Props) {

  if (error) {
    return (
      <div style={{ padding: 40, textAlign: "center", color: "#c00" }}>
        <div style={{ fontSize: 18, marginBottom: 12 }}>⚠ Failed to load data</div>
        <div style={{ fontSize: 12, color: "#888", marginBottom: 16 }}>{error}</div>
        <div style={{ fontSize: 12, background: "#f8f8f8", border: "1px solid #ddd", borderRadius: 4, padding: 12, display: "inline-block", textAlign: "left", maxWidth: 560 }}>
          <div style={{ fontWeight: 600, marginBottom: 8 }}>Start the backend:</div>
          <code style={{ display: "block", marginBottom: 4 }}>cd backend</code>
          <code style={{ display: "block", marginBottom: 4 }}>python -m scripts.init_db</code>
          <code style={{ display: "block", marginBottom: 4 }}>python -m scripts.seed</code>
          <code style={{ display: "block" }}>uvicorn app.main:app --reload</code>
        </div>
      </div>
    );
  }

  if (!data && loading) {
    return (
      <div style={{ display: "flex", alignItems: "center", justifyContent: "center", padding: 60 }}>
        <div style={{ width: 32, height: 32, border: "3px solid #2871b5", borderTopColor: "transparent", borderRadius: "50%", animation: "spin 0.8s linear infinite" }} />
        <style>{`@keyframes spin{to{transform:rotate(360deg)}}`}</style>
      </div>
    );
  }

  if (!data || data.total === 0) {
    return (
      <div style={{ padding: 60, textAlign: "center", color: "#888" }}>
        <div style={{ fontSize: 32, marginBottom: 8 }}>📋</div>
        <div>No records found. Adjust your filters.</div>
      </div>
    );
  }

  const start = (page - 1) * pageSize + 1;
  const end = Math.min(page * pageSize, data.total);

  return (
    <div style={{ display: "flex", flexDirection: "column", height: "100%" }}>
      {/* Table scroll area */}
      <div style={{ flex: 1, overflow: "auto" }}>
        <table className="cr-table">
          <thead>
            <tr>
              <th style={{ minWidth: 50 }}>Quota</th>
              <th style={{ minWidth: 60 }}>Category</th>
              <th style={{ minWidth: 100 }}>State</th>
              <th style={{ minWidth: 260 }}>Institute</th>
              <th style={{ minWidth: 200 }}>Course</th>
              {displayedFields.fee && <th style={{ minWidth: 80 }}>Fee</th>}
              {displayedFields.stipend && <th style={{ minWidth: 100 }}>Stipend Yr 1</th>}
              {displayedFields.bondYears && <th style={{ minWidth: 80 }}>Bond Yrs</th>}
              {displayedFields.bondPenalty && <th style={{ minWidth: 100 }}>Bond Penalty</th>}
              {displayedFields.beds && <th style={{ minWidth: 60 }}>Beds</th>}
              <th style={{ minWidth: 90, color: "#2871b5" }}>CR 2025 R1</th>
              {/* Future round placeholders */}
              <th style={{ minWidth: 90, color: "#bbb" }}>CR 2025 R2</th>
              <th style={{ minWidth: 90, color: "#bbb" }}>CR 2025 R3</th>
              <th style={{ minWidth: 90, color: "#bbb" }}>CR 2025 R4</th>
            </tr>
          </thead>
          <tbody>
            {data.data.map((row) => (
              <tr key={row.group_id}>
                {/* Quota */}
                <td>
                  <span className="badge-quota">{row.quota_norm ?? "—"}</span>
                </td>
                {/* Category */}
                <td>
                  <span className={`badge ${CAT_CLASS[row.allotted_category_norm ?? ""] ?? "badge-default"}`}>
                    {row.allotted_category_norm ?? "—"}
                  </span>
                </td>
                {/* State */}
                <td style={{ color: "#555", fontSize: 12 }}>{row.state ?? "—"}</td>
                {/* Institute */}
                <td>
                  <span className="inst-link" style={{ fontWeight: 500 }}>
                    {row.institute_name ?? "—"}
                  </span>
                </td>
                {/* Course */}
                <td style={{ color: "#333" }}>{row.course_norm ?? "—"}</td>
                {/* Placeholder cols */}
                {displayedFields.fee && <td style={{ color: "#bbb", textAlign: "center" }}>—</td>}
                {displayedFields.stipend && <td style={{ color: "#bbb", textAlign: "center" }}>—</td>}
                {displayedFields.bondYears && <td style={{ color: "#bbb", textAlign: "center" }}>—</td>}
                {displayedFields.bondPenalty && <td style={{ color: "#bbb", textAlign: "center" }}>—</td>}
                {displayedFields.beds && <td style={{ color: "#bbb", textAlign: "center" }}>—</td>}
                {/* CR 2025 R1 */}
                <td style={{ textAlign: "center" }}>
                  <button className="cr-link" onClick={() => onRowClick(row)} style={{ background: "none", border: "none", padding: 0, font: "inherit" }}>
                    {row.closing_rank != null
                      ? `${row.closing_rank.toLocaleString()}(${row.allotment_count})`
                      : "—"}
                  </button>
                </td>
                {/* Future rounds */}
                <td style={{ color: "#bbb", textAlign: "center" }}>—</td>
                <td style={{ color: "#bbb", textAlign: "center" }}>—</td>
                <td style={{ color: "#bbb", textAlign: "center" }}>—</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {/* Footer: count + pagination */}
      <div style={{
        borderTop: "1px solid #e0e0e0", background: "#fafafa",
        padding: "8px 16px", display: "flex", alignItems: "center", justifyContent: "space-between"
      }}>
        <div style={{ fontSize: 12, color: "#666" }}>
          {loading && <span style={{ color: "#2871b5", marginRight: 8 }}>Loading…</span>}
          {start.toLocaleString()}–{end.toLocaleString()} of {data.total.toLocaleString()} Records
        </div>
        {data.pages > 1 && (
          <Pagination current={page} total={data.pages} onChange={onPageChange} />
        )}
      </div>
    </div>
  );
}

function Pagination({ current, total, onChange }: { current: number; total: number; onChange: (p: number) => void }) {
  const pages: (number | "…")[] = [];
  if (total <= 7) {
    for (let i = 1; i <= total; i++) pages.push(i);
  } else {
    pages.push(1);
    if (current > 3) pages.push("…");
    for (let i = Math.max(2, current - 1); i <= Math.min(total - 1, current + 1); i++) pages.push(i);
    if (current < total - 2) pages.push("…");
    pages.push(total);
  }

  return (
    <div style={{ display: "flex", alignItems: "center", gap: 4 }}>
      <PgBtn disabled={current <= 1} onClick={() => onChange(current - 1)}>‹ Prev</PgBtn>
      {pages.map((p, i) =>
        p === "…"
          ? <span key={`e${i}`} style={{ padding: "0 4px", color: "#aaa" }}>…</span>
          : <PgBtn key={p} active={p === current} onClick={() => onChange(p as number)}>{p}</PgBtn>
      )}
      <PgBtn disabled={current >= total} onClick={() => onChange(current + 1)}>Next ›</PgBtn>
    </div>
  );
}

function PgBtn({ children, active, disabled, onClick }: {
  children: React.ReactNode; active?: boolean; disabled?: boolean; onClick?: () => void;
}) {
  return (
    <button onClick={onClick} disabled={disabled} style={{
      minWidth: 30, height: 26, padding: "0 8px", fontSize: 12, border: "1px solid",
      borderRadius: 3, cursor: disabled ? "not-allowed" : "pointer",
      background: active ? "#2871b5" : "#fff",
      color: active ? "#fff" : disabled ? "#ccc" : "#555",
      borderColor: active ? "#2871b5" : "#ddd",
    }}>
      {children}
    </button>
  );
}
