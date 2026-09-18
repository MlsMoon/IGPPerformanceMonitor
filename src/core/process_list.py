"""Running-process identity: one row per PID, Task Manager-style window titles.

The process picker used to list unique ``.exe`` names, so two Unity Editors
collapsed into one ``Unity.exe``. PresentMon can target ``--process_id``, and
the main window of each instance already carries the project name. This module
enumerates instances, formats the list label, and can flash / switch-to that
window the way Task Manager's Apps list does.
"""

from __future__ import annotations

import ctypes
import logging
from ctypes import wintypes
from dataclasses import dataclass

import psutil
import win32con
import win32gui
import win32process

logger = logging.getLogger(__name__)

FLASHW_ALL = 3
FLASHW_TIMERNOFG = 12


class FLASHWINFO(ctypes.Structure):
    _fields_ = [
        ("cbSize", wintypes.UINT),
        ("hwnd", wintypes.HWND),
        ("dwFlags", wintypes.DWORD),
        ("uCount", wintypes.UINT),
        ("dwTimeout", wintypes.DWORD),
    ]


@dataclass
class ProcessInstance:
    """One OS process the user can pick, flash, and capture."""

    pid: int
    name: str
    title: str = ""
    exe_path: str = ""
    # Legacy config: monitor every PID of this exe (``--process_name``).
    name_wide: bool = False

    def list_label(self) -> str:
        """Row text. Prefer the window title (Task Manager Apps) plus PID."""
        useful = _useful_title(self.title, self.name)
        if useful and self.pid:
            return f"{self.title.strip()}  ({self.pid})"
        if useful:
            return self.title.strip()
        if self.pid:
            return f"{self.name}  ({self.pid})"
        return self.name

    def compact_label(self) -> str:
        """Shorter label for overlays, stats chips, and chart legends."""
        return format_instance_label(
            self.name, self.pid, self.title, compact=True)

    def search_blob(self) -> str:
        return " ".join(
            (self.name, str(self.pid or ""), self.title, self.exe_path)
        ).lower()

    def tooltip(self) -> str:
        lines = [self.name]
        if self.pid:
            lines.append(f"PID: {self.pid}")
        if self.title:
            lines.append(self.title)
        if self.exe_path:
            lines.append(self.exe_path)
        return "\n".join(lines)

    def to_persist(self) -> dict:
        """JSON row. PID is a hint only — it is reused after a process exits."""
        data = {"name": self.name, "title": self.title}
        if self.pid:
            data["pid"] = self.pid
        if self.name_wide or not self.pid:
            data["name_wide"] = True
        return data


def format_instance_label(
    name: str,
    pid: int,
    title: str = "",
    *,
    compact: bool = False,
) -> str:
    """Task Manager-ish label. List rows always keep the PID when we have one."""
    useful = _useful_title(title, name)
    if compact:
        if useful:
            return title.strip()
        if pid:
            return f"{name} ({pid})"
        return name
    if useful and pid:
        return f"{name}  ({pid})  —  {title.strip()}"
    if pid:
        return f"{name}  ({pid})"
    return name


def _useful_title(title: str, name: str) -> bool:
    text = (title or "").strip()
    if not text:
        return False
    n = (name or "").lower()
    t = text.lower()
    if t == n:
        return False
    if n.endswith(".exe") and t == n[:-4]:
        return False
    return True


def list_process_instances() -> list[ProcessInstance]:
    """Every running ``.exe``, one entry per PID, sorted by name then PID."""
    titles = _main_window_titles_by_pid()
    found: list[ProcessInstance] = []
    for proc in psutil.process_iter(["pid", "name", "exe"]):
        try:
            info = proc.info
            name = info.get("name") or ""
            pid = int(info.get("pid") or 0)
            if pid <= 0 or not name.lower().endswith(".exe"):
                continue
            exe = info.get("exe") or ""
        except (psutil.NoSuchProcess, psutil.AccessDenied, TypeError, ValueError):
            continue
        found.append(ProcessInstance(
            pid=pid,
            name=name,
            title=titles.get(pid, ""),
            exe_path=exe,
        ))
    found.sort(key=lambda p: (0 if p.title else 1, p.name.lower(), p.pid))
    return found


def resolve_instance(
    name: str,
    title: str = "",
    hint_pid: int = 0,
    *,
    running: list[ProcessInstance] | None = None,
) -> ProcessInstance | None:
    """Re-bind a persisted target onto a live PID.

    Order: hint PID still that exe → unique window-title match → unique
    name match. Ambiguous duplicates stay unresolved (caller keeps name-wide).
    """
    name_l = (name or "").lower()
    if not name_l:
        return None
    pool = running if running is not None else list_process_instances()
    same = [p for p in pool if p.name.lower() == name_l]
    if not same:
        return None
    if hint_pid:
        for inst in same:
            if inst.pid == hint_pid:
                return inst
    title_s = (title or "").strip()
    if title_s:
        titled = [p for p in same if p.title.strip() == title_s]
        if len(titled) == 1:
            return titled[0]
        if titled:
            return titled[0]
    if len(same) == 1:
        return same[0]
    return None


def find_main_window(pid: int) -> int | None:
    """Largest visible, titled, non-tool top-level window for *pid*."""
    if pid <= 0:
        return None
    best = None
    best_area = 0

    def enum_callback(hwnd, _):
        nonlocal best, best_area
        area, _title = _window_score(hwnd, pid)
        if area > best_area:
            best_area = area
            best = hwnd
        return True

    win32gui.EnumWindows(enum_callback, None)
    return best


def flash_process_window(pid: int) -> bool:
    """Flash the taskbar / caption without stealing focus (Task Manager locate)."""
    hwnd = find_main_window(pid)
    if not hwnd:
        return False
    try:
        info = FLASHWINFO()
        info.cbSize = ctypes.sizeof(FLASHWINFO)
        info.hwnd = hwnd
        info.dwFlags = FLASHW_ALL | FLASHW_TIMERNOFG
        info.uCount = 3
        info.dwTimeout = 0
        ctypes.windll.user32.FlashWindowEx(ctypes.byref(info))
        return True
    except Exception:
        logger.debug("FlashWindowEx failed for pid=%s", pid, exc_info=True)
        try:
            win32gui.FlashWindow(hwnd, True)
            return True
        except Exception:
            return False


def switch_to_process_window(pid: int) -> bool:
    """Restore and foreground the instance's main window (Task Manager Switch to)."""
    hwnd = find_main_window(pid)
    if not hwnd:
        return False
    try:
        if win32gui.IsIconic(hwnd):
            win32gui.ShowWindow(hwnd, win32con.SW_RESTORE)
        else:
            win32gui.ShowWindow(hwnd, win32con.SW_SHOW)
        win32gui.BringWindowToTop(hwnd)
        win32gui.SetForegroundWindow(hwnd)
        return True
    except Exception:
        logger.debug("SetForegroundWindow failed for pid=%s", pid, exc_info=True)
        return flash_process_window(pid)


def instance_from_persist(
    row,
    *,
    running: list[ProcessInstance] | None = None,
) -> ProcessInstance | None:
    """Build a picker target from config.json (new dict or legacy name string)."""
    if isinstance(row, str):
        name = row.strip()
        if not name:
            return None
        live = resolve_instance(name, running=running)
        if live is not None:
            return ProcessInstance(
                pid=0, name=live.name, title="", name_wide=True,
                exe_path=live.exe_path,
            )
        return ProcessInstance(pid=0, name=name, name_wide=True)
    if not isinstance(row, dict):
        return None
    name = str(row.get("name") or "").strip()
    if not name:
        return None
    title = str(row.get("title") or "")
    hint = int(row.get("pid") or 0)
    name_wide = bool(row.get("name_wide"))
    live = resolve_instance(name, title, hint, running=running)
    if live is not None:
        if name_wide:
            return ProcessInstance(
                pid=0, name=live.name, title=live.title,
                exe_path=live.exe_path, name_wide=True,
            )
        return ProcessInstance(
            pid=live.pid, name=live.name, title=live.title,
            exe_path=live.exe_path,
        )
    return ProcessInstance(
        pid=0 if name_wide else hint,
        name=name,
        title=title,
        name_wide=name_wide or not hint,
    )


# ---------------------------------------------------------------------------
# Internals
# ---------------------------------------------------------------------------

def _main_window_titles_by_pid() -> dict[int, str]:
    """One EnumWindows pass: pid → title of the largest qualifying window."""
    best: dict[int, tuple[int, str]] = {}

    def enum_callback(hwnd, _):
        try:
            _tid, found_pid = win32process.GetWindowThreadProcessId(hwnd)
        except Exception:
            return True
        area, title = _window_score(hwnd, found_pid)
        if area <= 0:
            return True
        prev = best.get(found_pid)
        if prev is None or area > prev[0]:
            best[found_pid] = (area, title)
        return True

    try:
        win32gui.EnumWindows(enum_callback, None)
    except Exception:
        logger.debug("EnumWindows failed", exc_info=True)
        return {}
    return {pid: title for pid, (_area, title) in best.items()}


def _window_score(hwnd: int, expected_pid: int) -> tuple[int, str]:
    """Return (area, title) if *hwnd* is a usable main window for *expected_pid*."""
    try:
        if not win32gui.IsWindowVisible(hwnd):
            return 0, ""
        _tid, found_pid = win32process.GetWindowThreadProcessId(hwnd)
        if found_pid != expected_pid:
            return 0, ""
        ex_style = win32gui.GetWindowLong(hwnd, win32con.GWL_EXSTYLE)
        if ex_style & win32con.WS_EX_TOOLWINDOW:
            return 0, ""
        title = win32gui.GetWindowText(hwnd) or ""
        if not title:
            return 0, ""
        left, top, right, bottom = win32gui.GetWindowRect(hwnd)
        area = (right - left) * (bottom - top)
        if area <= 0:
            return 0, ""
        return area, title
    except Exception:
        return 0, ""
