# Design System (Unified UI)

## 1. Color Tokens

```css
:root {
  --ds-color-primary: #2563eb;
  --ds-color-accent: #0ea5a0;

  --ds-bg-page: #f3f5f7;
  --ds-surface: #ffffff;
  --ds-surface-muted: #f8fafc;

  --ds-text-main: #0f172a;
  --ds-text-secondary: #334155;
  --ds-text-muted: #64748b;

  --ds-border: rgba(15, 23, 42, 0.08);
  --ds-shadow-soft: 0 4px 20px rgba(0, 0, 0, 0.05);
}

:root[data-theme='dark'] {
  --ds-color-primary: #60a5fa;
  --ds-color-accent: #2dd4bf;

  --ds-bg-page: #0f1115;
  --ds-surface: #151b25;
  --ds-surface-muted: #1a2330;

  --ds-text-main: #e5e7eb;
  --ds-text-secondary: #cbd5e1;
  --ds-text-muted: #94a3b8;

  --ds-border: rgba(148, 163, 184, 0.24);
}
```

## 2. Typography

- Title: `var(--ds-font-title)`, weight `700`
- Body: `0.9375rem`, line-height `1.6`
- Meta: `0.8125rem`, muted color

## 3. Spacing & Radius

- Spacing scale: `8 / 12 / 16 / 24 / 32`
- Button/Input radius: `12px`
- Card radius: `16px`

## 4. Component Rules

- Button: hover brighten + soft shadow, active press-down
- Card: 1px border + unified shadow + lift on hover
- Input/Select: muted surface background + focus ring
- List/Table: remove strong split lines, use spacing + soft hover
- Navbar: sticky, blurred surface, compact status area

## 5. Implemented Key Components

- Vue components:
  - `src/components/ui/AppButton.vue`
  - `src/components/ui/AppCard.vue`
  - `src/components/ui/AppList.vue`
- React reference components:
  - `src/design-system/react-components.tsx`

## 6. Example Page Structure

- Route: `/design-system`
- File: `src/views/DesignSystemView.vue`
- Shows:
  - palette swatches
  - button variants
  - list/card/empty/loading patterns

## 7. Global Integration

- Theme tokens and Element Plus remap: `src/styles/base.css`
- Dark mode support:
  - auto follow system (`prefers-color-scheme`)
  - manual switch via top nav (`localStorage: tg_theme`)
