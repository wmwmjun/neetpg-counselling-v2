"use client";
import React, { useState } from "react";
import type { ClosingRankRow, PaginatedResponse, ClosingRankFilters } from "@/lib/api";
import type { FavoriteMap } from "@/hooks/useFavorites";
import { rowKey } from "@/hooks/useFavorites";

interface Props {
  data: PaginatedResponse<ClosingRankRow> | null;
  loading: boolean;
  error: string | null;
  page: number;
  pageSize: number;
  sortBy?: ClosingRankFilters["sort_by"];
  sortOrder?: "asc" | "desc";
  onPageChange: (p: number) => void;
  onGroupIdClick: (groupId: string) => void;
  onSort: (col: ClosingRankFilters["sort_by"]) => void;
  favorites: FavoriteMap;
  onToggleFavorite: (row: ClosingRankRow) => void;
  showFavoritesOnly: boolean;
  favoriteRows?: ClosingRankRow[];
}

const CAT_CLASS: Record<string, string> = {
  GN: "badge-GN", EW: "badge-EW", BC: "badge-BC", SC: "badge-SC", ST: "badge-ST",
};

/** Format a numeric-or-string rupee value. Non-numeric strings (e.g. "AS PER EXISTING RULES…") return "—". */
/** Format number as ₹ with Indian comma system (e.g. ₹1,23,400) */
function fmtRupees(v: number | string | null | undefined): string {
  if (v == null || v === "") return "—";
  const num = typeof v === "number" ? v : parseFloat(String(v).replace(/[₹,\s]/g, ""));
  if (isNaN(num)) return "—";
  if (num === 0) return "₹0";
  // Indian numbering: 1,23,45,678
  const s = Math.round(num).toString();
  if (s.length <= 3) return `₹${s}`;
  // Last 3 digits, then groups of 2
  const last3 = s.slice(-3);
  let rest = s.slice(0, -3);
  const parts: string[] = [];
  while (rest.length > 2) {
    parts.unshift(rest.slice(-2));
    rest = rest.slice(0, -2);
  }
  if (rest) parts.unshift(rest);
  return `₹${parts.join(",")},${last3}`;
}

function InstitutePopup({ row, onClose }: {
  row: ClosingRankRow;
  onClose: () => void;
}) {
  const displayName = row.institute_address_verified || row.institute_name || "—";
  const isMatched = row.inst_matched !== false && row.inst_matched !== null;

  return (
    <div
      style={{ position: "fixed", inset: 0, background: "rgba(0,0,0,0.35)", zIndex: 9999, display: "flex", alignItems: "center", justifyContent: "center" }}
      onClick={onClose}
    >
      <div
        style={{ background: "#fff", borderRadius: 8, padding: 24, maxWidth: 560, width: "90%", boxShadow: "0 8px 32px rgba(0,0,0,0.2)" }}
        onClick={e => e.stopPropagation()}
      >
        {/* Header */}
        <div style={{ fontWeight: 700, fontSize: 15, marginBottom: 4, color: "#1a1a2e" }}>
          {displayName}
          {!isMatched && (
            <span style={{ marginLeft: 8, fontSize: 11, color: "#e05c00", background: "#fff3e0", padding: "2px 6px", borderRadius: 3, fontWeight: 600 }}>
              Unmatched
            </span>
          )}
        </div>
        {(row.state || row.institute_pincode) && (
          <div style={{ fontSize: 12, color: "#2871b5", marginBottom: 12 }}>
            {[row.state, row.institute_pincode].filter(Boolean).join(" – ")}
          </div>
        )}

        {/* Address */}
        <div style={{ borderTop: "1px solid #eee", paddingTop: 10, marginBottom: 14 }}>
          <div style={{ fontSize: 11, fontWeight: 600, color: "#888", textTransform: "uppercase", letterSpacing: "0.06em", marginBottom: 5 }}>
            Address
          </div>
          <div style={{ fontSize: 13, color: "#444", lineHeight: 1.7 }}>
            {row.institute_address
              ? row.institute_address
              : <span style={{ color: "#aaa", fontStyle: "italic" }}>情報なし</span>}
          </div>
        </div>

        {/* University */}
        {row.inst_university && (
          <div style={{ borderTop: "1px solid #eee", paddingTop: 10, marginBottom: 14 }}>
            <div style={{ fontSize: 11, fontWeight: 600, color: "#888", textTransform: "uppercase", letterSpacing: "0.06em", marginBottom: 5 }}>
              University
            </div>
            <div style={{ fontSize: 13, color: "#444" }}>{row.inst_university}</div>
          </div>
        )}

        {/* Fee (admission — single value) */}
        {isMatched && row.inst_fee_yr1 != null && (
          <div style={{ borderTop: "1px solid #eee", paddingTop: 10, marginBottom: 14, display: "flex", justifyContent: "space-between", alignItems: "center" }}>
            <div style={{ fontSize: 11, fontWeight: 600, color: "#888", textTransform: "uppercase", letterSpacing: "0.06em" }}>
              Fee (Admission)
            </div>
            <div style={{ fontSize: 14, fontWeight: 600, color: "#1a1a2e" }}>{fmtRupees(row.inst_fee_yr1)}</div>
          </div>
        )}

        {/* Stipend Y1 / Y2 / Y3 */}
        {isMatched && (row.inst_stipend_yr1 || row.inst_stipend_yr2 || row.inst_stipend_yr3) && (
          <div style={{ borderTop: "1px solid #eee", paddingTop: 10, marginBottom: 14 }}>
            <div style={{ fontSize: 11, fontWeight: 600, color: "#888", textTransform: "uppercase", letterSpacing: "0.06em", marginBottom: 8 }}>
              Stipend (Monthly)
            </div>
            <div style={{ display: "flex", gap: 12 }}>
              {[
                { label: "Year 1", val: row.inst_stipend_yr1 },
                { label: "Year 2", val: row.inst_stipend_yr2 },
                { label: "Year 3", val: row.inst_stipend_yr3 },
              ].map(({ label, val }) => (
                <div key={label} style={{ flex: 1, background: "#f7f9ff", borderRadius: 6, padding: "8px 10px", textAlign: "center" }}>
                  <div style={{ fontSize: 10, color: "#888", marginBottom: 4 }}>{label}</div>
                  <div style={{ fontSize: 13, fontWeight: 600, color: "#2871b5" }}>{fmtRupees(val)}</div>
                </div>
              ))}
            </div>
          </div>
        )}

        {/* Bond Info */}
        {isMatched && (row.inst_bond_years || (row.inst_bond_forfeit && fmtRupees(row.inst_bond_forfeit) !== "—")) && (
          <div style={{ borderTop: "1px solid #eee", paddingTop: 10, marginBottom: 14 }}>
            <div style={{ display: "flex", gap: 16, flexWrap: "wrap" }}>
              {row.inst_bond_years && (
                <div>
                  <div style={{ fontSize: 11, fontWeight: 600, color: "#888", textTransform: "uppercase", letterSpacing: "0.06em" }}>Bond Service</div>
                  <div style={{ fontSize: 14, fontWeight: 600, color: "#333" }}>{row.inst_bond_years} year{Number(row.inst_bond_years) !== 1 ? "s" : ""}</div>
                </div>
              )}
              {row.inst_bond_forfeit && fmtRupees(row.inst_bond_forfeit) !== "—" && (
                <div>
                  <div style={{ fontSize: 11, fontWeight: 600, color: "#888", textTransform: "uppercase", letterSpacing: "0.06em" }}>Bond Penalty</div>
                  <div style={{ fontSize: 14, fontWeight: 600, color: "#c0392b" }}>{fmtRupees(row.inst_bond_forfeit)}</div>
                </div>
              )}
              {row.inst_beds && (
                <div>
                  <div style={{ fontSize: 11, fontWeight: 600, color: "#888", textTransform: "uppercase", letterSpacing: "0.06em" }}>Beds</div>
                  <div style={{ fontSize: 14, fontWeight: 600, color: "#333" }}>{row.inst_beds.toLocaleString()}</div>
                </div>
              )}
            </div>
          </div>
        )}

        <button onClick={onClose} style={{ marginTop: 8, background: "#2871b5", color: "#fff", border: "none", borderRadius: 4, padding: "6px 18px", cursor: "pointer", fontSize: 13 }}>閉じる</button>
      </div>
    </div>
  );
}

// Sortable column header
function SortTh({
  children, col, sortBy, sortOrder, onSort, style,
}: {
  children: React.ReactNode;
  col: ClosingRankFilters["sort_by"];
  sortBy?: ClosingRankFilters["sort_by"];
  sortOrder?: "asc" | "desc";
  onSort: (col: ClosingRankFilters["sort_by"]) => void;
  style?: React.CSSProperties;
}) {
  const active = sortBy === col;
  const arrow = active ? (sortOrder === "asc" ? " ▲" : " ▼") : " ⇅";
  return (
    <th
      onClick={() => onSort(col)}
      style={{
        cursor: "pointer", userSelect: "none", whiteSpace: "nowrap",
        ...style,
        color: active ? "#2871b5" : (style?.color ?? "#444"),
      }}
      title={active ? (sortOrder === "asc" ? "Z→A でソート" : "A→Z でソート") : "クリックでソート"}
    >
      {children}
      <span style={{ opacity: active ? 1 : 0.35, fontSize: 10, marginLeft: 2 }}>{arrow}</span>
    </th>
  );
}

export default function ClosingRankGrid({
  data, loading, error, page, pageSize,
  sortBy, sortOrder, onPageChange, onGroupIdClick, onSort,
  favorites, onToggleFavorite, showFavoritesOnly, favoriteRows,
}: Props) {
  const [popupRow, setPopupRow] = useState<ClosingRankRow | null>(null);

  const duplicateNames = React.useMemo(() => {
    const rows = showFavoritesOnly ? (favoriteRows ?? []) : (data?.data ?? []);
    const counts: Record<string, Set<string>> = {};
    for (const row of rows) {
      const name = row.institute_name ?? "";
      if (!counts[name]) counts[name] = new Set();
      counts[name].add(row.institute_city ?? "");
    }
    return new Set(Object.entries(counts).filter(([, cities]) => cities.size > 1).map(([name]) => name));
  }, [data, showFavoritesOnly, favoriteRows]);

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

  // In favorites-only mode: use favoriteRows directly
  const displayRows: ClosingRankRow[] = showFavoritesOnly
    ? (favoriteRows ?? [])
    : (data?.data ?? []);

  if (showFavoritesOnly && displayRows.length === 0) {
    return (
      <div style={{ padding: 60, textAlign: "center", color: "#888" }}>
        <div style={{ fontSize: 36, marginBottom: 10 }}>☆</div>
        <div style={{ fontSize: 15, marginBottom: 6 }}>お気に入りはまだありません</div>
        <div style={{ fontSize: 12 }}>行の ☆ ボタンをクリックして登録できます。</div>
      </div>
    );
  }

  if (!showFavoritesOnly && (!data || data.total === 0)) {
    return (
      <div style={{ padding: 60, textAlign: "center", color: "#888" }}>
        <div style={{ fontSize: 32, marginBottom: 8 }}>📋</div>
        <div>No records found. Adjust your filters.</div>
      </div>
    );
  }

  const total = showFavoritesOnly ? displayRows.length : (data?.total ?? 0);
  const pages = showFavoritesOnly ? 1 : (data?.pages ?? 1);
  const start = showFavoritesOnly ? 1 : (page - 1) * pageSize + 1;
  const end = showFavoritesOnly ? displayRows.length : Math.min(page * pageSize, total);

  return (
    <div style={{ display: "flex", flexDirection: "column", height: "100%" }}>
      {popupRow && (
        <InstitutePopup
          row={popupRow}
          onClose={() => setPopupRow(null)}
        />
      )}
      {/* Table scroll area */}
      <div style={{ flex: 1, overflow: "auto", position: "relative" }}>
        {loading && (
          <div style={{
            position: "absolute", inset: 0, zIndex: 10,
            background: "rgba(255,255,255,0.55)",
            display: "flex", alignItems: "flex-start", justifyContent: "center",
            paddingTop: 40, pointerEvents: "none",
          }}>
            <div style={{ display: "flex", alignItems: "center", gap: 8, background: "#fff", border: "1px solid #ddd", borderRadius: 6, padding: "8px 16px", boxShadow: "0 2px 8px rgba(0,0,0,0.10)" }}>
              <div style={{ width: 16, height: 16, border: "2px solid #2871b5", borderTopColor: "transparent", borderRadius: "50%", animation: "spin 0.8s linear infinite" }} />
              <span style={{ fontSize: 13, color: "#2871b5", fontWeight: 500 }}>Updating results…</span>
            </div>
          </div>
        )}
        <table className="cr-table">
          <thead>
            <tr>
              <th style={{ minWidth: 32, width: 32, textAlign: "center" }}>☆</th>
              <SortTh col="quota_norm" sortBy={sortBy} sortOrder={sortOrder} onSort={onSort} style={{ minWidth: 50 }}>
                Quota
              </SortTh>
              <SortTh col="allotted_category_norm" sortBy={sortBy} sortOrder={sortOrder} onSort={onSort} style={{ minWidth: 60 }}>
                Category
              </SortTh>
              <SortTh col="state" sortBy={sortBy} sortOrder={sortOrder} onSort={onSort} style={{ minWidth: 100 }}>
                State
              </SortTh>
              <SortTh col="institute_name" sortBy={sortBy} sortOrder={sortOrder} onSort={onSort} style={{ minWidth: 260 }}>
                Institute
              </SortTh>
              <SortTh col="institute_pincode" sortBy={sortBy} sortOrder={sortOrder} onSort={onSort} style={{ minWidth: 80 }}>
                Pincode
              </SortTh>
              <SortTh col="course_norm" sortBy={sortBy} sortOrder={sortOrder} onSort={onSort} style={{ minWidth: 200 }}>
                Course
              </SortTh>
              <SortTh col="inst_fee_yr1" sortBy={sortBy} sortOrder={sortOrder} onSort={onSort} style={{ minWidth: 80, fontSize: 11 }}>
                Fee
              </SortTh>
              <SortTh col="inst_stipend_yr1" sortBy={sortBy} sortOrder={sortOrder} onSort={onSort} style={{ minWidth: 90, fontSize: 11 }}>
                Stipend Y1
              </SortTh>
              <th style={{ minWidth: 70, fontSize: 11 }}>Bond Yrs</th>
              <SortTh col="inst_bond_forfeit" sortBy={sortBy} sortOrder={sortOrder} onSort={onSort} style={{ minWidth: 100, fontSize: 11 }}>
                Bond Penalty
              </SortTh>
              <th style={{ minWidth: 60, fontSize: 11 }}>Beds</th>
              <SortTh col="r1_closing_rank" sortBy={sortBy} sortOrder={sortOrder} onSort={onSort} style={{ minWidth: 100, color: "#2871b5" }}>
                CR 2025 R1
              </SortTh>
              <SortTh col="r2_closing_rank" sortBy={sortBy} sortOrder={sortOrder} onSort={onSort} style={{ minWidth: 100, color: "#e07b00" }}>
                CR 2025 R2
              </SortTh>
              <SortTh col="r3_closing_rank" sortBy={sortBy} sortOrder={sortOrder} onSort={onSort} style={{ minWidth: 100, color: "#2e7d32" }}>
                CR 2025 R3
              </SortTh>
              <SortTh col="r4_closing_rank" sortBy={sortBy} sortOrder={sortOrder} onSort={onSort} style={{ minWidth: 100, color: "#7b1fa2" }}>
                CR 2025 R4
              </SortTh>
            </tr>
          </thead>
          <tbody>
            {displayRows.map((row) => {
              const faved = favorites.has(rowKey(row));
              // Use display_name from institutes if matched, otherwise original name
              const displayName = row.institute_address_verified || row.institute_name || "—";
              const isUnmatched = row.inst_matched === false || row.inst_matched === null;
              return (
              <tr key={`${row.r1_group_id ?? row.r2_group_id ?? row.institute_name}-${row.course_norm}-${row.quota_norm}-${row.allotted_category_norm}`}>
                {/* Favorite star */}
                <td style={{ textAlign: "center", padding: "0 4px" }}>
                  <button
                    onClick={e => { e.stopPropagation(); onToggleFavorite(row); }}
                    title={faved ? "お気に入り解除" : "お気に入りに追加"}
                    style={{
                      background: "none", border: "none", cursor: "pointer",
                      fontSize: 16, lineHeight: 1, padding: "2px 0",
                      color: faved ? "#f5a623" : "#ccc",
                      transition: "color 0.15s",
                    }}
                  >
                    {faved ? "★" : "☆"}
                  </button>
                </td>
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
                {/* Institute — show display_name + unmatched flag */}
                <td>
                  <span style={{ display: "flex", alignItems: "center", gap: 4 }}>
                    {isUnmatched && (
                      <span title="Institute未対応" style={{
                        display: "inline-block", width: 8, height: 8, borderRadius: "50%",
                        background: "#e05c00", flexShrink: 0,
                      }} />
                    )}
                    <span className="inst-link" style={{ fontWeight: 500 }}>
                      {displayName}
                    </span>
                    <button
                      onClick={e => { e.stopPropagation(); setPopupRow(row); }}
                      title="詳細を表示"
                      style={{ background: "none", border: "none", cursor: "pointer", color: "#bbb", fontSize: 13, padding: "0 2px", lineHeight: 1 }}
                    >ⓘ</button>
                  </span>
                </td>
                {/* Pincode */}
                <td style={{ color: "#888", fontSize: 12, fontVariantNumeric: "tabular-nums" }}>
                  {row.institute_pincode ?? "—"}
                </td>
                {/* Course */}
                <td style={{ color: "#333" }}>{row.course_norm ?? "—"}</td>
                {/* Fee (admission) */}
                {(() => { const v = fmtRupees(row.inst_fee_yr1); return (
                <td style={{ textAlign: "right", fontSize: 12, color: v !== "—" ? "#333" : "#ccc", fontVariantNumeric: "tabular-nums" }}>
                  {v}
                </td>
                ); })()}
                {/* Stipend Y1 */}
                {(() => { const v = fmtRupees(row.inst_stipend_yr1); return (
                <td style={{ textAlign: "right", fontSize: 12, color: v !== "—" ? "#2871b5" : "#ccc", fontVariantNumeric: "tabular-nums" }}>
                  {v}
                </td>
                ); })()}
                {/* Bond Years */}
                <td style={{ textAlign: "center", fontSize: 12, color: row.inst_bond_years ? "#333" : "#ccc" }}>
                  {row.inst_bond_years ? `${row.inst_bond_years}yr` : "—"}
                </td>
                {/* Bond Penalty */}
                {(() => { const v = fmtRupees(row.inst_bond_forfeit); return (
                <td style={{ textAlign: "right", fontSize: 12, color: v !== "—" ? "#c0392b" : "#ccc", fontVariantNumeric: "tabular-nums" }}>
                  {v}
                </td>
                ); })()}
                {/* Beds */}
                <td style={{ textAlign: "center", fontSize: 12, color: row.inst_beds ? "#333" : "#ccc" }}>
                  {row.inst_beds ? row.inst_beds.toLocaleString() : "—"}
                </td>
                {/* CR 2025 R1 */}
                <td style={{ textAlign: "center" }}>
                  {row.r1_group_id ? (
                    <button className="cr-link" onClick={() => onGroupIdClick(row.r1_group_id!)} style={{ background: "none", border: "none", padding: 0, font: "inherit", color: "#2871b5" }}>
                      {row.r1_closing_rank != null
                        ? `${row.r1_closing_rank.toLocaleString()}(${row.r1_allotment_count})`
                        : "—"}
                    </button>
                  ) : <span style={{ color: "#bbb" }}>—</span>}
                </td>
                {/* CR 2025 R2 */}
                <td style={{ textAlign: "center" }}>
                  {row.r2_group_id ? (
                    <button className="cr-link" onClick={() => onGroupIdClick(row.r2_group_id!)} style={{ background: "none", border: "none", padding: 0, font: "inherit", color: "#e07b00" }}>
                      {row.r2_closing_rank != null
                        ? `${row.r2_closing_rank.toLocaleString()}(${row.r2_allotment_count})`
                        : "—"}
                    </button>
                  ) : <span style={{ color: "#bbb" }}>—</span>}
                </td>
                {/* CR 2025 R3 */}
                <td style={{ textAlign: "center" }}>
                  {row.r3_group_id ? (
                    <button className="cr-link" onClick={() => onGroupIdClick(row.r3_group_id!)} style={{ background: "none", border: "none", padding: 0, font: "inherit", color: "#2e7d32" }}>
                      {row.r3_closing_rank != null
                        ? `${row.r3_closing_rank.toLocaleString()}(${row.r3_allotment_count})`
                        : "—"}
                    </button>
                  ) : <span style={{ color: "#bbb" }}>—</span>}
                </td>
                {/* CR 2025 R4 */}
                <td style={{ textAlign: "center" }}>
                  {row.r4_group_id ? (
                    <button className="cr-link" onClick={() => onGroupIdClick(row.r4_group_id!)} style={{ background: "none", border: "none", padding: 0, font: "inherit", color: "#7b1fa2" }}>
                      {row.r4_closing_rank != null
                        ? `${row.r4_closing_rank.toLocaleString()}(${row.r4_allotment_count})`
                        : "—"}
                    </button>
                  ) : <span style={{ color: "#bbb" }}>—</span>}
                </td>
              </tr>
              );
            })}
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
          {showFavoritesOnly
            ? <><span style={{ color: "#f5a623", fontWeight: 600 }}>★ お気に入り</span> {displayRows.length.toLocaleString()} 件</>
            : <>{start.toLocaleString()}–{end.toLocaleString()} of {total.toLocaleString()} Records</>
          }
        </div>
        {!showFavoritesOnly && pages > 1 && (
          <Pagination current={page} total={pages} onChange={onPageChange} />
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
