/**
 * Typed API client for the NEET-PG Analytics backend.
 * All filtering is delegated to server-side SQL.
 */

const API_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

export interface MetadataResponse {
  years: number[];
  counselling_types: string[];
  counselling_states: (string | null)[];
  rounds: number[];
  quotas: string[];
  categories: string[];
  states: string[];
  courses: string[];
}

export interface ClosingRankRow {
  group_id: string;
  year: number;
  counselling_type: string;
  counselling_state: string | null;
  round: number;
  institute_name: string | null;
  state: string | null;
  course_norm: string | null;
  quota_norm: string | null;
  allotted_category_norm: string | null;
  closing_rank: number | null;
  allotment_count: number;
}

export interface PaginatedResponse<T> {
  data: T[];
  total: number;
  page: number;
  page_size: number;
  pages: number;
}

export interface DrillDownRow {
  rank: number | null;
  sno: number | null;
  round: number;
  state: string | null;
  institute_name: string | null;
  course_norm: string | null;
  quota_norm: string | null;
  allotted_category_norm: string | null;
  candidate_category_raw: string | null;
  remarks: string | null;
}

export interface DrillDownResponse {
  group_id: string;
  closing_rank: number | null;
  allotment_count: number;
  data: DrillDownRow[];
}

// ---------------------------------------------------------------------------
// Filter params
// ---------------------------------------------------------------------------

export interface ClosingRankFilters {
  year?: number;
  counselling_type?: string;
  counselling_state?: string;
  round?: number;
  quota_norm?: string;
  allotted_category_norm?: string;
  state?: string;
  course_norm?: string;
  rank_min?: number;
  rank_max?: number;
  search?: string;
  sort_by?: "institute_name" | "course_norm" | "closing_rank";
  sort_order?: "asc" | "desc";
  page?: number;
  page_size?: number;
}

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function buildQuery(params: Record<string, unknown>): string {
  const qs = new URLSearchParams();
  for (const [k, v] of Object.entries(params)) {
    if (v !== undefined && v !== null && v !== "") {
      qs.set(k, String(v));
    }
  }
  const s = qs.toString();
  return s ? `?${s}` : "";
}

async function apiFetch<T>(path: string): Promise<T> {
  const res = await fetch(`${API_URL}${path}`);
  if (!res.ok) {
    const body = await res.text();
    throw new Error(`API error ${res.status}: ${body}`);
  }
  return res.json() as Promise<T>;
}

// ---------------------------------------------------------------------------
// API calls
// ---------------------------------------------------------------------------

export async function fetchMetadata(
  params: Partial<{ year: number; counselling_type: string; counselling_state: string; round: number }>
): Promise<MetadataResponse> {
  return apiFetch<MetadataResponse>(`/metadata${buildQuery(params)}`);
}

export async function fetchClosingRanks(
  filters: ClosingRankFilters
): Promise<PaginatedResponse<ClosingRankRow>> {
  return apiFetch<PaginatedResponse<ClosingRankRow>>(
    `/closing-ranks${buildQuery(filters as Record<string, unknown>)}`
  );
}

export async function fetchDrillDown(groupId: string): Promise<DrillDownResponse> {
  return apiFetch<DrillDownResponse>(
    `/closing-ranks/${encodeURIComponent(groupId)}/allotments`
  );
}
