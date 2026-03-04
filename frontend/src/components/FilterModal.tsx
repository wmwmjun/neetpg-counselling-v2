"use client";
import React, { useState, useCallback } from "react";
import type { MetadataResponse, ClosingRankFilters } from "@/lib/api";

export interface DisplayedFields {
  fee: boolean; stipend: boolean; bondYears: boolean; bondPenalty: boolean; beds: boolean;
}

interface Props {
  open: boolean;
  filters: ClosingRankFilters;
  displayedFields: DisplayedFields;
  metadata: MetadataResponse | null;
  onApply: (f: ClosingRankFilters, df: DisplayedFields) => void;
  onClose: () => void;
}

const DEGREES = ["MD", "MS", "DNB", "DM", "MCh", "Diploma"];

export default function FilterModal({ open, filters, displayedFields, metadata, onApply, onClose }: Props) {
  const [local, setLocal] = useState<ClosingRankFilters>(filters);
  const [localDF, setLocalDF] = useState<DisplayedFields>(displayedFields);
  const [selectedDegrees, setSelectedDegrees] = useState<Set<string>>(new Set());

  React.useEffect(() => {
    if (open) { setLocal(filters); setLocalDF(displayedFields); }
  }, [open, filters, displayedFields]);

  const set = useCallback((key: keyof ClosingRankFilters, val: unknown) =>
    setLocal(p => ({ ...p, [key]: val === "" ? undefined : val })), []);

  const toggleDegree = (d: string) => {
    setSelectedDegrees(prev => {
      const next = new Set(prev);
      next.has(d) ? next.delete(d) : next.add(d);
      return next;
    });
  };

  const handleApply = () => {
    // Build course_norm filter from degree selection
    let f = { ...local };
    if (selectedDegrees.size === 1) {
      const [deg] = selectedDegrees;
      f = { ...f, course_norm: deg + " " };
    }
    onApply(f, localDF);
    onClose();
  };

  const handleClear = () => {
    setLocal({ year: 2025, counselling_type: "AIQ", round: 1, quota_norm: "AI" });
    setLocalDF({ fee: true, stipend: true, bondYears: true, bondPenalty: true, beds: true });
    setSelectedDegrees(new Set());
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

              {/* Session Rounds */}
              <FilterSection title="Session Rounds">
                <div style={{ fontSize: 12, color: "#555", marginBottom: 6, fontWeight: 600 }}>2025</div>
                <div style={{ display: "flex", gap: 6, flexWrap: "wrap" }}>
                  {[1, 2, 3, 4].map(r => (
                    <button key={r}
                      onClick={() => set("round", local.round === r ? undefined : r)}
                      style={{
                        padding: "3px 10px", borderRadius: 3, fontSize: 12, cursor: "pointer", border: "1px solid",
                        background: local.round === r ? "#2871b5" : "#fff",
                        color: local.round === r ? "#fff" : "#555",
                        borderColor: local.round === r ? "#2871b5" : "#ccc",
                        opacity: r > 1 ? 0.45 : 1,
                      }}
                      disabled={r > 1}
                    >R{r}</button>
                  ))}
                </div>
                <div style={{ fontSize: 11, color: "#aaa", marginTop: 4 }}>R2–R4 coming soon</div>
              </FilterSection>

              {/* Quota */}
              <FilterSection title="Quota">
                <select className="nv-select" style={{ width: "100%" }}
                  value={local.quota_norm ?? ""}
                  onChange={e => set("quota_norm", e.target.value)}>
                  <option value="">All Quotas</option>
                  {quotas.map(q => <option key={q} value={q}>{q}</option>)}
                </select>
              </FilterSection>

              {/* Category */}
              <FilterSection title="Category">
                <select className="nv-select" style={{ width: "100%" }}
                  value={local.allotted_category_norm ?? ""}
                  onChange={e => set("allotted_category_norm", e.target.value)}>
                  <option value="">All Categories</option>
                  {categories.map(c => <option key={c} value={c}>{c}</option>)}
                </select>
              </FilterSection>
            </div>

            {/* ── Middle column ── */}
            <div style={{ display: "flex", flexDirection: "column", gap: 16 }}>
              {/* State */}
              <FilterSection title="State">
                <select className="nv-select" style={{ width: "100%" }}
                  value={local.state ?? ""}
                  onChange={e => set("state", e.target.value)}>
                  <option value="">All States</option>
                  {states.map(s => <option key={s} value={s}>{s}</option>)}
                </select>
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
                  <input type="number" className="nv-input" style={{ width: 80 }} placeholder="Min" disabled />
                  <span style={{ color: "#999" }}>–</span>
                  <input type="number" className="nv-input" style={{ width: 80 }} placeholder="Max" disabled />
                </div>
                <div style={{ fontSize: 11, color: "#aaa", marginTop: 3 }}>Coming soon</div>
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
                  <input type="number" className="nv-input" style={{ width: 80 }} placeholder="Min" disabled />
                  <span style={{ color: "#999" }}>–</span>
                  <input type="number" className="nv-input" style={{ width: 80 }} placeholder="Max" disabled />
                </div>
                <div style={{ fontSize: 11, color: "#aaa", marginTop: 3 }}>Coming soon</div>
              </FilterSection>
            </div>

            {/* ── Right column ── */}
            <div style={{ display: "flex", flexDirection: "column", gap: 16 }}>
              {/* Course */}
              <FilterSection title="Course">
                <select className="nv-select" style={{ width: "100%" }}
                  value={local.course_norm ?? ""}
                  onChange={e => set("course_norm", e.target.value)}>
                  <option value="">All Courses</option>
                  {courses.map(c => <option key={c} value={c}>{c}</option>)}
                </select>
              </FilterSection>

              {/* Course Type */}
              <FilterSection title="Course Type">
                {["Clinical", "Non-Clinical", "Para-Clinical", "Pre-Clinical"].map(t => (
                  <label key={t} style={{ display: "flex", alignItems: "center", gap: 6, fontSize: 12, marginBottom: 4, cursor: "not-allowed", color: "#aaa" }}>
                    <input type="checkbox" disabled /> {t}
                  </label>
                ))}
                <div style={{ fontSize: 11, color: "#aaa" }}>Coming soon</div>
              </FilterSection>

              {/* Degree */}
              <FilterSection title="Degree">
                <div style={{ display: "flex", flexDirection: "column", gap: 4 }}>
                  {DEGREES.map(d => (
                    <label key={d} style={{ display: "flex", alignItems: "center", gap: 6, fontSize: 12, cursor: "pointer" }}>
                      <input type="checkbox"
                        checked={selectedDegrees.has(d)}
                        onChange={() => toggleDegree(d)}
                        style={{ cursor: "pointer" }} />
                      {d}
                    </label>
                  ))}
                </div>
              </FilterSection>
            </div>
          </div>

          {/* ── Displayed Fields ── */}
          <div style={{ marginTop: 20, paddingTop: 16, borderTop: "1px solid #e8e8e8" }}>
            <div style={{ fontWeight: 600, fontSize: 12, marginBottom: 10, color: "#555", textTransform: "uppercase", letterSpacing: "0.05em" }}>
              Displayed Fields
            </div>
            <div style={{ display: "flex", flexWrap: "wrap", gap: "6px 20px" }}>
              {(Object.keys(localDF) as (keyof DisplayedFields)[]).map(field => (
                <label key={field} style={{ display: "flex", alignItems: "center", gap: 6, fontSize: 12, cursor: "pointer" }}>
                  <input type="checkbox"
                    checked={localDF[field]}
                    onChange={() => setLocalDF(p => ({ ...p, [field]: !p[field] }))}
                    style={{ cursor: "pointer" }} />
                  {field === "fee" ? "Fee" : field === "stipend" ? "Stipend Year 1" : field === "bondYears" ? "Bond Years" : field === "bondPenalty" ? "Bond Penalty" : "Beds"}
                </label>
              ))}
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
