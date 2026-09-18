# 05 · Dialogs / offline analysis

## Key files

- `src/ui/dialogs/csv_export.py` — `CsvExportDialog`; header/row/stats helpers
- `src/core/metrics_schema.py` — export header / import aliases / NA formatting
- `src/ui/dialogs/csv_analysis_dialog.py` — offline analysis view
- `src/core/csv_importer.py` — `import_file`, encoding fallback
- `src/core/changelog.py` — locale file (`CHANGELOG.md` / `CHANGELOG.zh-CN.md`), `## X.Y.Z` parser
- `src/ui/dialogs/changelog_dialog.py` — version list + markdown for the current UI locale
- `src/core/user_manual.py` — `docs/` paths, locale folder, heading outline, safe markdown href resolve
- `src/ui/dialogs/user_manual.py` — Help → User Manual (tree of pages + H2/H3…, themed links)
- `src/ui/dialogs/shortcuts_dialog.py` — shortcut table; keep in sync with `main_window._init_ui()`

## Responsibilities

Export CSV (GUI + headless), import for offline analysis, show changelog and the bundled user manual.

## Pitfalls

- **CSV fields change only in `metrics_schema.CSV_COLUMNS`.** Header, `_frame_to_row`, and `COLUMN_MAP_V2` are derived. Do not keep hand-written column lists in export/parser.
- **`write_stats` is module-level** (GUI + headless). The instance method delegates.
- **Missing → `"NA"`** via `is not None` (not `>0`). Keep real 0.
- **Export encoding** is the system default (`open(newline="")` without encoding). Import tries utf-8-sig / gbk / latin-1.
- **Analysis groups by instance** (`group_frames_by_app` uses `frame_series_key`, not Application alone). Two Unity.exe in one CSV become two curves. Filenames must not keep the `|` from the series key.
- **Analysis UI is offline visualization** (summary + Performance / System / Data Quality). It reuses `ChartCard` (theme, crosshair, badges) and `chart_base.build_system_chip_bar`, but **not** the live `ChartViewMixin` grid. The chip bar used to be duplicated here — keep the shared builder.
- **Stutter analysis** (`stutter_analysis.py`) is compute-only. Default thresholds: `>33.3ms`, `>50ms`, `>2×` rolling median (120-frame window, 30-frame baseline). Frame time can be recovered from FPS. Does not change CSV schema.
- **Analysis dialog is modal** — no live theme toggle; each `exec_` builds with the current theme.
- **Imported FPS:** keep the CSV `FPS` column when present; otherwise derive from frame time.
- **Changelog path:** `resource_root()/CHANGELOG.md` (English) or
  `CHANGELOG.zh-CN.md` (`zh_CN`). Frozen = `_MEIPASS`. Missing locale file
  falls back to English. Headings must be exact `## X.Y.Z` (semver only) —
  extra `##` lines show up as fake versions in the left list. Both files must
  list the same versions; the `ui` area errors on drift.
- **Changelog copy is user-facing**, same bar as UI strings: detailed bullets
  with menu paths / before-after, in both languages. GitHub Release notes are
  generated from these files (`Scripts/extract_release_notes.py`), not from
  GitHub auto-notes. Writing rules: `.claude/skills/release/modules/01-prepare.md`.
- **User manual path:** `resource_root()/docs/<locale>/`. UI `zh_CN` → `zh-CN`, everything else → `en`. `resolve_doc_href` must stay inside `docs/` (no `..` escape). Bundle the whole `docs/` tree (`--add-data docs;docs`); do not ship only one language.
- **Manual screenshots** live in `docs/images/<en|zh-CN>/`, grabbed by `python -m src.selfcheck.docs_shots` (staging `temp/docs-shots/`). Relative markdown is `../images/<folder>/shot.png`. The in-app viewer needs `QTextDocument.setBaseUrl` on the page directory plus `searchPaths` that include `docs/` and `docs/images/`; otherwise `QTextBrowser` cannot find `../images/…`. Recapture workflow is the `docs-shots` skill — do not grab these by hand, and do not copy `temp/selfcheck/shots/` into the manual (those are verification grabs, often with the DEV badge). `-t ui` only walks in-app pages (`user-guide.md`, `troubleshooting.md`); README logos that point at `assets/` are GitHub-only and must stay outside that check.
- **Manual nav is a heading tree**, not a flat list. `page_outline` walks ATX headings, skips the document H1 and Contents/目录/目錄/目次. The dialog hides that TOC plus the language-switcher row (`prepare_in_app_markdown`) because the tree already has the structure. Add `###` (and deeper) under the user-guide H2s so the tree can nest.
- **Manual links are theme text**, never Qt's default `#0000FF` and not accent blue. Set `QPalette.Link` / `LinkVisited` and the document stylesheet to `text_muted`. Heading jump targets are a zero-width named anchor — `setAnchor` on the heading itself paints it as an underlined link.
- **Manual selection is a gray wash** (`hover_bg` + `text_primary`) on both the tree and `QTextBrowser`. App QSS gives lists the purple `selection` token and `QTextEdit` the accent-blue `selection-background-color`; widget-level QSS + palette must override both or the reader looks like a highlighter.
- **Manual images must be scaled to the viewport.** `QTextBrowser` will not wrap a 1600px PNG; it clips. After `setMarkdown`, walk `QTextImageFormat` and set width/height from the natural resource size. Refit on viewport resize. Horizontal scrollbar stays off.

## Checklist

- [ ] New enriched field → `metrics_schema` first; run `verify-metrics` roundtrip
- [ ] Stats → module-level `write_stats`
- [ ] Analysis colors go through `src.ui.theme`
- [ ] Import/export encodings stay consistent
- [ ] Shortcut changes update `main_window` **and** `shortcuts_dialog._SHORTCUTS` plus `sc_*` keys
- [ ] New manual page → `user_manual.PAGES` + files under every `docs/<locale>/` + both i18n keys
- [ ] New / changed user-guide screenshot → catalog row in `src/selfcheck/docs_shots.py`, recapture, judge PNGs, `--publish-only`, embed in every locale (ja → `images/en`, zh-TW → `images/zh-CN`)
- [ ] New version → `CHANGELOG.md` **and** `CHANGELOG.zh-CN.md` with the same `## X.Y.Z`

---
last_updated: 2026-09-18
