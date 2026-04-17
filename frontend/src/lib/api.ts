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
  course_types: string[];
}

export interface ClosingRankRow {
  r1_group_id: string | null;
  r2_group_id: string | null;
  year: number;
  counselling_type: string;
  counselling_state: string | null;
  institute_name: string | null;
  institute_city: string | null;
  institute_address: string | null;
  institute_address_verified: string | null;
  institute_pincode: string | null;
  state: string | null;
  course_norm: string | null;
  quota_norm: string | null;
  allotted_category_norm: string | null;
  r1_closing_rank: number | null;
  r1_allotment_count: number;
  r2_closing_rank: number | null;
  r2_allotment_count: number;
  r3_closing_rank: number | null;
  r3_allotment_count: number;
  r3_group_id: string | null;
  r4_closing_rank: number | null;
  r4_allotment_count: number;
  r4_group_id: string | null;
  // Institute profile data (joined via mapping)
  inst_fee_yr1: number | null;
  inst_fee_yr2: number | null;
  inst_fee_yr3: number | null;
  inst_stipend_yr1: string | null;
  inst_stipend_yr2: string | null;
  inst_stipend_yr3: string | null;
  inst_bond_forfeit: string | null;
  inst_bond_years: string | null;
  inst_beds: number | null;
  inst_university: string | null;
  inst_matched: boolean | null;
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
  quota_norm?: string[];
  allotted_category_norm?: string[];
  state?: string[];
  course_norm?: string[];
  course_type?: string[];
  rank_min?: number;
  rank_max?: number;
  search?: string;
  /** "r1"/"r2"/"r3"/"r4" の複数選択可 (OR条件); undefined = 全て表示 */
  round_display?: ("r1" | "r2" | "r3" | "r4")[];
  /** このランクが含まれるグループを表示 (closing_rank >= my_rank) */
  my_rank?: number;
  sort_by?: "quota_norm" | "allotted_category_norm" | "state" | "institute_name" | "institute_pincode" | "course_norm" | "r1_closing_rank" | "r2_closing_rank" | "r3_closing_rank" | "r4_closing_rank" | "inst_fee_yr1" | "inst_stipend_yr1" | "inst_bond_forfeit";
  sort_order?: "asc" | "desc";
  fee_min?: number;
  fee_max?: number;
  bond_min?: number;
  bond_max?: number;
  page?: number;
  page_size?: number;
}

function qs(params: Record<string, unknown>): string {
  const q = new URLSearchParams();
  for (const [k, v] of Object.entries(params)) {
    if (v === undefined || v === null || v === "") continue;
    if (Array.isArray(v)) {
      // Send each value as a separate param for FastAPI List[str] support
      for (const item of v) {
        if (item !== undefined && item !== null && item !== "") q.append(k, String(item));
      }
    } else {
      q.set(k, String(v));
    }
  }
  const s = q.toString();
  return s ? `?${s}` : "";
}

async function get<T>(path: string): Promise<T> {
  const url = `${API_URL}${path}`;
  let res: Response;
  try {
    res = await fetch(url);
  } catch (err) {
    throw new Error(
      `Failed to fetch ${url} — is NEXT_PUBLIC_API_URL set correctly? (${err instanceof Error ? err.message : err})`
    );
  }
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

export const exportClosingRanksUrl = (f: ClosingRankFilters): string =>
  `${API_URL}/closing-ranks/export${qs(f as Record<string, unknown>)}`;


// ---------------------------------------------------------------------------
// Institutes
// ---------------------------------------------------------------------------

export interface InstituteRow {
  institute_code: number;
  institute_name: string;
  display_name: string;
  address: string | null;
  state: string | null;
  pincode: string | null;
  university: string | null;
  fee_yr1: number | null;
  fee_yr2: number | null;
  fee_yr3: number | null;
  annual_fee: string | null;
  stipend_yr1: string | null;
  stipend_yr2: string | null;
  stipend_yr3: string | null;
  hostel_male: string | null;
  hostel_female: string | null;
  bond_forfeit: string | null;
  pwbd_friendly: string | null;
  website: string | null;
  match_status: string | null;
}

export interface InstituteFilters {
  search?: string;
  state?: string[];
  match_status?: string[];
  sort_by?: "display_name" | "state" | "pincode" | "annual_fee" | "stipend_yr1" | "institute_code";
  sort_order?: "asc" | "desc";
  page?: number;
  page_size?: number;
}

export const fetchInstitutes = (f: InstituteFilters): Promise<PaginatedResponse<InstituteRow>> =>
  get(`/institutes${qs(f as Record<string, unknown>)}`);


// ---------------------------------------------------------------------------
// Allotments (individual rank-wise records)
// ---------------------------------------------------------------------------

export interface AllotmentRow {
  id: number;
  year: number;
  counselling_type: string;
  counselling_state: string | null;
  round: number;
  sno: number | null;
  rank: number | null;
  quota_raw: string | null;
  quota_norm: string | null;
  institute_raw: string | null;
  institute_name: string | null;
  state: string | null;
  course_raw: string | null;
  course_norm: string | null;
  allotted_category_raw: string | null;
  allotted_category_norm: string | null;
  candidate_category_raw: string | null;
  remarks: string | null;
  source_page: number | null;
  r1_status: string | null;
  seat_outcome: string | null;
}

export interface AllotmentFilters {
  year?: number;
  counselling_type?: string;
  round?: number;
  quota_norm?: string;
  allotted_category_norm?: string;
  state?: string;
  course_norm?: string;
  institute_name?: string;
  rank_min?: number;
  rank_max?: number;
  search?: string;
  final_only?: boolean;
  sort_by?: "rank" | "institute_name" | "course_norm" | "sno";
  sort_order?: "asc" | "desc";
  page?: number;
  page_size?: number;
}

export const fetchAllotments = (f: AllotmentFilters): Promise<PaginatedResponse<AllotmentRow>> =>
  get(`/allotments${qs(f as Record<string, unknown>)}`);
