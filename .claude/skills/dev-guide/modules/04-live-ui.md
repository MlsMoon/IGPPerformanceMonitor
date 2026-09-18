# 04 · Live UI

## Key files

- `src/ui/views/monitor_view.py` — `MonitorView`; `CHART_REGISTRY` grid + stats + inline visibility
- `src/ui/chart_base.py` — `ChartCard`, `ChartViewMixin`, registry, EMA, reflow
- `src/core/app_config.py` — `%APPDATA%/IGPPerformanceMonitor/config.json` (theme, chart visibility, window/splitter, overlay click-through, monitored processes, timed seconds)
- `src/ui/panels/collapsible_section.py` — **the only** expand/collapse shell (chevron + title stay; body hides)
- `src/ui/panels/chart_visibility_panel.py` — chart show/hide chips inside `CollapsibleSection`
- `src/ui/panels/system_info_panel.py` — live system-info rows inside `CollapsibleSection`
- `src/ui/flow_layout.py` — wrapping row layout (system chips + chart-visibility chips)
- `src/ui/theme.py` — `Theme` / DARK / LIGHT, QSS generators, `Crosshair`, `RADIUS_*`. **All colours and corner radii come from here.** Sets `pg antialias=True` at import.
- `src/ui/win_chrome.py` — native (non-client) window theming: DWM dark title bar + caption/text/border colours
- `src/ui/motion.py` — durations, easing, `animate` / `fade_in` / `Transition`. **All animation goes through here.**
- `src/ui/views/overlay_window.py` — per-PID overlay; themed
- `src/ui/panels/process_panel.py` — instance picker (exe + window title + PID); persists `monitored_targets`

## Responsibilities

Live FPS/CPU/GPU/Mem/VRAM charts + stats + overlay; instant dark/light switch.

## Pitfalls

- **Colors only from `src.ui.theme`.** No hardcoded `#xxxxxx`. Accents: `palette()` / `metric_accent`; system curves: `total_cpu` / `total_gpu` / `vram`; semantic: `good` / `warn` / `bad`.
- **Theme switch:** `set_theme()` → `theme_changed_signal()`. `MainWindow` reapplies `app_qss`; `MonitorView` removes items, clears curve dicts, `apply_theme()`, `_refresh_charts()`. App-level QSS only — widget `setStyleSheet` wins over the app sheet.
- **QSS never reaches the title bar.** The non-client area is DWM's, so a dark app shows a white strip on top until `win_chrome.apply_to_widget()` sets `DWMWA_USE_IMMERSIVE_DARK_MODE` (+ Windows 11 caption/text/border colours). `main.py` calls `win_chrome.install(app)`, which themes later windows via `focusWindowChanged` and re-applies on theme change. `setWindowFlags` (always-on-top) **recreates the HWND and drops the attributes** — that is why `MainWindow.showEvent` re-applies. Every call is a silent no-op off Windows.
- **Layout:** `MainWindow._init_ui` only wires `_build_central` / `_build_menu_bar` / `_build_status_bar`; central must be built first because the View menu reads chart state off `MonitorView`. Menu entries go through `_add_action` / `_add_toggle` (toggles are checked **before** `toggled` is connected, so building a menu never fires a slot).
- **Menu text shares one gutter.** View mixes a submenu, plain actions, and checkable toggles. Qt 5.15.2's stylesheet style indents only checkable rows (QTBUG-90242). `_align_mixed_menu` puts a transparent icon on the plain rows so the labels line up. Do not "fix" this with extra `QMenu::item` left padding — that shifts every row and still leaves the delta.
- **Panels must be stretched, not pinned.** `ProcessPanel` gets stretch 1 in the side panel, otherwise the lists sit at their size hint and most of the window height is dead space. Two persisted splitters: `splitter_state` (side vs monitor view) and `stats_charts_splitter_state` (stats vs charts, saved by `MonitorView.save_layout_state` from `MainWindow.closeEvent`).
- **A plain `QLabel` reports its full text width as its minimum.** A long GPU name in the system-info bar used to push the window's real minimum width past 1100 px, ignoring `setMinimumSize(1000, 680)`. `SystemChip` is one **key + value row** (not a flowing pill). The value wraps; it is never elided with `...`. Do not put CPU/GPU/RAM/Display on one row — they squeeze and wrap mid-label. `minimumSizeHint` stays narrow. `build_system_chip_bar` / `populate_system_chip_bar` are shared with the analysis dialog; do not re-inline a copy.
- **Override a size hint's width, never its height.** Labels that compute height from `QFontMetrics` alone drop QSS padding (Qt resolves padding into the contents margins) and clip. `SystemChip` uses `heightForWidth` from the value label. `SystemInfoPanel` is `Preferred` (not `Maximum`) so wrapped rows are not clipped.
- **Long process names** elide (`ElideMiddle` + no horizontal scrollbar); list rows carry the full identity as a tooltip. Duplicate `.exe` names are **one row per PID** (`name  (pid)  —  window title`). Click flashes the window; right-click Switch to. Capture is `--process_id`. Persist `monitored_targets` `{name, title, pid?}` and re-bind by title after restart; keep writing `monitored_processes` as exe names for older builds.
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
- **Reuse collapsible chrome.** `CollapsibleSection` is the only expand/collapse shell. `ChartVisibilityPanel` and `SystemInfoPanel` wrap it. Do not copy another chevron + title. Collapse hides **only the body**; the header (chevron + title) stays. A custom `heightForWidth` that returns `-1` or `0` makes the whole block vanish — the shared class always floors height at the header. Layout snaps; `motion.fade_in` on expand; expand state is not persisted.
- **Visibility panel:** expand/collapse must emit `expanded_changed` so the View menu stays in sync. Per-chart visibility is persisted; expand state is not.
- **System info panel** is `CollapsibleSection` + `build_system_chip_bar`. Keep `MonitorView._sys_info_bar` as the `QFrame` so populate and tests still find it. When nested, `system_bar_qss(..., nested=True)` paints a transparent bar so the panel surface is not doubled.
- **System info bar** must refresh even with zero frames (`CaptureSession` writes `system_info` at init).
- **Multicore chart:** lazy per-core curves + bold average. Theme change must clear `_multicore_curves`. Drop curves when core count shrinks.
- **New series:** frametime is `1000/fps` (no EMA); app CPU cores / RAM / GPU power / temp as documented in 03.
- **FPS EMA is render-only.** CSV stays raw.
- **`_prepare_series` skips `None` explicitly.**
- **One overlay per PID** (`MainWindow._overlays`). Cached HWND, ~30fps poll, hide on minimize, `shutdown` on close. Copy through `tr()`. Click-through = `WA_TransparentForMouseEvents` (then the overlay context menu is unreachable — View menu is the fallback). F9 sets `set_suppressed`. Bind the PID at start so the overlay can park before the first frame.
- **Never hide an overlay with bare `hide()`.** `_update_position` calls `show()` every 33ms for as long as the target window is on screen, so the overlay bounces straight back. Visibility is gated by `_suppressed` (F9) and `_capture_active`; `set_capture_active(False)` stops both timers *and* hides, which is the only thing that sticks.
- **Overlay teardown belongs in `_on_state_changed(False)`, not `_stop_capture`.** The wrapper emits `state_changed(False)` from a `finally`, so it covers the Stop button, `--timed` auto-stop, the target exiting, and a failed launch; `_stop_capture` only covers the button. The *start* direction stays in `_start_capture`, which knows the currently configured PIDs — `_overlays` also holds entries from earlier sessions, and reactivating those resurrects stale overlays.
- **Stats list configured apps**, not only apps that presented. Idle apps are dimmed + "no frames".
- **ProcessPanel search:** debounce (~250ms) + `setUpdatesEnabled(False)`. Do not filter on every `textChanged` (Windows `QListWidget` relayouts per item).
- **List selection color:** do **not** rely on `selection-background-color` alone (Qt drops it without keyboard focus) or `QPalette::Highlight` (app QSS overrides it). Use `QListWidget::item:selected` **and** `::item:selected:!active` with `t.selection` / `t.selection_text`.
- **Shortcuts (Tier 0):** F5 capture, F9 overlay, Ctrl+D theme, Ctrl+E/I/J/T, F1 shortcuts dialog. Restore geometry **before** `show()`. Zero-frame warning on stop.

## Checklist

- [ ] New collapsible region → `CollapsibleSection` (do not fork a third header)
- [ ] Collapse → header still visible; body hidden; height ≥ header
- [ ] New chart / interaction → `ChartCard` / mixin + both locales
- [ ] Layout change → check 1920×1080 and a small/secondary screen
- [ ] Layout change → `minimumSizeHint()` of the window did not grow past `setMinimumSize`
- [ ] New top-level window → title bar themed (covered by `win_chrome.install`)
- [ ] Colors → theme tokens; radii → `RADIUS_*`; new widgets re-theme in `apply_theme`
- [ ] New animation → goes through `motion`, is a micro-interaction (not an entrance), and moves colour/opacity rather than layout
- [ ] Overlay → cached HWND, minimize hide, `shutdown`, `from src.i18n import tr`
- [ ] Overlay visibility → driven by `set_capture_active` / `set_suppressed`, never a bare `hide()`
- [ ] Series → DataStore history keyed by `frame_series_key` (exe + PID)

---
last_updated: 2026-09-18
