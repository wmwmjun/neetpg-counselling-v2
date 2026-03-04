"use client";
import React, { useState, useEffect, useCallback, useRef } from "react";
import ClosingRankGrid from "@/components/ClosingRankGrid";
import DrillDownModal from "@/components/DrillDownModal";
import FilterModal, { type DisplayedFields } from "@/components/FilterModal";
import {
  fetchMetadata, fetchClosingRanks, fetchDrillDown,
  type MetadataResponse, type ClosingRankFilters,
  type ClosingRankRow, type PaginatedResponse, type DrillDownResponse,
} from "@/lib/api";

const DEFAULT_FILTERS: ClosingRankFilters = {
  year: 2025, counselling_type: "AIQ", round: 1, quota_norm: "AI",
  sort_by: "institute_name", sort_order: "asc",
};
const DEFAULT_DF: DisplayedFields = { fee: true, stipend: true, bondYears: true, bondPenalty: true, beds: true };
const PAGE_SIZE = 50;
const DEBOUNCE = 300;

export default function HomePage() {
  const [filters, setFilters] = useState<ClosingRankFilters>(DEFAULT_FILTERS);
  const [displayedFields, setDisplayedFields] = useState<DisplayedFields>(DEFAULT_DF);
  const [page, setPage] = useState(1);

  const [metadata, setMetadata] = useState<MetadataResponse | null>(null);
  const [gridData, setGridData] = useState<PaginatedResponse<ClosingRankRow> | null>(null);
  const [gridLoading, setGridLoading] = useState(false);
  const [gridError, setGridError] = useState<string | null>(null);

  const [filterModalOpen, setFilterModalOpen] = useState(false);
  const [searchText, setSearchText] = useState("");

  const [activeGroupId, setActiveGroupId] = useState<string | null>(null);
  const [modalData, setModalData] = useState<DrillDownResponse | null>(null);
  const [modalLoading, setModalLoading] = useState(false);
  const [modalError, setModalError] = useState<string | null>(null);

  // Sort panel
  const [sortOpen, setSortOpen] = useState(false);

  // Load metadata
  useEffect(() => {
    fetchMetadata({ year: 2025, counselling_type: "AIQ", round: 1 })
      .then(setMetadata)
      .catch(console.error);
  }, []);

  // Debounced grid fetch
  const timer = useRef<ReturnType<typeof setTimeout> | null>(null);
  useEffect(() => {
    if (timer.current) clearTimeout(timer.current);
    timer.current = setTimeout(async () => {
      setGridLoading(true);
      setGridError(null);
      try {
        const res = await fetchClosingRanks({ ...filters, search: searchText || undefined, page, page_size: PAGE_SIZE });
        setGridData(res);
      } catch (e) {
        setGridError(e instanceof Error ? e.message : "Failed to load");
      } finally {
        setGridLoading(false);
      }
    }, DEBOUNCE);
    return () => { if (timer.current) clearTimeout(timer.current); };
  }, [filters, searchText, page]);

  const handleFilterApply = useCallback((f: ClosingRankFilters, df: DisplayedFields) => {
    setFilters(f); setDisplayedFields(df); setPage(1);
  }, []);

  const handleRowClick = useCallback(async (row: ClosingRankRow) => {
    setActiveGroupId(row.group_id);
    setModalData(null); setModalLoading(true); setModalError(null);
    try {
      setModalData(await fetchDrillDown(row.group_id));
    } catch (e) {
      setModalError(e instanceof Error ? e.message : "Failed to load");
    } finally {
      setModalLoading(false);
    }
  }, []);

  const closeModal = useCallback(() => {
    setActiveGroupId(null); setModalData(null); setModalError(null);
  }, []);

  // Count active filters (excluding defaults)
  const activeFilterCount = [
    filters.allotted_category_norm, filters.state, filters.course_norm,
    filters.rank_min, filters.rank_max,
  ].filter(Boolean).length;

  return (
    <div style={{ display: "flex", flexDirection: "column", height: "100vh", background: "#f0f0f0" }}>

      {/* ── Top header ── */}
      <div style={{ background: "#fff", borderBottom: "1px solid #ddd", padding: "10px 20px" }}>
        {/* Title row */}
        <div style={{ display: "flex", alignItems: "center", gap: 16, marginBottom: 6 }}>
          <div style={{ display: "flex", alignItems: "baseline", gap: 8 }}>
            <span style={{ fontSize: 20, fontWeight: 700, color: "#222" }}>Closing Ranks</span>
            <span style={{ fontSize: 12, color: "#2871b5", cursor: "pointer" }}>What's this?</span>
          </div>
          <div style={{ display: "flex", alignItems: "center", gap: 8, marginLeft: "auto" }}>
            <span style={{ fontSize: 12, color: "#888" }}>Spotted an error?</span>
          </div>
        </div>

        {/* Counselling type + session selector */}
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

        {/* Controls row */}
        <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
          {/* Search */}
          <input
            type="text"
            className="nv-input"
            placeholder="Search institute or course..."
            style={{ width: 240 }}
            value={searchText}
            onChange={e => { setSearchText(e.target.value); setPage(1); }}
          />

          {/* Active filter chips */}
          {filters.quota_norm && filters.quota_norm !== "AI" && (
            <FilterChip label={`Quota: ${filters.quota_norm}`} onRemove={() => { setFilters(p => ({ ...p, quota_norm: "AI" })); setPage(1); }} />
          )}
          {filters.allotted_category_norm && (
            <FilterChip label={`Cat: ${filters.allotted_category_norm}`} onRemove={() => { setFilters(p => ({ ...p, allotted_category_norm: undefined })); setPage(1); }} />
          )}
          {filters.state && (
            <FilterChip label={`State: ${filters.state}`} onRemove={() => { setFilters(p => ({ ...p, state: undefined })); setPage(1); }} />
          )}
          {filters.course_norm && (
            <FilterChip label={filters.course_norm.length > 20 ? filters.course_norm.slice(0, 20) + "…" : filters.course_norm} onRemove={() => { setFilters(p => ({ ...p, course_norm: undefined })); setPage(1); }} />
          )}
          {(filters.rank_min || filters.rank_max) && (
            <FilterChip label={`Rank: ${filters.rank_min ?? 0}–${filters.rank_max ?? "max"}`} onRemove={() => { setFilters(p => ({ ...p, rank_min: undefined, rank_max: undefined })); setPage(1); }} />
          )}

          <div style={{ marginLeft: "auto", display: "flex", alignItems: "center", gap: 8 }}>
            {/* Record count */}
            {gridData && (
              <span style={{ fontSize: 12, color: "#555", whiteSpace: "nowrap" }}>
                {((page - 1) * PAGE_SIZE + 1).toLocaleString()}–{Math.min(page * PAGE_SIZE, gridData.total).toLocaleString()} of{" "}
                <strong>{gridData.total.toLocaleString()}</strong> Records
              </span>
            )}

            {/* Sort button */}
            <div style={{ position: "relative" }}>
              <button className="btn-outline" onClick={() => setSortOpen(p => !p)}>
                ↕ Sort
              </button>
              {sortOpen && (
                <div style={{
                  position: "absolute", top: 32, right: 0, zIndex: 50,
                  background: "#fff", border: "1px solid #ddd", borderRadius: 4,
                  boxShadow: "0 4px 12px rgba(0,0,0,0.12)", width: 200, padding: "4px 0"
                }}>
                  {[
                    { label: "Institute (A→Z)", by: "institute_name", order: "asc" },
                    { label: "Institute (Z→A)", by: "institute_name", order: "desc" },
                    { label: "Course (A→Z)", by: "course_norm", order: "asc" },
                    { label: "Closing Rank ↑", by: "closing_rank", order: "asc" },
                    { label: "Closing Rank ↓", by: "closing_rank", order: "desc" },
                  ].map(opt => (
                    <button key={opt.label}
                      onClick={() => {
                        setFilters(p => ({ ...p, sort_by: opt.by as ClosingRankFilters["sort_by"], sort_order: opt.order as "asc" | "desc" }));
                        setPage(1); setSortOpen(false);
                      }}
                      style={{
                        display: "block", width: "100%", textAlign: "left",
                        padding: "7px 14px", fontSize: 12, background: "none", border: "none",
                        cursor: "pointer", color: "#333",
                        fontWeight: filters.sort_by === opt.by && filters.sort_order === opt.order ? 700 : 400,
                      }}
                    >
                      {opt.label}
                    </button>
                  ))}
                </div>
              )}
            </div>

            {/* Filter button */}
            <button
              className="btn-outline"
              onClick={() => setFilterModalOpen(true)}
              style={activeFilterCount > 0 ? { borderColor: "#2871b5", color: "#2871b5" } : {}}
            >
              ☰ Filter{activeFilterCount > 0 ? ` (${activeFilterCount})` : ""}
            </button>
          </div>
        </div>
      </div>

      {/* ── Main table area ── */}
      <div style={{ flex: 1, overflow: "hidden", display: "flex", flexDirection: "column" }}>
        <ClosingRankGrid
          data={gridData}
          loading={gridLoading}
          error={gridError}
          page={page}
          pageSize={PAGE_SIZE}
          displayedFields={displayedFields}
          onPageChange={setPage}
          onRowClick={handleRowClick}
        />
      </div>

      {/* Modals */}
      <FilterModal
        open={filterModalOpen}
        filters={filters}
        displayedFields={displayedFields}
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

      {/* Close sort dropdown on outside click */}
      {sortOpen && (
        <div style={{ position: "fixed", inset: 0, zIndex: 49 }} onClick={() => setSortOpen(false)} />
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
