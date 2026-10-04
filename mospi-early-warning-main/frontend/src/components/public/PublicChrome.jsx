/**
 * Public site chrome — the MoSPI/Dhrishti government-portal pattern.
 *
 * The authenticated console in `layout/` is a dense operations UI: collapsed
 * sidebar, 64px topbar, no page furniture. The *public* view is a different
 * job — it is a browsable government information page that has to read as
 * official, expose provenance, and work for a citizen on a phone. So it gets
 * its own shell here rather than reusing `AppShell`, which carries the
 * authenticated operations layout.
 *
 * Design language is taken from the live MoSPI PAIMANA portal:
 *   - Montserrat, uppercase section headings and nav labels
 *   - deep navy (#0a154d) navigation bar, white text, inverted dropdowns
 *   - very rounded geometry (30/20/15px cards, fully rounded buttons)
 *   - ministry block + partner logo top-left, utility pills top-right
 *
 * Colours come from `index.css` tokens rather than literals so these still
 * invert with the active theme.
 */

import { Link } from "react-router-dom";
import { Moon, Sun } from "lucide-react";

import { useTheme } from "../../hooks/usePreferences";

const NAVY = "#0a154d";
const NAVY_DEEP = "#060e37";
const ORANGE_FROM = "#ff9e2c";
const ORANGE_TO = "#f47c00";

export const DHRISHTI_LOGO = "/dhrishti-logo.svg";
export const CHAKRA_LOGO = "/chakra.png";
export const PAIMANA_URL = "https://paimana-proj.mospi.gov.in/";
export const MOSPI_URL = "https://www.mospi.gov.in/";
export const DFD_URL = "https://www.dic.gov.in/";

/** Inline wordmark so the mark and the name scale as one unit. */
export function DhrishtiMark({ className = "h-9", title = "Dhrishti", t, onLight = false, onDark = false }) {
  const titleTone = onDark
    ? "text-white"
    : onLight
      ? "text-[#12203A]"
      : "text-[#12203A] dark:text-white";
  const subTone = onDark ? "text-white/60" : onLight ? "text-[#12203A]/60" : "text-fg-3";
  return (
    <span className={`inline-flex items-center gap-2.5 ${className}`}>
      <DhrishtiGlyph className="h-full w-auto shrink-0" title={title} light={onDark} />
      <span className="flex min-w-0 flex-col leading-none">
        <span
          className={`text-[15px] font-extrabold uppercase tracking-tight ${titleTone}`}
        >
          {title}
        </span>
        <span
          className={`mt-0.5 text-[9px] font-semibold uppercase tracking-widest ${subTone}`}
        >
          {t?.("chrome.projectIntelligence") ?? "Project Intelligence"}
        </span>
      </span>
    </span>
  );
}

/** Thin utility strip: skip link, language, accessibility, PAIMANA cross-link. */
export function PublicUtilityBar({ language, setLanguage, languages, t }) {
  return (
    <div className="border-b border-line bg-page text-[11px]">
      <div className="mx-auto flex max-w-[1320px] items-center justify-end gap-1 px-4 py-1.5">
        <a
          href="#main-content"
          className="rounded px-2.5 py-2 font-semibold uppercase tracking-wider text-fg-3 transition-colors hover:text-fg"
        >
          {t("public.skip")}
        </a>
        <span aria-hidden="true" className="text-fg-4">
          |
        </span>
        <label className="flex items-center gap-1.5 rounded px-2.5 py-2 font-semibold uppercase tracking-wider text-fg-3">
          <GlobeGlyph />
          <select
            value={language}
            onChange={(e) => setLanguage(e.target.value)}
            className="bg-transparent text-[11px] font-semibold uppercase tracking-wider text-fg-2 outline-none"
            aria-label={t("language")}
          >
            {languages.map((l) => (
              <option key={l.code} value={l.code}>
                {l.native}
              </option>
            ))}
          </select>
        </label>
        <span aria-hidden="true" className="text-fg-4">
          |
        </span>
        <a
          href={PAIMANA_URL}
          target="_blank"
          rel="noreferrer"
          className="rounded px-2.5 py-2 font-semibold uppercase tracking-wider text-fg-3 transition-colors hover:text-fg"
        >
          PAIMANA
        </a>
      </div>
    </div>
  );
}

/**
 * Theme control.
 *
 * Two variants, one component. The masthead carries the full switch; the nav
 * carries an icon-only button so the setting stays reachable after the
 * masthead scrolls away - the Project Directory and High Value Projects
 * sections sit well below the fold, and a control you have to scroll back up
 * to find is not a control.
 *
 * The knob slides between a sun and a moon rather than the button swapping
 * icons in place, so the change reads as a state transition instead of a
 * flicker. `role="switch"` with `aria-checked` is what announces the current
 * state; the visible text names that state too, so the control is unambiguous
 * to someone who cannot see the knob.
 */
export function ThemeToggle({ t, variant = "switch" }) {
  const { dark, toggleTheme } = useTheme();

  const currentLabel = dark ? t("public.darkMode") : t("public.lightMode");
  const actionLabel = dark ? t("cmd.action.lightTheme") : t("cmd.action.darkTheme");

  if (variant === "icon") {
    return (
      <button
        type="button"
        role="switch"
        aria-checked={dark}
        aria-label={actionLabel}
        title={actionLabel}
        onClick={toggleTheme}
        className="flex h-9 w-9 shrink-0 items-center justify-center rounded-full border border-white/25 text-white/85 transition-colors hover:border-white/50 hover:text-white focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-white/70"
      >
        {dark ? <Sun size={15} /> : <Moon size={15} />}
      </button>
    );
  }

  return (
    <button
      type="button"
      role="switch"
      aria-checked={dark}
      title={actionLabel}
      onClick={toggleTheme}
      className="group flex h-9 shrink-0 items-center gap-2 rounded-full border border-line-strong bg-page p-1 pl-1 pr-4 transition hover:border-brand hover:shadow-sm focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand"
    >
      <span className="relative flex h-7 w-[68px] items-center">
        <span
          aria-hidden="true"
          className={`absolute h-7 w-7 rounded-full bg-brand shadow-sm transition-transform duration-300 ease-out ${
            dark ? "translate-x-10" : "translate-x-0"
          }`}
        />
        <Sun
          size={14}
          aria-hidden="true"
          className={`absolute left-1.5 z-10 transition-colors duration-200 ${
            dark ? "text-fg-4" : "text-white"
          }`}
        />
        <Moon
          size={14}
          aria-hidden="true"
          className={`absolute right-1.5 z-10 transition-colors duration-200 ${
            dark ? "text-white" : "text-fg-4"
          }`}
        />
      </span>

      <span className="text-[11px] font-bold uppercase tracking-wider text-fg-2 transition-colors group-hover:text-fg">
        {currentLabel}
      </span>
    </button>
  );
}

/** White masthead: ministry block + partner logo on the left, pills on the right. */
export function PublicMasthead({ loggedInUser, onLogin, onLogout, onOpenDirectory, t }) {
  return (
    <header className="border-b border-line bg-raised">
      <div className="mx-auto flex max-w-[1320px] flex-wrap items-center justify-between gap-4 px-4 py-4">
        <div className="flex min-w-0 items-center gap-5">
          <a
            href={MOSPI_URL}
            target="_blank"
            rel="noreferrer"
            className="flex min-w-0 items-center gap-3"
          >
            {/* Navy reads correctly on the light masthead. In dark mode it would
                disappear, so it collapses to black and inverts to white --
                brightness(0) first, because inverting navy directly would
                yield a washed pink rather than a clean white. */}
            <EmblemGlyph className="h-11 w-11 shrink-0 dark:[filter:brightness(0)_invert(1)]" t={t} />
            <span className="min-w-0">
              <span className="block text-[10px] font-bold uppercase leading-tight tracking-widest text-fg-3">
                {t("public.ministryBlock")}
              </span>
              <span className="mt-0.5 block text-[9px] font-semibold uppercase tracking-wider text-fg-4">
                {t("public.govtOfIndia")}
              </span>
            </span>
          </a>
          <a
            href={DFD_URL}
            target="_blank"
            rel="noreferrer"
            title={t("chrome.dfdName")}
            className="hidden shrink-0 items-center gap-2 border-l border-line pl-5 lg:flex"
          >
            <DfdGlyph className="h-8 w-8" t={t} />
            <span className="text-[9px] font-bold uppercase leading-tight tracking-widest text-fg-3">
              {t("chrome.dfdName")}
            </span>
          </a>
        </div>

        <div className="flex flex-wrap items-center gap-2.5">
          <ThemeToggle t={t} />

          <button
            type="button"
            onClick={onOpenDirectory}
            className="rounded-full px-5 py-2.5 text-[11px] font-bold uppercase tracking-wider text-white shadow-[0_4px_10px_rgba(244,124,0,0.35)] transition-all hover:-translate-y-px hover:shadow-[0_6px_14px_rgba(244,124,0,0.45)]"
            style={{ backgroundImage: `linear-gradient(180deg, ${ORANGE_FROM}, ${ORANGE_TO})` }}
          >
            {t("public.browse")}
          </button>

          {loggedInUser ? (
            <>
              {loggedInUser.role !== "viewer" && (
                <Link
                  to="/workspace"
                  className="rounded-full px-4 py-2.5 text-[11px] font-bold uppercase tracking-wider text-white transition-colors hover:opacity-90"
                  style={{ backgroundColor: NAVY }}
                >
                  Workspace →
                </Link>
              )}
              <span className="inline-flex items-center gap-2 rounded-full border border-line-strong bg-page px-4 py-2.5 text-[11px] font-bold uppercase tracking-wider text-fg-2">
                {loggedInUser.name || loggedInUser.email}
              </span>
              <button
                type="button"
                onClick={onLogout}
                className="rounded-full px-5 py-2.5 text-[11px] font-bold uppercase tracking-wider text-white transition-colors hover:opacity-90"
                style={{ backgroundColor: NAVY_DEEP }}
              >
                {t("public.signOut")}
              </button>
            </>
          ) : (
            <button
              type="button"
              onClick={onLogin}
              className="rounded px-2 py-1 font-semibold uppercase tracking-wider text-fg-3 transition-colors hover:text-fg-2"
            >
              {t("public.login")}
            </button>
          )}
        </div>
      </div>
    </header>
  );
}

/**
 * Deep-navy nav bar.
 *
 * Items come in three kinds. An item with a `#href` is a native anchor that
 * scrolls to a section on this page and updates the URL hash; an item with a
 * `/href` is a real route, rendered as a react-router link so a public visitor
 * can reach the read-only feature screens and share the URL; an item with
 * neither is a plain button for page-local actions. All of them are now links,
 * so hover reveals a target and the destination is shareable.
 */
export function PublicNav({ items, activeId, onSelect, t }) {
  return (
    <nav
      className="sticky top-0 z-30 shadow-sm"
      style={{ backgroundColor: NAVY }}
      aria-label={t("chrome.navPrimary")}
    >
      {/* The links scroll on a phone, so the theme toggle is a sibling of that
          scroller rather than a child of it: as a child it would scroll out of
          view with the links and defeat the point of putting it here. */}
      <div className="mx-auto flex max-w-[1320px] items-center gap-3 px-4">
        <div className="flex min-w-0 flex-1 items-center gap-1 overflow-x-auto">
          {items.map((item) => {
          const active = item.id === activeId;
          const style = {
            color: "#fff",
            borderBottom: `3px solid ${active ? ORANGE_TO : "transparent"}`,
          };
          const className =
            "shrink-0 px-4 py-3.5 text-[12px] font-bold uppercase tracking-wider transition-colors";

          if (item.href) {
            if (item.href.startsWith("#")) {
              return (
                <a
                  key={item.id}
                  href={item.href}
                  onClick={(e) => {
                    e.preventDefault();
                    onSelect(item);
                  }}
                  aria-current={active ? "true" : undefined}
                  className={className}
                  style={style}
                >
                  {item.label}
                </a>
              );
            }

            return (
              <Link
                key={item.id}
                to={item.href}
                aria-current={active ? "page" : undefined}
                className={className}
                style={style}
              >
                {item.label}
              </Link>
            );
          }

          return (
            <button
              key={item.id}
              type="button"
              onClick={() => onSelect(item)}
              aria-current={active ? "true" : undefined}
              className={className}
              style={style}
            >
              {item.label}
            </button>
          );
        })}
        </div>
      </div>
    </nav>
  );
}

export function PublicFooter({ t }) {
  // Anchor links stay on this page; the rest are routes into the read-only
  // feature screens, so the footer is a second way into every feature.
  const quickLinks = [
    [t("public.home"), "#top"],
    [t("public.highValue"), "#high-value"],
    [t("public.directory"), "#directory"],
    [t("public.dashboard"), "/dashboard"],
    [t("public.riskAnalytics"), "/risk"],
    [t("public.reports"), "/reports"],
    [t("public.knowledgeGraph"), "/graph"],
    [t("public.reportIssue"), "/report-an-issue"],
  ];

  const isRoute = (href) => href.startsWith("/");

  return (
    <footer style={{ backgroundColor: NAVY_DEEP }} className="mt-14 text-white/85">
      <div className="mx-auto max-w-[1320px] px-4 py-10">
        <div className="grid gap-8 md:grid-cols-3">
          <div>
            <div className="flex items-center gap-3">
              {/* Footer sits on deep navy in both themes, so the chakra is
                  forced white unconditionally rather than only in dark mode. */}
              <EmblemGlyph className="h-10 w-10" onDark t={t} />
              <span className="text-[10px] font-bold uppercase leading-tight tracking-widest">
                {t("public.ministryBlock")}
              </span>
            </div>
            <p className="mt-4 text-[11px] leading-relaxed text-white/60">
              {t("chrome.footerBlurb")}
            </p>
          </div>

          <div>
            <h4 className="text-[12px] font-bold uppercase tracking-widest text-white">
              {t("public.getInTouch")}
            </h4>
            <address className="mt-3 space-y-1 text-[11px] not-italic leading-relaxed text-white/60">
              <p>
                Khurshid Lal Bhawan, Janpath, New Delhi – 110001, India
              </p>
              <p>
                <a href="tel:01123455604" className="hover:text-white">
                  011-23455604
                </a>
              </p>
              <p>
                <a href="mailto:dir-ipmd@mospi.gov.in" className="hover:text-white">
                  dir-ipmd[at]mospi[dot]gov[dot]in
                </a>
              </p>
            </address>
          </div>

          <div>
            <h4 className="text-[12px] font-bold uppercase tracking-widest text-white">
              {t("public.quickLinks")}
            </h4>
            <ul className="mt-3 space-y-1.5 text-[11px]">
              {quickLinks.map(([label, href]) => (
                <li key={href}>
                  {isRoute(href) ? (
                    <Link
                      to={href}
                      className="text-white/60 transition-colors hover:text-white"
                    >
                      {label}
                    </Link>
                  ) : (
                    <a href={href} className="text-white/60 transition-colors hover:text-white">
                      {label}
                    </a>
                  )}
                </li>
              ))}
            </ul>
          </div>
        </div>
      </div>

      <div
        className="border-t border-white/10 py-4 text-center text-[10px] text-white/50"
        style={{ backgroundColor: NAVY }}
      >
        {t("chrome.footerLegal")}
      </div>
    </footer>
  );
}

/* ---------------------------------------------------------------- glyphs */

/** Shield mark on its own, for tight slots like the collapsed sidebar rail.
 *  `light` renders the shield in white for deep-navy surfaces. */
export function DhrishtiGlyph({ className = "h-7 w-7", title = "Dhrishti", light = false }) {
  const shield = light ? "#FFFFFF" : "#12203A";
  const line = light ? "#0A1C3F" : "#FFFFFF";
  return (
    <svg
      viewBox="0 0 100 124"
      className={className}
      role="img"
      aria-label={title}
    >
      <path
        d="M50 43 L150 43 L150 105 Q150 153 100 167 Q50 153 50 105 Z"
        transform="translate(-50 0)"
        fill={shield}
      />
      <path
        d="M70 130 L92 108 L112 118 L132 78"
        transform="translate(-50 0)"
        fill="none"
        stroke={line}
        strokeWidth="7"
        strokeLinecap="round"
        strokeLinejoin="round"
      />
      <circle cx="82" cy="78" r="7" fill="#0F766E" />
    </svg>
  );
}

function GlobeGlyph() {
  return (
    <svg viewBox="0 0 24 24" className="h-3.5 w-3.5" fill="none" stroke="currentColor" strokeWidth="2" aria-hidden="true">
      <circle cx="12" cy="12" r="9" />
      <path d="M3 12h18M12 3c2.5 3 2.5 15 0 18M12 3c-2.5 3-2.5 15 0 18" />
    </svg>
  );
}

/**
 * Ashoka Chakra: 24 spokes on a 15-degree pitch, radiating from a central hub
 * inside a double rim, each spoke a tapered wedge.
 *
 * This replaces the previous mark, which was a five-pointed star over four
 * bars. That was a loose "Ashoka-inspired" placeholder rather than the Chakra
 * itself, and the difference matters: the Chakra is a 24-spoke wheel, and the
 * earlier shape borrowed only the general idea of a national roundel.
 *
 * Rendered from `chakra.png` (1024x1024, transparent) rather than inlined SVG,
 * so the exact geometry is verifiable in the asset itself and can be swapped
 * for an official file without touching this component. The PNG is generated by
 * `backend/scripts/generate_chakra.py`; the same geometry is also inlined in
 * `favicon.svg`. If you replace the PNG, regenerate or hand-pick the favicon to
 * match, or the tab icon and the masthead will disagree.
 *
 * The national emblem proper (the Lion Capital) is a separate, legally
 * protected mark and is deliberately not attempted here. The Chakra is the
 * device used on the national flag. Any real deployment should still confirm
 * usage rules with MoSPI, since official emblems carry restrictions on
 * modification and on implying government endorsement.
 *
 * `onDark` is used for the footer, which sits on deep navy. A fixed navy PNG
 * would vanish there, and a CSS invert is avoided because inverting navy yields
 * a washed pink rather than a clean white.
 */
function EmblemGlyph({ className = "h-10 w-10", onDark = false, t }) {
  return (
    <img
      src={CHAKRA_LOGO}
      alt={t?.("chrome.chakraAlt") ?? "Ashoka Chakra, emblem of India"}
      width={1024}
      height={1024}
      className={`${className} object-contain ${
        onDark ? "opacity-95" : ""
      }`}
      style={onDark ? { filter: "brightness(0) invert(1)" } : undefined}
    />
  );
}

function DfdGlyph({ className = "h-8 w-8", t }) {
  return (
    <svg viewBox="0 0 32 32" className={className} role="img" aria-label={t?.("chrome.dfdName") ?? "Data for Development"}>
      <circle cx="16" cy="16" r="15" fill="#0e7c86" opacity="0.12" />
      <path
        d="M6 24 L13 14 L19 19 L26 8"
        fill="none"
        stroke="#0e7c86"
        strokeWidth="2.4"
        strokeLinecap="round"
        strokeLinejoin="round"
      />
      <circle cx="26" cy="8" r="2.6" fill="#0e7c86" />
    </svg>
  );
}
