# Damascus Transit Technologies — Brand Guidelines

> **Version 1.0 — April 2026**
> For use by the marketing team, developers, and external contractors

---

## 1. BRAND IDENTITY

### Mission Statement
Damascus Transit Technologies modernizes Syria's public transport through open-source technology — improving reliability, safety, and passenger experience for 2.5 million daily commuters.

### Brand Personality
- **Trustworthy** — government and institutional partners need to know we are serious
- **Innovative** — we are the first; we set the standard
- **Accessible** — we serve a public good; our design must be inclusive
- **Syrian** — rooted in Damascus, built for Syrian cities, proud of the origin

### Brand Promise
*Real-time visibility for everyone who moves Damascus.*

---

## 2. COLOR PALETTE

### Primary Colors

| Name | Hex | RGB | Usage |
|------|-----|-----|-------|
| **Qasioun Gold** | `#C4B47E` | 196, 180, 126 | Primary accent, headings, CTAs |
| **Orontes Green** | `#1B4332` | 27, 67, 50 | Primary background, header, footer |

*Named after Mount Qasioun overlooking Damascus and the Orontes River flowing through Syria.*

### Secondary Colors

| Name | Hex | RGB | Usage |
|------|-----|-----|-------|
| **Damascus White** | `#F9F6EF` | 249, 246, 239 | Page backgrounds, light sections |
| **Citadel Stone** | `#7A7060` | 122, 112, 96 | Body text, secondary headings |
| **Night Blue** | `#0D1B2A` | 13, 27, 42 | Dark mode background, deep contrast |

### Accent / Status Colors

| Name | Hex | Usage |
|------|-----|-------|
| **Active Green** | `#2D9E6B` | Vehicle active / system online |
| **Alert Amber** | `#E8A045` | Delayed / warning state |
| **Offline Red** | `#C0392B` | Vehicle offline / error state |

### Color Rules
- **Never** use Qasioun Gold text on a white background (insufficient contrast for accessibility)
- **Always** pair Qasioun Gold with Orontes Green or Night Blue for legibility
- On dark backgrounds (Orontes Green, Night Blue): use Damascus White for body text
- Status colors are functional only — do not use for decoration

---

## 3. TYPOGRAPHY

### Primary Typefaces

**Headings (Arabic):** IBM Plex Arabic — Bold, SemiBold
**Headings (English/Latin):** IBM Plex Sans — Bold, SemiBold
**Body (Arabic):** IBM Plex Arabic — Regular, Light
**Body (English):** IBM Plex Sans — Regular, Light
**Monospace / Technical:** IBM Plex Mono — Regular (for API documentation, code samples)

*Rationale: IBM Plex is open-source (OFL license), supports Arabic with excellent RTL rendering, and has a technical credibility appropriate for a transit technology brand.*

### Type Scale

| Level | Size | Weight | Usage |
|-------|------|--------|-------|
| Display | 48–64px | Bold | Hero headlines |
| H1 | 36px | Bold | Page titles |
| H2 | 28px | SemiBold | Section headings |
| H3 | 22px | SemiBold | Sub-sections |
| Body Large | 18px | Regular | Lead paragraphs |
| Body | 16px | Regular | Standard body text |
| Caption | 13px | Light | Labels, footnotes |
| Mono | 14px | Regular | Code, technical specs |

### Typography Rules
- **Arabic text** is always right-to-left (RTL); ensure CSS `direction: rtl` on Arabic containers
- **Line height:** 1.6 for body text; 1.2 for headings
- **Maximum line length:** 65 characters (English), 55 characters (Arabic) for readability
- **Never** set body text smaller than 14px
- **Bilingual documents:** Arabic above English, separated by a horizontal rule or visual divider

---

## 4. LOGO

### Primary Logo
The DAM logotype consists of:
1. **Mark** — a stylized bus / route icon (see `DamascusTransit_Mark.svg`)
2. **Wordmark** — "Damascus Transit" in IBM Plex Sans Bold / IBM Plex Arabic Bold

*Full logo file: `DamascusTransit_Logo.svg`*

### Logo Variations

| Variation | Use Case |
|-----------|----------|
| Full horizontal (mark + wordmark, EN) | Default — website header, documents, presentations |
| Full horizontal (mark + wordmark, AR) | Arabic-primary materials, government documents |
| Mark only | App icon, favicon, social media avatar, embroidery |
| Wordmark only | Space-constrained horizontal layouts |
| White on dark | Dark backgrounds, Orontes Green header |
| Dark on light | Light backgrounds, Damascus White pages |

### Logo Clearspace
Maintain a minimum clearspace around the logo equal to the height of the letter "D" in the wordmark on all sides.

### Logo Rules
- **Never** stretch, rotate, or skew the logo
- **Never** recolor the logo in anything other than approved palette colors
- **Never** place the full-color logo on a busy photograph without a solid color container
- **Never** use the mark at sizes smaller than 24px / 0.25 inches

---

## 5. ICONOGRAPHY

### Icon Style
- **Line icons** — 2px stroke, rounded caps, 24px base grid
- Style: clean, minimal, infrastructure-appropriate (no playful or rounded cartoon styles)
- Consistent with IBM Carbon Design System icon library (open-source)

### Core Icon Set

| Icon | Usage |
|------|-------|
| Bus / vehicle | Fleet, vehicles, operators |
| Map pin | Stops, locations, routes |
| Clock | Schedules, ETAs, wait times |
| Chart / graph | Analytics, government dashboard |
| GPS signal | Real-time tracking |
| Person | Passengers, commuters |
| Shield | Security, open-source, trust |
| Globe | International partnerships, GTFS |

---

## 6. PHOTOGRAPHY & IMAGERY

### Photography Style
- **Authentic Damascus scenes** — real streets, real buses, real commuters (not stock photos of Western transit systems)
- **People first** — show Damascene commuters, drivers, and operators; humanize the technology
- **Technology in context** — smartphones showing the app, GPS devices on vehicles, dashboards in use
- **Golden hour / warm light** — consistent with Qasioun Gold brand warmth; avoid cold/grey palettes

### Photography Rules
- **Always** obtain proper releases for people appearing in brand photography
- **Never** use generic Western-city transit stock photos — they undermine Syrian authenticity
- When authentic Damascus photography is not available, use illustrations or abstract data visualizations instead

### Illustrations
- Use when photography is unavailable or insufficient
- Style: flat vector, consistent with color palette, Orontes Green + Qasioun Gold dominant
- Technical diagrams (system architecture, network maps) use the full 5-color palette with Night Blue background

---

## 7. VOICE & TONE

### Brand Voice
The Damascus Transit Technologies voice is:
- **Clear** — technical content explained in plain language for both Arabic and English audiences
- **Confident** — we are the first; we state facts, not hedges
- **Grounded in Syria** — we cite Damascus neighborhoods, Syrian institutions, Syrian commuters — not generic MENA examples
- **Optimistic without overselling** — we acknowledge the scale of the problem before describing the solution

### Tone by Context

| Context | Tone |
|---------|------|
| Government/Ministry materials | Formal, data-driven, deferential to institutional hierarchy |
| Donor / World Bank | Professional, evidence-based, impact-focused |
| Social media | Conversational, specific, proud — not promotional |
| Passenger-facing app | Warm, simple, functional Arabic-first |
| Developer/GitHub | Technical, collaborative, peer-to-peer |
| Press releases | Neutral, factual, third-person |

### Language Rules
- **Numbers with context:** Always pair numbers with their meaning. Not "2.5M" but "2.5 million daily commuters."
- **Avoid:** "revolutionary," "disruptive," "world-class," "game-changing" — these are empty; cite real metrics instead
- **Prefer:** specific, verifiable claims: "45-minute average wait," "$30 hardware cost," "26 API endpoints"
- **Arabic:** Use Modern Standard Arabic (MSA) for formal/government materials; Levantine dialect acceptable for social media
- **Bilingual order:** Arabic leads in all consumer and government materials; English leads in international donor materials

---

## 8. DIGITAL BRAND STANDARDS

### Website
- Background: Damascus White `#F9F6EF`
- Navigation bar: Orontes Green `#1B4332` with Damascus White text
- CTAs: Qasioun Gold `#C4B47E` background with Night Blue `#0D1B2A` text
- Font rendering: enable subpixel antialiasing; use system font stack as fallback

### Social Media Profiles

| Platform | Profile image | Cover image | Handle |
|----------|--------------|-------------|--------|
| Twitter/X | DAM Mark (square, on Orontes Green) | City route map illustration | @DamascusTransit |
| LinkedIn | DAM Mark (square, on Orontes Green) | Damascus cityscape + platform UI mockup | Damascus Transit Technologies |
| Facebook | DAM Mark (square, on Orontes Green) | Same as LinkedIn | Damascus Transit Technologies |
| GitHub | DAM Mark (square, on white) | — | actuatorsos/SyrianTransitSystem |

### Email Signatures
```
[Name]
[Title] — Damascus Transit Technologies
damascustransit.com · github.com/actuatorsos/SyrianTransitSystem
[email] · Damascus, Syrian Arab Republic
```

---

## 9. DOCUMENT TEMPLATES

### Standard Document Header
- Orontes Green header bar, full width
- DAM logo (white on dark) — left-aligned (LTR) / right-aligned (RTL)
- Document title in Damascus White, IBM Plex Sans Bold 24px
- "Confidential" / "For [Audience] Use Only" label in Qasioun Gold caption text

### Standard Footer
- Citadel Stone rule line
- `© 2026 Damascus Transit Technologies Ltd. · damascustransit.com · [email]`
- IBM Plex Sans Light, 11px, Citadel Stone color

### Pitch Decks / Presentations
- Slide backgrounds: Orontes Green (dark slides) or Damascus White (light slides); never alternate randomly
- Data visualizations: use Active Green for positive metrics, Alert Amber for context, Offline Red for problems
- Maximum 5 lines of text per slide; images and data tables preferred over bullet lists

---

*Damascus Transit Technologies Ltd. — Brand Guidelines v1.0 — April 2026*
*For brand questions: press@damascustransit.com*
