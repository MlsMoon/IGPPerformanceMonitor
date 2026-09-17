# 01 · Entry and main frame

## Key files

- `src/main.py` — process entry; admin elevation; `--debug` / `--headless`; `run_headless_capture`
- `src/core/capture_session.py` — `CaptureSession`; shared DataStore + wrapper + sampler lifetime
- `src/ui/main_window.py` — menus, overlay, update check, GitHub link, Help → User Manual
- `src/config.py` — intervals, history window, PresentMon path

## Responsibilities

Start the app (GUI or headless), guarantee admin, and let `CaptureSession` own PresentMon + sampler. `MainWindow` owns UI / overlay / menus / updates only.

## Pitfalls

- **Three elevation paths** must stay consistent: `main.py` `relaunch_as_admin()` (`ShellExecuteW runas`), `Scripts/run_dev.bat` (`Start-Process -Verb RunAs`), EXE manifest (`--uac-admin` / `uac_admin=True`).
- **Headless uses `CaptureSession.run_blocking(config)`.** Do not hand-assemble DataStore/wrapper/sampler. Headless must start the sampler or CSV will lack system/process columns (`_enrich_frame` reads `_latest`).
- **GUI start/stop uses `CaptureSession.start/stop`.** The window may connect `session.wrapper` signals and read `session.data_store`, but must not call `wrapper.configure` + `sampler.configure` + `start` itself.
- **Startup update check:** `QTimer.singleShot(1500, self._auto_check_update)`; skip in dev; silent unless an update exists. Source is GitHub Releases (`DEFAULT_APP_MANIFEST_URL`).
- **Window icon:** `setWindowIcon(QIcon(str(_resolve_icon_path())))` → `assets/icon.png` (bundled when frozen). Do not add a menu-bar corner widget.
- **`win_chrome.install(app)` runs right after `setStyle("Fusion")`**, before the first window exists, so dialogs and message boxes get a themed title bar too. Details and the `setWindowFlags` caveat are in `04-live-ui.md`.
- **Menus are built by `_build_file_menu` / `_build_view_menu` / `_build_help_menu`** via the `_add_action` / `_add_toggle` helpers. New shortcuts must also land in `shortcuts_dialog._SHORTCUTS`.
- **`closeEvent`:** stop+wait wrapper and sampler, and `overlay.shutdown()` (otherwise overlays leak). Capture-time overlay hide is `set_capture_active(False)` from `_on_state_changed`, not a bare `hide()` in `_stop_capture`.

## Checklist

- [ ] Startup / elevation changed → verify `run_dev.bat` and the packaged EXE
- [ ] Headless still goes through `CaptureSession`; sampler starts; CSV has system header + stats
- [ ] GUI capture lifetime is only started/stopped by `CaptureSession`
- [ ] `closeEvent` closes overlays and joins worker threads

---
last_updated: 2026-09-17
