"""Update self-check: download, hash and cancel against a real localhost server.

No stand-in for urllib. A throwaway HTTP server on 127.0.0.1 serves a real
payload, so this walks the same code a release download walks — headers,
Content-Length, chunked reads, SHA256 over the result — without touching the
network or GitHub.
"""

from __future__ import annotations

import hashlib
import tempfile
import threading
from functools import partial
from http.server import HTTPServer, SimpleHTTPRequestHandler
from pathlib import Path

from src.core.app_update_service import (
    STAGE_VERIFY, AppUpdateCancelled, AppUpdateService, UpdateProgress,
)
from src.selfcheck.report import Report
from src.selfcheck.spec import Area

AREA = Area(
    name="update",
    judge="parent",
    touches=(
        "src/core/app_update_service.py",
        "src/core/release_manifest.py",
        "src/core/app_info.py",
        "src/auto_updater/",
        "src/ui/dialogs/update_progress.py",
    ),
)


class _QuietHandler(SimpleHTTPRequestHandler):
    def log_message(self, *args):
        pass


def run(report: Report, out_dir: str, **_kwargs) -> None:
    service = AppUpdateService()
    report.section("service")
    report.fact("manifest url", service.manifest_url)

    payload = bytes(range(256)) * 4096  # 1 MiB, several read chunks
    with tempfile.TemporaryDirectory() as td:
        root = Path(td)
        (root / "payload.bin").write_bytes(payload)

        handler = partial(_QuietHandler, directory=str(root))
        server = HTTPServer(("127.0.0.1", 0), handler)
        threading.Thread(target=server.serve_forever, daemon=True).start()
        url = f"http://127.0.0.1:{server.server_port}/payload.bin"
        try:
            _check_download(report, service, url, root, payload)
            _check_verify(report, service, root, payload)
            _check_cancel(report, service, url, root)
        finally:
            server.shutdown()
            server.server_close()


def _check_download(report, service, url, root, payload) -> None:
    report.section("download")
    with report.step("download"):
        dest = root / "out.bin"
        ticks: list[UpdateProgress] = []
        service._download(url, dest, ticks.append)

        report.fact("payload bytes", len(payload))
        report.fact("progress ticks", len(ticks))
        if dest.read_bytes() != payload:
            report.error("downloaded bytes differ from what the server served")
        if len(ticks) <= 2:
            report.suspect(
                f"only {len(ticks)} ticks — the bar will jump rather than fill")

        received = [t.received for t in ticks]
        if received != sorted(received):
            report.error("progress went backwards")
        report.fact("first tick", f"received={ticks[0].received}")
        report.fact("last tick",
                    f"received={ticks[-1].received} total={ticks[-1].total} "
                    f"fraction={ticks[-1].fraction}")
        if ticks[-1].total != len(payload):
            report.suspect("Content-Length was not reported, bar stays indeterminate")
        report.fact("unknown total reads as", UpdateProgress("app", 5, 0).fraction)


def _check_verify(report, service, root, payload) -> None:
    report.section("verify")
    with report.step("verify"):
        dest = root / "out.bin"
        digest = hashlib.sha256(payload).hexdigest()
        ticks: list[UpdateProgress] = []
        service._verify(dest, len(payload), digest, ticks.append)
        report.fact("verify ticks", len(ticks))
        report.fact("final stage", ticks[-1].stage if ticks else "(none)")
        report.fact("final fraction", ticks[-1].fraction if ticks else "(none)")
        if not ticks or ticks[-1].stage != STAGE_VERIFY:
            report.error("verification reported no progress")


def _check_cancel(report, service, url, root) -> None:
    report.section("cancel")
    with report.step("cancel"):
        dest = root / "cancelled.bin"
        cancelled = False
        try:
            service._download(url, dest, None, "app", lambda: True)
        except AppUpdateCancelled:
            cancelled = True
        report.fact("raises AppUpdateCancelled", cancelled)
        report.fact("partial file removed", not dest.exists())
        if not cancelled:
            report.error("a cancelled download ran to completion")
        if dest.exists():
            report.error("a cancelled download left a partial file behind")
