"""Modal progress dialog for downloading and installing an update.

The install is tens of megabytes over the network. Running it inline on the GUI
thread froze the window for the whole download with nothing but a status-bar
string, so it lives on a worker thread here and reports bytes to a real bar.
"""

from __future__ import annotations

import threading

from PyQt5.QtCore import QThread, Qt, pyqtSignal
from PyQt5.QtWidgets import (
    QDialog, QHBoxLayout, QLabel, QProgressBar, QPushButton, QVBoxLayout,
)

from src.core.app_update_service import (
    STAGE_APP, STAGE_INSTALL, STAGE_UPDATER, STAGE_VERIFY,
    AppUpdateCancelled, AppUpdateCheckResult, AppUpdateInstallResult,
    AppUpdateService, UpdateProgress,
)
from src.i18n import tr
from src.ui import theme

_STAGE_LABELS = {
    STAGE_APP: "update_stage_app",
    STAGE_UPDATER: "update_stage_updater",
    STAGE_VERIFY: "update_stage_verify",
    STAGE_INSTALL: "update_stage_install",
}

_BAR_SCALE = 1000       # the bar counts permille, so it moves on large files
_MB = 1024 * 1024


def _format_mb(value: int) -> str:
    return f"{value / _MB:.1f} MB"


class ManifestWorker(QThread):
    """Fetch the GitHub release manifest off the GUI thread.

    A 20s urllib timeout on the GUI thread froze Help → Check for Updates
    (and Version History) whenever GitHub was slow. The JSON is tiny; there
    is no progress bar, only status-bar copy.
    """

    check_finished = pyqtSignal(object)      # AppUpdateCheckResult
    manifest_finished = pyqtSignal(object)   # dict
    failed = pyqtSignal(str)

    def __init__(self, service: AppUpdateService, job: str, parent=None):
        super().__init__(parent)
        self._service = service
        self.job = job  # "check" | "manifest"

    def run(self) -> None:
        try:
            if self.job == "check":
                result: AppUpdateCheckResult = self._service.check_for_update()
                self.check_finished.emit(result)
            else:
                self.manifest_finished.emit(self._service.fetch_manifest())
        except Exception as exc:                      # noqa: BLE001 — reported to the user
            self.failed.emit(str(exc))


class _InstallWorker(QThread):
    """Runs AppUpdateService.install_update off the GUI thread."""

    progressed = pyqtSignal(object)     # UpdateProgress
    succeeded = pyqtSignal(object)      # AppUpdateInstallResult
    failed = pyqtSignal(str)
    cancelled = pyqtSignal()

    def __init__(self, service: AppUpdateService, manifest: dict, parent=None):
        super().__init__(parent)
        self._service = service
        self._manifest = manifest
        self._cancel = threading.Event()

    def cancel(self) -> None:
        self._cancel.set()

    def run(self) -> None:
        try:
            result = self._service.install_update(
                self._manifest,
                progress=self.progressed.emit,
                is_cancelled=self._cancel.is_set,
            )
        except AppUpdateCancelled:
            self.cancelled.emit()
        except Exception as exc:                      # noqa: BLE001 — reported to the user
            self.failed.emit(str(exc))
        else:
            self.succeeded.emit(result)


class UpdateProgressDialog(QDialog):
    """Shows download/verify progress; returns the install result, or None.

    Used for both updating and rolling back — only the window title differs.
    """

    def __init__(self, service: AppUpdateService, manifest: dict,
                 title: str, parent=None):
        super().__init__(parent)
        self.setWindowTitle(title)
        self.setMinimumWidth(420)
        # No close button: the Cancel button is the single way out, so the
        # worker can never be orphaned by a stray click on the title bar.
        self.setWindowFlags(
            (self.windowFlags() | Qt.CustomizeWindowHint) & ~Qt.WindowCloseButtonHint
        )

        self.result: AppUpdateInstallResult | None = None
        self._error: str | None = None

        t = theme.current_theme()
        root = QVBoxLayout(self)
        root.setContentsMargins(18, 16, 18, 14)
        root.setSpacing(10)

        self._stage_label = QLabel(tr("update_stage_app"))
        root.addWidget(self._stage_label)

        self._bar = QProgressBar()
        self._bar.setRange(0, 0)        # indeterminate until the first byte count
        self._bar.setTextVisible(False)
        root.addWidget(self._bar)

        self._detail = QLabel("")
        self._detail.setStyleSheet(f"color: {t.text_muted}; font-size: 9pt;")
        root.addWidget(self._detail)

        buttons = QHBoxLayout()
        buttons.addStretch()
        self._cancel_btn = QPushButton(tr("btn_cancel"))
        self._cancel_btn.clicked.connect(self._on_cancel)
        buttons.addWidget(self._cancel_btn)
        root.addLayout(buttons)

        self._worker = _InstallWorker(service, manifest, self)
        self._worker.progressed.connect(self._on_progress)
        self._worker.succeeded.connect(self._on_succeeded)
        self._worker.failed.connect(self._on_failed)
        self._worker.cancelled.connect(self.reject)

    @property
    def error(self) -> str | None:
        """The failure message, if the install failed rather than succeeded."""
        return self._error

    def exec_(self) -> int:
        self._worker.start()
        return super().exec_()

    def _on_progress(self, progress: UpdateProgress) -> None:
        self._stage_label.setText(tr(_STAGE_LABELS.get(progress.stage, "update_stage_app")))

        fraction = progress.fraction
        if fraction < 0:
            self._bar.setRange(0, 0)
            self._detail.setText("")
            return

        self._bar.setRange(0, _BAR_SCALE)
        self._bar.setValue(int(fraction * _BAR_SCALE))
        self._detail.setText(tr(
            "update_progress_bytes",
            _format_mb(progress.received),
            _format_mb(progress.total),
            int(fraction * 100),
        ))

    def _on_succeeded(self, result: AppUpdateInstallResult) -> None:
        self.result = result
        self.accept()

    def _on_failed(self, message: str) -> None:
        self._error = message
        self.reject()

    def _on_cancel(self) -> None:
        self._cancel_btn.setEnabled(False)
        self._stage_label.setText(tr("update_stage_cancelling"))
        self._bar.setRange(0, 0)
        self._detail.setText("")
        self._worker.cancel()

    def closeEvent(self, event):
        # Reached via Esc or a window-manager close: never leave the thread
        # running against a dialog that is going away.
        self._worker.cancel()
        self._worker.wait(5000)
        super().closeEvent(event)
