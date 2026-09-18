---
name: docs-shots
description: >
  Capture, judge, and publish real-window screenshots for the bundled user
  guide. Use when adding or refreshing user-guide images, docs/images/,
  manual screenshots, 用户手册截图, or running python -m src.selfcheck.docs_shots.
---

# User-guide screenshots

The PNGs in `docs/images/` are **the product**, photographed from the real
Qt window. They are not `temp/selfcheck/shots/` (those are verification
grabs, often with the DEV badge).

Catalog (ids, section numbers, locales) lives in `src/selfcheck/docs_shots.py`
as `SHOTS` + `GUIDE_IMAGE_LOCALE`. Do not keep a second table here.

## When

- User asks to add / refresh user-guide screenshots
- A shot is missing, stale after a layout change, or shows the wrong locale
- You added a `Shot(...)` row and need the PNG + markdown

Skip this for a one-line copy tweak in the guide with no UI change.

## Do not

- Copy `temp/selfcheck/shots/` into `docs/images/`
- `--publish` / `--publish-only` before you have **opened every new PNG**
- Invent process names or frames. Charts come from `temp/real_capture.csv`
- Dump the live machine process list (personal / in-progress titles leak)
- Show the DEV badge or `window_title_dev`
- Hand-crop in an editor as the source of truth — change the pose, recapture

## Commands

```bat
python -m src.selfcheck.docs_shots --list
python -m src.selfcheck.docs_shots
python -m src.selfcheck.docs_shots --only main-window,overlay --locale en
python -m src.selfcheck.docs_shots --publish-only
```

`Scripts\docs_shots.bat` is the same entry. No admin. Needs a real capture
already on disk (`temp/real_capture.csv`). If that file is missing, generate
it elevated:

```bat
Scripts\capture_debug.bat --process-name Unity.exe --timed 10 -o temp\real_capture.csv
```

Do not run unelevated `python -m src.main --headless` from an agent and wait
on UAC — `ShellExecuteW("runas")` blocks on the consent dialog.

Staging: `temp/docs-shots/<en|zh-CN>/<id>.png` (gitignored).
Published: `docs/images/<en|zh-CN>/<id>.png` (committed, bundled with `docs/`).

## Workflow

```
Task progress:
- [ ] Catalog: existing Shot row, or add one (id, section, kind)
- [ ] Capture to temp/docs-shots (never --publish yet)
- [ ] Open every new PNG at native size
- [ ] Fix pose / recapture until the judge list is clean
- [ ] --publish-only
- [ ] Embed in every locale of user-guide.md
- [ ] python -m src.main -t ui   (markdown image refs + manual dialog)
```

### Judge list (every PNG)

- Locale chrome matches the folder (`en` vs `zh-CN`)
- No DEV badge, no `DEV` window title
- Charts have a curve (empty session = missing `real_capture.csv`)
- Overlay FPS is plausible (about 15–240), not a 20k spike
- Process lists are capture identities (`Name  (pid)`), not this machine's
  Clash / 飞书 / project window titles
- Search box has no caret / focus ring
- Status bar and Start/Stop agree (picker pose = Start; live pose = Stop)
- Nothing you would not put on GitHub

The script already: sandboxes `%APPDATA%`, parks windows off-screen, hides
DEV chrome, filters compositor presenters (`dwm.exe`, …), seeds process rows
from the capture (not `list_process_instances`), and picks a median-ish
overlay frame.

### Markdown

Path from `docs/<guide>/user-guide.md`:

```
../images/en/<id>.png      en and ja
../images/zh-CN/<id>.png   zh-CN and zh-TW
```

`![]()` only — the in-app `QTextBrowser` resolves `../images/…` via
`setBaseUrl` on the page directory. Place the figure after the section's
opening paragraph (or after the numbered first-capture steps). Alt text is
localized; ja/zh-TW may add one line that the UI screenshot is English /
Simplified Chinese.

Do not auto-rewrite the guides from the script. The agent writes the
markdown after judging.

### After publish

`python -m src.main -t ui` — the ui area walks `![]()` / `<img>` in `docs/`
and errors on a missing file or a path that escapes `docs/`. That is the
check. Recapture is this skill, not a new `*_area.py`.

## Add a shot

1. Append a `Shot("id", section, "kind")` in `SHOTS`
2. Implement `kind` in `_capture_locale` (or reuse `main` / `overlay` / …)
3. Recapture `--only id`, judge, `--publish-only`
4. Embed in all four `user-guide.md` files
5. If the pose taught a new pitfall, add it to this list and to
   `dev-guide/modules/05-dialogs.md`
