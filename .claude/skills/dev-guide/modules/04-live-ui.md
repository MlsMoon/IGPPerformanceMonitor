# 04 · Live UI

## Key files

- `src/ui/views/monitor_view.py` — `MonitorView`; `CHART_REGISTRY` grid + stats + inline visibility
- `src/ui/chart_base.py` — `ChartCard`, `ChartViewMixin`, registry, EMA, reflow
- `src/core/app_config.py` — `%APPDATA%/IGPPerformanceMonitor/config.json` (theme, chart visibility, window/splitter, overlay click-through, monitored processes, timed seconds)
- `src/ui/panels/chart_visibility_panel.py` — collapsible show/hide chips
- `src/ui/theme.py` — `Theme` / DARK / LIGHT, QSS generators, `Crosshair`, `RADIUS_*`. **All colours and corner radii come from here.** Sets `pg antialias=True` at import.
- `src/ui/win_chrome.py` — native (non-client) window theming: DWM dark title bar + caption/text/border colours
- `src/ui/motion.py` — durations, easing, `animate` / `fade_in` / `Transition`. **All animation goes through here.**
- `src/ui/views/overlay_window.py` — per-app overlay; themed
- `src/ui/panels/process_panel.py` — process picker; persists monitored list + timer

## Responsibilities

Live FPS/CPU/GPU/Mem/VRAM charts + stats + overlay; instant dark/light switch.

## Pitfalls

- **Colors only from `src.ui.theme`.** No hardcoded `#xxxxxx`. Accents: `palette()` / `metric_accent`; system curves: `total_cpu` / `total_gpu` / `vram`; semantic: `good` / `warn` / `bad`.
- **Theme switch:** `set_theme()` → `theme_changed_signal()`. `MainWindow` reapplies `app_qss`; `MonitorView` removes items, clears curve dicts, `apply_theme()`, `_refresh_charts()`. App-level QSS only — widget `setStyleSheet` wins over the app sheet.
- **QSS never reaches the title bar.** The non-client area is DWM's, so a dark app shows a white strip on top until `win_chrome.apply_to_widget()` sets `DWMWA_USE_IMMERSIVE_DARK_MODE` (+ Windows 11 caption/text/border colours). `main.py` calls `win_chrome.install(app)`, which themes later windows via `focusWindowChanged` and re-applies on theme change. `setWindowFlags` (always-on-top) **recreates the HWND and drops the attributes** — that is why `MainWindow.showEvent` re-applies. Every call is a silent no-op off Windows.
- **Layout:** `MainWindow._init_ui` only wires `_build_central` / `_build_menu_bar` / `_build_status_bar`; central must be built first because the View menu reads chart state off `MonitorView`. Menu entries go through `_add_action` / `_add_toggle` (toggles are checked **before** `toggled` is connected, so building a menu never fires a slot).
- **Panels must be stretched, not pinned.** `ProcessPanel` gets stretch 1 in the side panel, otherwise the lists sit at their size hint and most of the window height is dead space. Two persisted splitters: `splitter_state` (side vs monitor view) and `stats_charts_splitter_state` (stats vs charts, saved by `MonitorView.save_layout_state` from `MainWindow.closeEvent`).
- **A plain `QLabel` reports its full text width as its minimum.** A long GPU name in the system-info bar used to push the window's real minimum width past 1100 px, ignoring `setMinimumSize(1000, 680)`. Chips are `chart_base.SystemChip` — natural width as the size hint, `_MIN_WIDTH` as the minimum, elided text plus a full-value tooltip. `build_system_chip_bar` / `populate_system_chip_bar` are shared with the analysis dialog; do not re-inline a copy.
- **Override a size hint's width, never its height.** `SystemChip` computed height from `QFontMetrics` and lost the 8px the stylesheet's `padding` contributes (Qt resolves QSS padding into the contents margins), so every chip clipped its own text. Take the height from `super().sizeHint()`. The width also carries `_SLACK` — font advances are a hair narrower than the painted glyphs, and sizing to the advance exactly shears a column off the last character.
- **Long process names** elide (`ElideMiddle` + no horizontal scrollbar); list rows carry the full name as a tooltip (`_process_item`).
- **Flat by construction: no shadows, no outlines on surfaces.** Depth is three background tints (window < panel < card), not elevation. `apply_shadow` is gone — do not reintroduce a `QGraphicsDropShadowEffect`.
- **Corner radii come from the `RADIUS_*` scale** (`SURFACE` 6 / `CARD` 6 / `CONTROL` 4 / `CHIP` 3), never a literal `border-radius: Npx`. The ceiling is deliberate and enforced by `test_theme`: this is a dense tool UI in Grafana/Linear territory (2–6px), not a content site (Geist's 8–12px). Only genuine circles (the header dot) hardcode a radius.
- **Count rounded shapes, not just their radius.** The stats readout is one `QFrame#StatsList` with `StatsRow` hairline-separated children, because ten stacked rounded tiles read as a column of blobs. Only the bottom row (`StatsRowLast`) drops its separator, so no hairline lands on the container's rounded edge.
- **Motion budget: micro-interactions only.** This is a high-frequency tool, so there are **no entrance animations** — not for the window, charts, stats or tables. `motion.FAST` (90ms) is hover/press feedback and must stay inside the ~100ms reaction window; `motion.NORMAL` (160ms) is a region appearing. Exits use `motion.exit_duration` (75%) and `CURVE_EXIT`; symmetric motion reads as sluggish. `Transition.to` picks the direction automatically.
- **Never animate a layout property.** The chip panel used to animate `maximumHeight`, which re-ran the flow layout every frame and dragged the charts below it up and down. The layout snaps; only opacity moves (`motion.fade_in`, which drops its `QGraphicsOpacityEffect` when done — leaving it on forces an offscreen pixmap per repaint).
- **`ChartCard` paints its own surface** (`paintEvent` + `motion.Transition`) because QSS has no transitions. Hover shifts the fill colour and nothing else: no underline, glow or lift. Anything that grows or slides on a surface hovered this often is decoration.
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
- **Never hide an overlay with bare `hide()`.** `_update_position` calls `show()` every 33ms for as long as the target window is on screen, so the overlay bounces straight back. Visibility is gated by `_suppressed` (F9) and `_capture_active`; `set_capture_active(False)` stops both timers *and* hides, which is the only thing that sticks.
- **Overlay teardown belongs in `_on_state_changed(False)`, not `_stop_capture`.** The wrapper emits `state_changed(False)` from a `finally`, so it covers the Stop button, `--timed` auto-stop, the target exiting, and a failed launch; `_stop_capture` only covers the button. The *start* direction stays in `_start_capture`, which knows the currently configured apps — `_overlays` also holds entries from earlier sessions, and reactivating those resurrects stale overlays.
- **Stats list configured apps**, not only apps that presented. Idle apps are dimmed + "no frames".
- **ProcessPanel search:** debounce (~250ms) + `setUpdatesEnabled(False)`. Do not filter on every `textChanged` (Windows `QListWidget` relayouts per item).
- **List selection color:** do **not** rely on `selection-background-color` alone (Qt drops it without keyboard focus) or `QPalette::Highlight` (app QSS overrides it). Use `QListWidget::item:selected` **and** `::item:selected:!active` with `t.selection` / `t.selection_text`.
- **Shortcuts (Tier 0):** F5 capture, F9 overlay, Ctrl+D theme, Ctrl+E/I/J/T, F1 shortcuts dialog. Restore geometry **before** `show()`. Zero-frame warning on stop.

## Checklist

- [ ] New chart / interaction → `ChartCard` / mixin + both locales
- [ ] Layout change → check 1920×1080 and a small/secondary screen
- [ ] Layout change → `minimumSizeHint()` of the window did not grow past `setMinimumSize`
- [ ] New top-level window → title bar themed (covered by `win_chrome.install`)
- [ ] Colors → theme tokens; radii → `RADIUS_*`; new widgets re-theme in `apply_theme`
- [ ] New animation → goes through `motion`, is a micro-interaction (not an entrance), and moves colour/opacity rather than layout
- [ ] Overlay → cached HWND, minimize hide, `shutdown`, `from src.i18n import tr`
- [ ] Overlay visibility → driven by `set_capture_active` / `set_suppressed`, never a bare `hide()`
- [ ] Series → DataStore history keyed by `frame.application`

---
last_updated: 2026-09-17
