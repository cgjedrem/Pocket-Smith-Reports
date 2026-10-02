import { Eye, EyeOff } from "lucide-react";
import { NavLink, Outlet } from "react-router-dom";

import { ErrorBoundary } from "@/components/ErrorBoundary";
import { toggleAmountsHidden, useAmountsHidden } from "@/lib/privacy-store";
import { cn } from "@/lib/utils";

// App shell — top nav + content outlet.
// No remount key on the outlet: page roots subscribe to the privacy flag
// themselves and re-render in place (FR-008, research.md Decision 3).
export function AppLayout() {
  const amountsHidden = useAmountsHidden();
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
          {/* Privacy toggle — masks every monetary amount app-wide.
              Sits directly after the nav links (NOT ml-auto): the mega
              report's fixed top-right section TOC would overlap it there. */}
          <button
            type="button"
            onClick={toggleAmountsHidden}
            aria-label={amountsHidden ? "Show amounts" : "Hide amounts"}
            aria-pressed={amountsHidden}
            className="rounded-md p-2 text-muted-foreground hover:text-foreground"
          >
            {amountsHidden ? <EyeOff size={18} /> : <Eye size={18} />}
          </button>
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
