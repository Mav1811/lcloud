---
name: Lcloud Landing Page Design
description: Design system and spec for the Lcloud marketing landing page
type: project
---

# Lcloud Landing Page — Design Spec
**Date:** 2026-04-25

---

## Goal

A visually distinctive, premium landing page for Lcloud — the reference is localsend.org.  
Audience: non-technical Android + Windows users. Minimalistic, interactive, no generic SaaS look.

---

## Design System

### Color Tokens

| Token | Value | Usage |
|-------|-------|-------|
| `--lc-page` | `#FDFCF8` | Warm linen body background |
| `--lc-page-warm` | `#F5F2EB` | Alt section backgrounds |
| `--lc-surface` | `#FFFFFF` | Cards, widgets |
| `--lc-primary` | `#006D6D` | Deep teal — brand color |
| `--lc-primary-dark` | `#004F4F` | Hover darken |
| `--lc-primary-light` | `#40B8B8` | Gradient end, accents |
| `--lc-primary-subtle` | `#D6F0F0` | Borders on primary |
| `--lc-primary-pale` | `#F0FAFA` | Light fills |
| `--lc-accent` | `#C96B00` | Warm amber — CTAs, "Coming Soon" |
| `--lc-accent-bright` | `#E07B00` | Accent hover |
| `--lc-ink` | `#1A1A1A` | Primary text |
| `--lc-ink-2` | `#444444` | Secondary text |
| `--lc-ink-3` | `#777777` | Muted text |
| `--lc-border` | `#E4E0D8` | Default borders |
| `--lc-success` | `#16A34A` | Success states |

**Contrast ratios (all AAA):**
- White on `--lc-primary` (#006D6D): **9.9:1** ✓
- `--lc-ink` on `--lc-page`: **17.2:1** ✓
- `--lc-ink-2` on `--lc-page`: **7.4:1** ✓

### Typography

| Role | Font | Weight | Notes |
|------|------|--------|-------|
| Display/Headings | Space Grotesk | 600–700 | Distinctive, not Inter |
| Body | DM Sans | 400–500 | Friendly, legible |

Scale: 12/14/16/18/20/24/32/44px + `clamp(2.75rem, 5.5vw, 4.5rem)` for hero.  
Letter-spacing: `-0.02em` on headings, `0.08–0.12em` on labels.

### Spacing

4px base grid: 4/8/12/16/20/24/32/40/48/64/80/96/128px via CSS custom properties.

### Radius

4 / 8 / 12 / 16 / 24 / 32 / 9999px

### Shadows

All shadows tinted with `rgba(0,109,109,…)` (primary teal) instead of grey — gives a warm, cohesive feel.

### Motion

| Token | Value | Usage |
|-------|-------|-------|
| `--dur-fast` | 120ms | Micro-interactions |
| `--dur-normal` | 200ms | Most hover/focus |
| `--dur-slow` | 350ms | Cards, panels |
| `--dur-xslow` | 600ms | Scroll reveal |
| `--ease-out` | `cubic-bezier(0.16,1,0.3,1)` | General |
| `--ease-spring` | `cubic-bezier(0.34,1.56,0.64,1)` | Icon hop |

---

## Page Structure

1. **Nav** — Logo + nav links + GitHub + Download CTA. Sticky with blur backdrop. Border appears on scroll.
2. **Hero** — Two-column: text + animated backup widget. Widget shows live backup loop (scanning → backing up → complete → restart).
3. **How It Works** — 3-step horizontal flow with connector line. Hover flips step number circle from outline to filled teal.
4. **Features** — 3-column grid of 6 cards. "Coming Soon" cards use amber accent. Icons hop on hover.
5. **Privacy** — Two-column: trust copy + 4-stat grid (0 servers, 0 accounts, 0B cloud, MIT).
6. **Download** — 2 platform cards (Android APK, Windows EXE) with top-border reveal on hover.
7. **Footer** — Logo + nav links + copy. Warm background.

---

## Interactions & States

- **Buttons:** Scale down on active (`0.97`), lift + shadow on hover, no-focus-ring-on-click (`:focus-visible` only)
- **Cards:** `translateY(-3px)` + shadow on hover, `border-color` transitions to primary
- **Feature icons:** Spring-scale + slight rotation on card hover
- **Scroll reveal:** `opacity 0 → 1` + `translateY(24px → 0)` with staggered delays per grid item
- **Nav links:** Underline slides in from left on hover

---

## Implementation

- Single `landing/index.html` — no build tool, no CDN Tailwind
- Google Fonts via `<link>` (Space Grotesk + DM Sans)
- Pure CSS custom properties, no preprocessor
- JS: IntersectionObserver for scroll reveal, setInterval-free animation loop for widget, nav scroll state
- Responsive: 3-col → 2-col → 1-col at 900px/600px breakpoints
