"use client";
import React, { useState, useEffect, useRef, useCallback } from "react";
import Link from "next/link";
import {
  fetchInstitutes, fetchMetadata,
  type InstituteRow, type InstituteFilters, type PaginatedResponse, type MetadataResponse,
} from "@/lib/api";

const PAGE_SIZE = 50;
const DEBOUNCE = 300;

const DEFAULT_FILTERS: InstituteFilters = {
  sort_by: "display_name",
  sort_order: "asc",
};

function formatINR(v: number | string | null | undefined): string {
  if (v == null || v === "") return "—";
  const num = typeof v === "number" ? v : parseFloat(String(v).replace(/[₹,\s]/g, ""));
  if (isNaN(num)) return "—";
  if (num === 0) return "₹0";
  const s = Math.round(num).toString();
  if (s.length <= 3) return `₹${s}`;
  const last3 = s.slice(-3);
  let rest = s.slice(0, -3);
  const parts: string[] = [];
  while (rest.length > 2) { parts.unshift(rest.slice(-2)); rest = rest.slice(0, -2); }
  if (rest) parts.unshift(rest);
  return `₹${parts.join(",")},${last3}`;
}

type SortKey = InstituteFilters["sort_by"];

export default function InstitutesPage() {
  const [filters, setFilters] = useState<InstituteFilters>(DEFAULT_FILTERS);
  const [page, setPage] = useState(1);
  const [searchText, setSearchText] = useState("");
  const [gridData, setGridData] = useState<PaginatedResponse<InstituteRow> | null>(null);
  const [gridLoading, setGridLoading] = useState(false);
  const [gridError, setGridError] = useState<string | null>(null);
  const [metadata, setMetadata] = useState<MetadataResponse | null>(null);
  const [expandedRow, setExpandedRow] = useState<number | null>(null);

  // Load metadata for state filter
  useEffect(() => {
    fetchMetadata({ year: 2025, counselling_type: "AIQ" })
      .then(setMetadata)
      .catch(console.error);
  }, []);

  // Debounced fetch
  const timer = useRef<ReturnType<typeof setTimeout> | null>(null);
  useEffect(() => {
    if (timer.current) clearTimeout(timer.current);
    setGridLoading(true);
    setGridError(null);
    timer.current = setTimeout(async () => {
      try {
        const res = await fetchInstitutes({
          ...filters,
          search: searchText || undefined,
          page,
          page_size: PAGE_SIZE,
        });
        setGridData(res);
      } catch (e) {
        setGridError(e instanceof Error ? e.message : "Failed to load");
      } finally {
        setGridLoading(false);
      }
    }, DEBOUNCE);
    return () => { if (timer.current) clearTimeout(timer.current); };
  }, [filters, searchText, page]);

  const handleSort = useCallback((col: SortKey) => {
    setFilters(prev => ({
      ...prev,
      sort_by: col,
      sort_order: prev.sort_by === col && prev.sort_order === "asc" ? "desc" : "asc",
    }));
    setPage(1);
  }, []);

  const setStateFilter = useCallback((vals: string[]) => {
    setFilters(prev => ({ ...prev, state: vals.length ? vals : undefined }));
    setPage(1);
  }, []);

  const states = metadata?.states ?? [];
  const totalPages = gridData ? gridData.pages : 1;

  const SortArrow = ({ col }: { col: SortKey }) => {
    if (filters.sort_by !== col) return <span style={{ opacity: 0.3 }}>↕</span>;
    return <span>{filters.sort_order === "asc" ? "↑" : "↓"}</span>;
  };

  const TH = ({ col, label, w, center }: { col: SortKey; label: string; w: number; center?: boolean }) => (
    <th
      onClick={() => handleSort(col)}
      style={{
        padding: "8px 6px", fontSize: 11, fontWeight: 600, color: "#fff",
        background: "#2d5f8a", cursor: "pointer", whiteSpace: "nowrap",
        width: w, minWidth: w, textAlign: center ? "center" : "left",
        borderRight: "1px solid rgba(255,255,255,0.15)",
        position: "sticky", top: 0, zIndex: 2,
      }}
    >
      {label} <SortArrow col={col} />
    </th>
  );

  const StaticTH = ({ label, w, center }: { label: string; w: number; center?: boolean }) => (
    <th style={{
      padding: "8px 6px", fontSize: 11, fontWeight: 600, color: "#fff",
      background: "#2d5f8a", whiteSpace: "nowrap",
      width: w, minWidth: w, textAlign: center ? "center" : "left",
      borderRight: "1px solid rgba(255,255,255,0.15)",
      position: "sticky", top: 0, zIndex: 2,
    }}>
      {label}
    </th>
  );

  const COLS = 7; // total visible columns (Name, State, Annual Fee, Stipend Y1/Y2/Y3, Bond Penalty)

  return (
    <div style={{ display: "flex", flexDirection: "column", height: "100vh", background: "#f0f0f0" }}>

      {/* ── Header ── */}
      <div style={{ background: "#fff", borderBottom: "1px solid #ddd", padding: "10px 20px 0" }}>
        <div style={{ display: "flex", alignItems: "center", gap: 16, marginBottom: 6 }}>
          <div style={{ display: "flex", alignItems: "baseline", gap: 12 }}>
            <Link href="/" style={{ fontSize: 14, color: "#2871b5", textDecoration: "none" }}>← Closing Ranks</Link>
            <span style={{ fontSize: 20, fontWeight: 700, color: "#222" }}>Institute Profiles</span>
          </div>
          <div style={{ display: "flex", alignItems: "center", gap: 8, marginLeft: "auto" }}>
            {gridData && (
              <span style={{ fontSize: 12, color: "#555", whiteSpace: "nowrap" }}>
                {((page - 1) * PAGE_SIZE + 1).toLocaleString()}–{Math.min(page * PAGE_SIZE, gridData.total).toLocaleString()} of{" "}
                <strong>{gridData.total.toLocaleString()}</strong>
              </span>
            )}
          </div>
        </div>

        {/* Filter bar */}
        <div style={{ display: "flex", alignItems: "center", gap: 8, flexWrap: "wrap", paddingBottom: 10 }}>
          <input
            type="text"
            placeholder="Search institute name, state, PIN..."
            value={searchText}
            onChange={e => { setSearchText(e.target.value); setPage(1); }}
            style={{
              padding: "6px 12px", fontSize: 13, border: "1px solid #ccc", borderRadius: 4,
              width: 320, outline: "none",
            }}
          />

          <div style={{ width: 1, height: 22, background: "#ddd" }} />

          <select
            value=""
            onChange={e => {
              const val = e.target.value;
              if (!val) return;
              const current = filters.state ?? [];
              if (!current.includes(val)) setStateFilter([...current, val]);
            }}
            style={{ padding: "5px 8px", fontSize: 12, border: "1px solid #ccc", borderRadius: 4 }}
          >
            <option value="">+ State</option>
            {states.map(s => <option key={s} value={s}>{s}</option>)}
          </select>

          {(filters.state ?? []).map(s => (
            <span
              key={s}
              style={{
                display: "inline-flex", alignItems: "center", gap: 4,
                padding: "3px 8px", fontSize: 11, background: "#e3f0ff", color: "#1a5694",
                borderRadius: 12, cursor: "pointer",
              }}
              onClick={() => setStateFilter((filters.state ?? []).filter(x => x !== s))}
            >
              {s} ✕
            </span>
          ))}

          {(searchText || (filters.state ?? []).length > 0) && (
            <button
              onClick={() => { setSearchText(""); setFilters(DEFAULT_FILTERS); setPage(1); }}
              style={{
                padding: "4px 10px", fontSize: 11, background: "transparent",
                border: "1px solid #ccc", borderRadius: 4, cursor: "pointer", color: "#888",
              }}
            >
              Clear all
            </button>
          )}
        </div>
      </div>

      {/* ── Grid ── */}
      <div style={{ flex: 1, overflow: "auto", position: "relative" }}>
        {gridLoading && (
          <div style={{
            position: "absolute", top: 0, left: 0, right: 0, height: 3,
            background: "linear-gradient(90deg, #2871b5 0%, #5ba3e6 50%, #2871b5 100%)",
            backgroundSize: "200% 100%", animation: "shimmer 1.5s infinite",
          }} />
        )}

        {gridError && (
          <div style={{ padding: 20, color: "#c00", textAlign: "center" }}>{gridError}</div>
        )}

        <table style={{ width: "100%", borderCollapse: "collapse", fontSize: 12 }}>
          <thead>
            <tr>
              <TH col="display_name" label="Institute Name" w={320} />
              <TH col="state" label="State" w={130} />
              <TH col="annual_fee" label="Annual Fee" w={110} center />
              <TH col="stipend_yr1" label="Stipend Y1" w={110} center />
              <StaticTH label="Stipend Y2" w={110} center />
              <StaticTH label="Stipend Y3" w={110} center />
              <StaticTH label="Bond Penalty" w={110} center />
            </tr>
          </thead>
          <tbody>
            {gridData?.data.map((row) => {
              const isExpanded = expandedRow === row.institute_code;
              return (
                <React.Fragment key={row.institute_code}>
                  <tr
                    onClick={() => setExpandedRow(isExpanded ? null : row.institute_code)}
                    style={{
                      cursor: "pointer",
                      background: isExpanded ? "#f5f9ff" : "#fff",
                      borderBottom: "1px solid #eee",
                    }}
                    onMouseEnter={e => { if (!isExpanded) (e.currentTarget as HTMLElement).style.background = "#fafafa"; }}
                    onMouseLeave={e => { if (!isExpanded) (e.currentTarget as HTMLElement).style.background = "#fff"; }}
                  >
                    <td style={{ padding: "6px 8px", fontWeight: 500 }}>
                      {row.display_name}
                    </td>
                    <td style={{ padding: "6px", fontSize: 11 }}>{row.state ?? ""}</td>
                    <td style={{ padding: "6px", textAlign: "center" }}>{formatINR(row.annual_fee)}</td>
                    <td style={{ padding: "6px", textAlign: "center" }}>{formatINR(row.stipend_yr1)}</td>
                    <td style={{ padding: "6px", textAlign: "center" }}>{formatINR(row.stipend_yr2)}</td>
                    <td style={{ padding: "6px", textAlign: "center" }}>{formatINR(row.stipend_yr3)}</td>
                    <td style={{ padding: "6px", textAlign: "center" }}>{row.bond_forfeit ? formatINR(row.bond_forfeit) : "—"}</td>
                  </tr>

                  {/* Expanded detail row */}
                  {isExpanded && (
                    <tr style={{ background: "#f5f9ff" }}>
                      <td colSpan={COLS} style={{ padding: "12px 20px", borderBottom: "2px solid #2871b5" }}>
                        <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr 1fr", gap: "8px 24px", fontSize: 12 }}>
                          <div><strong>Annual Fee:</strong> {formatINR(row.annual_fee)}</div>
                          <div><strong>Bond Penalty:</strong> {row.bond_forfeit ? formatINR(row.bond_forfeit) : "—"}</div>
                          <div><strong>PIN Code:</strong> {row.pincode ?? "—"}</div>
                          <div><strong>Stipend Y1:</strong> {formatINR(row.stipend_yr1)}</div>
                          <div><strong>Stipend Y2:</strong> {formatINR(row.stipend_yr2)}</div>
                          <div><strong>Stipend Y3:</strong> {formatINR(row.stipend_yr3)}</div>
                          {row.university && <div style={{ gridColumn: "1 / -1" }}><strong>University:</strong> {row.university}</div>}
                          {row.address && <div style={{ gridColumn: "1 / -1", color: "#555" }}>{row.address}</div>}
                        </div>
                      </td>
                    </tr>
                  )}
                </React.Fragment>
              );
            })}
          </tbody>
        </table>

        {!gridLoading && gridData?.data.length === 0 && (
          <div style={{ padding: 40, textAlign: "center", color: "#888" }}>No institutes found.</div>
        )}
      </div>

      {/* ── Pagination ── */}
      {gridData && gridData.pages > 1 && (
        <div style={{
          display: "flex", alignItems: "center", justifyContent: "center", gap: 8,
          padding: "8px 20px", background: "#fff", borderTop: "1px solid #ddd",
        }}>
          <button
            disabled={page <= 1}
            onClick={() => setPage(p => Math.max(1, p - 1))}
            style={{
              padding: "4px 12px", fontSize: 12, border: "1px solid #ccc", borderRadius: 4,
              cursor: page <= 1 ? "default" : "pointer", background: "#fff",
              opacity: page <= 1 ? 0.5 : 1,
            }}
          >
            ← Prev
          </button>
          <span style={{ fontSize: 12, color: "#555" }}>
            Page {page} of {totalPages}
          </span>
          <button
            disabled={page >= totalPages}
            onClick={() => setPage(p => Math.min(totalPages, p + 1))}
            style={{
              padding: "4px 12px", fontSize: 12, border: "1px solid #ccc", borderRadius: 4,
              cursor: page >= totalPages ? "default" : "pointer", background: "#fff",
              opacity: page >= totalPages ? 0.5 : 1,
            }}
          >
            Next →
          </button>
        </div>
      )}

      <style>{`
        @keyframes shimmer {
          0% { background-position: -200% 0; }
          100% { background-position: 200% 0; }
        }
      `}</style>
    </div>
  );
}
