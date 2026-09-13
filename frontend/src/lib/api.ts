import {
  AskResponse,
  DocumentItem,
  DocumentStatusResponse,
  HealthResponse,
  UploadResponse,
} from "@/types/api";

const API_BASE_URL =
  process.env.NEXT_PUBLIC_API_URL?.replace(/\/+$/, "") || "http://127.0.0.1:8000";

export async function fetchHealth(): Promise<HealthResponse> {
  const res = await fetch(`${API_BASE_URL}/health`, {
    cache: "no-store",
  });
  if (!res.ok) {
    throw new Error(`Health check failed: HTTP ${res.status}`);
  }
  return res.json();
}

export async function fetchDocuments(): Promise<DocumentItem[]> {
  const res = await fetch(`${API_BASE_URL}/documents`, {
    cache: "no-store",
  });
  if (!res.ok) {
    throw new Error(`Failed to fetch documents: HTTP ${res.status}`);
  }
  return res.json();
}

export async function deleteDocument(
  docId: string
): Promise<{ deleted: boolean; doc_id: string; chunks_removed: number }> {
  const res = await fetch(`${API_BASE_URL}/documents/${docId}`, {
    method: "DELETE",
  });
  if (!res.ok) {
    let errorDetail = `Failed to delete document: HTTP ${res.status}`;
    try {
      const data = await res.json();
      if (data.detail) errorDetail = data.detail;
    } catch {}
    throw new Error(errorDetail);
  }
  return res.json();
}

export async function uploadDocument(file: File): Promise<UploadResponse> {
  const formData = new FormData();
  formData.append("file", file);

  const res = await fetch(`${API_BASE_URL}/documents/upload`, {
    method: "POST",
    body: formData,
  });

  if (!res.ok) {
    let errorDetail = `Upload failed with HTTP ${res.status}`;
    try {
      const data = await res.json();
      if (data.detail) errorDetail = data.detail;
    } catch {}
    throw new Error(errorDetail);
  }
  return res.json();
}

export async function fetchUploadStatus(
  jobId: string
): Promise<DocumentStatusResponse> {
  const res = await fetch(`${API_BASE_URL}/documents/status/${jobId}`, {
    cache: "no-store",
  });
  if (!res.ok) {
    let errorDetail = `Failed to get status: HTTP ${res.status}`;
    try {
      const data = await res.json();
      if (data.detail) errorDetail = data.detail;
    } catch {}
    throw new Error(errorDetail);
  }
  return res.json();
}

export async function askQuestion(params: {
  query: string;
  company_name?: string | null;
  fiscal_year?: string | null;
}): Promise<AskResponse> {
  const body: Record<string, any> = { query: params.query };
  if (params.company_name) body.company_name = params.company_name;
  if (params.fiscal_year) body.fiscal_year = params.fiscal_year;

  const res = await fetch(`${API_BASE_URL}/ask`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify(body),
  });

  if (!res.ok) {
    let errorDetail = `Query failed with HTTP ${res.status}`;
    try {
      const data = await res.json();
      if (data.detail) errorDetail = data.detail;
    } catch {}
    throw new Error(errorDetail);
  }
  return res.json();
}

export function formatFiscalYear(fy?: string | null): string {
  if (!fy) return "";
  const trimmed = fy.trim();
  return trimmed.toUpperCase().startsWith("FY") ? trimmed : `FY ${trimmed}`;
}

