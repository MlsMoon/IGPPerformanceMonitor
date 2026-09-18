"""CSV export dialog and functionality."""

import csv
import os
from datetime import datetime

from PyQt5.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QPushButton,
    QLabel, QFileDialog, QCheckBox, QMessageBox,
    QGroupBox, QRadioButton,
)

from src.i18n import tr
from src.core.data_store import DataStore
from src.core.metrics_schema import (
    CSV_EXPORT_HEADER_V2,
    frame_to_row,
)
from src.models import FrameData, format_display_outputs, frame_series_key, pretty_series_key
from src.ui import theme

_HOME = os.path.expanduser("~")


def _frame_to_row(frame: FrameData) -> list:
    """Convert a FrameData to a CSV row list."""
    return frame_to_row(frame)


def _build_sys_info_rows(store: DataStore) -> list[list]:
    """Build system info header rows for CSV."""
    rows = []
    info = store.get_system_info()
    if info:
        rows.append([f"# System: CPU={info.cpu_name}, GPU={info.gpu_name}, "
                      f"RAM={info.ram_total_gb}GB, Display={format_display_outputs(info)}"])
    apps = store.get_monitored_apps_display()
    if apps:
        rows.append([f"# Monitored: {apps}"])
    rows.append([f"# Export Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"])
    rows.append([])  # blank separator
    return rows


def _write_comment_row(f, row: list):
    """Write a single-field comment row directly to file (bypass csv.writer quoting)."""
    if row and row[0].startswith("#"):
        f.write(row[0] + "\n")
    elif row and not any(row):
        f.write("\n")


def _write_comment_line(f, line: str):
    """Write a comment line directly to file."""
    f.write(line + "\n")


def write_stats(filepath: str, store: DataStore, frames: list[FrameData], proc_name: str = ""):
    """Append summary statistics to *filepath* (module-level; GUI + headless share this).

    ``store`` is accepted for API symmetry with ``_build_sys_info_rows`` (currently
    unused but keeps the signature stable for future system-level stats).
    """
    if not frames:
        return
    fps_values = sorted([f.fps for f in frames if f.fps is not None and f.fps > 0])
    if not fps_values:
        return

    n = len(fps_values)
    avg_fps = sum(fps_values) / n
    p99_idx = int(n * 0.01)
    p95_idx = int(n * 0.05)

    mem_vals = [f.app_memory_mb for f in frames if f.app_memory_mb is not None]
    cpu_vals = [f.app_cpu_percent for f in frames if f.app_cpu_percent is not None]
    avg_mem = sum(mem_vals) / len(mem_vals) if mem_vals else 0
    avg_cpu = sum(cpu_vals) / len(cpu_vals) if cpu_vals else 0

    with open(filepath, "a", newline="") as f:
        f.write("\n")
        _write_comment_line(f, f"# {tr('summary_title')}")
        _write_comment_line(f, f"# {tr('summary_process')}, {pretty_series_key(proc_name) if proc_name else frames[0].application}")
        _write_comment_line(f, f"# {tr('summary_total_frames')}, {n}")
        _write_comment_line(f, f"# {tr('summary_avg_fps')}, {round(avg_fps, 1)}")
        _write_comment_line(f, f"# {tr('summary_min_fps')}, {round(fps_values[0], 1)}")
        _write_comment_line(f, f"# {tr('summary_max_fps')}, {round(fps_values[-1], 1)}")
        _write_comment_line(f, f"# {tr('summary_1p_low')}, {round(fps_values[p99_idx] if p99_idx < n else 0, 1)}")
        _write_comment_line(f, f"# {tr('summary_5p_low')}, {round(fps_values[p95_idx] if p95_idx < n else 0, 1)}")
        _write_comment_line(f, f"# Avg App Memory (MB), {round(avg_mem, 1)}")
        _write_comment_line(f, f"# Avg App CPU%, {round(avg_cpu, 1)}")


class CsvExportDialog(QDialog):
    """Dialog for exporting captured data to CSV."""

    def __init__(self, data_store: DataStore, parent=None):
        super().__init__(parent)
        self._data_store = data_store
        self.setWindowTitle(tr("export_title"))
        self.setMinimumWidth(450)
        self._init_ui()

    def _init_ui(self):
        layout = QVBoxLayout(self)

        frame_count = self._data_store.get_frame_count()
        elapsed = self._data_store.get_elapsed_seconds()
        info_label = QLabel(
            f"<b>{tr('capture_summary')}</b><br>"
            f"{tr('total_frames')}: {frame_count}<br>"
            f"{tr('duration')}: {elapsed:.1f} {tr('seconds_unit')}"
        )
        layout.addWidget(info_label)

        # Scope
        scope_group = QGroupBox(tr("export_scope"))
        scope_layout = QVBoxLayout(scope_group)
        self._all_frames_radio = QRadioButton(tr("all_frames"))
        self._all_frames_radio.setChecked(True)
        scope_layout.addWidget(self._all_frames_radio)
        self._per_process_radio = QRadioButton(tr("per_process"))
        scope_layout.addWidget(self._per_process_radio)
        layout.addWidget(scope_group)

        # Options
        options_group = QGroupBox(tr("options"))
        options_layout = QVBoxLayout(options_group)
        self._include_header_cb = QCheckBox(tr("include_header"))
        self._include_header_cb.setChecked(True)
        options_layout.addWidget(self._include_header_cb)
        self._include_stats_cb = QCheckBox(tr("include_stats"))
        self._include_stats_cb.setChecked(True)
        options_layout.addWidget(self._include_stats_cb)
        layout.addWidget(options_group)

        # Buttons
        btn_row = QHBoxLayout()
        btn_row.addStretch()
        cancel_btn = QPushButton(tr("btn_cancel"))
        cancel_btn.clicked.connect(self.reject)
        btn_row.addWidget(cancel_btn)
        export_btn = QPushButton(tr("btn_export"))
        export_btn.setStyleSheet(theme.panel_button_qss(theme.current_theme(), "primary"))
        export_btn.clicked.connect(self._export)
        btn_row.addWidget(export_btn)
        layout.addLayout(btn_row)

    def _export(self):
        frames = self._data_store.get_all_frames()
        if not frames:
            QMessageBox.warning(self, tr("no_data_title"), tr("no_data_text"))
            return

        if self._per_process_radio.isChecked():
            procs: dict[str, list[FrameData]] = {}
            for f in frames:
                key = frame_series_key(f)
                procs.setdefault(key, []).append(f)

            dir_path = QFileDialog.getExistingDirectory(self, tr("select_dir"), _HOME)
            if not dir_path:
                return

            timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
            for proc_name, proc_frames in procs.items():
                label = pretty_series_key(proc_name)
                safe_name = (
                    label.replace(".exe", "").replace(" ", "_")
                    .replace("|", "_").replace("(", "").replace(")", "")
                )
                filepath = os.path.join(dir_path, f"igpmon-{safe_name}-{timestamp}.csv")
                self._write_csv(filepath, proc_frames)
                self._write_stats(filepath, proc_frames, proc_name)

            QMessageBox.information(
                self, tr("export_complete"),
                tr("export_complete_multi", len(procs), dir_path)
            )
        else:
            timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
            main_app = frames[0].application or "capture"
            safe_app = main_app.replace(".exe", "").replace(" ", "_")
            default_name = f"igpmon-{safe_app}-{timestamp}.csv"
            filepath, _ = QFileDialog.getSaveFileName(
                self, tr("save_csv"), os.path.join(_HOME, default_name), tr("csv_filter")
            )
            if not filepath:
                return
            self._write_csv(filepath, frames)
            self._write_stats(filepath, frames)
            QMessageBox.information(
                self, tr("export_complete"), tr("export_complete_single", filepath)
            )
        self.accept()

    def _write_csv(self, filepath: str, frames: list[FrameData]):
        """Write frame data to CSV with system info header rows."""
        with open(filepath, "w", newline="") as f:
            writer = csv.writer(f)

            # System info header rows — write directly to avoid csv quoting
            for row in _build_sys_info_rows(self._data_store):
                _write_comment_row(f, row)

            # CSV column header
            if self._include_header_cb.isChecked():
                writer.writerow(CSV_EXPORT_HEADER_V2)

            for frame in frames:
                writer.writerow(_frame_to_row(frame))

    def _write_stats(self, filepath: str, frames: list[FrameData], proc_name: str = ""):
        """Append summary statistics (delegates to module-level write_stats)."""
        if not self._include_stats_cb.isChecked() or not frames:
            return
        write_stats(filepath, self._data_store, frames, proc_name)
