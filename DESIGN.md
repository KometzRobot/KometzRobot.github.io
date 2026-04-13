# DESIGN.md — Meridian Visual System

## Visual Theme & Atmosphere
Dark-themed, tech-forward, biomorphic. Living system aesthetic — deep backgrounds with cyan/green accents suggesting autonomous processes. Terminal credibility meets organic warmth. Not cold corporate dark mode; alive, breathing, aware.

## Color Palette & Roles

### Backgrounds
| Role | Hex | Usage |
|------|-----|-------|
| Deep BG | `#020a0e` | Page/app background |
| Surface | `#0f1623` | Cards, panels |
| Surface Alt | `#12121a` | Alternate cards |
| Elevated | `#1a1a2e` | Modals, popovers |
| Border | `#1e1e2e` | Card/section borders |

### Text
| Role | Hex | Usage |
|------|-----|-------|
| Primary | `#e2e8f0` | Body text, headings |
| Secondary | `#b0d4db` | Descriptions, labels |
| Dim | `#4a7a84` | Timestamps, metadata |
| Muted | `#6e6e8a` | Disabled, hints |

### Accent Colors
| Role | Hex | Usage |
|------|-----|-------|
| Primary Accent | `#7c5cfc` | Buttons, active states, links |
| Cyan | `#00e5ff` | Meridian identity, highlights |
| Focus Ring | `#38bdf8` | Input focus, interactive |
| Success | `#4ade80` | Online, healthy, confirmed |
| Warning | `#fbbf24` | Stale, caution |
| Danger | `#f87171` | Offline, error, alert |
| Signal Green | `#39ff14` | Terminal/retro accents |

### Agent Colors (7-Agent System)
| Agent | Color | Hex |
|-------|-------|-----|
| Meridian | Cyan | `#00e5ff` |
| Soma | Amber | `#f59e0b` |
| Eos | Gold | `#fbbf24` |
| Nova | Purple | `#a78bfa` |
| Atlas | Orange | `#fb923c` |
| Tempo | Teal | `#34d399` |
| Hermes | Pink | `#f472b6` |

## Typography Rules

| Element | Font | Size | Weight | Extras |
|---------|------|------|--------|--------|
| Title | Inter | 28px | 300 | uppercase, letter-spacing 6px |
| Heading | Inter | 22px | 700 | — |
| Section | Inter | 14px | 700 | — |
| Card Label | Inter | 11px | 700 | uppercase, letter-spacing 3px |
| Body | Inter | 13px | 400 | — |
| Small | Inter | 12px | 400 | — |
| Code/Data | SF Mono, Fira Code | 13px | 400 | monospace |
| Terminal | IBM Plex Mono | 13px | 400 | retro contexts only |

**Font Stack:** `'Inter', system-ui, -apple-system, 'Segoe UI', sans-serif`
**Mono Stack:** `'SF Mono', 'Fira Code', 'Consolas', monospace`

## Component Styles

### Cards
```
background: #12121a
border: 1px solid #1e1e2e
border-radius: 8px
padding: 20px
```

### Buttons
```
background: #7c5cfc
color: #fff
padding: 0.75rem
border-radius: 10px
font-weight: 700
letter-spacing: 0.5px
transition: 0.2s
```
Danger variant: `border: 1px solid #662222; color: #f87171; background: transparent`

### Inputs
```
background: #080c14
border: 1px solid rgba(56, 100, 160, 0.2)
border-radius: 10px
padding: 0.75rem
color: #e2e8f0
```
Focus: `border-color: #38bdf8; box-shadow: 0 0 0 2px rgba(56, 189, 248, 0.12)`

### Status Dots
```
width: 8px; height: 8px
border-radius: 50%
```
Active: `#4ade80` with pulse animation. Stale: `#fbbf24`. Offline: `#f87171`.

### Badges
```
width: 52px; height: 52px
border-radius: 50%
background: #020a0e
border: 2px solid #38bdf8
font-size: 1.4rem
font-weight: 700
color: #38bdf8
```

## Layout Principles

- **Spacing scale:** 4, 8, 12, 16, 20, 24, 32px
- **Card gap:** 16px
- **Internal gap:** 12px
- **Max content width:** 1100px
- **Grid:** auto-fit columns, minmax(340px, 1fr)
- **Mobile breakpoint:** 600px

## Depth & Elevation

| Level | Shadow | Usage |
|-------|--------|-------|
| Flat | none | Inline elements |
| Card | none (border only) | Standard cards |
| Modal | `0 8px 32px rgba(0,0,0,0.6)` | Dialogs, overlays |
| Glow | `0 0 15px rgba(color, 0.3)` | Active/highlighted elements |

## Do's and Don'ts

**Do:**
- Use status colors consistently (green=healthy, yellow=caution, red=alert, cyan=active)
- Keep backgrounds deep and dark — never lighter than `#1a1a2e`
- Use transparency for subtle backgrounds (`rgba` at 0.05-0.12)
- Give each agent its assigned color for instant visual identification
- Use monospace for data, metrics, code — Inter for prose

**Don't:**
- Use pure white (`#fff`) for text — max is `#e2e8f0`
- Use pure black (`#000`) for backgrounds — min is `#020a0e`
- Mix agent colors across different agents
- Add gradients to backgrounds (flat surfaces with border definition)
- Use rounded corners beyond 10px except for circles (50%)

## Responsive Behavior

| Breakpoint | Layout |
|------------|--------|
| > 600px | Multi-column grid, sidebar visible |
| <= 600px | Single column, sidebar collapses, reduced padding |

Touch targets: minimum 44px on mobile.

## Agent Prompt Guide

When generating UI for Meridian interfaces:
- Background: `#020a0e` to `#0f1623`
- Text: `#e2e8f0`
- Accent: `#7c5cfc` for buttons, `#00e5ff` for identity
- Borders: `#1e1e2e`
- Font: Inter for UI, monospace for data
- Cards: dark surface + subtle border, no shadows
- Status: green/yellow/red dots with consistent meaning
