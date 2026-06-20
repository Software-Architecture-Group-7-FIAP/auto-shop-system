# Color Palette Application Instructions

Apply the **Color Hunt palette** ([reference image](./Color%20Hunt%20Palette%20091413285a48408a71b0e4cc.png)) across the Auto Shop System frontend. The palette is a monochromatic green scale designed for a **dark, emerald-themed admin UI**.

---

## 1. Palette Reference

| Swatch | Hex | Token name | Role |
|--------|-----|------------|------|
| ![#091413](https://via.placeholder.com/16/091413/091413.png) | `#091413` | `--color-base` | App canvas, page background |
| ![#285A48](https://via.placeholder.com/16/285A48/285A48.png) | `#285A48` | `--color-surface` | Navigation bar, list panel, cards, elevated panels |
| ![#408A71](https://via.placeholder.com/16/408A71/408A71.png) | `#408A71` | `--color-primary` | Primary buttons, links, titles, focus rings, active icons |
| ![#B0E4CC](https://via.placeholder.com/16/B0E4CC/B0E4CC.png) | `#B0E4CC` | `--color-accent` | Headings on dark bg, selected row highlight, hover text, CTA emphasis |

Hex values are also listed in [`color_pallets.md`](./color_pallets.md).

---

## 2. Design Intent

- **Dark-first:** Use `#091413` as the main background; avoid reverting to light grays (`#F5F5F5`, `#FFFFFF`) except for detail panels if readability requires it.
- **Layered depth:** Darker layers sit behind lighter ones: base → surface → detail/content.
- **Single accent family:** All interactive emphasis flows through `#408A71` (actions) and `#B0E4CC` (highlights). Do not reintroduce the old teal `#4A8888`.
- **Functional colors stay separate:** Destructive actions (`btn-danger`) may keep a red tone so errors remain visually distinct from the green palette.

---

## 3. CSS Custom Properties

Add these tokens at the top of `frontend/src/styles.css` (after the font import):

```css
:root {
  /* Palette */
  --color-base: #091413;
  --color-surface: #285A48;
  --color-primary: #408A71;
  --color-accent: #B0E4CC;

  /* Derived */
  --color-surface-raised: #1e2e28;       /* detail panel — between base and surface */
  --color-border: rgba(176, 228, 204, 0.2);
  --color-border-strong: rgba(176, 228, 204, 0.35);
  --color-text: #B0E4CC;
  --color-text-muted: rgba(176, 228, 204, 0.65);
  --color-text-on-primary: #091413;
  --color-primary-hover: #357a63;
  --color-surface-hover: rgba(64, 138, 113, 0.15);
  --color-scrollbar-track: #285A48;
  --color-scrollbar-thumb: #408A71;
}
```

Use tokens everywhere instead of hard-coded hex values so future palette tweaks require only `:root` changes.

---

## 4. Mapping: Old Colors → New Tokens

The current `styles.css` uses a light gray + teal scheme. Replace as follows:

| Current value | Used for | Replace with |
|---------------|----------|--------------|
| `#F5F5F5` | `body`, list block, menu, login bg | `var(--color-base)` |
| `#EAEAEA` | Navigation, list header, scrollbar track, btn-secondary | `var(--color-surface)` |
| `#FFFFFF` | Detail panel, selected list item, menu cards, login card | `var(--color-surface-raised)` |
| `#4A8888` | Links, titles, primary btn, focus, selection border | `var(--color-primary)` |
| `#3D7373` | Primary btn hover | `var(--color-primary-hover)` |
| `#6F6F6F` | Body text, icons, secondary btn text | `var(--color-text-muted)` |
| `#333` | Input text, readonly labels | `var(--color-text)` |
| `#999` | Muted text, borders, scrollbar thumb | `var(--color-text-muted)` or `var(--color-border-strong)` |
| `#DDD` / `#CCC` / `#EEE` | Borders | `var(--color-border)` |
| `#C44` / `#A33` | Danger button | Keep (or use `#D46A6A` / `#B85555` if a softer red is preferred) |

---

## 5. Component-by-Component Rules

Apply these rules in `frontend/src/styles.css`. Component-level CSS files mostly defer to globals; avoid duplicating colors locally.

### 5.1 Global / Body

```css
body {
  background: var(--color-base);
  color: var(--color-text-muted);
}

a {
  color: var(--color-primary);
}
```

### 5.2 Layout (`.wrapper`, panels)

| Element | Background | Border |
|---------|------------|--------|
| `.navigation-block` | `var(--color-surface)` | `1px solid var(--color-border)` |
| `.model-list-block` | `var(--color-base)` | right: `var(--color-border)` |
| `.model-detail-block` | `var(--color-surface-raised)` | — |
| `.list-header` | `var(--color-surface)` | bottom: `var(--color-border)` |

### 5.3 Lists

- **Default row:** transparent background, `var(--color-text-muted)` text.
- **Hover:** `background: var(--color-surface-hover)`.
- **Selected:** `border-left: 3px solid var(--color-accent)`; background `var(--color-surface-raised)`; text `var(--color-text)`.

### 5.4 Typography accents

- `.detail-title-text`, `.head-nav-title`, `.menu-title`, `.login-card h1`, `.action-section h3` → `color: var(--color-accent)`.
- `.model-detail-message`, `.menu-subtitle`, `.login-card p`, `.menu-auth` → `color: var(--color-text-muted)`.

### 5.5 Forms

```css
.text-input,
.select-input {
  color: var(--color-text);
  border-bottom: 1px solid var(--color-border-strong);
}

.text-input:focus,
.select-input:focus {
  border-bottom-color: var(--color-accent);
}

.field-name label.readonly {
  color: var(--color-text);
  border-bottom: 1px solid var(--color-border);
}
```

### 5.6 Buttons

| Class | Background | Text | Hover |
|-------|------------|------|-------|
| `.btn-primary` | `var(--color-primary)` | `var(--color-text-on-primary)` | `var(--color-primary-hover)` |
| `.btn-secondary` | `transparent` | `var(--color-text-muted)` | `var(--color-surface-hover)` + border `var(--color-primary)` |
| `.btn-danger` | `#C44` (unchanged) | `#fff` | `#A33` |

Secondary buttons: add `border: 1px solid var(--color-border-strong)`.

### 5.7 Navigation & Menu

- `.head-nav-icon` → `var(--color-text-muted)`; hover → `var(--color-accent)`.
- `.menu li a` → background `var(--color-surface)`; border `var(--color-border)`; text `var(--color-text-muted)`.
- `.menu li a:hover` → border-color `var(--color-accent)`; color `var(--color-accent)`.
- `.login-card` → background `var(--color-surface)`; border `var(--color-border)`; reduce box-shadow opacity or remove (dark UI).

### 5.8 Scrollbars

```css
.scrollbar::-webkit-scrollbar-track {
  background: var(--color-scrollbar-track);
}
.scrollbar::-webkit-scrollbar-thumb {
  background: var(--color-scrollbar-thumb);
}
```

---

## 6. Step-by-Step Application Checklist

1. **Add `:root` tokens** to `frontend/src/styles.css` (section 3).
2. **Replace all hard-coded palette hex values** in `styles.css` using the mapping table (section 4).
3. **Search the codebase** for leftover old colors:
   ```bash
   rg -i "#4a8888|#f5f5f5|#eaeaea|#6f6f6f" frontend/src
   ```
4. **Update inline styles** if any exist (e.g. `ngStyle` border colors in list templates) to use `var(--color-accent)` or a CSS class instead of `#999`.
5. **Run the dev server** and verify every screen:
   - Home menu (`/`)
   - Login (`/login`)
   - At least one entity list + detail page
   - Create form and delete confirmation
6. **Check contrast** on primary buttons and body text (see section 7).
7. **Update docs:** adjust the color list in `frontend/docs/LLM_FRONTEND_BUILD_GUIDE.md` section 12 to reference this file.

---

## 7. Accessibility Notes

| Combination | Approx. use | Guidance |
|-------------|-------------|----------|
| `#B0E4CC` on `#091413` | Body text, titles | Good contrast — safe for primary readable text |
| `#B0E4CC` at 65% opacity on `#091413` | Muted labels | Acceptable for secondary text; avoid going below ~55% opacity |
| `#091413` on `#408A71` | Primary button label | Good contrast |
| `#408A71` on `#091413` | Links, icons | Use for accents only, not long paragraphs |
| `#285A48` on `#091413` | Surface panels | Structural separation only — do not place small text directly on `#285A48` without `#B0E4CC` |

Do not use `#408A71` as paragraph text on `#091413` for long content; prefer `#B0E4CC`.

---

## 8. Optional Extensions

### Light detail panel variant

If the detail form feels too dark, keep the list column dark and use a slightly lifted panel:

```css
--color-surface-raised: #122019;
```

Only introduce true white (`#FFFFFF`) if a specific form requires print/export readability.

### Status badges (future)

| Status | Background | Text |
|--------|------------|------|
| Success | `rgba(64, 138, 113, 0.25)` | `#B0E4CC` |
| Warning | `rgba(176, 228, 204, 0.15)` | `#B0E4CC` |
| Error | `rgba(204, 68, 68, 0.2)` | `#F0A0A0` |

---

## 9. Files to Touch

| File | Action |
|------|--------|
| `frontend/src/styles.css` | Primary — add tokens and replace all color values |
| `frontend/docs/LLM_FRONTEND_BUILD_GUIDE.md` | Update section 12 palette reference |
| `frontend/src/app/component/**/*.css` | Only if local overrides exist (most are empty stubs) |
| Entity list templates | Replace inline `#999` / `#4A8888` in `ngStyle` if present |

---

## 10. Visual Hierarchy Summary

```
┌─────────────────────────────────────────────────────────┐
│  navigation-block          (#285A48 — surface)          │
├──────────────────────┬──────────────────────────────────┤
│  model-list-block    │  model-detail-block              │
│  (#091413 — base)    │  (#122019 — surface-raised)      │
│                      │                                  │
│  selected → accent   │  titles → accent                 │
│  border (#B0E4CC)    │  inputs → text (#B0E4CC)         │
│                      │  primary btn → #408A71           │
└──────────────────────┴──────────────────────────────────┘
```

This hierarchy keeps the palette cohesive: darkest canvas, mid-tone structure, mint highlights for reading and interaction, sage green for actions.
