# 05 · Dialogs / offline analysis

## Key files

- `src/ui/dialogs/csv_export.py` — `CsvExportDialog`; header/row/stats helpers
- `src/core/metrics_schema.py` — export header / import aliases / NA formatting
- `src/ui/dialogs/csv_analysis_dialog.py` — offline analysis view
- `src/core/csv_importer.py` — `import_file`, encoding fallback
- `src/ui/dialogs/changelog_dialog.py` — renders `CHANGELOG.md` (`## X.Y.Z` blocks)
- `src/ui/dialogs/shortcuts_dialog.py` — shortcut table; keep in sync with `main_window._init_ui()`

## Responsibilities

Export CSV (GUI + headless), import for offline analysis, show changelog.

## Pitfalls

- **CSV fields change only in `metrics_schema.CSV_COLUMNS`.** Header, `_frame_to_row`, and `COLUMN_MAP_V2` are derived. Do not keep hand-written column lists in export/parser.
- **`write_stats` is module-level** (GUI + headless). The instance method delegates.
- **Missing → `"NA"`** via `is not None` (not `>0`). Keep real 0.
- **Export encoding** is the system default (`open(newline="")` without encoding). Import tries utf-8-sig / gbk / latin-1.
- **Analysis UI is offline visualization** (summary + Performance / System / Data Quality). It reuses `ChartCard` (theme, crosshair, badges) and `chart_base.build_system_chip_bar`, but **not** the live `ChartViewMixin` grid. The chip bar used to be duplicated here — keep the shared builder.
- **Stutter analysis** (`stutter_analysis.py`) is compute-only. Default thresholds: `>33.3ms`, `>50ms`, `>2×` rolling median (120-frame window, 30-frame baseline). Frame time can be recovered from FPS. Does not change CSV schema.
- **Analysis dialog is modal** — no live theme toggle; each `exec_` builds with the current theme.
- **Imported FPS:** keep the CSV `FPS` column when present; otherwise derive from frame time.
- **Changelog path:** `resource_root()/CHANGELOG.md` (frozen = `_MEIPASS`).

## Checklist

- [ ] New enriched field → `metrics_schema` first; run `verify-metrics` roundtrip
- [ ] Stats → module-level `write_stats`
- [ ] Analysis colors go through `src.ui.theme`
- [ ] Import/export encodings stay consistent
- [ ] Shortcut changes update `main_window` **and** `shortcuts_dialog._SHORTCUTS` plus `sc_*` keys

---
last_updated: 2026-09-17
