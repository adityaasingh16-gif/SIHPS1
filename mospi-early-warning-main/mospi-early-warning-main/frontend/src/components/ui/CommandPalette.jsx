export { CommandPalette };

import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import {
  Activity,
  Bell,
  Brain,
  Building2,
  CircleDollarSign,
  Clock3,
  Command as CommandIcon,
  CornerDownLeft,
  Download,
  FileText,
  Gauge,
  Home,
  LogOut,
  Map as MapIcon,
  Moon,
  Network,
  Search,
  ShieldCheck,
  Sun,
  Target,
} from "lucide-react";

import { useT } from "../../hooks/useT";

/**
 * Command palette (Cmd/Ctrl+K).
 *
 * The app has twelve destinations plus a global search in the top bar. Once
 * the sidebar is dense, clicking through it is the slowest interaction in the
 * product, so this puts every destination, every project, and the handful of
 * global actions one keystroke away.
 *
 * Accessibility notes, because a palette is unusable without them:
 *  - labelled as a modal dialog with aria-modal, and focus moves into the
 *    input on open and is restored to the trigger on close;
 *  - the active row is tracked with aria-activedescendant, so the input keeps
 *    focus and the arrow keys drive a virtual cursor rather than moving real
 *    DOM focus;
 *  - Tab is trapped inside the dialog;
 *  - the whole thing closes on Escape, and the listener is inert when closed.
 */

/** `labelKey` is resolved through the translator at render time. */
const PAGES = [
  { id: "dashboard", labelKey: "cmd.page.dashboard", group: "goTo", icon: Home },
  { id: "warnings", labelKey: "cmd.page.warnings", group: "goTo", icon: Bell },
  { id: "risk", labelKey: "cmd.page.risk", group: "goTo", icon: Gauge },
  { id: "cost", labelKey: "cmd.page.cost", group: "goTo", icon: CircleDollarSign },
  { id: "time", labelKey: "cmd.page.time", group: "goTo", icon: Clock3 },
  { id: "projects", labelKey: "cmd.page.projects", group: "goTo", icon: Target },
  { id: "states", labelKey: "cmd.page.states", group: "goTo", icon: MapIcon },
  { id: "ministries", labelKey: "cmd.page.ministries", group: "goTo", icon: Building2 },
  { id: "graph", labelKey: "cmd.page.graph", group: "goTo", icon: Network },
  { id: "reports", labelKey: "cmd.page.reports", group: "goTo", icon: FileText },
  { id: "workspace", labelKey: "cmd.page.workspace", group: "goTo", icon: ShieldCheck },
];

/** Subsequence match, so "mlstd" finds "ML Studio". */
function fuzzy(haystack, needle) {
  if (!needle) return true;
  const h = haystack.toLowerCase();
  const n = needle.toLowerCase();
  let i = 0;
  for (const ch of n) {
    if (ch === " ") continue;
    i = h.indexOf(ch, i);
    if (i === -1) return false;
    i += 1;
  }
  return true;
}

function CommandPalette({
  open,
  onOpen,
  onClose,
  projects = [],
  onNavigate,
  onSelectProject,
  onToggleTheme,
  dark,
  onExport,
  onLogout,
}) {
  const t = useT();
  const [query, setQuery] = useState("");
  const [cursor, setCursor] = useState(0);
  const inputRef = useRef(null);
  const listRef = useRef(null);
  const restoreRef = useRef(null);

  const close = useCallback(() => {
    setQuery("");
    setCursor(0);
    onClose();
  }, [onClose]);

  // Open: remember what had focus, then move focus into the input.
  useEffect(() => {
    if (!open) return undefined;
    restoreRef.current = document.activeElement;
    const t = setTimeout(() => inputRef.current?.focus(), 0);
    return () => {
      clearTimeout(t);
      const el = restoreRef.current;
      if (el && typeof el.focus === "function") el.focus();
    };
  }, [open]);

  // Cmd/Ctrl+K toggles the palette from anywhere in the app.
  useEffect(() => {
    if (typeof onOpen !== "function") return undefined;
    const onKey = (e) => {
      if ((e.metaKey || e.ctrlKey) && e.key.toLowerCase() === "k") {
        e.preventDefault();
        if (open) close();
        else onOpen();
      }
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [open, close, onOpen]);

  const actions = useMemo(
    () => [
      {
        id: "__theme",
        label: dark ? t("cmd.action.lightTheme") : t("cmd.action.darkTheme"),
        group: "actions",
        icon: dark ? Sun : Moon,
        run: onToggleTheme,
      },
      ...(onExport
        ? [
            {
              id: "__export",
              label: t("cmd.action.exportCsv"),
              group: "actions",
              icon: Download,
              run: onExport,
            },
          ]
        : []),
      ...(onLogout
        ? [
            {
              id: "__logout",
              label: t("cmd.action.signOut"),
              group: "actions",
              icon: LogOut,
              run: onLogout,
            },
          ]
        : []),
    ],
    [dark, onToggleTheme, onExport, onLogout, t]
  );

  const results = useMemo(() => {
    const q = query.trim();

    // Pages are matched on their translated label and on the route id, so the
    // palette stays reachable by typing a stable identifier in either language.
    const pages = PAGES.filter(
      (p) => fuzzy(t(p.labelKey), q) || fuzzy(p.id, q)
    ).map((p) => ({
      ...p,
      label: t(p.labelKey),
      group: t("cmd.group.goTo"),
      kind: "page",
    }));

    // Project results are capped: rendering 2,000 rows into the DOM would make
    // the arrow-key cursor unusable. The cap is stated in the footer.
    const PROJECT_CAP = 50;
    const matches = projects
      .filter((p) => {
        const name = p.name || p.project_name || "";
        const id = String(p.id ?? p.project_id ?? "");
        return fuzzy(name, q) || (q.length > 1 && fuzzy(id, q));
      })
      .slice(0, PROJECT_CAP)
      .map((p) => ({
        id: `p:${p.id ?? p.project_id}`,
        label: p.name || p.project_name || t("cmd.unnamedProject"),
        sub: p.ministry || p.state || p.sector || undefined,
        group: t("cmd.group.projects"),
        icon: Activity,
        kind: "project",
        payload: p,
      }));

    const acts = q
      ? actions.filter((a) => fuzzy(a.label, q))
      : actions;

    return [...pages, ...matches, ...acts];
  }, [query, projects, actions, t]);

  const grouped = useMemo(() => {
    const map = new Map();
    for (const r of results) {
      if (!map.has(r.group)) map.set(r.group, []);
      map.get(r.group).push(r);
    }
    return [...map.entries()];
  }, [results]);

  // Clamp during render rather than in an effect. The result set can shrink
  // under the cursor (a late projects fetch, or a query that narrows), and
  // syncing that with setState-in-effect causes a second render pass.
  const safeCursor = results.length ? Math.min(cursor, results.length - 1) : 0;

  const runAt = useCallback(
    (item) => {
      if (!item) return;
      if (item.kind === "page") {
        onNavigate?.(item.id);
      } else if (item.kind === "project") {
        onSelectProject?.(item.payload);
      } else if (typeof item.run === "function") {
        item.run();
      }
      close();
    },
    [onNavigate, onSelectProject, close]
  );

  const onKeyDown = (e) => {
    if (e.key === "Escape") {
      e.preventDefault();
      close();
      return;
    }
    if (e.key === "ArrowDown") {
      e.preventDefault();
      setCursor((c) => (results.length ? (c + 1) % results.length : 0));
      return;
    }
    if (e.key === "ArrowUp") {
      e.preventDefault();
      setCursor((c) =>
        results.length ? (c - 1 + results.length) % results.length : 0
      );
      return;
    }
    if (e.key === "Home") {
      e.preventDefault();
      setCursor(0);
      return;
    }
    if (e.key === "End") {
      e.preventDefault();
      setCursor(Math.max(0, results.length - 1));
      return;
    }
    if (e.key === "Enter") {
      e.preventDefault();
      runAt(results[safeCursor]);
      return;
    }
    if (e.key === "Tab") {
      // Trap: the only focusable things are the input and the backdrop, and
      // Tab should never escape a modal dialog.
      e.preventDefault();
      inputRef.current?.focus();
    }
  };

  if (!open) return null;

  let flatIndex = -1;

  return (
    <div
      className="fixed inset-0 z-[100] flex items-start justify-center px-4 pt-[12vh]"
      role="presentation"
    >
      <div
        className="absolute inset-0 bg-scrim/50 backdrop-blur-sm"
        onClick={close}
        aria-hidden="true"
      />

      <div
        role="dialog"
        aria-modal="true"
        aria-label={t("cmd.title")}
        onKeyDown={onKeyDown}
        className="relative w-full max-w-xl overflow-hidden rounded-2xl border border-line bg-overlay shadow-pop"
      >
        <div className="flex items-center gap-3 border-b border-line px-4">
          <Search size={17} className="shrink-0 text-fg-3" aria-hidden="true" />
          <input
            ref={inputRef}
            value={query}
            onChange={(e) => {
              setQuery(e.target.value);
              setCursor(0);
            }}
            placeholder={t("cmd.searchPlaceholder")}
            aria-label={t("cmd.searchLabel")}
            aria-controls="command-palette-list"
            aria-activedescendant={
              results[safeCursor] ? `cmd-${results[safeCursor].id}` : undefined
            }
            autoComplete="off"
            spellCheck={false}
            className="h-14 flex-1 bg-transparent text-sm text-fg outline-none placeholder:text-fg-4"
          />
          <kbd className="hidden shrink-0 rounded border border-line bg-sunken px-1.5 py-0.5 text-[10px] font-semibold text-fg-3 sm:block">
            {t("cmd.esc")}
          </kbd>
        </div>

        <div
          ref={listRef}
          id="command-palette-list"
          role="listbox"
          aria-label={t("cmd.results")}
          className="max-h-[52vh] overflow-y-auto overscroll-contain p-2"
        >
          {results.length === 0 ? (
            <p className="px-3 py-10 text-center text-sm text-fg-3">
              {t("cmd.nothingMatches")} {" "}
              <span className="font-semibold text-fg">“{query}”</span>
            </p>
          ) : (
            grouped.map(([group, items]) => (
              <div key={group} className="mb-1 last:mb-0">
                <p className="px-3 pb-1 pt-2 text-[10px] font-bold uppercase tracking-widest text-fg-4">
                  {group}
                </p>

                {items.map((item) => {
                  flatIndex += 1;
                  const active = flatIndex === safeCursor;
                  const Icon = item.icon;

                  return (
                    <div
                      key={item.id}
                      id={`cmd-${item.id}`}
                      role="option"
                      aria-selected={active}
                      // pointerdown rather than click so the blur that follows
                      // a mouse press does not close the palette first.
                      onMouseDown={(e) => {
                        e.preventDefault();
                        runAt(item);
                      }}
                      onMouseEnter={() => setCursor(flatIndex)}
                      className={`flex cursor-pointer items-center gap-3 rounded-lg px-3 py-2.5 text-sm transition ${
                        active
                          ? "bg-brand-subtle text-brand-subtle-fg"
                          : "text-fg-2"
                      }`}
                    >
                      {Icon && (
                        <Icon size={16} className="shrink-0" aria-hidden="true" />
                      )}
                      <span className="min-w-0 flex-1 truncate">
                        {item.label}
                      </span>
                      {item.sub && (
                        <span className="shrink-0 truncate text-[11px] text-fg-4">
                          {item.sub}
                        </span>
                      )}
                      {active && (
                        <CornerDownLeft
                          size={13}
                          className="shrink-0 opacity-70"
                          aria-hidden="true"
                        />
                      )}
                    </div>
                  );
                })}
              </div>
            ))
          )}
        </div>

        <div className="flex items-center gap-4 border-t border-line bg-sunken/60 px-4 py-2 text-[10px] text-fg-3">
          <span className="inline-flex items-center gap-1.5">
            <kbd className="rounded border border-line bg-raised px-1">↑</kbd>
            <kbd className="rounded border border-line bg-raised px-1">↓</kbd>
            {t("cmd.navigate")}
          </span>
          <span className="inline-flex items-center gap-1.5">
            <kbd className="rounded border border-line bg-raised px-1">↵</kbd>
            {t("cmd.select")}
          </span>
          <span className="ml-auto inline-flex items-center gap-1.5">
            <CommandIcon size={11} aria-hidden="true" />
            {t("cmd.openHint")}
          </span>
        </div>
      </div>
    </div>
  );
}
