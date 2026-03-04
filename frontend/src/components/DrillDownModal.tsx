"use client";
import React, { useEffect } from "react";
import type { DrillDownResponse } from "@/lib/api";

const CAT_CLASS: Record<string, string> = {
  GN: "badge-GN", EW: "badge-EW", BC: "badge-BC", SC: "badge-SC", ST: "badge-ST",
};

interface Props {
  groupId: string | null;
  data: DrillDownResponse | null;
  loading: boolean;
  error: string | null;
  onClose: () => void;
}

export default function DrillDownModal({ groupId, data, loading, error, onClose }: Props) {
  useEffect(() => {
    const h = (e: KeyboardEvent) => { if (e.key === "Escape") onClose(); };
    document.addEventListener("keydown", h);
    return () => document.removeEventListener("keydown", h);
  }, [onClose]);

  useEffect(() => {
    if (groupId) document.body.style.overflow = "hidden";
    return () => { document.body.style.overflow = ""; };
  }, [groupId]);

  if (!groupId) return null;

  const rows = data?.data ?? [];
  const title = rows[0]
    ? `${rows[0].institute_name ?? ""} · ${rows[0].course_norm ?? ""}`
    : "Allotments";

  return (
    <div className="modal-overlay" onClick={e => { if (e.target === e.currentTarget) onClose(); }}>
      <div style={{
        background: "#fff", borderRadius: 6, width: "100%", maxWidth: 860,
        maxHeight: "88vh", display: "flex", flexDirection: "column",
        boxShadow: "0 8px 40px rgba(0,0,0,0.22)"
      }}>
        {/* Header */}
        <div style={{ padding: "14px 20px", borderBottom: "1px solid #e0e0e0", display: "flex", alignItems: "flex-start", justifyContent: "space-between" }}>
          <div>
            <div style={{ fontWeight: 700, fontSize: 14, marginBottom: 4 }}>
              Allotments up to Closing Rank
            </div>
            <div style={{ fontSize: 12, color: "#666" }}>
              {title}
            </div>
            {data && (
              <div style={{ fontSize: 11, color: "#888", marginTop: 4 }}>
                {data.allotment_count} record{data.allotment_count !== 1 ? "s" : ""} &nbsp;·&nbsp;
                Closing Rank: <span style={{ color: "#2871b5", fontWeight: 700 }}>{data.closing_rank?.toLocaleString() ?? "—"}</span>
                &nbsp;·&nbsp; R{rows[0]?.round ?? 1} – 2025
              </div>
            )}
          </div>
          <button onClick={onClose} style={{ background: "none", border: "none", fontSize: 22, cursor: "pointer", color: "#888", lineHeight: 1, marginLeft: 12 }}>×</button>
        </div>

        {/* Body */}
        <div style={{ flex: 1, overflowY: "auto" }}>
          {loading && (
            <div style={{ display: "flex", alignItems: "center", justifyContent: "center", padding: 48 }}>
              <div style={{ width: 28, height: 28, border: "3px solid #2871b5", borderTopColor: "transparent", borderRadius: "50%", animation: "spin 0.8s linear infinite" }} />
              <style>{`@keyframes spin{to{transform:rotate(360deg)}}`}</style>
            </div>
          )}
          {error && !loading && (
            <div style={{ padding: 32, textAlign: "center", color: "#c00", fontSize: 13 }}>{error}</div>
          )}
          {!loading && !error && rows.length === 0 && (
            <div style={{ padding: 40, textAlign: "center", color: "#888" }}>No allotments found.</div>
          )}
          {!loading && !error && rows.length > 0 && (
            <table className="cr-table" style={{ fontSize: 12 }}>
              <thead>
                <tr>
                  <th>Round</th>
                  <th>State</th>
                  <th>Institute</th>
                  <th>Course</th>
                  <th>Quota</th>
                  <th>Allotted Cat.</th>
                  <th>Candidate Cat.</th>
                  <th style={{ textAlign: "right", color: "#2871b5" }}>AI Rank</th>
                </tr>
              </thead>
              <tbody>
                {rows.map((r, i) => (
                  <tr key={i} style={r.rank === data?.closing_rank ? { background: "#fffbea" } : {}}>
                    <td style={{ textAlign: "center", color: "#666" }}>R{r.round}</td>
                    <td style={{ color: "#555" }}>{r.state ?? "—"}</td>
                    <td style={{ fontWeight: 500 }}>{r.institute_name ?? "—"}</td>
                    <td>{r.course_norm ?? "—"}</td>
                    <td style={{ textAlign: "center" }}>
                      <span className="badge-quota">{r.quota_norm ?? "—"}</span>
                    </td>
                    <td style={{ textAlign: "center" }}>
                      <span className={`badge ${CAT_CLASS[r.allotted_category_norm ?? ""] ?? "badge-default"}`}>
                        {r.allotted_category_norm ?? "—"}
                      </span>
                    </td>
                    <td style={{ textAlign: "center", color: "#888", fontSize: 11 }}>
                      {r.candidate_category_raw ?? "—"}
                    </td>
                    <td style={{ textAlign: "right", fontWeight: r.rank === data?.closing_rank ? 700 : 400, color: r.rank === data?.closing_rank ? "#e07d38" : "#2871b5", fontFamily: "monospace" }}>
                      {r.rank?.toLocaleString() ?? "—"}
                      {r.rank === data?.closing_rank && <span style={{ fontSize: 10, marginLeft: 4, color: "#e07d38" }}>CR</span>}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </div>

        {/* Footer */}
        <div style={{ padding: "10px 20px", borderTop: "1px solid #e0e0e0", display: "flex", justifyContent: "space-between", alignItems: "center", fontSize: 11, color: "#aaa" }}>
          <span>Sorted by AI Rank ascending · Highlighted row = Closing Rank</span>
          <button className="btn-ghost" style={{ fontSize: 12 }} onClick={onClose}>Close</button>
        </div>
      </div>
    </div>
  );
}
