"""Test AppUpdateService validation, and download progress/cancel over real HTTP.

The download tests run against a throwaway localhost server rather than mocking
urllib, so they exercise the same code path a release download takes (headers,
chunked reads, Content-Length) without touching the network.
"""

import hashlib
import tempfile
import threading
from functools import partial
from http.server import HTTPServer, SimpleHTTPRequestHandler
from pathlib import Path

from src.core.app_update_service import (
    STAGE_VERIFY, AppUpdateCancelled, AppUpdateError, AppUpdateService,
)
from src.core.release_manifest import REQUIRED_MANIFEST_FIELDS


def _valid_manifest() -> dict:
    return {
        "version": "1.2.3",
        "mainExeName": "IGPPerformanceMonitor.exe",
        "mainExeUrl": "https://github.com/MlsMoon/IGPPerformanceMonitor/releases/download/v1.2.3/IGPPerformanceMonitor.exe",
        "mainExeSha256": "a" * 64,
        "mainExeSize": 100,
        "updaterExeName": "auto_updater.exe",
        "updaterExeUrl": "https://github.com/MlsMoon/IGPPerformanceMonitor/releases/download/v1.2.3/auto_updater.exe",
        "updaterExeSha256": "b" * 64,
        "updaterExeSize": 50,
        "updatedAt": "2026-09-17T00:00:00Z",
    }


def run():
    service = AppUpdateService({"app_manifest_url": "https://example.invalid/app_manifest.json"})
    assert service.manifest_url.endswith("app_manifest.json")

    ok = service._validate(_valid_manifest())
    assert ok["version"] == "1.2.3"

    try:
        service._validate({"version": "1.0.0"})
        raise AssertionError("expected missing-field error")
    except AppUpdateError as exc:
        assert "Missing fields" in str(exc)

    try:
        service._validate(["not", "an", "object"])  # type: ignore[arg-type]
        raise AssertionError("expected type error")
    except AppUpdateError as exc:
        assert "object" in str(exc)

    for key in REQUIRED_MANIFEST_FIELDS:
        broken = _valid_manifest()
        del broken[key]
        try:
            service._validate(broken)
            raise AssertionError(f"expected missing {key}")
        except AppUpdateError:
            pass

    _check_download_progress(service)


class _QuietHandler(SimpleHTTPRequestHandler):
    def log_message(self, *args):
        pass


def _check_download_progress(service: AppUpdateService) -> None:
    """Download a real payload over HTTP and watch progress, then cancellation."""
    payload = bytes(range(256)) * 4096           # 1 MiB, several read chunks
    with tempfile.TemporaryDirectory() as td:
        root = Path(td)
        (root / "payload.bin").write_bytes(payload)

        handler = partial(_QuietHandler, directory=str(root))
        server = HTTPServer(("127.0.0.1", 0), handler)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        url = f"http://127.0.0.1:{server.server_port}/payload.bin"
        try:
            dest = root / "out.bin"
            ticks = []
            service._download(url, dest, ticks.append)

            assert dest.read_bytes() == payload, "downloaded bytes must match"
            assert len(ticks) > 2, "progress should report more than start and end"
            assert ticks[0].received == 0, "first tick is the starting point"
            assert ticks[-1].received == len(payload), "last tick is the full size"
            assert ticks[-1].total == len(payload), "Content-Length should be reported"
            assert ticks[-1].fraction == 1.0, "a finished download is 100%"
            received = [t.received for t in ticks]
            assert received == sorted(received), "progress must not go backwards"

            # Unknown size must read as indeterminate, not as 0%.
            from src.core.app_update_service import UpdateProgress
            assert UpdateProgress("app", 5, 0).fraction == -1.0, "unknown total"

            # Verifying a big file also reports progress.
            digest = hashlib.sha256(payload).hexdigest()
            vticks = []
            service._verify(dest, len(payload), digest, vticks.append)
            assert vticks and vticks[-1].stage == STAGE_VERIFY, "verify reports too"
            assert vticks[-1].fraction == 1.0, "verify finishes at 100%"

            # Cancelling mid-flight must raise and leave no partial file.
            partial_dest = root / "cancelled.bin"
            try:
                service._download(url, partial_dest, None, "app", lambda: True)
                raise AssertionError("expected cancellation")
            except AppUpdateCancelled:
                pass
            assert not partial_dest.exists(), "a cancelled download must clean up"
        finally:
            server.shutdown()
            server.server_close()
