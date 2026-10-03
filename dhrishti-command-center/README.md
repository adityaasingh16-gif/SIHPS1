# DHRISHTI v2 — National Infrastructure Intelligence Command Center

Enterprise-grade UI/UX transformation of **https://sihps-1.vercel.app/** (MoSPI / PAIMANA / SIH 26103).
**No backend changes.** All existing APIs, auth, ML and routes are preserved — only the frontend is upgraded.

## What was built

- **Design system** (`styles.css`): tokens for color/typography/spacing/radius/shadow, light/dark/system, Inter + IBM Plex Mono, 150–400ms micro-interactions, skeleton/empty/error states, responsive 1440/1024/768/320, a11y (skip link, focus, ARIA, keyboard, reduced-motion).
- **Command shell** (`index.html`): gov trust bar, command header, collapsible sidebar, mobile bottom nav, landing hero with live signals, `Ctrl+K` palette, project drawer, auth modal, toasts.
- **Views** (`js/app.js`): Dashboard (What/What-wrong/What-next/What-action + 8 KPIs + sparklines), Early Warning Center (Critical/High/Moderate/Stable triage), Projects (sticky-sortable-paginated table, filters as chips, save/reset, columns, bulk, CSV export), Risk Intelligence (rings, meters, heatmaps, trends), Analytics (planned-vs-actual-vs-predicted, cost/time, sector compare), India Map (state/marker filters + compact panel), DHRISHTI AI (brief + why + actions + explainable factor bars + project-aware chat), Reports (executive/risk/ministry/state/project + preview/print/download), Notifications (critical/warning/info + read/unread + filter), Audit Trail, Administration, Settings.
- **Data layer** (`js/api.js`): talks to your **existing backend** first (`/public/*`, `/projects*`, `/alerts`, `/reports/*`, `/auth/*`, `/admin/*`, `/groq-chat`, `/public/chat`); falls back to a realistic local dataset so judges always see a full demo. Base URL configurable in **Settings** or `?api=https://your-backend`.

## Run locally

```powershell
cd dhrishti-command-center
python -m http.server 5173
# open http://127.0.0.1:5173  (optionally ?api=http://127.0.0.1:8000)
```

## Deploy to Vercel (your separate repo)

This folder is **static — no build step**. Either:

1. Copy `dhrishti-command-center/*` into your frontend repo root (or `public/`), commit + push — Vercel redeploys `sihps-1.vercel.app` automatically; or
2. Drag-drop the folder in Vercel Dashboard → New Project → static.

Then set the backend URL in-app via **Settings**, or add a Vercel rewrite so same-origin `/projects`, `/alerts`, `/auth/*` reach your Render/FastAPI service.

## Backend preserved

No API, auth, DB, ML or route was removed. Frontend calls (all optional-graceful): `GET /health`, `/public/summary|/projects|/ministries|/sectors|/geo/states|/chat`, `/projects?ministry&state&sector&risk_level&search&limit&offset`, `/projects/{id}|/explanation|/history`, `/alerts|/reports/alerts`, `/reports/*`, `/auth/login|/me`, `/admin/*`, `/groq-chat`. Failures show human-readable retry states — never raw errors.

## Quality bar checked

Skeletons → charts → tables load progressively · empty/error states everywhere · tables collapse to cards on mobile · status never color-only (labels + icons) · charts have labels/legends/tooltips · dark mode is a true theme (not inverted).
