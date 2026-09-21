import { NavLink, Outlet } from "react-router-dom";

import { ErrorBoundary } from "@/components/ErrorBoundary";
import { cn } from "@/lib/utils";

// App shell — top nav + content outlet.
export function AppLayout() {
  return (
    <div className="flex min-h-screen flex-col">
      <header className="border-b-2 border-accent bg-card px-6">
        <nav className="flex h-14 items-center gap-6">
          <NavLink
            to="/sync"
            className={({ isActive }) =>
              cn(
                "border-b-2 border-transparent px-2 py-1 text-base no-underline",
                isActive
                  ? "border-accent text-accent"
                  : "text-muted-foreground hover:text-foreground",
              )
            }
          >
            Sync
          </NavLink>
          <NavLink
            to="/reports"
            className={({ isActive }) =>
              cn(
                "border-b-2 border-transparent px-2 py-1 text-base no-underline",
                isActive
                  ? "border-accent text-accent"
                  : "text-muted-foreground hover:text-foreground",
              )
            }
          >
            Monthly Reports
          </NavLink>
          <NavLink
            to="/mega-reports"
            className={({ isActive }) =>
              cn(
                "border-b-2 border-transparent px-2 py-1 text-base no-underline",
                isActive
                  ? "border-accent text-accent"
                  : "text-muted-foreground hover:text-foreground",
              )
            }
          >
            Mega Reports
          </NavLink>
          <NavLink
            to="/bills"
            className={({ isActive }) =>
              cn(
                "border-b-2 border-transparent px-2 py-1 text-base no-underline",
                isActive
                  ? "border-accent text-accent"
                  : "text-muted-foreground hover:text-foreground",
              )
            }
          >
            Bills
          </NavLink>
          <NavLink
            to="/settings"
            className={({ isActive }) =>
              cn(
                "border-b-2 border-transparent px-2 py-1 text-base no-underline",
                isActive
                  ? "border-accent text-accent"
                  : "text-muted-foreground hover:text-foreground",
              )
            }
          >
            Settings
          </NavLink>
          <NavLink
            to="/docs"
            className={({ isActive }) =>
              cn(
                "border-b-2 border-transparent px-2 py-1 text-base no-underline",
                isActive
                  ? "border-accent text-accent"
                  : "text-muted-foreground hover:text-foreground",
              )
            }
          >
            Docs
          </NavLink>
        </nav>
      </header>
      <main className="mx-auto w-full max-w-[1200px] flex-1 p-6">
        <ErrorBoundary>
          <Outlet />
        </ErrorBoundary>
      </main>
    </div>
  );
}