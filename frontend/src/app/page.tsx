"use client";
import React, { useState, useEffect, useCallback, useRef } from "react";
import Link from "next/link";
import ClosingRankGrid from "@/components/ClosingRankGrid";
import DrillDownModal from "@/components/DrillDownModal";
import FilterModal from "@/components/FilterModal";
import {
  fetchMetadata, fetchClosingRanks, fetchDrillDown, exportClosingRanksUrl,
  type MetadataResponse, type ClosingRankFilters,
  type ClosingRankRow, type PaginatedResponse, type DrillDownResponse,
} from "@/lib/api";
import { useFavorites } from "@/hooks/useFavorites";

const DEFAULT_FILTERS: ClosingRankFilters = {
  year: 2025, counselling_type: "AIQ",
  sort_by: "institute_name", sort_order: "asc",
};
const PAGE_SIZE = 50;
const DEBOUNCE = 300;

export default function HomePage() {
  const [filters, setFilters] = useState<ClosingRankFilters>(DEFAULT_FILTERS);
  const [page, setPage] = useState(1);

  const [metadata, setMetadata] = useState<MetadataResponse | null>(null);
  const [gridData, setGridData] = useState<PaginatedResponse<ClosingRankRow> | null>(null);
  const [gridLoading, setGridLoading] = useState(false);
  const [gridError, setGridError] = useState<string | null>(null);

  const [filterModalOpen, setFilterModalOpen] = useState(false);
  const [showFavoritesOnly, setShowFavoritesOnly] = useState(false);
  const { favorites, toggleFavorite, clearFavorites } = useFavorites();

  // Quick-filter local state (top bar)
  const [searchText, setSearchText] = useState("");
  const [myRankText, setMyRankText] = useState("");

  const [activeGroupId, setActiveGroupId] = useState<string | null>(null);
  const [modalData, setModalData] = useState<DrillDownResponse | null>(null);
  const [modalLoading, setModalLoading] = useState(false);
  const [modalError, setModalError] = useState<string | null>(null);

  // Load metadata
  useEffect(() => {
    fetchMetadata({ year: 2025, counselling_type: "AIQ" })
      .then(setMetadata)
      .catch(console.error);
  }, []);

  // Debounced grid fetch
  const timer = useRef<ReturnType<typeof setTimeout> | null>(null);
  useEffect(() => {
    if (timer.current) clearTimeout(timer.current);
    // Show loading immediately (don't wait for debounce) so stale data
    // isn't misleadingly shown with updated filter chips
    setGridLoading(true);
    setGridError(null);
    timer.current = setTimeout(async () => {
      try {
        const myRankNum = myRankText ? parseInt(myRankText, 10) : undefined;
        const res = await fetchClosingRanks({
          ...filters,
          search: searchText || undefined,
          my_rank: myRankNum && !isNaN(myRankNum) ? myRankNum : undefined,
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
  }, [filters, searchText, myRankText, page]);

  const handleFilterApply = useCallback((f: ClosingRankFilters) => {
    setFilters(f); setPage(1);
  }, []);

  const handleGroupIdClick = useCallback(async (groupId: string) => {
    setActiveGroupId(groupId);
    setModalData(null); setModalLoading(true); setModalError(null);
    try {
      setModalData(await fetchDrillDown(groupId));
    } catch (e) {
      setModalError(e instanceof Error ? e.message : "Failed to load");
    } finally {
      setModalLoading(false);
    }
  }, []);

  const closeModal = useCallback(() => {
    setActiveGroupId(null); setModalData(null); setModalError(null);
  }, []);

  // Clear all filters
  const handleClearAll = useCallback(() => {
    setFilters(DEFAULT_FILTERS);
    setSearchText("");
    setMyRankText("");
    setPage(1);
  }, []);

  // Sort handler (from column header clicks)
  const handleSort = useCallback((col: ClosingRankFilters["sort_by"]) => {
    setFilters(prev => ({
      ...prev,
      sort_by: col,
      sort_order: prev.sort_by === col && prev.sort_order === "asc" ? "desc" : "asc",
    }));
    setPage(1);
  }, []);

  // Multi-value filter setter helper
  const setMultiFilter = useCallback((key: keyof ClosingRankFilters, values: string[]) => {
    setFilters(prev => ({ ...prev, [key]: values.length ? values : undefined }));
    setPage(1);
  }, []);

  // CSV export — build URL with all current filters and trigger download
  const handleExportCsv = useCallback(() => {
    const myRankNum = myRankText ? parseInt(myRankText, 10) : undefined;
    const url = exportClosingRanksUrl({
      ...filters,
      search: searchText || undefined,
      my_rank: myRankNum && !isNaN(myRankNum) ? myRankNum : undefined,
    });
    const a = document.createElement("a");
    a.href = url;
    a.download = "";
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
  }, [filters, searchText, myRankText]);

  // Round display toggle — multi-select
  const toggleRound = useCallback((r: "r1" | "r2" | "r3" | "r4") => {
    setFilters(prev => {
      const current = prev.round_display ?? [];
      const next = current.includes(r)
        ? current.filter(x => x !== r)
        : [...current, r];
      return { ...prev, round_display: next.length ? next : undefined };
    });
    setPage(1);
  }, []);
  const clearRounds = useCallback(() => {
    setFilters(prev => ({ ...prev, round_display: undefined }));
    setPage(1);
  }, []);

  // Count active advanced filters (excluding defaults and quick-bar items)
  const activeFilterCount = [
    filters.quota_norm, filters.allotted_category_norm, filters.state, filters.course_norm,
    filters.course_type,
    filters.rank_min, filters.rank_max,
    filters.fee_min, filters.fee_max, filters.bond_min, filters.bond_max,
  ].filter(v => v !== undefined && v !== null).length;

  // Any filter active (for Clear All button visibility)
  const hasActiveFilters = !!(
    searchText || myRankText || filters.round_display?.length ||
    filters.quota_norm?.length || filters.allotted_category_norm?.length ||
    filters.state?.length || filters.course_norm?.length ||
    filters.course_type?.length ||
    filters.rank_min || filters.rank_max ||
    filters.fee_min || filters.fee_max || filters.bond_min || filters.bond_max
  );

  const quotas = metadata?.quotas ?? [];
  const categories = metadata?.categories ?? [];
  const states = metadata?.states ?? [];
  const courses = metadata?.courses ?? [];

  const roundDisplay = filters.round_display ?? [];

  return (
    <div style={{ display: "flex", flexDirection: "column", height: "100vh", background: "#f0f0f0" }}>

      {/* ── Top header ── */}
      <div style={{ background: "#fff", borderBottom: "1px solid #ddd", padding: "10px 20px 0" }}>
        {/* Title row */}
        <div style={{ display: "flex", alignItems: "center", gap: 16, marginBottom: 6 }}>
          <div style={{ display: "flex", alignItems: "baseline", gap: 8 }}>
            <span style={{ fontSize: 20, fontWeight: 700, color: "#222" }}>Closing Ranks</span>
            <Link href="/institutes" style={{ fontSize: 12, color: "#2871b5", textDecoration: "none", padding: "3px 10px", border: "1px solid #2871b5", borderRadius: 4 }}>Institute Profiles →</Link>
          </div>
          <div style={{ display: "flex", alignItems: "center", gap: 8, marginLeft: "auto" }}>
            {gridData && (
              <span style={{ fontSize: 12, color: "#555", whiteSpace: "nowrap" }}>
                {((page - 1) * PAGE_SIZE + 1).toLocaleString()}–{Math.min(page * PAGE_SIZE, gridData.total).toLocaleString()} of{" "}
                <strong>{gridData.total.toLocaleString()}</strong> Records
              </span>
            )}
            <span style={{ fontSize: 12, color: "#888" }}>Spotted an error?</span>
          </div>
        </div>

        {/* Counselling type selector */}
        <div style={{ display: "flex", alignItems: "center", gap: 10, marginBottom: 8 }}>
          <select className="nv-select" style={{ fontWeight: 600, color: "#222" }} value="AIQ" onChange={() => {}}>
            <option value="AIQ">All India Counselling – PG Medical</option>
            <option value="STATE" disabled>State Counselling (coming soon)</option>
          </select>
          <button className="btn-outline" style={{ fontSize: 12, color: "#2871b5" }}>
            Go to counselling ↗
          </button>
        </div>

        {/* Info line */}
        <div style={{ fontSize: 11, color: "#888", marginBottom: 8 }}>
          * Click on Ranks to view the allotment list. &nbsp;|&nbsp;
          Click on the record for detailed information. &nbsp;|&nbsp;
          * indicates additional remarks.
        </div>

        {/* ── Quick filter bar ── */}
        <div style={{ display: "flex", alignItems: "center", gap: 8, flexWrap: "wrap", paddingBottom: 10 }}>

          {/* Round multi-select toggle */}
          <div style={{ display: "flex", alignItems: "center", gap: 4 }}>
            <span style={{ fontSize: 12, color: "#888", whiteSpace: "nowrap" }}>Round</span>
            <div style={{ display: "flex", border: "1px solid #ddd", borderRadius: 4, overflow: "hidden" }}>
              <button
                onClick={clearRounds}
                style={{
                  padding: "4px 10px", fontSize: 12, border: "none", cursor: "pointer",
                  borderRight: "1px solid #ddd",
                  background: roundDisplay.length === 0 ? "#2871b5" : "#fff",
                  color: roundDisplay.length === 0 ? "#fff" : "#555",
                  fontWeight: roundDisplay.length === 0 ? 600 : 400,
                }}
              >All</button>
              {(["r1", "r2", "r3", "r4"] as const).map((r, i) => {
                const active = roundDisplay.includes(r);
                const colors: Record<string, string> = { r1: "#2871b5", r2: "#e07b00", r3: "#2e7d32", r4: "#7b1fa2" };
                return (
                  <button
                    key={r}
                    onClick={() => toggleRound(r)}
                    style={{
                      padding: "4px 10px", fontSize: 12, border: "none", cursor: "pointer",
                      borderRight: i < 3 ? "1px solid #ddd" : "none",
                      background: active ? colors[r] : "#fff",
                      color: active ? "#fff" : "#555",
                      fontWeight: active ? 600 : 400,
                    }}
                  >
                    {r.toUpperCase()}
                  </button>
                );
              })}
            </div>
          </div>

          {/* Divider */}
          <div style={{ width: 1, height: 22, background: "#ddd" }} />

          {/* Search */}
          <input
            type="text"
            className="nv-input"
            placeholder="Search institute…"
            style={{ width: 180 }}
            value={searchText}
            onChange={e => { setSearchText(e.target.value); setPage(1); }}
          />

          {/* Rank input */}
          <div style={{ display: "flex", alignItems: "center", gap: 4 }}>
            <input
              type="number"
              className="nv-input"
              placeholder="My Rank"
              style={{ width: 90 }}
              value={myRankText}
              onChange={e => { setMyRankText(e.target.value); setPage(1); }}
            />
            {myRankText && (
              <button
                onClick={() => { setMyRankText(""); setPage(1); }}
                style={{ background: "none", border: "none", cursor: "pointer", color: "#999", fontSize: 14, padding: "0 2px" }}
              >×</button>
            )}
          </div>

          {/* Divider */}
          <div style={{ width: 1, height: 22, background: "#ddd" }} />

          {/* Quota multi-select */}
          <div style={{ display: "flex", alignItems: "center", gap: 4, fontSize: 12 }}>
            <span style={{ color: "#888", whiteSpace: "nowrap" }}>Quota</span>
            <MultiSelectCombo
              items={quotas}
              selected={filters.quota_norm ?? []}
              onChange={v => setMultiFilter("quota_norm", v)}
              placeholder="All"
              unitLabel="quotas"
              width={100}
            />
          </div>

          {/* Category multi-select */}
          <div style={{ display: "flex", alignItems: "center", gap: 4, fontSize: 12 }}>
            <span style={{ color: "#888", whiteSpace: "nowrap" }}>Category</span>
            <MultiSelectCombo
              items={categories}
              selected={filters.allotted_category_norm ?? []}
              onChange={v => setMultiFilter("allotted_category_norm", v)}
              placeholder="All"
              unitLabel="categories"
              width={120}
            />
          </div>

          {/* State multi-select */}
          <div style={{ display: "flex", alignItems: "center", gap: 4, fontSize: 12 }}>
            <span style={{ color: "#888", whiteSpace: "nowrap" }}>State</span>
            <MultiSelectCombo
              items={states}
              selected={filters.state ?? []}
              onChange={v => setMultiFilter("state", v)}
              placeholder="All"
              unitLabel="states"
              width={130}
            />
          </div>

          {/* Course multi-select */}
          <div style={{ display: "flex", alignItems: "center", gap: 4, fontSize: 12 }}>
            <span style={{ color: "#888", whiteSpace: "nowrap" }}>Course</span>
            <MultiSelectCombo
              items={courses}
              selected={filters.course_norm ?? []}
              onChange={v => setMultiFilter("course_norm", v)}
              placeholder="e.g. MD General"
              unitLabel="courses"
              width={160}
            />
          </div>

          {/* Spacer */}
          <div style={{ flex: 1 }} />

          {/* Clear All button — only visible when any filter is active */}
          {hasActiveFilters && (
            <button
              onClick={handleClearAll}
              style={{
                padding: "4px 12px", fontSize: 12, border: "1px solid #e44",
                borderRadius: 4, cursor: "pointer", background: "#fff8f8",
                color: "#c33", fontWeight: 600, whiteSpace: "nowrap",
              }}
            >
              ✕ Clear All
            </button>
          )}

          {/* Favorites toggle button */}
          <button
            onClick={() => setShowFavoritesOnly(v => !v)}
            title={showFavoritesOnly ? "全件表示に戻す" : "お気に入りのみ表示"}
            style={{
              padding: "4px 12px", fontSize: 12,
              border: `1px solid ${showFavoritesOnly ? "#f5a623" : "#ddd"}`,
              borderRadius: 4, cursor: "pointer",
              background: showFavoritesOnly ? "#fff8ed" : "#fff",
              color: showFavoritesOnly ? "#c47d00" : "#888",
              fontWeight: showFavoritesOnly ? 700 : 400,
              whiteSpace: "nowrap",
              display: "flex", alignItems: "center", gap: 4,
            }}
          >
            {showFavoritesOnly ? "★" : "☆"}
            お気に入り
            {favorites.size > 0 && (
              <span style={{
                background: showFavoritesOnly ? "#f5a623" : "#ddd",
                color: showFavoritesOnly ? "#fff" : "#666",
                borderRadius: "999px", padding: "0 6px",
                fontSize: 11, fontWeight: 700, lineHeight: "18px",
              }}>
                {favorites.size}
              </span>
            )}
          </button>

          {/* Clear favorites — only when in favorites mode */}
          {showFavoritesOnly && favorites.size > 0 && (
            <button
              onClick={() => { clearFavorites(); }}
              title="全てのお気に入りを解除"
              style={{
                padding: "4px 12px", fontSize: 12, border: "1px solid #e44",
                borderRadius: 4, cursor: "pointer", background: "#fff8f8",
                color: "#c33", fontWeight: 600, whiteSpace: "nowrap",
              }}
            >
              ✕ クリア
            </button>
          )}

          {/* CSV download button */}
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

          {/* Advanced filter button */}
          <button
            className="btn-outline"
            onClick={() => setFilterModalOpen(true)}
            style={activeFilterCount > 0 ? { borderColor: "#2871b5", color: "#2871b5" } : {}}
          >
            ☰ Filters{activeFilterCount > 0 ? ` (${activeFilterCount})` : ""}
          </button>
        </div>

        {/* Active filter chips — shown for any selected values */}
        {(
          (filters.quota_norm ?? []).length >= 1 ||
          (filters.allotted_category_norm ?? []).length >= 1 ||
          (filters.state ?? []).length >= 1 ||
          (filters.course_norm ?? []).length >= 1 ||
          (filters.course_type ?? []).length >= 1 ||
          filters.rank_min || filters.rank_max
        ) && (
          <div style={{ display: "flex", flexWrap: "wrap", gap: 6, paddingBottom: 8 }}>
            {(filters.course_type ?? []).map(v => (
              <FilterChip key={`ct-${v}`} label={`Type: ${v}`} onRemove={() => { const next = (filters.course_type ?? []).filter(x => x !== v); setFilters(p => ({ ...p, course_type: next.length ? next : undefined })); setPage(1); }} />
            ))}
            {(filters.quota_norm ?? []).map(v => (
              <FilterChip key={`q-${v}`} label={`Quota: ${v}`} onRemove={() => { const next = (filters.quota_norm ?? []).filter(x => x !== v); setFilters(p => ({ ...p, quota_norm: next.length ? next : undefined })); setPage(1); }} />
            ))}
            {(filters.allotted_category_norm ?? []).map(v => (
              <FilterChip key={`c-${v}`} label={`Cat: ${v}`} onRemove={() => { const next = (filters.allotted_category_norm ?? []).filter(x => x !== v); setFilters(p => ({ ...p, allotted_category_norm: next.length ? next : undefined })); setPage(1); }} />
            ))}
            {(filters.state ?? []).map(v => (
              <FilterChip key={`s-${v}`} label={`State: ${v}`} onRemove={() => { const next = (filters.state ?? []).filter(x => x !== v); setFilters(p => ({ ...p, state: next.length ? next : undefined })); setPage(1); }} />
            ))}
            {(filters.course_norm ?? []).map(v => (
              <FilterChip key={`cr-${v}`} label={`Course: ${v.length > 22 ? v.slice(0, 22) + "…" : v}`} onRemove={() => { const next = (filters.course_norm ?? []).filter(x => x !== v); setFilters(p => ({ ...p, course_norm: next.length ? next : undefined })); setPage(1); }} />
            ))}
            {(filters.rank_min || filters.rank_max) && (
              <FilterChip label={`Rank: ${filters.rank_min ?? 0}–${filters.rank_max ?? "max"}`} onRemove={() => { setFilters(p => ({ ...p, rank_min: undefined, rank_max: undefined })); setPage(1); }} />
            )}
          </div>
        )}
      </div>

      {/* ── Main table area ── */}
      <div style={{ flex: 1, overflow: "hidden", display: "flex", flexDirection: "column" }}>
        <ClosingRankGrid
          data={gridData}
          loading={gridLoading}
          error={gridError}
          page={page}
          pageSize={PAGE_SIZE}
          sortBy={filters.sort_by}
          sortOrder={filters.sort_order}
          onPageChange={setPage}
          onGroupIdClick={handleGroupIdClick}
          onSort={handleSort}
          favorites={favorites}
          onToggleFavorite={toggleFavorite}
          showFavoritesOnly={showFavoritesOnly}
          favoriteRows={showFavoritesOnly ? Array.from(favorites.values()) : undefined}
        />
      </div>

      {/* Modals */}
      <FilterModal
        open={filterModalOpen}
        filters={filters}
        metadata={metadata}
        onApply={handleFilterApply}
        onClose={() => setFilterModalOpen(false)}
      />

      <DrillDownModal
        groupId={activeGroupId}
        data={modalData}
        loading={modalLoading}
        error={modalError}
        onClose={closeModal}
      />
    </div>
  );
}

// ---------------------------------------------------------------------------
// MultiSelectCombo — generic type-to-filter + checkbox multi-select
// ---------------------------------------------------------------------------
function MultiSelectCombo({
  items,
  selected,
  onChange,
  placeholder,
  unitLabel,
  width = 140,
}: {
  items: string[];
  selected: string[];
  onChange: (v: string[]) => void;
  placeholder: string;
  unitLabel: string;
  width?: number;
}) {
  const [query, setQuery] = useState("");
  const [open, setOpen] = useState(false);
  const containerRef = useRef<HTMLDivElement>(null);

  // Close dropdown on outside click
  useEffect(() => {
    function handler(e: MouseEvent) {
      if (containerRef.current && !containerRef.current.contains(e.target as Node)) {
        setOpen(false);
        setQuery("");
      }
    }
    document.addEventListener("mousedown", handler);
    return () => document.removeEventListener("mousedown", handler);
  }, []);

  const filtered = items.filter(item =>
    item !== "" && item.toLowerCase().includes(query.toLowerCase())
  );

  const toggle = (item: string) => {
    const next = selected.includes(item)
      ? selected.filter(x => x !== item)
      : [...selected, item];
    onChange(next);
  };

  // What shows in the input field
  const inputValue = open
    ? query
    : selected.length === 1
      ? (selected[0].length > Math.floor(width / 7) ? selected[0].slice(0, Math.floor(width / 7)) + "…" : selected[0])
      : "";

  const inputPlaceholder = selected.length > 1
    ? `${selected.length} ${unitLabel} selected`
    : selected.length === 1
      ? ""
      : placeholder;

  return (
    <div ref={containerRef} style={{ position: "relative" }}>
      {/* Input trigger */}
      <div style={{ position: "relative", display: "flex", alignItems: "center" }}>
        <input
          type="text"
          className="nv-input"
          style={{ width, fontSize: 12, paddingRight: selected.length > 0 ? 20 : undefined }}
          placeholder={inputPlaceholder}
          value={inputValue}
          onFocus={() => setOpen(true)}
          onChange={e => { setQuery(e.target.value); setOpen(true); }}
          onKeyDown={e => { if (e.key === "Escape") { setOpen(false); setQuery(""); } }}
        />
        {selected.length > 0 && (
          <button
            onMouseDown={e => { e.preventDefault(); onChange([]); setQuery(""); setOpen(false); }}
            style={{
              position: "absolute", right: 4, background: "none", border: "none",
              cursor: "pointer", color: "#bbb", fontSize: 15, padding: 0, lineHeight: 1,
            }}
            title={`Clear ${unitLabel}`}
          >×</button>
        )}
      </div>

      {/* Dropdown panel */}
      {open && (
        <div style={{
          position: "absolute", top: "calc(100% + 2px)", left: 0, zIndex: 2000,
          background: "#fff", border: "1px solid #ccc", borderRadius: 5,
          boxShadow: "0 6px 20px rgba(0,0,0,0.13)",
          maxHeight: 260, overflowY: "auto",
          minWidth: Math.max(width, 200),
        }}>
          {/* Header: count + Clear all */}
          <div style={{
            padding: "5px 10px", borderBottom: "1px solid #eee",
            fontSize: 11, color: "#999", display: "flex", justifyContent: "space-between", alignItems: "center",
          }}>
            <span>
              {filtered.length === items.length
                ? `${items.length} ${unitLabel}`
                : `${filtered.length} / ${items.length} ${unitLabel}`}
              {items.length > 10 && filtered.length === items.length && " — type to filter"}
            </span>
            {selected.length > 0 && (
              <button
                onMouseDown={e => { e.preventDefault(); onChange([]); setQuery(""); }}
                style={{ background: "none", border: "none", cursor: "pointer", color: "#e44", fontSize: 11, padding: 0 }}
              >Clear all</button>
            )}
          </div>

          {/* Options */}
          {filtered.length === 0 ? (
            <div style={{ padding: "10px 12px", fontSize: 12, color: "#888" }}>
              No {unitLabel} match &quot;{query}&quot;
            </div>
          ) : (
            filtered.map(item => {
              const checked = selected.includes(item);
              return (
                <label
                  key={item}
                  onMouseDown={e => { e.preventDefault(); toggle(item); }}
                  style={{
                    display: "flex", alignItems: "center", gap: 8,
                    padding: "6px 12px", cursor: "pointer", fontSize: 12,
                    background: checked ? "#e8f0fe" : "transparent",
                  }}
                >
                  <input
                    type="checkbox"
                    checked={checked}
                    readOnly
                    style={{ margin: 0, cursor: "pointer", accentColor: "#2871b5" }}
                  />
                  <span style={{ color: checked ? "#1a56a5" : "#333", fontWeight: checked ? 500 : 400 }}>
                    {item}
                  </span>
                </label>
              );
            })
          )}
        </div>
      )}
    </div>
  );
}

function FilterChip({ label, onRemove }: { label: string; onRemove: () => void }) {
  return (
    <span style={{
      display: "inline-flex", alignItems: "center", gap: 4,
      background: "#e8f0fe", color: "#2871b5", borderRadius: 3,
      padding: "2px 8px", fontSize: 11, fontWeight: 500,
    }}>
      {label}
      <button onClick={onRemove} style={{ background: "none", border: "none", cursor: "pointer", color: "#2871b5", padding: 0, fontSize: 13, lineHeight: 1 }}>×</button>
    </span>
  );
}
