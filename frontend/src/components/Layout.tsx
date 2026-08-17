import { Link, Outlet, useNavigate } from "react-router-dom";

import { useAuth } from "../auth";

export default function Layout() {
  const { user, logout } = useAuth();
  const navigate = useNavigate();

  const handleLogout = () => {
    logout();
    navigate("/login");
  };

  return (
    <div className="min-h-screen">
      <header className="bg-slate-900 text-white shadow">
        <div className="mx-auto flex max-w-6xl items-center justify-between px-4 py-3">
          <Link to="/" className="text-lg font-bold tracking-tight">
            Login Portal
          </Link>
          <nav className="flex items-center gap-4 text-sm">
            {user && (
              <>
                <Link to="/" className="hover:text-slate-300">
                  Dashboard
                </Link>
                {(user.role === "reviewer" || user.role === "admin") && (
                  <Link to="/review" className="hover:text-slate-300">
                    Review Queue
                  </Link>
                )}
                <span className="text-slate-400" title={user.email ?? user.phone ?? ""}>
                  {user.username} · {user.role}
                </span>
                <button
                  onClick={handleLogout}
                  className="rounded bg-slate-700 px-3 py-1 hover:bg-slate-600"
                >
                  Log out
                </button>
              </>
            )}
          </nav>
        </div>
      </header>
      <main className="mx-auto max-w-6xl px-4 py-8">
        <Outlet />
      </main>
    </div>
  );
}
