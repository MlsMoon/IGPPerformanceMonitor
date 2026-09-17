---
name: dev-guide
description: |
  IGP Performance Monitor development guide (by module). Read the matching
  module note before changing any src/ file: key files, responsibilities,
  pitfalls, and checklists. After a large change, update the module note.
  Triggers: "dev guide", before modifying src/, after large changes, "which module"
---

# Dev Guide — IGP Performance Monitor

This guide is organized by module. **Before changing any `src/` module**, read the matching note in the index below so you do not repeat known pitfalls.

Overview / commands / PresentMon quirks live in root `CLAUDE.md`. This skill is "what to watch when you edit this area".

## Data flow (short)

```
PresentMon --stdout--> CsvParser --> FrameData
  PresentMonWrapper._enrich_frame()  # stamp from SystemMetricsSampler._latest (do not sample here)
  DataStore.add_frame()              # frames + fps/mem/cpu/gpu history (key=frame.application)
    ├─ MonitorView (live ChartCard grid, FPS EMA)
    ├─ CsvExportDialog / --headless
    └─ OverlayWindow
SystemMetricsSampler (QThread, ~500ms) → DataStore snapshots + _latest cache
CaptureSession owns DataStore + wrapper + sampler for GUI and headless
```

## Module index (if you touch X, read Y)

| Change involves | Read first |
|---|---|
| Startup / elevation / headless / menus | `modules/01-entry.md` |
| Capture / sampling / psutil / NVML / PresentMon parse | `modules/02-capture.md` |
| FrameData / fields / snapshots / history / stats | `modules/03-storage.md` |
| Live charts / ChartCard / overlay / process panel / theme | `modules/04-live-ui.md` |
| CSV export/import / offline analysis / changelog | `modules/05-dialogs.md` |
| Version / self-update / auto_updater / GitHub Releases | `modules/06-version-update.md` |
| UI strings / translation | `modules/07-i18n.md` |
| Build / installer / GitHub Release CI | `modules/08-build-release.md` |

Each module note has four sections: **Key files / Responsibilities / Pitfalls / Checklist**.

## Maintenance rules

A **large change** is any of:

- Data-flow semantics or path (sample → store → consume)
- Module interface (`FrameData` / snapshots / `SessionConfig` fields, CSV columns, public signatures)
- A new or fixed pitfall
- A new module or file

After a large change you **must**:

1. Update the matching `modules/0N-*.md` pitfalls or checklist
2. Set `last_updated` at the bottom to today's date
3. If you add/remove a module, update this index and the Key Modules table in `CLAUDE.md`
4. If you touched metric fields, run `verify-metrics`

Project-owned skills stay **English**. UI copy stays bilingual.

> A script cannot write these notes (an LLM has to judge). This rule + `CLAUDE.md` + the Stop hook is the semi-automatic loop.
