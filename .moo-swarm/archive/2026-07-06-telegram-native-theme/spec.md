# Feature: Telegram-Native Theme

Use `window.Telegram.WebApp.themeParams` to make Halo look like a true Telegram-native interface — colors matching the user's Telegram theme exactly.

## Summary

Telegram injects CSS custom properties (`--tg-theme-bg-color`, `--tg-theme-text-color`, etc.) when the page is served as a Mini App. We read these on load and map them to Halo's CSS variable system, giving a native look without manual theming.

## Acceptance Criteria

1. ✅ When opened as Telegram Mini App (`window.Telegram.WebApp` available), Halo uses `themeParams` for all major color tokens
2. ✅ Graceful fallback: in regular browser (no SDK), uses existing `@media (prefers-color-scheme)`
3. ✅ Telegram `themeChanged` event re-applies tokens when user switches Telegram theme
4. ✅ Colors mapped: bg_color → `--color-bg`, secondary_bg_color → `--color-surface`, text_color → `--color-text-primary`, hint_color → `--color-text-muted`, button_color → `--color-accent`, link_color → accent text
5. ✅ No visual flash/glitch during theme injection (runs before first paint via FOUC script)
6. ✅ Works alongside existing Chart.js and Mermaid.js dark/light rendering

## Effort

Low (2–3 hours). Pure frontend JS + CSS vars.

## Open Questions

- Should we also map `section_bg_color`, `header_bg_color`, `subtitle_text_color` for deeper integration?
- Does Telegram inject `--tg-*` vars automatically in Mini App mode, or must we read `themeParams` manually?

## Dependencies

- Telegram WebApp SDK (`https://telegram.org/js/telegram-web-app.js`) loaded in `<head>`
- Fallback: `@media (prefers-color-scheme)` for non-Telegram browsers