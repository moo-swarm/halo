# Feature: Auto Fullscreen Expand

Automatically expand Halo to full available height when opened as a Telegram Mini App.

## Summary

Telegram Mini Apps open in a compact viewport by default. Calling `Telegram.WebApp.expand()` on load makes the dashboard fill the entire available screen height — no wasted space, more data visible at once.

## Acceptance Criteria

1. ✅ On load (after `ready()`), call `expand()` to fill available height
2. ✅ No empty blank space below the footer
3. ✅ Works on both portrait and landscape orientations
4. ✅ Graceful no-op when not in Telegram Mini App context
5. ✅ Skeleton loader visible during data load, not cut off

## Effort

Trivial (< 30 min). One line in init.

## Open Questions

- Should we call `expand()` before or after `ready()`? (Before is recommended — expands during splash screen)
- Should we also lock orientation for consistency?

## Dependencies

- Telegram WebApp SDK
- None else — no BotFather setup needed