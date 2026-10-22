# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

@AGENTS.md

## Claude-specific

- The project's facts and commands are in AGENTS.md (imported above), shared with Codex. Edit them there.
- Before committing prose (PRD, READMEs, `deploy/README.md`, `data/seed/SOURCE.md`), apply the teaching-prose skill (`~/teaching/ta/.claude/skills/teaching-prose/SKILL.md`). Its `prose-check.sh` hook lives in the prep repos and does not scan this one, so run the greps from its `references/checks.md` by hand.
- `web/` follows the stack below. Add a shadcn component with `npx shadcn@latest add <name>` from `web/`.
- Before tagging a version, take screenshots of every page in light and dark mode for Zhi's review.

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
