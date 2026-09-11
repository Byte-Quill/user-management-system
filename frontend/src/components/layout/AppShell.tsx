import { Link, NavLink, Outlet, useLocation, useNavigate } from "react-router";
import { useEffect, useState } from "react";

import { useAuth } from "@/features/auth/hooks/useAuth";
import { useBodyScrollLock } from "@/hooks/useBodyScrollLock";
import { ROLE_LABELS } from "@/components/layout/Layout";

type IconElement = React.ReactElement;

interface NavEntry {
  to: string;
  label: string;
  end?: boolean;
  icon: IconElement;
}
const ICON_CLASS = "h-[18px] w-[18px]";

const ICONS = {
  dashboard: (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" className={ICON_CLASS} aria-hidden="true">
      <path strokeLinecap="round" strokeLinejoin="round" d="M3.75 6A2.25 2.25 0 0 1 6 3.75h2.25A2.25 2.25 0 0 1 10.5 6v2.25a2.25 2.25 0 0 1-2.25 2.25H6a2.25 2.25 0 0 1-2.25-2.25V6ZM3.75 15.75A2.25 2.25 0 0 1 6 13.5h2.25a2.25 2.25 0 0 1 2.25 2.25V18a2.25 2.25 0 0 1-2.25 2.25H6A2.25 2.25 0 0 1 3.75 18v-2.25ZM13.5 6a2.25 2.25 0 0 1 2.25-2.25H18A2.25 2.25 0 0 1 20.25 6v12a2.25 2.25 0 0 1-2.25 2.25h-2.25A2.25 2.25 0 0 1 13.5 18V6Z" />
    </svg>
  ),
  plus: (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" className="h-4 w-4" aria-hidden="true">
      <path strokeLinecap="round" d="M12 4.5v15m7.5-7.5h-15" />
    </svg>
  ),
  queue: (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" className={ICON_CLASS} aria-hidden="true">
      <path strokeLinecap="round" strokeLinejoin="round" d="M3.75 6.75h16.5M3.75 12h16.5m-16.5 5.25h16.5" />
    </svg>
  ),
  users: (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" className={ICON_CLASS} aria-hidden="true">
      <path strokeLinecap="round" strokeLinejoin="round" d="M15 19.13a9.38 9.38 0 0 0 2.63.37 9.34 9.34 0 0 0 4.12-.95 4.13 4.13 0 0 0-7.53-2.5M15 19.13v-.01c0-1.11-.29-2.16-.79-3.07M15 19.13v.11A12.32 12.32 0 0 1 8.62 21c-2.33 0-4.51-.65-6.37-1.77l-.01-.1a6.38 6.38 0 0 1 11.97-3.07M12 6.38a3.38 3.38 0 1 1-6.75 0 3.38 3.38 0 0 1 6.75 0Zm8.25 2.25a2.63 2.63 0 1 1-5.25 0 2.63 2.63 0 0 1 5.25 0Z" />
    </svg>
  ),
  chart: (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" className={ICON_CLASS} aria-hidden="true">
      <path strokeLinecap="round" strokeLinejoin="round" d="M3 13.13C3 12.5 3.5 12 4.13 12h2.25c.62 0 1.12.5 1.12 1.13v6.75c0 .62-.5 1.12-1.12 1.12h-2.25A1.13 1.13 0 0 1 3 19.88v-6.75ZM9.75 8.63c0-.62.5-1.13 1.13-1.13h2.25c.62 0 1.12.5 1.12 1.13v11.25c0 .62-.5 1.12-1.12 1.12h-2.25a1.13 1.13 0 0 1-1.13-1.12V8.63ZM16.5 4.13c0-.62.5-1.13 1.13-1.13h2.25c.62 0 1.12.5 1.12 1.13v15.75c0 .62-.5 1.12-1.12 1.12h-2.25a1.13 1.13 0 0 1-1.13-1.12V4.13Z" />
    </svg>
  ),
  logout: (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" className={ICON_CLASS} aria-hidden="true">
      <path strokeLinecap="round" strokeLinejoin="round" d="M15.75 9V5.25A2.25 2.25 0 0 0 13.5 3h-6a2.25 2.25 0 0 0-2.25 2.25v13.5A2.25 2.25 0 0 0 7.5 21h6a2.25 2.25 0 0 0 2.25-2.25V15m3 0 3-3m0 0-3-3m3 3H9" />
    </svg>
  ),
  menu: (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" className="h-5 w-5" aria-hidden="true">
      <path strokeLinecap="round" d="M3.75 6.75h16.5M3.75 12h16.5m-16.5 5.25h16.5" />
    </svg>
  ),
};
function SectionLabel({ children }: { children: string }) {
  return (
    <p className="px-3 pb-1.5 pt-4 text-[11px] font-semibold uppercase tracking-[0.1em] text-ink-400">
      {children}
    </p>
  );
}

const railLink = ({ isActive }: { isActive: boolean }) =>
  `group flex items-center gap-3 rounded-xl px-3 py-2 text-sm font-medium transition-all ${
    isActive
      ? "bg-ink-900 text-white shadow-sm"
      : "text-ink-500 hover:bg-ink-100/70 hover:text-ink-900"
  }`;
export default function AppShell() {
  const { user, logout } = useAuth();
  const navigate = useNavigate();
  const location = useLocation();
  const [sidebarOpen, setSidebarOpen] = useState(false);

  useEffect(() => {
    setSidebarOpen(false);
  }, [location.pathname]);

  useBodyScrollLock(sidebarOpen);

  const handleLogout = () => {
    logout();
    navigate("/login");
  };

  const displayName =
    [user?.first_name, user?.last_name].filter(Boolean).join(" ") || user?.username || "";
  const initials = (displayName[0] ?? user?.username?.[0] ?? "?").toUpperCase();

  const adminItems: NavEntry[] = [
    ...((user?.role === "admin" || user?.role === "super_admin"
      ? [{ to: "/review", label: "Review Queue", end: false, icon: ICONS.queue }]
      : []) as NavEntry[]),
    ...(user?.role === "super_admin" ? [{ to: "/users", label: "Users", icon: ICONS.users }] : []),
  ];

  const insightItems: NavEntry[] =
    user?.role === "ceo" ? [{ to: "/analytics", label: "Analytics", icon: ICONS.chart }] : [];
  const rail = (
    <div className="flex h-full flex-col">
      <Link to="/" className="flex items-center gap-2.5 px-3 pb-2 pt-1" aria-label="Login Portal home">
        <span className="flex h-9 w-9 items-center justify-center rounded-xl bg-gradient-to-br from-brand-500 to-brand-700 text-sm font-bold text-white shadow-md shadow-brand-600/30">
          LP
        </span>
        <span className="leading-tight">
          <span className="block text-[15px] font-bold tracking-tight text-ink-900">
            Login Portal
          </span>
          <span className="block text-[11px] font-medium text-ink-400">
            Identity verification
          </span>
        </span>
      </Link>

      <nav aria-label="Primary" className="nice-scroll mt-3 flex-1 overflow-y-auto pb-4">
        <SectionLabel>Workspace</SectionLabel>
        <div className="space-y-0.5 px-1.5">
          <NavLink to="/" end className={railLink}>
            <span aria-hidden="true">{ICONS.dashboard}</span>
            Dashboard
          </NavLink>
          {user?.role === "applicant" && (
            <NavLink to="/applications/new" className={railLink}>
              <span aria-hidden="true">{ICONS.plus}</span>
              New application
            </NavLink>
          )}
        </div>
        {adminItems.length > 0 && (
          <>
            <SectionLabel>Administration</SectionLabel>
            <div className="space-y-0.5 px-1.5">
              {adminItems.map((item) => (
                <NavLink key={item.to} to={item.to} end={item.end} className={railLink}>
                  <span aria-hidden="true">{item.icon}</span>
                  {item.label}
                </NavLink>
              ))}
            </div>
          </>
        )}
        {insightItems.length > 0 && (
          <>
            <SectionLabel>Insights</SectionLabel>
            <div className="space-y-0.5 px-1.5">
              {insightItems.map((item) => (
                <NavLink key={item.to} to={item.to} className={railLink}>
                  <span aria-hidden="true">{item.icon}</span>
                  {item.label}
                </NavLink>
              ))}
            </div>
          </>
        )}
        <SectionLabel>Account</SectionLabel>
        <div className="space-y-0.5 px-1.5">
          <span className="flex items-center gap-3 rounded-xl px-3 py-2">
            <span
              title={user?.email ?? user?.phone ?? user?.username}
              className="flex h-9 w-9 shrink-0 items-center justify-center rounded-full bg-gradient-to-br from-brand-500 to-brand-700 text-xs font-bold text-white"
            >
              {initials}
            </span>
            <span className="min-w-0 flex-1 leading-tight">
              <span className="block truncate text-sm font-semibold text-ink-900">
                {displayName}
              </span>
              <span className="block truncate text-xs text-ink-400">
                {user ? ROLE_LABELS[user.role] ?? user.role : ""}
              </span>
            </span>
          </span>
        </div>
      </nav>

      <div className="border-t border-ink-100 px-3 py-3">
        <button
          onClick={handleLogout}
          className="flex w-full items-center gap-3 rounded-xl px-3 py-2 text-sm font-medium text-ink-500 transition hover:bg-red-50 hover:text-red-700"
        >
          <span aria-hidden="true">{ICONS.logout}</span>
          Log out
        </button>
      </div>
    </div>
  );
  return (
    <div className="min-h-screen bg-ink-50">
      <header className="sticky top-0 z-40 border-b border-ink-200/70 bg-white/85 backdrop-blur-md">
        <div className="mx-auto flex h-16 max-w-7xl items-center gap-3 px-4 sm:px-6">
          <button
            type="button"
            onClick={() => setSidebarOpen(true)}
            aria-label="Open navigation"
            className="rounded-xl p-2 text-ink-600 transition hover:bg-ink-100 lg:hidden"
          >
            <span aria-hidden="true">{ICONS.menu}</span>
          </button>
          <Link to="/" className="flex items-center gap-2.5 lg:hidden">
            <span className="flex h-8 w-8 items-center justify-center rounded-lg bg-gradient-to-br from-brand-500 to-brand-700 text-xs font-bold text-white">
              LP
            </span>
            <span className="text-[15px] font-bold tracking-tight text-ink-900">Login Portal</span>
          </Link>
          <div className="ml-auto flex items-center gap-2">
            <span className="hidden items-center gap-1.5 rounded-full bg-emerald-50 px-2.5 py-1 text-xs font-semibold text-emerald-700 ring-1 ring-inset ring-emerald-200 sm:inline-flex">
              <span className="h-1.5 w-1.5 rounded-full bg-emerald-500" aria-hidden="true" />
              All systems normal
            </span>
            {user && (
              <span className="hidden items-center gap-2 rounded-full border border-ink-200/80 bg-white py-1 pl-1 pr-3 shadow-xs md:inline-flex">
                <span className="flex h-6 w-6 items-center justify-center rounded-full bg-gradient-to-br from-brand-500 to-brand-700 text-[10px] font-bold text-white">
                  {initials}
                </span>
                <span className="max-w-40 truncate text-xs font-semibold text-ink-800">
                  {displayName}
                </span>
              </span>
            )}
          </div>
        </div>
      </header>

      <div className="mx-auto flex max-w-7xl items-start gap-6 px-4 py-6 sm:px-6">
        <aside className="sticky top-24 hidden w-64 shrink-0 self-start rounded-2xl border border-ink-200/70 bg-white py-3 shadow-card lg:block">
          {rail}
        </aside>

        {sidebarOpen && (
          <div className="fixed inset-0 z-50 lg:hidden" role="dialog" aria-modal="true" aria-label="Navigation">
            <div
              className="absolute inset-0 bg-ink-950/45 backdrop-blur-[2px] motion-safe:animate-fade-in"
              onClick={() => setSidebarOpen(false)}
              aria-hidden="true"
            />
            <aside className="nice-scroll absolute inset-y-0 left-0 w-72 max-w-[85vw] overflow-y-auto border-r border-ink-200/70 bg-white py-3 shadow-pop motion-safe:animate-[drawer-in_0.28s_cubic-bezier(0.22,1,0.36,1)_both]">
              <div className="flex justify-end px-3">
                <button
                  type="button"
                  onClick={() => setSidebarOpen(false)}
                  aria-label="Close navigation"
                  className="rounded-lg p-2 text-ink-500 transition hover:bg-ink-100"
                >
                  ✕
                </button>
              </div>
              {rail}
            </aside>
          </div>
        )}

        <main className="min-w-0 flex-1">
          <Outlet />
        </main>
      </div>
    </div>
  );
}