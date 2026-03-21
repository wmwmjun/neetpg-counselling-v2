"use client";
import React, { useState, useCallback, useRef, useEffect } from "react";
import type { MetadataResponse, ClosingRankFilters } from "@/lib/api";

interface Props {
  open: boolean;
  filters: ClosingRankFilters;
  metadata: MetadataResponse | null;
  onApply: (f: ClosingRankFilters) => void;
  onClose: () => void;
}

// ---------------------------------------------------------------------------
// Searchable Multi-Select component
// ---------------------------------------------------------------------------
interface MultiSelectProps {
  options: string[];
  selected: string[];
  onChange: (vals: string[]) => void;
  placeholder?: string;
}

function SearchableMultiSelect({ options, selected, onChange, placeholder = "All" }: MultiSelectProps) {
  const [open, setOpen] = useState(false);
  const [query, setQuery] = useState("");
  const ref = useRef<HTMLDivElement>(null);

  // Close on outside click
  useEffect(() => {
    if (!open) return;
    const handler = (e: MouseEvent) => {
      if (ref.current && !ref.current.contains(e.target as Node)) setOpen(false);
    };
    document.addEventListener("mousedown", handler);
    return () => document.removeEventListener("mousedown", handler);
  }, [open]);

  const filtered = options.filter(o => o.toLowerCase().includes(query.toLowerCase()));

  const toggle = (val: string) => {
    if (selected.includes(val)) onChange(selected.filter(v => v !== val));
    else onChange([...selected, val]);
  };

  const label = selected.length === 0
    ? placeholder
    : selected.length === 1
      ? selected[0]
      : `${selected.length} selected`;

  const hasValue = selected.length > 0;

  return (
    <div ref={ref} style={{ position: "relative" }}>
      {/* Trigger */}
      <button
        type="button"
        onClick={() => setOpen(o => !o)}
        style={{
          width: "100%", display: "flex", alignItems: "center", justifyContent: "space-between",
          padding: "5px 8px", borderRadius: 4, border: `1px solid ${hasValue ? "#2871b5" : "#ccc"}`,
          background: hasValue ? "#f0f6ff" : "#fff", cursor: "pointer",
          fontSize: 12, color: hasValue ? "#2871b5" : "#555", textAlign: "left",
          gap: 4,
        }}
      >
        <span style={{ flex: 1, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>
          {label}
        </span>
        {hasValue && (
          <span
            onClick={(e) => { e.stopPropagation(); onChange([]); }}
            style={{ color: "#999", fontSize: 14, lineHeight: 1, padding: "0 2px", cursor: "pointer" }}
            title="Clear"
          >×</span>
        )}
        <span style={{ color: "#999", fontSize: 10 }}>{open ? "▲" : "▼"}</span>
      </button>

      {/* Dropdown */}
      {open && (
        <div style={{
          position: "absolute", zIndex: 9999, top: "100%", left: 0, right: 0, marginTop: 2,
          background: "#fff", border: "1px solid #ddd", borderRadius: 4,
          boxShadow: "0 4px 12px rgba(0,0,0,0.12)", minWidth: 200,
        }}>
          {/* Search */}
          <div style={{ padding: "6px 8px", borderBottom: "1px solid #eee" }}>
            <input
              autoFocus
              type="text"
              value={query}
              onChange={e => setQuery(e.target.value)}
              placeholder="Search..."
              style={{
                width: "100%", padding: "4px 8px", border: "1px solid #ddd",
                borderRadius: 3, fontSize: 12, outline: "none", boxSizing: "border-box",
              }}
            />
          </div>

          {/* Options list */}
          <div style={{ maxHeight: 200, overflowY: "auto" }}>
            {filtered.length === 0 ? (
              <div style={{ padding: "8px 10px", fontSize: 12, color: "#999" }}>No results</div>
            ) : (
              filtered.map(opt => (
                <label
                  key={opt}
                  style={{
                    display: "flex", alignItems: "center", gap: 7,
                    padding: "5px 10px", cursor: "pointer", fontSize: 12,
                    background: selected.includes(opt) ? "#f0f6ff" : "transparent",
                  }}
                  onMouseEnter={e => (e.currentTarget.style.background = selected.includes(opt) ? "#e0ecff" : "#f5f5f5")}
                  onMouseLeave={e => (e.currentTarget.style.background = selected.includes(opt) ? "#f0f6ff" : "transparent")}
                >
                  <input
                    type="checkbox"
                    checked={selected.includes(opt)}
                    onChange={() => toggle(opt)}
                    style={{ cursor: "pointer", accentColor: "#2871b5" }}
                  />
                  <span style={{ flex: 1 }}>{opt}</span>
                </label>
              ))
            )}
          </div>

          {/* Footer */}
          {selected.length > 0 && (
            <div style={{
              padding: "5px 10px", borderTop: "1px solid #eee",
              display: "flex", justifyContent: "space-between", alignItems: "center",
            }}>
              <span style={{ fontSize: 11, color: "#888" }}>{selected.length} selected</span>
              <button
                onClick={() => { onChange([]); setQuery(""); }}
                style={{ fontSize: 11, color: "#e05c00", background: "none", border: "none", cursor: "pointer" }}
              >Clear all</button>
            </div>
          )}
        </div>
      )}
    </div>
  );
}

// ---------------------------------------------------------------------------
// Main FilterModal
// ---------------------------------------------------------------------------
const DEGREES = ["MD", "MS", "DNB", "DM", "MCh", "Diploma"];

export default function FilterModal({ open, filters, metadata, onApply, onClose }: Props) {
  const [local, setLocal] = useState<ClosingRankFilters>(filters);

  React.useEffect(() => {
    if (open) { setLocal(filters); }
  }, [open, filters]);

  const set = useCallback((key: keyof ClosingRankFilters, val: unknown) =>
    setLocal(p => ({ ...p, [key]: val })), []);

  const handleApply = () => {
    onApply(local);
    onClose();
  };

  const handleClear = () => {
    setLocal({ year: local.year, counselling_type: "AIQ", fee_min: undefined, fee_max: undefined, bond_min: undefined, bond_max: undefined, course_type: undefined });
  };

  if (!open) return null;

  const courses = metadata?.courses ?? [];
  const states = metadata?.states ?? [];
  const quotas = metadata?.quotas ?? [];
  const categories = metadata?.categories ?? [];

  return (
    <>
      {/* Backdrop */}
      <div className="fixed inset-0 z-[199] bg-black/40" onClick={onClose} />

      {/* Side sheet */}
      <div className="filter-sheet">
        {/* Header */}
        <div style={{ padding: "14px 20px", borderBottom: "1px solid #e0e0e0", display: "flex", alignItems: "center", justifyContent: "space-between" }}>
          <span style={{ fontWeight: 700, fontSize: 15 }}>Filters</span>
          <button onClick={onClose} style={{ background: "none", border: "none", fontSize: 20, cursor: "pointer", color: "#666", lineHeight: 1 }}>×</button>
        </div>

        {/* Body */}
        <div style={{ flex: 1, overflowY: "auto", padding: "16px 20px" }}>
          <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr 1fr", gap: 24 }}>

            {/* ── Left column ── */}
            <div style={{ display: "flex", flexDirection: "column", gap: 16 }}>
              {/* AI Rank */}
              <FilterSection title="AI Rank">
                <div style={{ display: "flex", gap: 6, alignItems: "center" }}>
                  <input type="number" className="nv-input" style={{ width: 80 }} placeholder="Min"
                    value={local.rank_min ?? ""} onChange={e => set("rank_min", e.target.value === "" ? undefined : Number(e.target.value))} />
                  <span style={{ color: "#999" }}>–</span>
                  <input type="number" className="nv-input" style={{ width: 80 }} placeholder="Max"
                    value={local.rank_max ?? ""} onChange={e => set("rank_max", e.target.value === "" ? undefined : Number(e.target.value))} />
                </div>
              </FilterSection>

              {/* Quota */}
              <FilterSection title="Quota">
                <SearchableMultiSelect
                  options={quotas}
                  selected={local.quota_norm ?? []}
                  onChange={v => set("quota_norm", v.length ? v : undefined)}
                  placeholder="All Quotas"
                />
              </FilterSection>

              {/* Category */}
              <FilterSection title="Category">
                <SearchableMultiSelect
                  options={categories}
                  selected={local.allotted_category_norm ?? []}
                  onChange={v => set("allotted_category_norm", v.length ? v : undefined)}
                  placeholder="All Categories"
                />
              </FilterSection>
            </div>

            {/* ── Middle column ── */}
            <div style={{ display: "flex", flexDirection: "column", gap: 16 }}>
              {/* State */}
              <FilterSection title="State">
                <SearchableMultiSelect
                  options={states}
                  selected={local.state ?? []}
                  onChange={v => set("state", v.length ? v : undefined)}
                  placeholder="All States"
                />
              </FilterSection>

              {/* Institute Type */}
              <FilterSection title="Institute Type">
                <select className="nv-select" style={{ width: "100%" }} disabled>
                  <option>All Types</option>
                  <option>Government</option>
                  <option>Private</option>
                  <option>Deemed</option>
                </select>
                <div style={{ fontSize: 11, color: "#aaa", marginTop: 3 }}>Coming soon</div>
              </FilterSection>

              {/* Beds */}
              <FilterSection title="Beds">
                <div style={{ display: "flex", gap: 6, alignItems: "center" }}>
                  <input type="number" className="nv-input" style={{ width: 80 }} placeholder="Min" disabled />
                  <span style={{ color: "#999" }}>–</span>
                  <input type="number" className="nv-input" style={{ width: 80 }} placeholder="Max" disabled />
                </div>
                <div style={{ fontSize: 11, color: "#aaa", marginTop: 3 }}>Coming soon</div>
              </FilterSection>

              {/* Fee */}
              <FilterSection title="Fee (₹)">
                <div style={{ display: "flex", gap: 6, alignItems: "center" }}>
                  <input
                    type="number" className="nv-input" style={{ width: 80 }} placeholder="Min"
                    value={local.fee_min ?? ""}
                    onChange={e => set("fee_min", e.target.value === "" ? undefined : Number(e.target.value))}
                  />
                  <span style={{ color: "#999" }}>–</span>
                  <input
                    type="number" className="nv-input" style={{ width: 80 }} placeholder="Max"
                    value={local.fee_max ?? ""}
                    onChange={e => set("fee_max", e.target.value === "" ? undefined : Number(e.target.value))}
                  />
                </div>
                {(local.fee_min || local.fee_max) && (
                  <div style={{ fontSize: 11, color: "#2871b5", marginTop: 3 }}>
                    {local.fee_min ? `₹${(local.fee_min/100000).toFixed(1)}L` : "—"} 〜 {local.fee_max ? `₹${(local.fee_max/100000).toFixed(1)}L` : "—"}
                  </div>
                )}
              </FilterSection>

              {/* Bond Years */}
              <FilterSection title="Bond Years">
                <div style={{ display: "flex", gap: 6, alignItems: "center" }}>
                  <input type="number" className="nv-input" style={{ width: 80 }} placeholder="Min" disabled />
                  <span style={{ color: "#999" }}>–</span>
                  <input type="number" className="nv-input" style={{ width: 80 }} placeholder="Max" disabled />
                </div>
                <div style={{ fontSize: 11, color: "#aaa", marginTop: 3 }}>Coming soon</div>
              </FilterSection>

              {/* Bond Penalty */}
              <FilterSection title="Bond Penalty (₹)">
                <div style={{ display: "flex", gap: 6, alignItems: "center" }}>
                  <input
                    type="number" className="nv-input" style={{ width: 80 }} placeholder="Min"
                    value={local.bond_min ?? ""}
                    onChange={e => set("bond_min", e.target.value === "" ? undefined : Number(e.target.value))}
                  />
                  <span style={{ color: "#999" }}>–</span>
                  <input
                    type="number" className="nv-input" style={{ width: 80 }} placeholder="Max"
                    value={local.bond_max ?? ""}
                    onChange={e => set("bond_max", e.target.value === "" ? undefined : Number(e.target.value))}
                  />
                </div>
                {(local.bond_min || local.bond_max) && (
                  <div style={{ fontSize: 11, color: "#2871b5", marginTop: 3 }}>
                    {local.bond_min ? `₹${(local.bond_min/100000).toFixed(1)}L` : "—"} 〜 {local.bond_max ? `₹${(local.bond_max/100000).toFixed(1)}L` : "—"}
                  </div>
                )}
              </FilterSection>
            </div>

            {/* ── Right column ── */}
            <div style={{ display: "flex", flexDirection: "column", gap: 16 }}>
              {/* Course */}
              <FilterSection title="Course">
                <SearchableMultiSelect
                  options={courses}
                  selected={local.course_norm ?? []}
                  onChange={v => set("course_norm", v.length ? v : undefined)}
                  placeholder="All Courses"
                />
              </FilterSection>

              {/* Course Type */}
              <FilterSection title="Course Type">
                {["Clinical", "Non-Clinical", "Para-Clinical", "Pre-Clinical"].map(t => {
                  const isSelected = (local.course_type ?? []).includes(t);
                  return (
                    <label key={t} style={{ display: "flex", alignItems: "center", gap: 6, fontSize: 12, marginBottom: 4, cursor: "pointer" }}>
                      <input
                        type="checkbox"
                        checked={isSelected}
                        onChange={() => {
                          const current = local.course_type ?? [];
                          const next = isSelected
                            ? current.filter(v => v !== t)
                            : [...current, t];
                          set("course_type", next.length ? next : undefined);
                        }}
                        style={{ cursor: "pointer", accentColor: "#e05c00" }}
                      /> {t}
                    </label>
                  );
                })}
              </FilterSection>

              {/* Degree */}
              <FilterSection title="Degree">
                <div style={{ display: "flex", flexDirection: "column", gap: 4 }}>
                  {DEGREES.map(d => {
                    const isSelected = (local.course_norm ?? []).some(c => c.startsWith(d + " ") || c === d);
                    return (
                      <label key={d} style={{ display: "flex", alignItems: "center", gap: 6, fontSize: 12, cursor: "pointer" }}>
                        <input
                          type="checkbox"
                          checked={isSelected}
                          onChange={() => {
                            const prefix = d + " ";
                            const current = local.course_norm ?? [];
                            if (isSelected) {
                              set("course_norm", current.filter(c => !c.startsWith(prefix) && c !== d) || undefined);
                            } else {
                              set("course_norm", [...current, prefix]);
                            }
                          }}
                          style={{ cursor: "pointer" }} />
                        {d}
                      </label>
                    );
                  })}
                </div>
              </FilterSection>
            </div>
          </div>
        </div>

        {/* Footer */}
        <div style={{
          padding: "12px 20px", borderTop: "1px solid #e0e0e0",
          display: "flex", alignItems: "center", justifyContent: "space-between", gap: 10
        }}>
          <div style={{ display: "flex", gap: 8 }}>
            <button className="btn-ghost" onClick={handleClear}>Clear</button>
          </div>
          <div style={{ display: "flex", gap: 8, alignItems: "center" }}>
            <button className="btn-ghost" onClick={onClose}>Cancel</button>
            <button className="btn-orange" onClick={handleApply}>View Results</button>
          </div>
        </div>
      </div>
    </>
  );
}

function FilterSection({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <div>
      <div style={{ fontWeight: 600, fontSize: 11, color: "#555", textTransform: "uppercase", letterSpacing: "0.05em", marginBottom: 6 }}>
        {title}
      </div>
      {children}
    </div>
  );
}
