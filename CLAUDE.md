# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this is

oim-shop is an open-source reference product for OIM7510 and OIM6301: Northwind Traders' internal sales system, built as a ladder of three tagged versions (`v1`, `v2`, `v3`). Requirements are in `docs/prd.md`; read it before changing scope, and ask Zhi rather than editing a requirement.

This repository is public and mirrored to two orgs (`OIM7510/oim-shop`, `OIM6301/oim-shop`). Nothing course-specific goes in it: no roster, tokens, assignment answers, course instructions, or server hostnames, IPs and memory figures. Server facts live outside the repo.

## The version ladder

The git history between tags is teaching material. Each tag must be a state where every test passes and the app runs on its own, and a later version's files do not appear before its tag (no `api/` or `web/` in `v1`).

- **v1**: `v1/index.html` alone, no build step, calling `https://oim.zhili.dev/shop` (oim-api) directly from the browser.
- **v2**: `api/` (FastAPI + SQLite) serves the data from its own database, `web/` is the interface. Adds dashboard, customers, orders, employees, and a sync from oim-api.
- **v3**: GitHub sign-in and order entry, with the business rules in PRD §6.

Before each tag, Zhi reviews screenshots of every page in light and dark mode.

## Architecture (v2 onward)

- **One origin.** `/api/*` is FastAPI; everything else is the built web app. No CORS.
- **api/**: raw parameterised SQL, no ORM; schema changes are numbered `.sql` migrations. Python `>=3.14,<3.15`, run through uv with `--python 3.14`.
- **Contract.** `web/` generates its types from FastAPI's OpenAPI schema with `openapi-typescript`, so an API change that the frontend does not follow fails the build.
- **Data.** `data/seed/` holds the Northwind seed (jpwhite3/northwind-SQLite3, MIT) and its licence, so the app runs without oim-api. oim-api serves the same orders on a clock shifted forward so orders keep arriving until 2027-06-30. `oim-shop sync` pulls new orders incrementally; `oim-shop reset` returns entered orders and stock to the seed. Both are CLI commands run by systemd timers, not an in-app scheduler.
- **Deployment.** The image is built in GitHub Actions for `linux/amd64`, pushed to GHCR, and pulled on the server (rootless podman, Quadlet unit in `deploy/`). Jobs that push or deploy are gated on `github.repository == 'OIM7510/oim-shop'`, because the OIM6301 mirror runs the same workflows.

## Text students read

`docs/prd.md`, `README.md` and every other committed prose file are read by students. Before committing them, apply the teaching-prose skill (`~/teaching/ta/.claude/skills/teaching-prose/SKILL.md`). Its `prose-check.sh` hook lives in the prep repos and does not scan this one, so run the greps from its `references/checks.md` by hand.

## Frontend Stack

One library per concern. Prefer mature libraries over hand-rolled code; component source lives in the repo (shadcn), not in a black-box package. Do not add a library for a concern not listed here, or a second library for a concern already covered, without asking first. Packages that `npx shadcn add` installs, and official companions of listed libraries (such as `@hookform/resolvers` or `@tanstack/router-plugin`), are allowed.

| Concern | Use | Notes |
| --- | --- | --- |
| Framework | Vite + React + TanStack Router | Use Next.js instead only when SSR or SEO is a requirement |
| Styling | Tailwind CSS | No CSS-in-JS, no second styling system |
| Components | shadcn/ui, style `nova` (`radix-nova` in `components.json`) | Add via `npx shadcn add`; edit the copied source rather than wrapping it |
| Icons | lucide-react | No other icon set; inline SVG only for brand logos lucide does not ship |
| Animation | motion | All hand-written animation; keep shadcn's built-in transitions as they are |
| Server state | @tanstack/react-query | All API data lives here, never in Zustand |
| Client state | zustand | UI-only state (sidebar, selections, preferences) |
| Forms | react-hook-form + zod | Through shadcn Field (not the legacy Form component); zod schemas double as API types |
| Tables | @tanstack/react-table | Through shadcn Data Table |
| Charts | recharts | Through shadcn Chart |
| Layout panels | react-resizable-panels | Through shadcn Resizable |
| Drag and drop | @dnd-kit/react | Pre-1.0: pin the exact version; the legacy `@dnd-kit/core` line has had no release since 2024-12 |
| Toasts | sonner | Through shadcn Sonner |

Where a row says "through shadcn", the shadcn component decides the underlying library and its major version; follow it rather than installing the library directly.

Copied from `~/.claude/templates/frontend-stack.md`, last verified 2026-10-20.
