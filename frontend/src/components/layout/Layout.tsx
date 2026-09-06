import { Link, NavLink, Outlet, useNavigate } from "react-router";

import { useAuth } from "@/features/auth/hooks/useAuth";

const ROLE_LABELS: Record<string, string> = {
  applicant: "Applicant",
  admin: "Admin",
  super_admin: "Super Admin",
  ceo: "CEO",
};

const linkClass = ({ isActive }: { isActive: boolean }) =>
  `rounded-lg px-3 py-1.5 font-medium transition-colors ${
    isActive ? "bg-slate-800 text-white" : "text-slate-300 hover:bg-slate-800/60 hover:text-white"
  }`;

export default function Layout() {
  const { user, logout } = useAuth();
  const navigate = useNavigate();

  const handleLogout = () => {
    logout();
    navigate("/login");
  };

  const initials = (user?.first_name?.[0] ?? user?.username?.[0] ?? "?").toUpperCase();

  return (
    <div className="min-h-screen bg-slate-50">
      <header className="border-b border-slate-800 bg-slate-900 text-white shadow">
        <div className="mx-auto flex max-w-6xl items-center justify-between gap-4 px-4 py-3">
          <Link to="/" className="flex items-center gap-2 text-lg font-bold tracking-tight">
            <span className="flex h-8 w-8 items-center justify-center rounded-lg bg-blue-600 text-sm">
              LP
            </span>
            Login Portal
          </Link>
          <nav className="flex items-center gap-1 text-sm">
            {user && (
              <>
                <NavLink to="/" end className={linkClass}>
                  Dashboard
                </NavLink>
                {(user.role === "admin" || user.role === "super_admin") && (
                  <NavLink to="/review" className={linkClass}>
                    Review Queue
                  </NavLink>
                )}
                {user.role === "super_admin" && (
                  <NavLink to="/users" className={linkClass}>
                    Users
                  </NavLink>
                )}
                {user.role === "ceo" && (
                  <NavLink to="/analytics" className={linkClass}>
                    Analytics
                  </NavLink>
                )}
              </>
            )}
          </nav>
          {user && (
            <div className="flex items-center gap-3">
              <div className="hidden text-right sm:block">
                <p className="text-sm font-medium leading-tight">
                  {[user.first_name, user.last_name].filter(Boolean).join(" ") || user.username}
                </p>
                <p className="text-xs leading-tight text-slate-400">
                  {ROLE_LABELS[user.role] ?? user.role}
                </p>
              </div>
              <span
                title={user.email ?? user.phone ?? user.username}
                className="flex h-8 w-8 items-center justify-center rounded-full bg-blue-600 text-xs font-bold"
              >
                {initials}
              </span>
              <button
                onClick={handleLogout}
                className="rounded-lg border border-slate-700 px-3 py-1.5 text-sm font-medium text-slate-300 transition-colors hover:bg-slate-800 hover:text-white"
              >
                Log out
              </button>
            </div>
          )}
        </div>
      </header>
      <main className="mx-auto max-w-6xl px-4 py-8">
        <Outlet />
      </main>
    </div>
  );
}
