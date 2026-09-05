import { useCallback, useEffect, useState } from "react";

import * as api from "../api";
import { errorMessage } from "../api";
import { Field, PasswordInput, Select, TextInput } from "../components/Field";
import Pagination from "../components/Pagination";
import { usePaginatedList } from "../hooks/usePaginatedList";
import type { ManagedUser, Role } from "../types";

const roles: Role[] = ["applicant", "admin", "super_admin", "ceo"];

export default function UsersPage() {
  const [searchInput, setSearchInput] = useState("");
  const [search, setSearch] = useState("");
  const [role, setRole] = useState("");
  const [message, setMessage] = useState("");
  const [formError, setFormError] = useState("");
  const [refresh, setRefresh] = useState(0);
  const [form, setForm] = useState({ email: "", first_name: "", last_name: "", password: "", role: "applicant" as Role });
  const fetchUsers = useCallback((page: number) => api.listUsers(page, search, role), [search, role, refresh]);
  const list = usePaginatedList(fetchUsers, "Failed to load users.");

  // Debounce keystrokes: usePaginatedList refetches whenever the fetcher
  // identity changes, so the debounced `search` keeps it to one call per
  // settled input instead of one call per character typed.
  useEffect(() => {
    const timer = setTimeout(() => setSearch(searchInput), 300);
    return () => clearTimeout(timer);
  }, [searchInput]);

  useEffect(() => { list.setPageNum(1); }, [search, role]);

  const update = async (user: ManagedUser, changes: { role?: Role; is_active?: boolean }) => {
    try {
      await api.updateUser(user.id, changes);
      setMessage("User updated.");
      setRefresh((value) => value + 1);
    } catch (error) { setFormError(errorMessage(error, "Could not update user.")); }
  };

  const resetPassword = async (user: ManagedUser) => {
    const newPassword = window.prompt(`New password for ${user.email ?? user.username}`);
    if (!newPassword) return;
    try {
      await api.setUserPassword(user.id, newPassword);
      setMessage("Password updated.");
      setFormError("");
    } catch (error) { setFormError(errorMessage(error, "Could not update password.")); }
  };

  const submit = async (event: React.FormEvent) => {
    event.preventDefault();
    setFormError("");
    try {
      await api.createUser(form);
      setMessage("User created.");
      setForm({ email: "", first_name: "", last_name: "", password: "", role: "applicant" });
      setRefresh((value) => value + 1);
    } catch (error) { setFormError(errorMessage(error, "Could not create user.")); }
  };

  return <div className="space-y-8">
    <div><h1 className="text-2xl font-bold">User Management</h1><p className="mt-1 text-sm text-slate-500">Create accounts, assign roles, and control access.</p></div>
    <form onSubmit={submit} className="grid gap-4 rounded-lg bg-white p-5 shadow sm:grid-cols-2 lg:grid-cols-5">
      <Field label="Email"><TextInput type="email" value={form.email} onChange={(e) => setForm({ ...form, email: e.target.value })} /></Field>
      <Field label="First name"><TextInput required value={form.first_name} onChange={(e) => setForm({ ...form, first_name: e.target.value })} /></Field>
      <Field label="Last name"><TextInput required value={form.last_name} onChange={(e) => setForm({ ...form, last_name: e.target.value })} /></Field>
      <Field label="Password"><PasswordInput required value={form.password} onChange={(e) => setForm({ ...form, password: e.target.value })} /></Field>
      <Field label="Role"><Select value={form.role} onChange={(e) => setForm({ ...form, role: e.target.value as Role })}>{roles.map((item) => <option key={item}>{item}</option>)}</Select></Field>
      <button className="rounded bg-blue-600 px-4 py-2 text-sm font-semibold text-white hover:bg-blue-700 sm:col-span-2 lg:col-span-5 lg:w-fit">Create user</button>
    </form>
    {(message || formError || list.error) && <p className={formError || list.error ? "text-sm text-red-600" : "text-sm text-green-700"}>{formError || list.error || message}</p>}
    <div className="flex gap-3"><TextInput placeholder="Search users" value={searchInput} onChange={(e) => setSearchInput(e.target.value)} /><Select value={role} onChange={(e) => setRole(e.target.value)}><option value="">All roles</option>{roles.map((item) => <option key={item}>{item}</option>)}</Select></div>
    <div className="overflow-x-auto rounded-lg bg-white shadow"><table className="w-full text-left text-sm"><thead className="border-b text-xs uppercase text-slate-500"><tr><th className="p-4">User</th><th className="p-4">Role</th><th className="p-4">Status</th><th className="p-4">Actions</th></tr></thead><tbody>{list.items.map((user) => <tr key={user.id} className="border-b last:border-0"><td className="p-4"><strong>{user.first_name} {user.last_name}</strong><br /><span className="text-slate-500">{user.email ?? user.phone ?? user.username}</span></td><td className="p-4"><Select value={user.role} onChange={(e) => void update(user, { role: e.target.value as Role })}>{roles.map((item) => <option key={item}>{item}</option>)}</Select></td><td className="p-4">{user.is_active ? "Active" : "Inactive"}</td><td className="space-x-3 p-4"><button className="text-blue-600 hover:underline" onClick={() => void update(user, { is_active: !user.is_active })}>{user.is_active ? "Deactivate" : "Activate"}</button><button className="text-blue-600 hover:underline" onClick={() => void resetPassword(user)}>Reset password</button></td></tr>)}</tbody></table></div>
    <Pagination count={list.count} pageNum={list.pageNum} hasNext={list.hasNext} hasPrev={list.hasPrev} loading={list.loading} onPageChange={list.setPageNum} label="users" />
  </div>;
}
