"""Pose the real window and grab user-manual screenshots.

Staging writes ``temp/docs-shots/<docs-locale>/<id>.png``. Nothing in
``docs/images/`` is touched until ``--publish-only`` (or ``--publish`` after a
capture). An agent must open the PNGs and judge them before publishing — the
script does not.

    python -m src.selfcheck.docs_shots
    python -m src.selfcheck.docs_shots --only main-window,overlay --locale en
    python -m src.selfcheck.docs_shots --publish-only

This is not a self-check area. Image *references* in the markdown are checked
by ``-t ui``.
"""

from __future__ import annotations

import argparse
import json
import os
import shutil
import sys
from collections import Counter
from dataclasses import dataclass
from pathlib import Path

from src.core.process_list import ProcessInstance
from src.core.user_manual import docs_root, locale_folder
from src.i18n import set_locale, tr
from src.models import frame_series_key
from src.selfcheck import data
from src.selfcheck.replay import SETTLE_MS, seed_window, spin
from src.ui.panels.process_panel import _process_item

# UI locale -> docs/images/<folder>
_DOCS_LOCALE = {
    "en": "en",
    "zh_CN": "zh-CN",
}

# Guides that have no matching UI reuse another locale's shots.
GUIDE_IMAGE_LOCALE = {
    "en": "en",
    "zh-CN": "zh-CN",
    "zh-TW": "zh-CN",
    "ja": "en",
}

_MAIN_SIZE = (1280, 800)
_ANALYSIS_SIZE = (1200, 780)
_MAX_WIDTH = 1600
_MAX_HEIGHT = 1100
_PARK = (-8000, -8000)
_TOP_APPS = 3
# Compositor / helper presenters make FPS charts unreadable and are not
# what the user-guide is documenting. Still real frames — just not these.
_NOISE_EXES = frozenset({
    "dwm.exe", "msedgewebview2.exe", "textinputhost.exe",
    "searchapp.exe", "searchhost.exe", "shellexperiencehost.exe",
    "startmenuexperiencehost.exe", "explorer.exe",
})


@dataclass(frozen=True)
class Shot:
    """One committed user-guide screenshot.

    *section* is the user-guide H2 number (English headings in the skill).
    *kind* selects the pose. The catalog in this file is the list — do not
    keep a parallel table in markdown.
    """

    id: str
    section: int
    kind: str
    theme: str = "dark"
    locales: tuple[str, ...] = ("en", "zh_CN")


# Add a row here, then recapture, judge, publish, and embed in every locale.
SHOTS: tuple[Shot, ...] = (
    Shot("main-window", 4, "main"),
    Shot("process-panel", 3, "process_panel"),
    Shot("charts-panel", 6, "charts_panel"),
    Shot("overlay", 7, "overlay"),
    Shot("export-csv", 9, "export"),
    Shot("csv-analysis", 10, "analysis"),
    Shot("theme-light", 8, "light", theme="light"),
)


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


def _staging_root(out: Path | None = None) -> Path:
    return out or (_repo_root() / "temp" / "docs-shots")


def _published_dir(docs_locale: str) -> Path:
    return docs_root() / "images" / docs_locale


def _shot_path(root: Path, docs_locale: str, shot_id: str) -> Path:
    return root / docs_locale / f"{shot_id}.png"


def _park(widget) -> None:
    widget.move(*_PARK)
    widget.show()
    spin(SETTLE_MS)


def _save(widget, path: Path) -> dict:
    spin(SETTLE_MS)
    pix = widget.grab()
    if pix.isNull() or pix.width() < 8 or pix.height() < 8:
        raise RuntimeError(f"grab produced an empty pixmap for {path.name}")
    from PyQt5.QtCore import Qt
    if pix.width() > _MAX_WIDTH:
        pix = pix.scaledToWidth(_MAX_WIDTH, Qt.SmoothTransformation)
    if pix.height() > _MAX_HEIGHT:
        pix = pix.scaledToHeight(_MAX_HEIGHT, Qt.SmoothTransformation)
    path.parent.mkdir(parents=True, exist_ok=True)
    if not pix.save(str(path), "PNG"):
        raise RuntimeError(f"failed to write {path}")
    return {
        "path": str(path),
        "width": pix.width(),
        "height": pix.height(),
        "bytes": path.stat().st_size,
    }


def _defocus(window) -> None:
    """Search box otherwise keeps a caret and a focus ring in the grab."""
    window._process_panel._search_input.clearFocus()
    window.setFocus()


def _hide_dev_chrome(window) -> None:
    """User-facing shots must not show the source-tree DEV badge."""
    window.setWindowTitle(tr("window_title"))
    if window._dev_badge is not None:
        window._dev_badge.hide()


def _guide_frames(frames):
    """Drop compositor/helper presenters so the charts read as a user session."""
    cleaned = [
        f for f in frames
        if (f.application or "").lower() not in _NOISE_EXES
    ]
    return cleaned or list(frames)


def _instances_from_frames(frames, limit: int | None = None) -> list[ProcessInstance]:
    """Identity-only rows from the capture. No live window titles (those are local)."""
    counts = Counter(
        frame_series_key(f) for f in frames if f.application or f.process_id
    )
    items = counts.most_common(limit) if limit else counts.most_common()
    out: list[ProcessInstance] = []
    for key, _n in items:
        name, pid = key, 0
        if "|" in key:
            name, _, pid_s = key.rpartition("|")
            if pid_s.isdigit():
                pid = int(pid_s)
        out.append(ProcessInstance(pid=pid, name=name, title=""))
    return out


def _seed_process_lists(window, frames) -> None:
    """Monitored = busiest captured apps; Available = the rest of that capture.

    The live machine list is not used: a developer desktop would publish
    unrelated (and sometimes personal) process names.
    """
    monitored = _instances_from_frames(frames, limit=_TOP_APPS)
    chosen = {(t.name.lower(), t.pid) for t in monitored}
    rest = [
        inst for inst in _instances_from_frames(frames)
        if (inst.name.lower(), inst.pid) not in chosen
    ]
    panel = window._process_panel
    panel._targets = monitored
    panel._rebuild_monitored_list()
    panel._available_list.clear()
    for inst in rest[:12]:
        panel._available_list.addItem(_process_item(inst))


def _pose_picker(window, frames) -> None:
    """First-capture layout: one monitored app, the others still available, Start."""
    _hide_dev_chrome(window)
    instances = _instances_from_frames(frames)
    unity = next((i for i in instances if i.name.lower() == "unity.exe"), None)
    monitored = [unity] if unity is not None else instances[:1]
    rest = [i for i in instances if i not in monitored]
    panel = window._process_panel
    panel._targets = list(monitored)
    panel._rebuild_monitored_list()
    panel._available_list.clear()
    for inst in rest:
        panel._available_list.addItem(_process_item(inst))
    panel.set_capture_state(False)
    window._status_label.setText(tr("status_ready_hint"))
    window.resize(*_MAIN_SIZE)
    window._splitter.setSizes([340, _MAIN_SIZE[0] - 340])
    _defocus(window)


def _dress_live(window, frames, span: float) -> None:
    """Look like a running session: Stop button, capturing status, charts filled."""
    import time

    _hide_dev_chrome(window)
    _seed_process_lists(window, frames)
    window._process_panel.set_capture_state(True)
    window._status_label.setText(tr("status_capture_running"))
    count = window._data_store.get_frame_count()
    window._status_bar.showMessage(tr("status_capturing", count, span))
    # Export dialog reads wall-clock elapsed; align it with the replayed span.
    window._data_store._session_start_time = time.time() - max(span, 1.0)
    window._monitor_view.set_system_info_expanded(True)
    window._monitor_view.set_visibility_panel_expanded(False)
    window.resize(*_MAIN_SIZE)
    window._monitor_view.refresh_display_layout()
    window._splitter.setSizes([340, _MAIN_SIZE[0] - 340])
    _defocus(window)


def _best_frame(frames):
    """A typical overlay sample — not the max-FPS spike PresentMon can emit."""
    def plausible(frame) -> bool:
        fps = frame.fps
        ft = frame.ms_between_presents
        if fps is None or not (15.0 <= fps <= 240.0):
            return False
        if ft is None or ft < 2.0:
            return False
        if (frame.application or "").lower() in _NOISE_EXES:
            return False
        return True

    good = [f for f in frames if plausible(f)]
    if not good:
        good = [
            f for f in frames
            if f.fps is not None and 15.0 <= f.fps <= 400.0
        ]
    if not good:
        return frames[-1] if frames else None
    unity = [f for f in good if (f.application or "").lower() == "unity.exe"]
    pool = unity or good
    return pool[len(pool) // 2]


def _close(widget) -> None:
    widget.close()
    widget.deleteLater()
    spin(50)


def _capture_locale(locale: str, frames, wanted: set[str], staging: Path) -> list[dict]:
    from PyQt5.QtWidgets import QTabWidget

    from src.core.csv_importer import import_file
    from src.ui.dialogs.csv_analysis_dialog import CsvAnalysisDialog
    from src.ui.dialogs.csv_export import CsvExportDialog
    from src.ui.main_window import MainWindow
    from src.ui.views.overlay_window import OverlayWindow
    from src.ui import theme

    set_locale(locale)
    docs_loc = _DOCS_LOCALE[locale]
    written: list[dict] = []

    theme.set_theme("dark")
    spin(SETTLE_MS)
    window = MainWindow()
    span = seed_window(window, frames)
    _park(window)

    def take(shot_id: str, widget) -> None:
        if shot_id not in wanted:
            return
        info = _save(widget, _shot_path(staging, docs_loc, shot_id))
        info.update({"id": shot_id, "locale": locale, "docs_locale": docs_loc})
        written.append(info)
        print(f"  wrote {docs_loc}/{shot_id}.png  {info['width']}x{info['height']}")

    if "process-panel" in wanted:
        _pose_picker(window, frames)
        spin(SETTLE_MS)
        take("process-panel", window._process_panel)

    _dress_live(window, frames, span)
    spin(SETTLE_MS)
    take("main-window", window)

    if "charts-panel" in wanted:
        window._monitor_view.set_visibility_panel_expanded(True)
        window._monitor_view.refresh_display_layout()
        spin(SETTLE_MS)
        take("charts-panel", window)
        window._monitor_view.set_visibility_panel_expanded(False)

    if "overlay" in wanted:
        frame = _best_frame(frames)
        overlay = OverlayWindow(frame.application if frame else "app.exe")
        if frame is not None:
            overlay.update_frame(frame)
            overlay._refresh_display()
        overlay.adjustSize()
        _park(overlay)
        take("overlay", overlay)
        overlay.shutdown()

    if "export-csv" in wanted:
        export = CsvExportDialog(window._data_store)
        export.adjustSize()
        _park(export)
        take("export-csv", export)
        _close(export)

    if "csv-analysis" in wanted:
        result = import_file(data.ensure_real_capture())
        result.frames = list(frames)
        result.monitored_apps = sorted({
            f.application for f in frames if f.application
        })
        result.file_path = "igpmon-session.csv"
        analysis = CsvAnalysisDialog(result)
        analysis.resize(*_ANALYSIS_SIZE)
        tabs = analysis.findChild(QTabWidget)
        if tabs is not None:
            tabs.setCurrentIndex(0)
        _park(analysis)
        take("csv-analysis", analysis)
        _close(analysis)

    if "theme-light" in wanted:
        theme.set_theme("light")
        spin(SETTLE_MS)
        window._monitor_view.refresh_display_layout()
        spin(SETTLE_MS)
        take("theme-light", window)
        theme.set_theme("dark")

    _close(window)
    return written


def capture(staging: Path, *, only: set[str] | None, locales: list[str]) -> list[dict]:
    frames = _guide_frames(data.load_real_frames())
    if not frames:
        raise SystemExit(
            "docs shots need a real capture (charts would be empty).\n"
            + data.MISSING_MSG
        )
    wanted = {s.id for s in SHOTS}
    if only:
        unknown = only - wanted
        if unknown:
            raise SystemExit(f"unknown shot id(s): {', '.join(sorted(unknown))}")
        wanted = only
    catalog = [s for s in SHOTS if s.id in wanted]
    written: list[dict] = []
    print(f"frames: {len(frames)}")
    print(f"staging: {staging}")
    for locale in locales:
        need = {s.id for s in catalog if locale in s.locales}
        if not need:
            continue
        print(f"\nlocale {locale} ({locale_folder(locale)})")
        written.extend(_capture_locale(locale, frames, need, staging))
    manifest = staging / "manifest.json"
    manifest.write_text(json.dumps(written, indent=2), encoding="utf-8")
    print(f"\nmanifest: {manifest}")
    print(f"shots: {len(written)}")
    return written


def publish(staging: Path) -> list[Path]:
    if not staging.is_dir():
        raise SystemExit(f"staging folder missing: {staging}")
    copied: list[Path] = []
    for locale_dir in staging.iterdir():
        if not locale_dir.is_dir():
            continue
        dest_dir = _published_dir(locale_dir.name)
        dest_dir.mkdir(parents=True, exist_ok=True)
        for png in sorted(locale_dir.glob("*.png")):
            dest = dest_dir / png.name
            shutil.copy2(png, dest)
            copied.append(dest)
            print(f"  published {dest.relative_to(docs_root())}")
    if not copied:
        raise SystemExit(f"no PNGs under {staging}")
    print(f"published: {len(copied)}")
    return copied


def _print_catalog() -> None:
    print("id               section  kind            theme  locales")
    for shot in SHOTS:
        print(
            f"{shot.id:<16} {shot.section:<8} {shot.kind:<15} "
            f"{shot.theme:<6} {','.join(shot.locales)}"
        )
    print("\nGuide image folders (no extra UI locales):")
    for guide, folder in GUIDE_IMAGE_LOCALE.items():
        print(f"  docs/{guide}/user-guide.md  ->  ../images/{folder}/")


def _parse_only(raw: str | None) -> set[str] | None:
    if not raw:
        return None
    return {part.strip() for part in raw.split(",") if part.strip()}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Grab user-manual screenshots from the real window.")
    parser.add_argument("--list", action="store_true", help="print the shot catalog")
    parser.add_argument("--only", help="comma-separated shot ids")
    parser.add_argument("--locale", help="en and/or zh_CN, comma-separated")
    parser.add_argument("--out", type=Path, help="staging folder (default temp/docs-shots)")
    parser.add_argument("--publish", action="store_true",
                        help="capture, then copy staging to docs/images/")
    parser.add_argument("--publish-only", action="store_true",
                        help="copy staging to docs/images/ without recapturing")
    args = parser.parse_args(argv)

    if args.list:
        _print_catalog()
        return 0

    staging = _staging_root(args.out)

    if args.publish_only:
        publish(staging)
        return 0

    locales = ["en", "zh_CN"]
    if args.locale:
        locales = [part.strip() for part in args.locale.split(",") if part.strip()]
        unknown = [loc for loc in locales if loc not in _DOCS_LOCALE]
        if unknown:
            raise SystemExit(f"unknown locale(s): {', '.join(unknown)} (en, zh_CN)")

    from src import selfcheck
    selfcheck._start_qt()

    capture(staging, only=_parse_only(args.only), locales=locales)
    if args.publish:
        publish(staging)
    else:
        print("\nJudge the PNGs, then:  python -m src.selfcheck.docs_shots --publish-only")
    return 0


if __name__ == "__main__":
    # Avoid a GBK console eating the paths.
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8", errors="replace")
        except (AttributeError, OSError):
            pass
    os.chdir(_repo_root())
    raise SystemExit(main())
