# Feature: Sticky Bottom Button (MainButton)

Add a `Telegram.WebApp.MainButton` at the bottom of Halo for quick actions: manual data refresh and GitHub link.

## Summary

Telegram Mini Apps can show a sticky button at the bottom of the viewport (`MainButton`). We use it for two modes:
- Default: "Refresh data" — triggers `loadDashboardData()`
- While loading: shows a progress spinner via `showProgress(true)`
- Stretch: "Open on GitHub" — if user long-presses or we detect stale data

## Acceptance Criteria

1. ✅ MainButton visible with text "↻ Refresh" when data is loaded
2. ✅ Tapping MainButton triggers data refresh (`loadDashboardData()`)
3. ✅ During refresh, button shows progress spinner (`showProgress()`) and text "Refreshing…"
4. ✅ On refresh complete, spinner hides, button re-enables
5. ✅ On refresh failure, button shows "↻ Retry" with `notificationOccurred("error")`
6. ✅ Graceful no-op when not in Telegram Mini App context

## Effort

Low (2–3 hours). Pure frontend, no backend.

## Open Questions

- Should we add a secondary action via secondary button (e.g., "Open GitHub")?
- Progress spinner: `leaveActive=true` or `false`? (true = button stays tappable, false = disabled during load)

## Dependencies

- Telegram WebApp SDK loaded
- Bot API 6.1+
- No BotFather setup needed