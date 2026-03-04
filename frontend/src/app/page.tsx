"use client";

import React, { useState, useEffect, useCallback, useRef } from "react";
import FilterBar, { DEFAULT_FILTERS } from "@/components/FilterBar";
import ClosingRankGrid from "@/components/ClosingRankGrid";
import DrillDownModal from "@/components/DrillDownModal";
import {
  fetchMetadata,
  fetchClosingRanks,
  fetchDrillDown,
  type MetadataResponse,
  type ClosingRankFilters,
  type ClosingRankRow,
  type PaginatedResponse,
  type DrillDownResponse,
} from "@/lib/api";

const DEBOUNCE_MS = 350;

export default function HomePage() {
  // ------------------------------------------------------------------
  // State: filters & pagination
  // ------------------------------------------------------------------
  const [filters, setFilters] = useState<ClosingRankFilters>({
    ...DEFAULT_FILTERS,
  });
  const [page, setPage] = useState(1);

  // ------------------------------------------------------------------
  // State: metadata
  // ------------------------------------------------------------------
  const [metadata, setMetadata] = useState<MetadataResponse | null>(null);

  // ------------------------------------------------------------------
  // State: closing ranks table
  // ------------------------------------------------------------------
  const [gridData, setGridData] = useState<PaginatedResponse<ClosingRankRow> | null>(null);
  const [gridLoading, setGridLoading] = useState(false);
  const [gridError, setGridError] = useState<string | null>(null);

  // ------------------------------------------------------------------
  // State: drill-down modal
  // ------------------------------------------------------------------
  const [activeGroupId, setActiveGroupId] = useState<string | null>(null);
  const [modalData, setModalData] = useState<DrillDownResponse | null>(null);
  const [modalLoading, setModalLoading] = useState(false);
  const [modalError, setModalError] = useState<string | null>(null);

  // ------------------------------------------------------------------
  // Load metadata on mount
  // ------------------------------------------------------------------
  useEffect(() => {
    fetchMetadata({ year: 2025, counselling_type: "AIQ", round: 1 })
      .then(setMetadata)
      .catch((err) => console.error("Metadata fetch error:", err));
  }, []);

  // ------------------------------------------------------------------
  // Debounced grid fetch
  // ------------------------------------------------------------------
  const debounceTimer = useRef<ReturnType<typeof setTimeout> | null>(null);

  const loadGrid = useCallback(
    (currentFilters: ClosingRankFilters, currentPage: number) => {
      if (debounceTimer.current) clearTimeout(debounceTimer.current);
      debounceTimer.current = setTimeout(async () => {
        setGridLoading(true);
        setGridError(null);
        try {
          const result = await fetchClosingRanks({
            ...currentFilters,
            page: currentPage,
            page_size: 50,
          });
          setGridData(result);
        } catch (err) {
          setGridError(err instanceof Error ? err.message : "Failed to load data");
        } finally {
          setGridLoading(false);
        }
      }, DEBOUNCE_MS);
    },
    []
  );

  // Re-fetch whenever filters or page change
  useEffect(() => {
    loadGrid(filters, page);
  }, [filters, page, loadGrid]);

  // ------------------------------------------------------------------
  // Handlers
  // ------------------------------------------------------------------
  const handleFilterChange = useCallback((updates: Partial<ClosingRankFilters>) => {
    setFilters((prev) => ({ ...prev, ...updates }));
    setPage(1);
  }, []);

  const handleClearFilters = useCallback(() => {
    setFilters({ ...DEFAULT_FILTERS });
    setPage(1);
  }, []);

  const handleRowClick = useCallback(async (row: ClosingRankRow) => {
    setActiveGroupId(row.group_id);
    setModalData(null);
    setModalLoading(true);
    setModalError(null);
    try {
      const result = await fetchDrillDown(row.group_id);
      setModalData(result);
    } catch (err) {
      setModalError(err instanceof Error ? err.message : "Failed to load allotments");
    } finally {
      setModalLoading(false);
    }
  }, []);

  const handleModalClose = useCallback(() => {
    setActiveGroupId(null);
    setModalData(null);
    setModalError(null);
  }, []);

  // ------------------------------------------------------------------
  // Render
  // ------------------------------------------------------------------
  return (
    <div className="flex flex-col h-screen overflow-hidden">
      <FilterBar
        filters={filters}
        metadata={metadata}
        loading={gridLoading}
        onFilterChange={handleFilterChange}
        onClear={handleClearFilters}
      />

      <main className="flex-1 overflow-hidden flex flex-col">
        <ClosingRankGrid
          data={gridData}
          loading={gridLoading}
          error={gridError}
          page={page}
          onPageChange={setPage}
          onRowClick={handleRowClick}
        />
      </main>

      <DrillDownModal
        groupId={activeGroupId}
        data={modalData}
        loading={modalLoading}
        error={modalError}
        onClose={handleModalClose}
      />
    </div>
  );
}
