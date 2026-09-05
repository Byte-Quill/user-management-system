import { request } from "./client";

import type {
  ApplicationPayload,
  AuditEntry,
  KYCApplication,
  KycDocument,
  Page,
} from "@/types";

export const listApplications = (page = 1) =>
  request<Page<KYCApplication>>(`/applications/?page=${page}`);
export const getApplication = (id: string) => request<KYCApplication>(`/applications/${id}/`);
export const createApplication = (payload: ApplicationPayload) =>
  request<KYCApplication>("/applications/", { method: "POST", body: JSON.stringify(payload) });
export const updateApplication = (id: string, payload: ApplicationPayload) =>
  request<KYCApplication>(`/applications/${id}/`, {
    method: "PATCH",
    body: JSON.stringify(payload),
  });
export const submitApplication = (id: string) =>
  request<KYCApplication>(`/applications/${id}/submit/`, { method: "POST" });

export const uploadDocument = (id: string, docType: string, file: File) => {
  const form = new FormData();
  form.append("doc_type", docType);
  form.append("file", file);
  return request<KycDocument>(`/applications/${id}/documents/`, {
    method: "POST",
    body: form,
  });
};

export const deleteDocument = (id: string, docId: string) =>
  request<void>(`/applications/${id}/documents/${docId}/`, { method: "DELETE" });

export const reviewApplication = (id: string, decision: string, notes: string) =>
  request<KYCApplication>(`/applications/${id}/review/`, {
    method: "POST",
    body: JSON.stringify({ decision, notes }),
  });

export const fetchAudit = (id: string, page = 1) =>
  request<Page<AuditEntry>>(`/applications/${id}/audit/?page=${page}`);
export const fetchReviewQueue = (page = 1) =>
  request<Page<KYCApplication>>(`/review-queue/?page=${page}`);
