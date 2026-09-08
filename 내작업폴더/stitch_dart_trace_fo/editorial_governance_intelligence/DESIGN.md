---
name: Editorial Governance Intelligence
colors:
  surface: '#f8f9ff'
  surface-dim: '#cbdbf5'
  surface-bright: '#f8f9ff'
  surface-container-lowest: '#ffffff'
  surface-container-low: '#eff4ff'
  surface-container: '#e5eeff'
  surface-container-high: '#dce9ff'
  surface-container-highest: '#d3e4fe'
  on-surface: '#0b1c30'
  on-surface-variant: '#434655'
  inverse-surface: '#213145'
  inverse-on-surface: '#eaf1ff'
  outline: '#747686'
  outline-variant: '#c4c5d7'
  surface-tint: '#2151da'
  primary: '#0037b0'
  on-primary: '#ffffff'
  primary-container: '#1d4ed8'
  on-primary-container: '#cad3ff'
  inverse-primary: '#b7c4ff'
  secondary: '#565e74'
  on-secondary: '#ffffff'
  secondary-container: '#dae2fd'
  on-secondary-container: '#5c647a'
  tertiary: '#8f000b'
  on-tertiary: '#ffffff'
  tertiary-container: '#bb0112'
  on-tertiary-container: '#ffc7c1'
  error: '#ba1a1a'
  on-error: '#ffffff'
  error-container: '#ffdad6'
  on-error-container: '#93000a'
  primary-fixed: '#dce1ff'
  primary-fixed-dim: '#b7c4ff'
  on-primary-fixed: '#001551'
  on-primary-fixed-variant: '#0039b5'
  secondary-fixed: '#dae2fd'
  secondary-fixed-dim: '#bec6e0'
  on-secondary-fixed: '#131b2e'
  on-secondary-fixed-variant: '#3f465c'
  tertiary-fixed: '#ffdad6'
  tertiary-fixed-dim: '#ffb4ab'
  on-tertiary-fixed: '#410002'
  on-tertiary-fixed-variant: '#93000b'
  background: '#f8f9ff'
  on-background: '#0b1c30'
  surface-variant: '#d3e4fe'
typography:
  display-xl:
    fontFamily: Noto Sans
    fontSize: 40px
    fontWeight: '700'
    lineHeight: 52px
    letterSpacing: -0.02em
  display-xl-mobile:
    fontFamily: Noto Sans
    fontSize: 30px
    fontWeight: '700'
    lineHeight: 40px
    letterSpacing: -0.02em
  headline-lg:
    fontFamily: Noto Sans
    fontSize: 28px
    fontWeight: '600'
    lineHeight: 38px
    letterSpacing: -0.015em
  headline-lg-mobile:
    fontFamily: Noto Sans
    fontSize: 22px
    fontWeight: '600'
    lineHeight: 30px
    letterSpacing: -0.015em
  headline-md:
    fontFamily: Noto Sans
    fontSize: 20px
    fontWeight: '600'
    lineHeight: 28px
    letterSpacing: -0.01em
  title-sm:
    fontFamily: Noto Sans
    fontSize: 16px
    fontWeight: '600'
    lineHeight: 24px
    letterSpacing: -0.005em
  body-lg:
    fontFamily: Noto Sans
    fontSize: 16px
    fontWeight: '400'
    lineHeight: 26px
    letterSpacing: -0.005em
  body-md:
    fontFamily: Noto Sans
    fontSize: 14px
    fontWeight: '400'
    lineHeight: 22px
    letterSpacing: 0em
  body-sm:
    fontFamily: Noto Sans
    fontSize: 13px
    fontWeight: '400'
    lineHeight: 20px
    letterSpacing: 0em
  caption:
    fontFamily: Noto Sans
    fontSize: 11px
    fontWeight: '500'
    lineHeight: 16px
    letterSpacing: 0.02em
  mono-data-lg:
    fontFamily: JetBrains Mono
    fontSize: 18px
    fontWeight: '600'
    lineHeight: 24px
    letterSpacing: -0.02em
  mono-data-sm:
    fontFamily: JetBrains Mono
    fontSize: 12px
    fontWeight: '500'
    lineHeight: 16px
    letterSpacing: 0em
rounded:
  sm: 0.125rem
  DEFAULT: 0.25rem
  md: 0.375rem
  lg: 0.5rem
  xl: 0.75rem
  full: 9999px
spacing:
  unit-2xs: 0.125rem
  unit-xs: 0.25rem
  unit-sm: 0.5rem
  unit-md: 1rem
  unit-lg: 1.5rem
  unit-xl: 2rem
  unit-2xl: 3rem
  gutter-mobile: 1rem
  gutter-desktop: 1.5rem
  max-width: 80rem
---

## Brand & Style

This design system delivers an authoritative, high-density financial research interface centered on corporate governance and regulatory filings. Drawing direct inspiration from clean, publication-grade editorial layouts, it marries the analytical precision of capital markets infrastructure with the refined typography of elite investigative journals.

### Target Audience & Emotional Intent
- **Audience:** Institutional equity analysts, corporate governance researchers, legal counsels, shareholder activists, and sophisticated retail investors navigating complex Korean regulatory filings (DART).
- **Emotional Response:** Unshakable credibility, intellectual clarity, calm analytical focus, and zero cognitive fatigue. The UI feels like an objective financial dossier—deliberate, audited, and strictly factual.

### Design Movement: Financial Editorial Modernism
The aesthetic synthesizes Scandinavian documentarian minimalism with systematic financial data architecture:
- **Hairline Precision:** Thin, structured boundary lines that segregate intricate shareholder structures without introducing visual heaviness.
- **Typographic Gravity:** Heavy reliance on structured weights, strict vertical leading, and tabular alignment to anchor complex Korean alphanumeric disclosures.
- **Restraint Over Decoration:** Zero illustrative noise, zero dramatic drop shadows, and absolute intentionality in every color marker.

## Colors

The palette is engineered around high legibility, strict contrast ratios, and institutional authority. Color serves strictly as a taxonomy of truth and hierarchy rather than ornamentation.

### Core Swatches & Roles
- **Primary Accent (`#1D4ED8` / `#1E40AF`):** Confident Cobalt Blue. Reserved exclusively for actionable data paths, audited validation badges, active navigation indicators, and primary verification anchors.
- **Secondary Slate (`#0F172A` / `#1E293B`):** Deep Obsidian & Charcoal. Drives display headlines, primary metric readouts, and core shareholder entities. Replaces pure black to eliminate harsh optical vibration against pale paper backgrounds.
- **Tertiary Alert (`#DC2626`):** Regulatory Crimson. Strictly confined to disclosure amendments (`정정 공시`), regulatory warnings, compliance violations, and critical voting discrepancies. Never used for standard UI dismissals.
- **Neutral Anchors (`#334155`, `#64748B`, `#94A3B8`):** Body copy, contextual metadata, legal footnote annotations, and secondary governance nodes.

### Background & Surface Hierarchy
- **Canvas (`#F8FAFC`):** Soft parchment-tinted warm white that minimizes eye strain during extended analytical review sessions.
- **Surface Elevation (`#FFFFFF`):** Crisp white for research dossiers, corporate cards, and modal sheets.
- **Borders & Dividers (`#E2E8F0`):** Hairline structure at 1px thickness (`border-slate-200`) providing architectural structure.

### Dark Mode Semantic Mapping
When toggled to dark mode:
- Canvas shifts to `#090D16` with elevated surfaces at `#0F172A`.
- Borders drop to a soft slate `#1E293B`.
- Primary cobalt elevates slightly to `#3B82F6` for WCAG AAA contrast against dark slabs.

## Typography

Typography prioritizes bilingual harmony (Hangul and Latin alphanumerics) and extreme tabular precision.

### Font Family Allocations
- **Primary Editorial (`Noto Sans`):** Selected for its balanced vertical metrics in Korean script, crisp rendering at high density, and clean neutral tone that never compromises judicial or regulatory rigor.
- **Tabular & Code Reference (`JetBrains Mono`):** Applied exclusively to monetary amounts, share percentages, DART filing report numbers (`접수번호`), and verification timestamps (`YYYY.MM.DD`).

### Typographic Directives
- **Tabular Lining Figures:** All numeric readouts across tables, equity distributions, and ownership matrices must declare `font-variant-numeric: tabular-nums` to ensure exact column alignment.
- **Korean Word Break & Tracking:** Hangul body content enforces `word-break: keep-all` to prevent unnatural mid-syllable breaks in corporate names and legal clauses. Tight negative tracking (`-0.01em` to `-0.02em`) is applied to headlines to eliminate loose optical spacing common in Korean web typography.

## Layout & Spacing

The layout model is anchored to a structured 12-column fixed grid with an absolute ceiling of `1280px` (`80rem`), centered with dynamic safety gutters.

### Grid & Breakpoints
- **Desktop (`>= 1024px`):** 12 columns, `24px` (`1.5rem`) gutters, dynamic auto margins up to `1280px`. Left or split sidebars anchor metadata while wide cards accommodate complex ownership matrices and timeline feeds.
- **Tablet (`768px - 1023px`):** 8 columns, `20px` gutters, `24px` page margins. Lateral analytical panels collapse into tabbed segments.
- **Mobile (`< 768px`):** 4 columns, `16px` gutters, `16px` outer margins. Multi-column ownership tables reflow into stacked disclosure cards with horizontal data tags.

### Spacing Philosophy
Generous internal container padding (`1.5rem` to `2rem`) offsets dense tabular data, establishing an editorial cadence. Negative space is functional: it establishes boundaries without relying on heavy background fills.

## Elevation & Depth

This design system avoids theatrical 3D elevation, heavy drop shadows, and soft neomorphic blurs. Depth is communicated strictly via **low-contrast outlines** and **tonal layering**.

### Spatial Hierarchy
- **Level 0 (Canvas):** `#F8FAFC`. The foundational workspace.
- **Level 1 (Surface Dossier):** `#FFFFFF`. Bound by a crisp `1px` border in `#E2E8F0`. Every card, table container, and comparative matrix rests on this tier.
- **Level 2 (Interactive Flyouts & Overlays):** Dropdowns, date pickers, and context popovers leverage `#FFFFFF` paired with an ultra-subtle, diffused hairline shadow: `0 4px 16px -2px rgba(15, 23, 42, 0.04), 0 0 0 1px rgba(226, 232, 240, 0.8)`.
- **Level 3 (Modal Sheets & Filings):** Dedicated legal audit modals sit atop an opaque scrim (`rgba(15, 23, 42, 0.4)` with `backdrop-filter: blur(2px)`), retaining complete typographic clarity.

## Shapes

The system implements a **Soft** shape geometry (`roundedness: 1`). 

### Radius Architecture
- **Base UI Controls (`4px` / `0.25rem`):** Applied to form inputs, utility action buttons, status pills, and code markers. Communicates analytical rigor and structural discipline.
- **Cards & Data Tables (`8px` / `0.5rem`):** Containers and filing summary cards use a controlled radius that softens visual corners without sacrificing rectangular grid alignment.
- **Pills & Badges:** Distinctive status chips utilize a slightly increased radius (`4px` to `6px`) rather than full pill circular rounding to preserve the editorial character.

## Components

### 1. Distinctive 4-Part Evidence Status Pills
The core verification anchor of the interface, communicating disclosure validity at a glance:
- **Structure:** A locked horizontal lockup containing 4 coordinated status tokens:
  1. `공식 공시` (Official Filing): `#F1F5F9` background, `#334155` text, hairline border `#CBD5E1`.
  2. `검증 완료` (Verified): Deep cobalt tint `#EFF6FF`, `#1D4ED8` text, `#BFDBFE` border with a `2px` cobalt confirmation dot.
  3. `정정 공시 반영` (Amendment Reflected): Light rose `#FEF2F2`, `#DC2626` text, `#FECACA` border. Indicates revised shareholder numbers or corrected share counts.
  4. `기준일 YYYY.MM.DD` (Effective Date): `#F8FAFC` background, `#64748B` JetBrains Mono text, recording the exact legal cut-off.
- **Spacing:** `2px` internal padding, `6px` lateral chip spacing, height fixed to `24px`, font size `11px` weight `600`.

### 2. Buttons
- **Primary:** `#1D4ED8` background, `#FFFFFF` text, `4px` radius. Hover shifts to `#1E40AF`. Pressed scales down to `0.98`. Focus ring: `2px` offset with `#93C5FD`.
- **Secondary / Ghost:** Transparent background, `#0F172A` text, `1px` border `#E2E8F0`. Hover shifts to `#F8FAFC` background and `#0F172A` border.
- **Destructive / Flag:** `#FEF2F2` background, `#DC2626` text, `1px` border `#FCA5A5`. Used exclusively for reporting reporting discrepancies.

### 3. Data Tables & Ownership Matrices
- **Table Headers:** `12px` JetBrains Mono, uppercase, `#64748B`, `font-weight: 600`, background `#F8FAFC`, bordered bottom with `1px` `#CBD5E1`.
- **Table Cells:** `14px` Noto Sans (`tabular-nums`), vertical padding `12px`, horizontal padding `16px`. Alternating rows maintain pure white with a faint `#F8FAFC` hover transition.
- **Ownership Delta:** Positive shifts render in `#1D4ED8` (`+0.45%`), negative shifts in `#DC2626` (`-1.20%`), static stakes in `#64748B`.

### 4. Input Fields & Search
- **DART Search Field:** Tall format (`44px`), `1px` solid `#CBD5E1` border, `#FFFFFF` background, leading regulatory filing icon. Focus triggers a razor `#1D4ED8` border without thick neon rings. Placeholder text rests at `#94A3B8`.

### 5. Research Dossier Cards
- Constructed with `#FFFFFF` fill, bounded by `1px` solid `#E2E8F0`.
- Includes an editorial header section: Category stamp (`지배구조 분석`), Title (`최대주주 및 특수관계인 지분 변동`), followed by the 4-part evidence status pill cluster aligned right.
- Generous padding: `24px` on desktop, `16px` on mobile screens.

### 6. Interactive Governance Tree Nodes
- Stakeholder connection cards featuring relational connecting hairlines (`#CBD5E1`).
- Key executive chips with share percentages rendered in `JetBrains Mono` bold beside voting power differentials.