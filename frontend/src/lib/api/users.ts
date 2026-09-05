import { request } from "./client";

import type { ManagedUser, Page, Role } from "@/types";

export const listUsers = (page = 1, search = "", role = "") => {
  const params = new URLSearchParams({ page: String(page) });
  if (search) params.set("search", search);
  if (role) params.set("role", role);
  return request<Page<ManagedUser>>(`/users/?${params}`);
};

export const createUser = (payload: {
  email?: string;
  password: string;
  first_name: string;
  last_name: string;
  phone?: string;
  role: Role;
}) => request<ManagedUser>("/users/", { method: "POST", body: JSON.stringify(payload) });

export const updateUser = (id: number, payload: { role?: Role; is_active?: boolean }) =>
  request<ManagedUser>(`/users/${id}/`, { method: "PATCH", body: JSON.stringify(payload) });

export const setUserPassword = (id: number, newPassword: string) =>
  request<{ detail: string }>(`/users/${id}/set_password/`, {
    method: "POST",
    body: JSON.stringify({ new_password: newPassword }),
  });
