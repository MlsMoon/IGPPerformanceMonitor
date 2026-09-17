# Troubleshooting

[English](README.md) · [简体中文](../zh-CN/troubleshooting.md) · [繁體中文](../zh-TW/troubleshooting.md) · [日本語](../ja/troubleshooting.md)

Companion to the [user guide](user-guide.md).

## Administrator / “Access denied”

PresentMon needs ETW. If elevation fails:

- Right-click the EXE → **Run as administrator**
- Or add your account to **Performance Log Users** (Computer Management → Local Users and Groups → Groups), then sign out and back in
- Group Policy or antivirus can block `ShellExecuteW("runas")`. Run from an already-elevated Command Prompt

The packaged EXE declares `requireAdministrator`. The Python entry and `Scripts\run_dev.bat` relaunch with UAC.

## No frames captured

The stop dialog means PresentMon ran but no presents were parsed.

- Process name must match the presenter (`game.exe`, not the store launcher)
- The app must be **rendering**. A minimized Unity editor or a service will not produce frames
- Click **Refresh Process List** after the game starts
- Full-screen exclusive titles: try borderless window if the session stays empty
- Headless: read `temp\igp_debug.log` for PresentMon stderr

## GPU / VRAM / power / temp are empty

Those series need an NVIDIA backend (NVML, or GPUtil wrapping `nvidia-smi`).

- Install a current Game Ready / Studio driver
- AMD and Intel GPUs still get FPS and frame time from PresentMon
- On machines with no GPU backend, those charts start hidden — show them from View → Charts if you later install a driver
- Per-process GPU can briefly read **higher than** total GPU. That is two different NVIDIA APIs, not a bug in the chart

Blank cells are missing samples (`None`), not zero.

## Overlay is missing or on the wrong window

- Capture must be running; overlays hide when you stop
- **F9** may have suppressed them
- The tracker uses the **largest** visible titled window. A tiny always-on-top tool window is ignored
- Multi-window apps (Unity Editor, browsers): the overlay follows the largest panel
- Minimized targets hide the overlay until restored

## Cannot click the overlay

**View → Click-through** sends mouse events to the game. Right-click on the overlay then does nothing. Turn click-through off from the View menu, or use **F9** to hide overlays.

## Self-update does nothing / “dev mode”

Help → Check for Updates only works in the **frozen EXE**. `python -m src.main` always reports dev mode.

If a packaged check fails: network, GitHub outage, or a corporate proxy that blocks `github.com`. Downloads must send a normal browser User-Agent (the app already does).

Rollback needs a previous version stored from an earlier update. A first install has nothing to roll back to.

## Wrong UI language

There is no language item in the menus.

```bat
set IGP_LANG=en
set IGP_LANG=zh_CN
```

A Windows locale that starts with `zh` selects Simplified Chinese. Traditional Chinese Windows still maps to `zh_CN` in the UI. `docs/zh-TW/` is documentation only.

Restart the app after changing `IGP_LANG`.

## Charts disappeared

Visibility is persisted. **View → Charts** or **Ctrl+J** and tick the cards again. Maximize one card hides the others until you restore it.

## Window too narrow / names cut off

Long GPU and process names are **elided** on purpose so the window stays near 1000×680. Hover the chip or list row for the full string.

## High overhead / noisy capture

Do not monitor the entire machine in the GUI. Use a short explicit list. `--all-processes` is for short headless captures only.

Unlocked-FPS games look jumpy in raw FPS; the live chart EMA is cosmetic. Use frame time or 1% low for hitching.

## Title bar is white in dark mode

Fixed in current builds: the app themes the DWM title bar and re-applies it after Always on Top (that flag recreates the HWND). If you still see a white strip, you are on an old build — update from GitHub Releases.

## Headless from a non-admin agent produced no files

`python -m src.main --headless` relaunches via UAC. The elevated process does not inherit the original console, so output can vanish. Use `Scripts\capture_debug.bat`, which self-elevates and still writes `temp\`.

## Still stuck

1. Help → About — note version and build (`yyyyMMdd-HHmmss-gitsha`)
2. Reproduce with `--debug` and attach `temp\igp_debug.log`
3. Open an issue on [GitHub](https://github.com/MlsMoon/IGPPerformanceMonitor/issues)

Security reports: do not file a public issue. Use [SECURITY.md](../../SECURITY.md).
