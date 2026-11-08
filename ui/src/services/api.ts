import type {
  BomCompareRequest,
  BomComparisonResult,
  BomLink,
  ChangeImpactAnalysis,
  ConfirmChangeResponse,
  DigitalThreadResponse,
  DraftChangeRequestInput,
  DraftChangeResponse,
  ErrorResponse,
  ImpactRequest,
  IssueDetailResponse,
  IssuesSummaryResponse,
  PaginatedChangesResponse,
  PaginatedPartsResponse,
  Part,
  WhereUsedItem,
} from "@/types/api";
import { instrumentedFetch } from "@/lib/telemetry";

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || "http://127.0.0.1:8000";

export interface SystemHealthResponse {
  status: string;
  backend: "mock" | "windchill" | string;
  version: string;
  timestamp: string;
}

/**
 * Standard HTTP error handler extracting backend ErrorResponse envelope.
 */
async function handleResponse<T>(res: Response): Promise<T> {
  if (!res.ok) {
    let errorPayload: ErrorResponse = {
      error: "HTTPError",
      message: `Request failed with status ${res.status}`,
    };
    try {
      const data = await res.json();
      if (data && (data.error || data.message || data.detail)) {
        errorPayload = data;
      }
    } catch {
      // Ignore JSON parse failure on non-JSON error
    }
    const err = new Error(errorPayload.message || errorPayload.error || "An error occurred");
    (err as any).status = res.status;
    (err as any).response = errorPayload;
    throw err;
  }
  return res.json() as Promise<T>;
}

// ============================================================================
// System Health Probe
// ============================================================================

export async function getSystemHealth(): Promise<SystemHealthResponse> {
  const res = await instrumentedFetch(`${API_BASE_URL}/health`);
  return handleResponse<SystemHealthResponse>(res);
}

// ============================================================================
// Parts Catalog
// ============================================================================

export async function getParts(params?: {
  query?: string;
  lifecycle_state?: string;
  page?: number;
  page_size?: number;
}): Promise<PaginatedPartsResponse> {
  const searchParams = new URLSearchParams();
  if (params?.query) searchParams.set("query", params.query);
  if (params?.lifecycle_state) searchParams.set("lifecycle_state", params.lifecycle_state);
  if (params?.page) searchParams.set("page", String(params.page));
  if (params?.page_size) searchParams.set("page_size", String(params.page_size));

  const url = `${API_BASE_URL}/parts?${searchParams.toString()}`;
  const res = await instrumentedFetch(url);
  return handleResponse<PaginatedPartsResponse>(res);
}

export async function getPart(partNumber: string, version?: string): Promise<Part> {
  const searchParams = new URLSearchParams();
  if (version) searchParams.set("version", version);
  const queryStr = searchParams.toString() ? `?${searchParams.toString()}` : "";
  const res = await instrumentedFetch(`${API_BASE_URL}/parts/${encodeURIComponent(partNumber)}${queryStr}`);
  return handleResponse<Part>(res);
}

// ============================================================================
// Bill of Materials (BOM) & Where-Used
// ============================================================================

export async function getPartBom(partNumber: string, levels: number = 1): Promise<BomLink[]> {
  const res = await instrumentedFetch(`${API_BASE_URL}/parts/${encodeURIComponent(partNumber)}/bom?levels=${levels}`);
  return handleResponse<BomLink[]>(res);
}

export async function getPartWhereUsed(partNumber: string, recursive: boolean = false): Promise<WhereUsedItem[]> {
  const res = await instrumentedFetch(`${API_BASE_URL}/parts/${encodeURIComponent(partNumber)}/where-used?recursive=${recursive}`);
  return handleResponse<WhereUsedItem[]>(res);
}

export async function compareBoms(assemblyA: string, assemblyB: string): Promise<BomComparisonResult> {
  const payload: BomCompareRequest = {
    assembly_a: assemblyA,
    assembly_b: assemblyB,
  };
  const res = await instrumentedFetch(`${API_BASE_URL}/bom/compare`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  return handleResponse<BomComparisonResult>(res);
}

// ============================================================================
// Diagnostics & Planted Issues
// ============================================================================

export async function getIssuesSummary(): Promise<IssuesSummaryResponse> {
  const res = await instrumentedFetch(`${API_BASE_URL}/issues/summary`);
  return handleResponse<IssuesSummaryResponse>(res);
}

export async function getIssuesByType(
  type: string,
  page: number = 1,
  pageSize: number = 20
): Promise<IssueDetailResponse> {
  const res = await instrumentedFetch(`${API_BASE_URL}/issues/${type}?page=${page}&page_size=${pageSize}`);
  return handleResponse<IssueDetailResponse>(res);
}

// ============================================================================
// Change Impact Analysis
// ============================================================================

export async function analyzeImpact(partNumber: string): Promise<ChangeImpactAnalysis> {
  const payload: ImpactRequest = { part_number: partNumber };
  const res = await instrumentedFetch(`${API_BASE_URL}/impact`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  return handleResponse<ChangeImpactAnalysis>(res);
}

// ============================================================================
// Change Requests & Two-Step Safety Gate
// ============================================================================

export async function getChangeRequests(params?: {
  page?: number;
  page_size?: number;
  status?: string;
}): Promise<PaginatedChangesResponse> {
  const searchParams = new URLSearchParams();
  if (params?.page) searchParams.set("page", String(params.page));
  if (params?.page_size) searchParams.set("page_size", String(params.page_size));
  if (params?.status) searchParams.set("status", params.status);

  const res = await instrumentedFetch(`${API_BASE_URL}/changes?${searchParams.toString()}`);
  return handleResponse<PaginatedChangesResponse>(res);
}

export async function draftChangeRequest(payload: DraftChangeRequestInput): Promise<DraftChangeResponse> {
  const res = await instrumentedFetch(`${API_BASE_URL}/changes/draft`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  return handleResponse<DraftChangeResponse>(res);
}

export async function confirmChangeRequest(draftId: string): Promise<ConfirmChangeResponse> {
  const res = await instrumentedFetch(`${API_BASE_URL}/changes/${encodeURIComponent(draftId)}/confirm`, {
    method: "POST",
  });
  return handleResponse<ConfirmChangeResponse>(res);
}

// ============================================================================
// Digital Thread (Cross-Domain ERP + QMS + IIoT + PLM)
// ============================================================================

export async function getDigitalThread(partNumber: string): Promise<DigitalThreadResponse> {
  const res = await instrumentedFetch(`${API_BASE_URL}/digital-thread/${encodeURIComponent(partNumber)}`);
  return handleResponse<DigitalThreadResponse>(res);
}
