"use client";
import React, { useState, useEffect, useRef, useCallback } from "react";
import {
  fetchAllotments,
  exportAllotmentsUrl,
  type AllotmentRow,
  type AllotmentFilters,
  type PaginatedResponse,
} from "@/lib/api";

const PAGE_SIZE = 100;
const DEBOUNCE = 300;

const ROUND_COLORS: Record<number, string> = {
  1: "#2871b5",
  2: "#e07b00",
  3: "#2e7d32",
  4: "#7b1fa2",
};

const OUTCOME_COLORS: Record<string, { color: string; bg: string }> = {
  RETAINED: { color: "#1b5e20", bg: "#e8f5e9" },
  UPGRADED:  { color: "#0d47a1", bg: "#e3f2fd" },
  LOST:      { color: "#b71c1c", bg: "#ffebee" },
  FRESH:     { color: "#4e342e", bg: "#efebe9" },
  NOT_ALLOTTED: { color: "#757575", bg: "#f5f5f5" },
};

interface Props {
  year: number;
  counsellingType: string;
}

export default function AllotmentView({ year, counsellingType }: Props) {
  const [data, setData] = useState<PaginatedResponse<AllotmentRow> | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [page, setPage] = useState(1);

  const [searchText, setSearchText] = useState("");
  const [rankMinText, setRankMinText] = useState("");
  const [rankMaxText, setRankMaxText] = useState("");
  const [selectedRound, setSelectedRound] = useState<number | undefined>(undefined);
  const [finalOnly, setFinalOnly] = useState(false);
  const [sortBy, setSortBy] = useState<AllotmentFilters["sort_by"]>("rank");
  const [sortOrder, setSortOrder] = useState<"asc" | "desc">("asc");

  const timer = useRef<ReturnType<typeof setTimeout> | null>(null);

  useEffect(() => {
    if (timer.current) clearTimeout(timer.current);
    setLoading(true);
    setError(null);
    timer.current = setTimeout(async () => {
      try {
        const rankMin = rankMinText ? parseInt(rankMinText, 10) : undefined;
        const rankMax = rankMaxText ? parseInt(rankMaxText, 10) : undefined;
        const res = await fetchAllotments({
          year,
          counselling_type: counsellingType,
          round: selectedRound,
          search: searchText || undefined,
          rank_min: rankMin && !isNaN(rankMin) ? rankMin : undefined,
          rank_max: rankMax && !isNaN(rankMax) ? rankMax : undefined,
          final_only: finalOnly || undefined,
          sort_by: sortBy,
          sort_order: sortOrder,
          page,
          page_size: PAGE_SIZE,
        });
        setData(res);
      } catch (e) {
        setError(e instanceof Error ? e.message : "Failed to load");
      } finally {
        setLoading(false);
      }
    }, DEBOUNCE);
    return () => { if (timer.current) clearTimeout(timer.current); };
  }, [year, counsellingType, selectedRound, finalOnly, searchText, rankMinText, rankMaxText, sortBy, sortOrder, page]);

  // Build current filters (shared between API fetch and CSV export URL)
  const currentFilters = useCallback((): AllotmentFilters => {
    const rankMin = rankMinText ? parseInt(rankMinText, 10) : undefined;
    const rankMax = rankMaxText ? parseInt(rankMaxText, 10) : undefined;
    return {
      year,
      counselling_type: counsellingType,
      round: selectedRound,
      search: searchText || undefined,
      rank_min: rankMin && !isNaN(rankMin) ? rankMin : undefined,
      rank_max: rankMax && !isNaN(rankMax) ? rankMax : undefined,
      final_only: finalOnly || undefined,
      sort_by: sortBy,
      sort_order: sortOrder,
    };
  }, [year, counsellingType, selectedRound, searchText, rankMinText, rankMaxText, finalOnly, sortBy, sortOrder]);

  const handleExportCsv = useCallback(() => {
    const url = exportAllotmentsUrl(currentFilters());
    const a = document.createElement("a");
    a.href = url;
    a.download = "";
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
  }, [currentFilters]);

  // Reset page when filters change
  const setFilter = useCallback((fn: () => void) => {
    fn();
    setPage(1);
  }, []);

  const handleSort = useCallback((col: AllotmentFilters["sort_by"]) => {
    if (sortBy === col) {
      setSortOrder(prev => (prev === "asc" ? "desc" : "asc"));
    } else {
      setSortBy(col);
      setSortOrder("asc");
    }
    setPage(1);
  }, [sortBy]);

  const SortIcon = ({ col }: { col: AllotmentFilters["sort_by"] }) => {
    if (sortBy !== col) return <span style={{ color: "#ccc", marginLeft: 3 }}>↕</span>;
    return <span style={{ color: "#2871b5", marginLeft: 3 }}>{sortOrder === "asc" ? "↑" : "↓"}</span>;
  };

  const rows = data?.data ?? [];
  const totalPages = data?.pages ?? 1;
  const total = data?.total ?? 0;

  const hasFilters = !!(searchText || rankMinText || rankMaxText || selectedRound !== undefined || finalOnly);

  return (
    <div style={{ display: "flex", flexDirection: "column", height: "100%", overflow: "hidden" }}>

      {/* Filter bar */}
      <div style={{
        background: "#fff", borderBottom: "1px solid #ddd",
        padding: "8px 20px", display: "flex", alignItems: "center", gap: 8, flexWrap: "wrap",
      }}>

        {/* Round selector */}
        <div style={{ display: "flex", alignItems: "center", gap: 4 }}>
          <span style={{ fontSize: 12, color: "#888", whiteSpace: "nowrap" }}>Round</span>
          <div style={{ display: "flex", border: "1px solid #ddd", borderRadius: 4, overflow: "hidden" }}>
            <button
              onClick={() => setFilter(() => setSelectedRound(undefined))}
              style={{
                padding: "4px 10px", fontSize: 12, border: "none", cursor: "pointer",
                borderRight: "1px solid #ddd",
                background: selectedRound === undefined ? "#2871b5" : "#fff",
                color: selectedRound === undefined ? "#fff" : "#555",
                fontWeight: selectedRound === undefined ? 600 : 400,
              }}
            >All</button>
            {([1, 2, 3, 4] as const).map((r, i) => {
              const active = selectedRound === r;
              const bg = ROUND_COLORS[r];
              return (
                <button
                  key={r}
                  onClick={() => setFilter(() => setSelectedRound(r))}
                  style={{
                    padding: "4px 10px", fontSize: 12, border: "none", cursor: "pointer",
                    borderRight: i < 3 ? "1px solid #ddd" : "none",
                    background: active ? bg : "#fff",
                    color: active ? "#fff" : "#555",
                    fontWeight: active ? 600 : 400,
                  }}
                >R{r}</button>
              );
            })}
          </div>
        </div>

        <div style={{ width: 1, height: 22, background: "#ddd" }} />

        {/* Search */}
        <input
          type="text"
          className="nv-input"
          placeholder="Search institute or course…"
          style={{ width: 220 }}
          value={searchText}
          onChange={e => { setSearchText(e.target.value); setPage(1); }}
        />

        {/* Rank range */}
        <div style={{ display: "flex", alignItems: "center", gap: 4 }}>
          <span style={{ fontSize: 12, color: "#888" }}>Rank</span>
          <input
            type="number"
            className="nv-input"
            placeholder="Min"
            style={{ width: 80 }}
            value={rankMinText}
            onChange={e => { setRankMinText(e.target.value); setPage(1); }}
          />
          <span style={{ fontSize: 12, color: "#aaa" }}>–</span>
          <input
            type="number"
            className="nv-input"
            placeholder="Max"
            style={{ width: 80 }}
            value={rankMaxText}
            onChange={e => { setRankMaxText(e.target.value); setPage(1); }}
          />
        </div>

        <div style={{ width: 1, height: 22, background: "#ddd" }} />

        {/* Final Round Only toggle */}
        <button
          onClick={() => { setFinalOnly(v => !v); setSelectedRound(undefined); setPage(1); }}
          title={
            finalOnly
              ? "全ラウンド表示に戻す"
              : "各ランクの最終ラウンドのみ表示（LOST/NOT_ALLOTTED除外）"
          }
          style={{
            padding: "4px 12px", fontSize: 12,
            border: `1px solid ${finalOnly ? "#2e7d32" : "#ddd"}`,
            borderRadius: 4, cursor: "pointer",
            background: finalOnly ? "#e8f5e9" : "#fff",
            color: finalOnly ? "#1b5e20" : "#555",
            fontWeight: finalOnly ? 700 : 400,
            whiteSpace: "nowrap",
          }}
        >
          {finalOnly ? "✓ Final Round Only" : "Final Round Only"}
        </button>

        {/* Clear all filters */}
        {hasFilters && (
          <button
            onClick={() => {
              setSearchText("");
              setRankMinText("");
              setRankMaxText("");
              setSelectedRound(undefined);
              setFinalOnly(false);
              setPage(1);
            }}
            style={{
              padding: "4px 10px", fontSize: 12, border: "1px solid #e44",
              borderRadius: 4, cursor: "pointer", background: "#fff8f8",
              color: "#c33", fontWeight: 600,
            }}
          >✕ Clear</button>
        )}

        <div style={{ flex: 1 }} />

        {/* CSV download */}
        <button
          onClick={handleExportCsv}
          title="Download filtered results as CSV"
          style={{
            padding: "4px 12px", fontSize: 12, border: "1px solid #4caf50",
            borderRadius: 4, cursor: "pointer", background: "#f1faf1",
            color: "#2e7d32", fontWeight: 600, whiteSpace: "nowrap",
          }}
        >
          ⬇ CSV
        </button>

        {/* Record count */}
        {data && !loading && (
          <span style={{ fontSize: 12, color: "#555", whiteSpace: "nowrap" }}>
            {((page - 1) * PAGE_SIZE + 1).toLocaleString()}–
            {Math.min(page * PAGE_SIZE, total).toLocaleString()} of{" "}
            <strong>{total.toLocaleString()}</strong> allotments
          </span>
        )}
      </div>

      {/* Info line */}
      <div style={{ background: finalOnly ? "#f0fff4" : "#fffbf0", borderBottom: `1px solid ${finalOnly ? "#b2dfdb" : "#f0e6c0"}`, padding: "5px 20px", fontSize: 11, color: finalOnly ? "#1b5e20" : "#7a6000" }}>
        {finalOnly
          ? "各ランクの最終ラウンド配属先のみ表示しています（LOST / NOT_ALLOTTED は除外）。同じRankに複数の大学・コースが表示される場合、同ラウンドで複数allotmentがあることを示します。"
          : "各ランカーが各ラウンドでどの大学・コースに配属されたかを表示します。同じRankの行はR1→R2→R3の順にソートされます。R2以降は Outcome 列でシート状況（RETAINED / UPGRADED / LOST）を確認できます。「Final Round Only」で最終配属先のみ絞り込めます。"
        }
      </div>

      {/* Table */}
      <div style={{ flex: 1, overflow: "auto" }}>
        {loading && (
          <div style={{ textAlign: "center", padding: 48, color: "#888", fontSize: 14 }}>Loading…</div>
        )}
        {!loading && error && (
          <div style={{ textAlign: "center", padding: 48, color: "#c33", fontSize: 14 }}>{error}</div>
        )}
        {!loading && !error && rows.length === 0 && (
          <div style={{ textAlign: "center", padding: 48, color: "#888", fontSize: 14 }}>
            {total === 0
              ? "Allotmentデータが見つかりません。PDFを取り込んでください。"
              : "条件に一致するレコードがありません。"}
          </div>
        )}
        {!loading && !error && rows.length > 0 && (
          <table style={{ width: "100%", borderCollapse: "collapse", fontSize: 12 }}>
            <thead>
              <tr style={{ background: "#f5f5f5", position: "sticky", top: 0, zIndex: 1, boxShadow: "0 1px 0 #ddd" }}>
                <Th onClick={() => handleSort("rank")} style={{ width: 80 }}>
                  Rank <SortIcon col="rank" />
                </Th>
                <Th style={{ width: 60 }}>Round</Th>
                <Th onClick={() => handleSort("institute_name")} style={{ minWidth: 200 }}>
                  Institute <SortIcon col="institute_name" />
                </Th>
                <Th style={{ minWidth: 140 }}>City / Pincode</Th>
                <Th onClick={() => handleSort("course_norm")} style={{ minWidth: 160 }}>
                  Course <SortIcon col="course_norm" />
                </Th>
                <Th style={{ width: 60 }}>Quota</Th>
                <Th style={{ width: 80 }}>Category</Th>
                <Th style={{ width: 120 }}>State</Th>
                <Th style={{ width: 110 }}>Outcome</Th>
              </tr>
            </thead>
            <tbody>
              {rows.map((row, i) => {
                const outcomeStyle = row.seat_outcome ? OUTCOME_COLORS[row.seat_outcome] : null;
                return (
                  <tr
                    key={row.id}
                    style={{ background: i % 2 === 0 ? "#fff" : "#fafafa", borderBottom: "1px solid #eee" }}
                  >
                    {/* Rank */}
                    <td style={{ ...tdBase, fontWeight: 700, color: "#111", fontSize: 13 }}>
                      {row.rank?.toLocaleString() ?? "–"}
                    </td>

                    {/* Round badge */}
                    <td style={tdBase}>
                      <span style={{
                        background: ROUND_COLORS[row.round] ?? "#888",
                        color: "#fff", borderRadius: 3,
                        padding: "2px 7px", fontWeight: 700, fontSize: 11,
                      }}>
                        R{row.round}
                      </span>
                    </td>

                    {/* Institute */}
                    <td style={{ ...tdBase, maxWidth: 280 }}>
                      <span
                        title={row.institute_raw ?? undefined}
                        style={{ overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap", display: "block" }}
                      >
                        {row.institute_name ?? row.institute_raw ?? "–"}
                      </span>
                    </td>

                    {/* Address (city + pincode) */}
                    <td style={{ ...tdBase, maxWidth: 160 }}>
                      {row.institute_city || row.institute_pincode ? (
                        <span style={{ overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap", display: "block", color: "#555", fontSize: 11 }}>
                          {[row.institute_city, row.institute_pincode].filter(Boolean).join(" ")}
                        </span>
                      ) : (
                        <span style={{ color: "#ccc", fontSize: 11 }}>–</span>
                      )}
                    </td>

                    {/* Course */}
                    <td style={{ ...tdBase, maxWidth: 240 }}>
                      <span
                        title={row.course_raw ?? undefined}
                        style={{ overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap", display: "block" }}
                      >
                        {row.course_norm ?? row.course_raw ?? "–"}
                      </span>
                    </td>

                    {/* Quota */}
                    <td style={tdBase}>{row.quota_norm ?? "–"}</td>

                    {/* Category */}
                    <td style={tdBase}>{row.allotted_category_norm ?? "–"}</td>

                    {/* State */}
                    <td style={tdBase}>{row.state ?? "–"}</td>

                    {/* Outcome */}
                    <td style={tdBase}>
                      {outcomeStyle ? (
                        <span style={{
                          background: outcomeStyle.bg,
                          color: outcomeStyle.color,
                          borderRadius: 3, padding: "2px 6px",
                          fontWeight: 600, fontSize: 11,
                        }}>
                          {row.seat_outcome}
                        </span>
                      ) : (
                        <span style={{ color: "#bbb", fontSize: 11 }}>–</span>
                      )}
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        )}
      </div>

      {/* Pagination */}
      {totalPages > 1 && (
        <div style={{
          background: "#fff", borderTop: "1px solid #ddd",
          padding: "8px 20px", display: "flex", alignItems: "center",
          justifyContent: "center", gap: 4,
        }}>
          <PageBtn onClick={() => setPage(1)} disabled={page <= 1}>«</PageBtn>
          <PageBtn onClick={() => setPage(p => Math.max(1, p - 1))} disabled={page <= 1}>‹</PageBtn>
          {buildPageNumbers(page, totalPages).map((p, i) =>
            p === -1
              ? <span key={`ellipsis-${i}`} style={{ padding: "0 4px", color: "#aaa" }}>…</span>
              : <PageBtn key={p} onClick={() => setPage(p)} active={p === page}>{p}</PageBtn>
          )}
          <PageBtn onClick={() => setPage(p => Math.min(totalPages, p + 1))} disabled={page >= totalPages}>›</PageBtn>
          <PageBtn onClick={() => setPage(totalPages)} disabled={page >= totalPages}>»</PageBtn>
        </div>
      )}
    </div>
  );
}

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function buildPageNumbers(current: number, total: number): number[] {
  if (total <= 9) return Array.from({ length: total }, (_, i) => i + 1);
  const pages: number[] = [];
  const add = (n: number) => { if (!pages.includes(n)) pages.push(n); };
  add(1);
  if (current > 4) pages.push(-1);
  for (let i = Math.max(2, current - 2); i <= Math.min(total - 1, current + 2); i++) add(i);
  if (current < total - 3) pages.push(-1);
  add(total);
  return pages;
}

function Th({
  children,
  onClick,
  style,
}: {
  children: React.ReactNode;
  onClick?: () => void;
  style?: React.CSSProperties;
}) {
  return (
    <th
      onClick={onClick}
      style={{
        padding: "8px 12px",
        textAlign: "left",
        fontSize: 11,
        fontWeight: 600,
        color: "#555",
        borderBottom: "2px solid #ddd",
        whiteSpace: "nowrap",
        cursor: onClick ? "pointer" : "default",
        userSelect: "none",
        ...style,
      }}
    >
      {children}
    </th>
  );
}

function PageBtn({
  children,
  onClick,
  disabled,
  active,
}: {
  children: React.ReactNode;
  onClick: () => void;
  disabled?: boolean;
  active?: boolean;
}) {
  return (
    <button
      onClick={onClick}
      disabled={disabled}
      style={{
        padding: "4px 8px",
        fontSize: 12,
        border: `1px solid ${active ? "#2871b5" : "#ddd"}`,
        borderRadius: 3,
        cursor: disabled ? "default" : "pointer",
        background: active ? "#2871b5" : "#fff",
        color: active ? "#fff" : disabled ? "#bbb" : "#555",
        fontWeight: active ? 600 : 400,
        minWidth: 32,
      }}
    >
      {children}
    </button>
  );
}

const tdBase: React.CSSProperties = {
  padding: "6px 12px",
  verticalAlign: "middle",
};
