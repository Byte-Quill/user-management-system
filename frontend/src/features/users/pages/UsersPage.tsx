import { useCallback, useEffect, useState } from "react";

import * as api from "@/lib/api";
import { errorMessage } from "@/lib/api";
import { Field, PasswordInput, Select, TextInput } from "@/components/ui/Field";
import Pagination from "@/components/ui/Pagination";
import Alert from "@/components/ui/Alert";
import Button from "@/components/ui/Button";
import Modal from "@/components/ui/Modal";
import PasswordStrength from "@/components/ui/PasswordStrength";
import { SkeletonTable } from "@/components/ui/Skeleton";
import { usePaginatedList } from "@/hooks/usePaginatedList";
import {
  capitalizeFirst,
  validateConfirmPassword,
  validateEmail,
  validateName,
  validatePassword,
} from "@/lib/validation";
import type { ManagedUser, Role } from "@/types";

const roles: Role[] = ["applicant", "admin", "super_admin", "ceo"];

const ROLE_LABELS: Record<Role, string> = {
  applicant: "Applicant",
  admin: "Admin",
  super_admin: "Super Admin",
  ceo: "CEO",
};

export default function UsersPage() {
  const [searchInput, setSearchInput] = useState("");
  const [search, setSearch] = useState("");
  const [role, setRole] = useState("");
  const [message, setMessage] = useState("");
  const [formError, setFormError] = useState("");
  const [refresh, setRefresh] = useState(0);
  const [form, setForm] = useState({ email: "", first_name: "", last_name: "", password: "", role: "applicant" as Role });

  const [createErrors, setCreateErrors] = useState<Record<string, string>>({});

  const [resetTarget, setResetTarget] = useState<ManagedUser | null>(null);
  const [newPassword, setNewPassword] = useState("");
  const [confirmPassword, setConfirmPassword] = useState("");
  const [resetError, setResetError] = useState("");
  const [resetting, setResetting] = useState(false);

  const fetchUsers = useCallback((page: number) => api.listUsers(page, search, role), [search, role, refresh]);
  const list = usePaginatedList(fetchUsers, "Failed to load users.");

  useEffect(() => {
    const timer = setTimeout(() => setSearch(searchInput), 300);
    return () => clearTimeout(timer);
  }, [searchInput]);

  useEffect(() => { list.setPageNum(1); }, [search, role]);

  const openReset = (user: ManagedUser) => {
    setResetTarget(user);
    setNewPassword("");
    setConfirmPassword("");
    setResetError("");
  };

  const confirmReset = async () => {
    if (!resetTarget) return;
    const pwError = validatePassword(newPassword);
    const confirmError = validateConfirmPassword(newPassword, confirmPassword);
    if (pwError || confirmError) {
      setResetError(pwError ?? confirmError ?? "");
      return;
    }
    setResetError("");
    setResetting(true);
    try {
      await api.setUserPassword(resetTarget.id, newPassword);
      setMessage(`Password updated for ${resetTarget.email ?? resetTarget.username}.`);
      setFormError("");
      setResetTarget(null);
    } catch (error) {
      setResetError(errorMessage(error, "Could not update password."));
    } finally {
      setResetting(false);
    }
  };

  const update = async (user: ManagedUser, changes: { role?: Role; is_active?: boolean }) => {
    try {
      await api.updateUser(user.id, changes);
      setMessage("User updated.");
      setFormError("");
      setRefresh((value) => value + 1);
    } catch (error) { setFormError(errorMessage(error, "Could not update user.")); }
  };

  const submit = async (event: React.FormEvent) => {
    event.preventDefault();

    const errors: Record<string, string> = {};
    const emailError = validateEmail(form.email);
    if (emailError) errors.email = emailError;
    const firstNameError = validateName(form.first_name, "First name");
    if (firstNameError) errors.first_name = firstNameError;
    const lastNameError = validateName(form.last_name, "Last name");
    if (lastNameError) errors.last_name = lastNameError;
    const passwordError = validatePassword(form.password);
    if (passwordError) errors.password = passwordError;
    setCreateErrors(errors);
    if (Object.keys(errors).length > 0) return;
    setFormError("");
    try {
      await api.createUser({
        ...form,
        first_name: capitalizeFirst(form.first_name.trim()),
        last_name: capitalizeFirst(form.last_name.trim()),
      });
      setMessage("User created.");
      setForm({ email: "", first_name: "", last_name: "", password: "", role: "applicant" });
      setCreateErrors({});
      setRefresh((value) => value + 1);
    } catch (error) { setFormError(errorMessage(error, "Could not create user.")); }
  };

  const setCreateField = (key: keyof typeof form) =>
    (e: React.ChangeEvent<HTMLInputElement | HTMLSelectElement>) => {
      setForm({ ...form, [key]: e.target.value });
      setCreateErrors((prev) => {
        if (!(key in prev)) return prev;
        const next = { ...prev };
        delete next[key];
        return next;
      });
    };

  return <div className="space-y-8">
    <div>
      <h1 className="text-2xl font-bold text-slate-900">User Management</h1>
      <p className="mt-1 text-sm text-slate-500">Create accounts, assign roles, and control access.</p>
    </div>

    <form onSubmit={submit} className="grid gap-4 rounded-xl border border-slate-200 bg-white p-5 shadow-sm sm:grid-cols-2 lg:grid-cols-5">
      <Field label="Email" error={createErrors.email}>
        <TextInput type="email" value={form.email} onChange={setCreateField("email")} invalid={!!createErrors.email} />
      </Field>
      <Field label="First name" error={createErrors.first_name}>
        <TextInput required value={form.first_name} onChange={setCreateField("first_name")} invalid={!!createErrors.first_name} />
      </Field>
      <Field label="Last name" error={createErrors.last_name}>
        <TextInput required value={form.last_name} onChange={setCreateField("last_name")} invalid={!!createErrors.last_name} />
      </Field>
      <Field label="Password" error={createErrors.password} hint="Min 8 chars, not too common.">
        <PasswordInput required value={form.password} onChange={setCreateField("password")} invalid={!!createErrors.password} />
        <PasswordStrength password={form.password} />
      </Field>
      <Field label="Role"><Select value={form.role} onChange={setCreateField("role")}>{roles.map((item) => <option key={item} value={item}>{ROLE_LABELS[item]}</option>)}</Select></Field>
      <div className="sm:col-span-2 lg:col-span-5"><Button type="submit">Create user</Button></div>
    </form>

    {(message || formError || list.error) && (
      <Alert variant={formError || list.error ? "error" : "success"}>{formError || list.error || message}</Alert>
    )}

    <div className="flex gap-3">
      <TextInput placeholder="Search users" value={searchInput} onChange={(e) => setSearchInput(e.target.value)} />
      <Select value={role} onChange={(e) => setRole(e.target.value)} className="w-44">
        <option value="">All roles</option>
        {roles.map((item) => <option key={item} value={item}>{ROLE_LABELS[item]}</option>)}
      </Select>
    </div>

    <div className="overflow-x-auto rounded-xl border border-slate-200 bg-white shadow-sm">
      {list.loading && list.items.length === 0 ? (
        <SkeletonTable />
      ) : (
        <table className="w-full text-left text-sm">
          <thead className="border-b border-slate-200 bg-slate-50 text-xs uppercase tracking-wide text-slate-500">
            <tr><th className="p-4">User</th><th className="p-4">Role</th><th className="p-4">Status</th><th className="p-4">Actions</th></tr>
          </thead>
          <tbody className="divide-y divide-slate-100">
            {list.items.map((user) => (
              <tr key={user.id} className="transition hover:bg-slate-50">
                <td className="p-4">
                  <strong className="text-slate-900">{user.first_name} {user.last_name}</strong>
                  <br /><span className="text-slate-500">{user.email ?? user.phone ?? user.username}</span>
                </td>
                <td className="p-4">
                  <Select value={user.role} onChange={(e) => void update(user, { role: e.target.value as Role })}>
                    {roles.map((item) => <option key={item} value={item}>{ROLE_LABELS[item]}</option>)}
                  </Select>
                </td>
                <td className="p-4">
                  <span className={`inline-flex items-center gap-1.5 rounded-full px-2 py-0.5 text-xs font-semibold ${user.is_active ? "bg-emerald-50 text-emerald-700 ring-1 ring-inset ring-emerald-200" : "bg-slate-100 text-slate-500 ring-1 ring-inset ring-slate-200"}`}>
                    <span className={`h-1.5 w-1.5 rounded-full ${user.is_active ? "bg-emerald-500" : "bg-slate-400"}`} />
                    {user.is_active ? "Active" : "Inactive"}
                  </span>
                </td>
                <td className="p-4">
                  <div className="flex flex-wrap gap-3">
                    <Button size="sm" variant="secondary" onClick={() => void update(user, { is_active: !user.is_active })}>
                      {user.is_active ? "Deactivate" : "Activate"}
                    </Button>
                    <Button size="sm" variant="secondary" onClick={() => openReset(user)}>
                      Reset password
                    </Button>
                  </div>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </div>

    <Pagination count={list.count} pageNum={list.pageNum} hasNext={list.hasNext} hasPrev={list.hasPrev} loading={list.loading} onPageChange={list.setPageNum} label="users" />

    <Modal open={!!resetTarget} title="Reset password" onClose={() => setResetTarget(null)}>
      <form onSubmit={(e) => { e.preventDefault(); void confirmReset(); }} className="space-y-4">
        <p className="text-sm text-slate-600">
          Set a new password for <strong>{resetTarget?.email ?? resetTarget?.username}</strong>.
          This revokes all of their active sessions.
        </p>
        <Field label="New password" error={resetError && validatePassword(newPassword) ? resetError : undefined}>
          <PasswordInput required autoFocus value={newPassword} onChange={(e) => setNewPassword(e.target.value)} />
          <PasswordStrength password={newPassword} />
        </Field>
        <Field label="Confirm new password" error={resetError && !validatePassword(newPassword) ? resetError : undefined}>
          <PasswordInput required value={confirmPassword} onChange={(e) => setConfirmPassword(e.target.value)} />
        </Field>
        <div className="flex justify-end gap-3 pt-2">
          <Button type="button" variant="secondary" onClick={() => setResetTarget(null)}>Cancel</Button>
          <Button type="submit" loading={resetting}>Update password</Button>
        </div>
      </form>
    </Modal>
  </div>;
}
