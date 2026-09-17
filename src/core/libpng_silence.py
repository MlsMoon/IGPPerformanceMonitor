"""Drop libpng iCCP warnings that Qt writes to C-level stderr.

Our own ``assets/icon.png`` has no iCCP chunk. The spam is Qt's bundled
style / message-box PNGs: libpng calls ``fprintf(stderr, ...)``, which
bypasses a Python ``sys.stderr`` wrapper. This module dup2s fd 2 (and the
Win32 ``STD_ERROR_HANDLE``) through a pipe and drops those lines.

Set ``IGP_KEEP_LIBPNG_WARNINGS=1`` to leave stderr alone.
"""

from __future__ import annotations

import atexit
import os
import sys
import threading

_DROP = b"libpng warning: iCCP"
_installed = False
_pump_thread: threading.Thread | None = None


def should_drop(line: bytes) -> bool:
    return _DROP in line


def install() -> None:
    """Install once, before QApplication is constructed."""
    global _installed
    if _installed or os.environ.get("IGP_KEEP_LIBPNG_WARNINGS"):
        return
    try:
        orig_fd = os.dup(2)
    except OSError:
        return
    try:
        read_fd, write_fd = os.pipe()
        os.dup2(write_fd, 2)
        os.close(write_fd)
    except OSError:
        try:
            os.close(orig_fd)
        except OSError:
            pass
        return
    _retarget_win32_stderr()
    global _pump_thread
    _pump_thread = threading.Thread(
        target=_pump,
        args=(read_fd, orig_fd),
        name="libpng-stderr-filter",
        daemon=True,
    )
    _pump_thread.start()
    atexit.register(_drain)
    _installed = True


def _drain() -> None:
    """Close the pipe writer so the pump can flush the last lines."""
    try:
        nul = os.open(os.devnull, os.O_WRONLY)
        try:
            os.dup2(nul, 2)
        finally:
            os.close(nul)
    except OSError:
        pass
    thread = _pump_thread
    if thread is not None:
        thread.join(timeout=1.0)


def _retarget_win32_stderr() -> None:
    """Point the process STD_ERROR_HANDLE at the redirected fd 2."""
    if sys.platform != "win32":
        return
    try:
        import ctypes
        import msvcrt

        kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
        kernel32.SetStdHandle(ctypes.c_uint(0xFFFFFFF4), msvcrt.get_osfhandle(2))
    except OSError:
        return


def _pump(read_fd: int, orig_fd: int) -> None:
    buf = b""
    try:
        while True:
            try:
                chunk = os.read(read_fd, 4096)
            except OSError:
                break
            if not chunk:
                break
            buf += chunk
            while True:
                idx = buf.find(b"\n")
                if idx < 0:
                    break
                line, buf = buf[: idx + 1], buf[idx + 1 :]
                if should_drop(line):
                    continue
                try:
                    os.write(orig_fd, line)
                except OSError:
                    return
        if buf and not should_drop(buf):
            try:
                os.write(orig_fd, buf)
            except OSError:
                pass
    finally:
        try:
            os.close(read_fd)
        except OSError:
            pass
