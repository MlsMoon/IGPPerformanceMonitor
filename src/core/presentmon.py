"""PresentMon CLI wrapper — manages the PresentMon subprocess in a QThread."""

import logging
import os
import subprocess
import threading

from PyQt5.QtCore import QThread, pyqtSignal

from src.config import PRESENTMON_EXE
from src.models import SessionConfig
from src.core.csv_parser import CsvParser
from src.core.data_store import DataStore
from src.i18n import tr

logger = logging.getLogger(__name__)


class PresentMonError(Exception):
    """Raised when PresentMon encounters an error."""
    pass


class PresentMonWrapper(QThread):
    """Runs PresentMon in a background thread, enriching frames with system metrics."""

    frame_captured = pyqtSignal(object)   # FrameData
    capture_error = pyqtSignal(str)
    state_changed = pyqtSignal(bool)      # True=running, False=stopped
    status_message = pyqtSignal(str)

    def __init__(self, data_store: DataStore, parent=None):
        super().__init__(parent)
        self._data_store = data_store
        self._process: subprocess.Popen | None = None
        self._running = False
        self._config: SessionConfig | None = None
        self._parser = CsvParser()
        self._sampler = None  # SystemMetricsSampler, injected via set_metrics_sampler

    @property
    def is_running(self) -> bool:
        return self._running

    def set_metrics_sampler(self, sampler):
        """Inject the SystemMetricsSampler whose latest cache stamps frames."""
        self._sampler = sampler

    def configure(self, config: SessionConfig):
        """Set the capture configuration."""
        self._config = config

    def _build_command(self) -> list[str]:
        """Build the PresentMon command line from config."""
        if not os.path.exists(PRESENTMON_EXE):
            raise PresentMonError(f"PresentMon not found at: {PRESENTMON_EXE}")

        cmd = [PRESENTMON_EXE]
        cmd.append("--output_stdout")
        cmd.append("--no_console_stats")

        if self._config.use_v1_metrics:
            cmd.append("--v1_metrics")
        else:
            cmd.append("--v2_metrics")

        for name in self._config.process_names:
            cmd.extend(["--process_name", name])
        for pid in self._config.process_ids:
            cmd.extend(["--process_id", str(pid)])

        for name in self._config.exclude_names:
            cmd.extend(["--exclude", name])

        if self._config.timed_seconds > 0:
            cmd.extend(["--timed", str(self._config.timed_seconds)])
            cmd.append("--terminate_after_timed")

        if not self._config.track_display:
            cmd.append("--no_track_display")
        if not self._config.track_input:
            cmd.append("--no_track_input")
        if not self._config.track_gpu:
            cmd.append("--no_track_gpu")

        if self._config.hotkey:
            cmd.extend(["--hotkey", self._config.hotkey])

        # Stop any existing session with the same name (cleanup from prior crash)
        cmd.append("--stop_existing_session")

        return cmd

    def run(self):
        """Main thread method — runs PresentMon and reads stdout."""
        if not self._config:
            self.capture_error.emit(tr("wrapper_no_config"))
            return

        proc: subprocess.Popen | None = None

        try:
            cmd = self._build_command()
            logger.info(f"PresentMon cmd: {' '.join(cmd)}")

            startupinfo = None
            if os.name == "nt":
                startupinfo = subprocess.STARTUPINFO()
                startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
                startupinfo.wShowWindow = subprocess.SW_HIDE

            proc = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                bufsize=1,
                startupinfo=startupinfo,
            )
            stderr_lines: list[str] = []

            def _read_stderr():
                if proc.stderr is None:
                    return
                for err_line in proc.stderr:
                    err_line = err_line.rstrip()
                    if err_line:
                        stderr_lines.append(err_line)
                        logger.warning(f"PresentMon stderr: {err_line}")

            stderr_thread = threading.Thread(target=_read_stderr, daemon=True)
            stderr_thread.start()
            self._process = proc
            self._running = True
            self.state_changed.emit(True)
            self.status_message.emit(tr("wrapper_starting"))

            # Read stdout line by line
            raw_line_count = 0
            for line in proc.stdout:
                if not self._running:
                    break
                raw_line_count += 1
                line = line.strip()
                if not line:
                    continue

                if raw_line_count <= 3:
                    logger.info(f"PresentMon raw line #{raw_line_count} [{len(line)} chars]: {line[:300]}")

                frame = self._parser.parse_line(line)
                if frame is not None:
                    self._handle_frame(frame)

            logger.info(f"PresentMon stdout ended. Total raw lines: {raw_line_count}, frames stored: {self._data_store.get_frame_count()}")

            # Process finished; stderr has been drained by the helper thread.
            return_code = proc.wait()
            stderr_thread.join(timeout=1)
            stderr_output = "\n".join(stderr_lines)
            logger.info(
                "PresentMon exited with code %s. Total raw lines: %s, frames stored: %s",
                return_code,
                raw_line_count,
                self._data_store.get_frame_count(),
            )

            if return_code != 0 and self._running:
                if "access denied" in stderr_output.lower():
                    msg = tr("wrapper_access_denied")
                else:
                    msg = tr("wrapper_exit_error", return_code, stderr_output[:500])
                self.capture_error.emit(msg)
            elif return_code == 0:
                self.status_message.emit(tr("wrapper_stopped"))

        except FileNotFoundError:
            self.capture_error.emit(tr("wrapper_not_found", PRESENTMON_EXE))
        except Exception as e:
            logger.exception("PresentMon error")
            self.capture_error.emit(str(e))
        finally:
            self._running = False
            self.state_changed.emit(False)
            # Kill the process if still alive
            if proc is not None:
                try:
                    proc.kill()
                    proc.wait(timeout=3)
                except Exception:
                    pass
            self._process = None

    def _enrich_frame(self, frame):
        """Stamp a parsed FrameData with the most recent system/process metrics.

        Metrics are sampled independently by SystemMetricsSampler on a fixed
        cadence (avoids psutil's per-frame 0.0 problem); here we copy the
        latest cached values so CSV exports stay consistent with the live view.
        """
        sampler = self._sampler
        if sampler is None:
            return

        sys_latest = sampler.latest_system
        frame.total_cpu_percent = sys_latest.get("total_cpu_percent")
        frame.total_gpu_percent = sys_latest.get("total_gpu_percent")
        frame.total_ram_used_gb = sys_latest.get("total_ram_used_gb")
        frame.gpu_vram_total_mb = sys_latest.get("gpu_vram_total_mb")
        frame.gpu_vram_used_mb = sys_latest.get("gpu_vram_used_mb")
        frame.gpu_vram_percent = sys_latest.get("gpu_vram_percent")

        pid = frame.process_id
        if pid > 0:
            pp = sampler.latest_per_process(pid)
            frame.app_memory_mb = pp.get("app_memory_mb")
            frame.app_cpu_percent = pp.get("app_cpu_percent")
            frame.app_cpu_cores = pp.get("app_cpu_cores")
            frame.app_gpu_percent = pp.get("app_gpu_percent")
            frame.app_vram_mb = pp.get("app_vram_mb")

    def _handle_frame(self, frame) -> bool:
        """Register, enrich, store, and emit a parsed frame."""
        if not self._is_monitored(frame):
            return False
        if self._sampler is not None:
            self._sampler.track_pid(frame.process_id)
        self._enrich_frame(frame)
        self._data_store.add_frame(frame)
        self.frame_captured.emit(frame)
        return True

    def _is_monitored(self, frame) -> bool:
        """Check if frame belongs to a user-selected process."""
        if self._config is None:
            return True
        names = self._config.process_names
        ids = self._config.process_ids
        if not names and not ids:
            return True
        # Check by PID
        if ids and frame.process_id in ids:
            return True
        # Check by name (case-insensitive)
        if names:
            app = frame.application.lower()
            if any(n.lower() == app for n in names):
                return True
        return False

    def stop(self):
        """Stop the PresentMon capture (called from main thread)."""
        self._running = False
        # Kill the subprocess; the run() finally block handles final cleanup
        if self._process is not None:
            try:
                self._process.kill()
            except Exception:
                pass
