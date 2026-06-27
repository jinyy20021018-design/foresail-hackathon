# ForeSail DESIGN.md

Visual system for the ForeSail trade-risk app. Register: **product** (dashboard/tool). **Light theme**, bright royal-blue accent (#2563EB), cool tinted neutrals, near-white fact cards, soft semantic icon circles, with a **dark-navy Route Risk Map panel** for contrast. Matches the user's approved hi-fi mockups. UI language: **English**. No magenta.

## Color (OKLCH, light, deep-navy accent)

Strategy: **Restrained** — near-white fact surfaces, a cool-gray page canvas, and one royal-blue accent for primary/selection/links. Red/amber/green are reserved for semantic status and icon circles (color + icon + text, color-blind safe). Never `#000`/`#fff`; neutrals are tinted toward hue 262.

```css
--bg:          oklch(0.985 0.004 255);  /* page background, very light cool gray */
--s1:          oklch(1 0 0);            /* white surface */
--s2:          oklch(0.975 0.005 255);  /* subtle gray */
--s3:          oklch(0.955 0.006 255);
--border:      oklch(0.91 0.006 255);
--border2:     oklch(0.85 0.010 255);
--text:        oklch(0.27 0.022 262);   /* dark slate */
--muted:       oklch(0.52 0.020 262);
--faint:       oklch(0.66 0.015 262);
--accent:      oklch(0.42 0.115 262);   /* DEEP NAVY/INDIGO: primary, links, selection */
--accent2:     oklch(0.34 0.120 264);   /* hover (darker) */
--accent-soft: oklch(0.42 0.115 262 / 0.10);

/* risk STATUS only */
--danger:  oklch(0.55 0.205 25);   /* AT_RISK / critical 🔴 */
--warn:    oklch(0.66 0.150 62);   /* watch / due-soon 🟠 */
--ok:      oklch(0.58 0.135 155);  /* clear / ok 🟢 */
```
Seat coloring on map/axis: our seat = `--accent` (solid); counterparty = `--faint` (dashed, "contract-derived").
Shadows: nearly flat — `0 1px 2px` at ~4% alpha. Prefer borders and tinted surfaces over floating cards.

## Typography
- `Inter, "Segoe UI", system-ui, sans-serif`. One family. Tabular nums for money/dates/countdowns.
- Fixed rem scale ~1.2; weights 400/600/700/800 for hierarchy. Prose ≤72ch; tables can run dense.

## Layout
- **IA (confirmed with user):** Page 1 = **Case Library / Overview** (summary cards + search/filter + cases table). Click a case → **Case Workspace**: **Overview first** (Verdict + Case Snapshot + Watch Profile + Route Risk Map + Liability strip), **then the agent pipeline runs in order** (External Events → Relevance → Risks & Obligations → Actions & Drafts → Treatment Plans → Agent Trace), each explicit/expandable.
- No redundant left nav inside a case (pipeline stages ARE the structure; breadcrumb back to Library). Cross-case snapshot lives on Library.
- Radius 5px for badges, 8px for controls, 10px for surfaces, 12px only for the dark map; spacing 4/8/12/16/24; vary for rhythm.

## Components & motion
- Every control: default/hover/focus/active/disabled. Status = badge (dot + icon + label), never color alone.
- 150–250ms ease-out. Countdown pulses, agent trace streams. Don't animate layout props.

## Signature components
1. **Route Risk Map** — stylized light SVG (not Leaflet): navy route, faint grid, events plotted with pulse, Incoterm transfer point ◆; our-seat leg solid+navy, counterparty dashed+faint. (CIF: transfer at loading → seller leg tiny, main voyage is buyer's.)
2. **Liability strip (Incoterms)** — risk/cost/obligation lanes along the voyage with the transfer point.

## Bans (project)
No magenta. No garish bright blue (use deep navy). No left-sidebar nav inside case. No per-field approve grind (default-accept + exception-review). No side-stripe borders, gradient text, hero-metric cliché. UI copy in English.
