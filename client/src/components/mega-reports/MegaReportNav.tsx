// MegaReportNav — sticky right-side TOC for the mega report.
// Highlights the entry currently in view via IntersectionObserver.
// Clicking jumps to that entry with smooth scroll.

import { useEffect, useMemo, useState } from "react";
import { cn } from "@/lib/utils";
import type { MegaReportResponse } from "@/types/mega_report";
import { buildNavItems, type NavItem } from "@/components/mega-reports/buildNavItems";
import styles from "./MegaReportNav.module.css";

interface MegaReportNavProps {
  report: MegaReportResponse;
}

export function MegaReportNav({ report }: MegaReportNavProps) {
  // Floating panel — start visible on desktop; default hidden on small
  // screens where it would overlap content. Persisted in localStorage.
  const [isOpen, setIsOpen] = useState<boolean>(() => {
    if (typeof window === "undefined") return true;
    const stored = window.localStorage.getItem("mega-nav-open");
    if (stored !== null) return stored === "1";
    return window.innerWidth > 900;
  });
  const [activeId, setActiveId] = useState<string>("kpi");

  // Persist toggle state.
  useEffect(() => {
    if (typeof window === "undefined") return;
    window.localStorage.setItem("mega-nav-open", isOpen ? "1" : "0");
  }, [isOpen]);

  // Build full nav structure — shared with export dialog.
  const navItems: NavItem[] = useMemo(() => buildNavItems(report), [report]);

  const flatIds = useMemo(
    () =>
      navItems.flatMap((n) => [n.id, ...(n.children ?? []).map((c) => c.id)]),
    [navItems],
  );

  useEffect(() => {
    if (typeof window === "undefined") return;
    const headings: HTMLElement[] = flatIds.flatMap((id) =>
      Array.from(document.querySelectorAll<HTMLElement>(`#${CSS.escape(id)}`)),
    );
    if (headings.length === 0) return;

    const observer = new IntersectionObserver(
      (entries) => {
        const visible = entries
          .filter((e) => e.isIntersecting)
          .sort((a, b) => a.boundingClientRect.top - b.boundingClientRect.top);
        if (visible.length > 0) {
          setActiveId(visible[0].target.id);
        }
      },
      {
        rootMargin: "-15% 0px -70% 0px",
        threshold: 0,
      },
    );

    headings.forEach((h) => observer.observe(h));
    return () => observer.disconnect();
  }, [flatIds]);

  const scrollTo = (id: string) => (e: React.MouseEvent) => {
    e.preventDefault();
    const el = document.getElementById(id);
    if (el) {
      el.scrollIntoView({ behavior: "smooth", block: "start" });
      setActiveId(id);
    }
  };

  return (
    <>
      <button
        type="button"
        className={cn(
          styles.toggleButton,
          isOpen && styles.toggleButtonAnchored,
        )}
        onClick={() => setIsOpen((v) => !v)}
        aria-label={isOpen ? "Hide sections navigation" : "Show sections navigation"}
        aria-expanded={isOpen}
        aria-controls="mega-nav-panel"
      >
        <span
          className={cn(styles.toggleIcon, isOpen && styles.toggleIconOpen)}
          aria-hidden="true"
        />
      </button>
      <div
        id="mega-nav-panel"
        className={cn(
          styles.wrapper,
          isOpen ? styles.wrapperVisible : styles.wrapperHidden,
        )}
        aria-hidden={!isOpen}
      >
        <nav aria-label="Mega report sections" className={styles.nav}>
          <div className={styles.title}>Sections</div>
          <ul className={styles.list}>
            {navItems.map((item) => {
              const isActive = activeId === item.id;
              const hasChildren = !!item.children?.length;
              const childActive = hasChildren
                ? item.children!.some((c) => c.id === activeId)
                : false;
              return (
                <li key={item.id}>
                  <a
                    href={`#${item.id}`}
                    onClick={scrollTo(item.id)}
                    className={cn(
                      styles.link,
                      (isActive || childActive) && styles.active,
                    )}
                    aria-current={isActive ? "true" : undefined}
                  >
                    <span className={styles.number}>{item.number}</span>
                    <span className={styles.label}>{item.title}</span>
                  </a>
                  {hasChildren && (
                    <ul className={styles.sublist}>
                      {item.children!.map((child) => {
                        const isChildActive = activeId === child.id;
                        return (
                          <li key={child.id}>
                            <a
                              href={`#${child.id}`}
                              onClick={scrollTo(child.id)}
                              className={cn(
                                styles.sublink,
                                isChildActive && styles.active,
                              )}
                              aria-current={isChildActive ? "true" : undefined}
                            >
                              <span className={styles.label}>{child.title}</span>
                            </a>
                          </li>
                        );
                      })}
                    </ul>
                  )}
                </li>
              );
            })}
          </ul>
        </nav>
      </div>
    </>
  );
}
