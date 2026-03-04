const API_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

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

function qs(params: Record<string, unknown>): string {
  const q = new URLSearchParams();
  for (const [k, v] of Object.entries(params)) {
    if (v !== undefined && v !== null && v !== "") q.set(k, String(v));
  }
  const s = q.toString();
  return s ? `?${s}` : "";
}

async function get<T>(path: string): Promise<T> {
  const res = await fetch(`${API_URL}${path}`);
  if (!res.ok) {
    const body = await res.text().catch(() => "");
    throw new Error(`API ${res.status}: ${body || res.statusText}`);
  }
  return res.json() as Promise<T>;
}

export const fetchMetadata = (p: Record<string, unknown> = {}): Promise<MetadataResponse> =>
  get(`/metadata${qs(p)}`);

export const fetchClosingRanks = (f: ClosingRankFilters): Promise<PaginatedResponse<ClosingRankRow>> =>
  get(`/closing-ranks${qs(f as Record<string, unknown>)}`);

export const fetchDrillDown = (groupId: string): Promise<DrillDownResponse> =>
  get(`/closing-ranks/${encodeURIComponent(groupId)}/allotments`);
