# 04 · Live UI

## Key files

- `src/ui/views/monitor_view.py` — `MonitorView`; `CHART_REGISTRY` grid + stats + inline visibility
- `src/ui/chart_base.py` — `ChartCard`, `ChartViewMixin`, registry, EMA, reflow
- `src/core/app_config.py` — `%APPDATA%/IGPPerformanceMonitor/config.json` (theme, chart visibility, window/splitter, overlay click-through, monitored processes, timed seconds)
- `src/ui/panels/chart_visibility_panel.py` — collapsible show/hide chips
- `src/ui/theme.py` — `Theme` / DARK / LIGHT, QSS generators, `Crosshair`, shadows. **All colors come from here.** Sets `pg antialias=True` at import.
- `src/ui/views/overlay_window.py` — per-app overlay; themed
- `src/ui/panels/process_panel.py` — process picker; persists monitored list + timer

## Responsibilities

Live FPS/CPU/GPU/Mem/VRAM charts + stats + overlay; instant dark/light switch.

## Pitfalls

- **Colors only from `src.ui.theme`.** No hardcoded `#xxxxxx`. Accents: `palette()` / `metric_accent`; system curves: `total_cpu` / `total_gpu` / `vram`; semantic: `good` / `warn` / `bad`.
- **Theme switch:** `set_theme()` → `theme_changed_signal()`. `MainWindow` reapplies `app_qss`; `MonitorView` removes items, clears curve dicts, `apply_theme()`, `_refresh_charts()`. App-level QSS only — widget `setStyleSheet` wins over the app sheet.
- **Elevation/shadows:** `theme.apply_shadow`. Qt caches the effect (safe under 500ms plot redraws). Re-apply on theme change. Three surfaces: window < panel < card. Overlay uses themed `panel_bg` + `text_primary`, not hardcoded black.
- **`ChartCard`:** header dot + title + live badge + autosize/maximize. `pg.TextItem.anchor` is a **Point, not callable** — use `setAnchor` / `setPos`. A wrong `.anchor((..),(..))` crash shipped once.
- **`CHART_REGISTRY` is the only chart list.** Adding a chart = registry + monitor_view refresh branch + i18n keys. Do not hardcode parallel lists.
- **Reflow:** `_compute_layout` packs visible cards; column count follows viewport width (`clamp(width//340, 1, 4)`). `set_chart_visible` is the only visibility entry (menu / panel / right-click Hide). Persist via `app_config`. GPU charts default hidden when no GPU. Do not reflow while maximized.
- **1080p:** charts live in a scroll area with min card heights. Do not hide charts by default to "fit".
- **DPI:** `configure_high_dpi()` before `QApplication`. `ChartCard.refresh_axis_layout()` after resize / `screenChanged`. Cosmetic 1px axis pens.
- **Visibility panel:** expand/collapse must emit `expanded_changed` so the View menu stays in sync. Expand state is not persisted; per-chart visibility is.
- **System info bar** must refresh even with zero frames (`CaptureSession` writes `system_info` at init).
- **Multicore chart:** lazy per-core curves + bold average. Theme change must clear `_multicore_curves`. Drop curves when core count shrinks.
- **New series:** frametime is `1000/fps` (no EMA); app CPU cores / RAM / GPU power / temp as documented in 03.
- **FPS EMA is render-only.** CSV stays raw.
- **`_prepare_series` skips `None` explicitly.**
- **One overlay per app** (`MainWindow._overlays`). Cached HWND, ~30fps poll, hide on minimize, `shutdown` on close. Copy through `tr()`. Click-through = `WA_TransparentForMouseEvents` (then the overlay context menu is unreachable — View menu is the fallback). F9 sets `set_suppressed`.
- **Stats list configured apps**, not only apps that presented. Idle apps are dimmed + "no frames".
- **ProcessPanel search:** debounce (~250ms) + `setUpdatesEnabled(False)`. Do not filter on every `textChanged` (Windows `QListWidget` relayouts per item).
- **List selection color:** do **not** rely on `selection-background-color` alone (Qt drops it without keyboard focus) or `QPalette::Highlight` (app QSS overrides it). Use `QListWidget::item:selected` **and** `::item:selected:!active` with `t.selection` / `t.selection_text`.
- **Shortcuts (Tier 0):** F5 capture, F9 overlay, Ctrl+D theme, Ctrl+E/I/J/T, F1 shortcuts dialog. Restore geometry **before** `show()`. Zero-frame warning on stop.

## Checklist

- [ ] New chart / interaction → `ChartCard` / mixin + both locales
- [ ] Layout change → check 1920×1080 and a small/secondary screen
- [ ] Colors → theme tokens; new widgets re-theme in `apply_theme`
- [ ] Overlay → cached HWND, minimize hide, `shutdown`, `from src.i18n import tr`
- [ ] Series → DataStore history keyed by `frame.application`

---
last_updated: 2026-09-17
