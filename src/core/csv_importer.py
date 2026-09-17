"""CSV importer — parses exported CSV back into structured data for analysis."""

import logging
import re
from dataclasses import dataclass

from src.models import FrameData, SystemInfo
from src.core.csv_parser import CsvParser

logger = logging.getLogger(__name__)


def _open_csv(path: str):
    """Open a CSV file with encoding fallback.

    Tries UTF-8-SIG (most common), then GBK (Chinese Windows ANSI),
    then latin-1 (last resort — never fails).
    """
    # Read raw bytes and test full decode — a single-byte test is unreliable
    # because encoding errors can appear deep inside the file.
    with open(path, "rb") as f:
        raw = f.read()

    for enc in ("utf-8-sig", "gbk", "latin-1"):
        try:
            raw.decode(enc)
            return open(path, "r", encoding=enc, newline="")
        except UnicodeDecodeError:
            continue
    # Unreachable — latin-1 can decode any byte
    return open(path, "r", encoding="latin-1", newline="")


def _strip_quoted_comment(line: str) -> str:
    """Remove surrounding double quotes from a single-field csv.writer row.

    When csv.writer writes a single-field row containing commas (like a comment
    header), it wraps the value in quotes.  Strip them so startswith('#') works.
    """
    if line.startswith('"#') and line.endswith('"'):
        return line[1:-1]
    return line


@dataclass
class ImportResult:
    """Result of importing a CSV file."""
    system_info: SystemInfo | None = None
    monitored_apps: list[str] | None = None
    frames: list[FrameData] | None = None
    file_path: str = ""


def import_file(path: str) -> ImportResult:
    """Parse an exported CSV file and return structured data."""
    result = ImportResult(file_path=path)
    parser = CsvParser()

    with _open_csv(path) as f:
        lines = f.readlines()

    frames: list[FrameData] = []
    in_data_section = False

    for line in lines:
        line = line.rstrip("\n").rstrip("\r")

        # Unwrap csv.writer auto-quoting on single-field lines
        stripped = _strip_quoted_comment(line)

        # Parse comment/header lines before data section
        if not in_data_section:
            if stripped.startswith("# System:"):
                result.system_info = _parse_system_info(stripped)
                continue
            if stripped.startswith("# Monitored:"):
                result.monitored_apps = _parse_monitored(stripped)
                continue
            if stripped.startswith("#"):
                continue
            if line.strip() == "":
                continue
            # First non-comment, non-empty line = CSV header
            parser.parse_header(line)
            in_data_section = True
            continue

        # Data section — any comment line after data started = summary
        if stripped.startswith("#"):
            break
        if line.strip() == "":
            continue

        frame = parser.parse_line(line)
        if frame is not None:
            frames.append(frame)

    result.frames = frames
    logger.info(f"Imported {len(frames)} frames from {path}")
    if result.system_info:
        logger.info(f"  System: {result.system_info.cpu_name}, {result.system_info.gpu_name}")
    if result.monitored_apps:
        logger.info(f"  Apps: {result.monitored_apps}")

    return result


def _parse_system_info(line: str) -> SystemInfo:
    """Parse '# System: CPU=..., GPU=..., RAM=..., Display=...' into SystemInfo."""
    info = SystemInfo()
    # CPU=
    m = re.search(r"CPU=([^,]+)", line)
    if m:
        info.cpu_name = m.group(1).strip()
    # GPU=
    m = re.search(r"GPU=([^,]+)", line)
    if m:
        info.gpu_name = m.group(1).strip()
    # RAM=
    m = re.search(r"RAM=([\d.]+)GB", line)
    if m:
        info.ram_total_gb = float(m.group(1))
    # Display=...@...Hz or Display=...@...Hz / ...@...Hz
    m = re.search(r"Display=(.+?)(?:,\s*[A-Za-z][A-Za-z0-9_ ]*=|$)", line)
    if m:
        displays = re.findall(r"(\d+x\d+)@(\d+)Hz", m.group(1))
        info.display_outputs = [f"{res}@{hz}Hz" for res, hz in displays]
        if displays:
            info.display_resolution = displays[0][0]
            info.display_refresh_hz = int(displays[0][1])
    return info


def _parse_monitored(line: str) -> list[str]:
    """Parse '# Monitored: App1, App2' into list of app names."""
    m = re.search(r"Monitored:\s*(.+)", line)
    if m:
        return [a.strip() for a in m.group(1).split(",") if a.strip()]
    return []


def group_frames_by_app(frames: list[FrameData]) -> dict[str, list[FrameData]]:
    """Group frames by application name."""
    groups: dict[str, list[FrameData]] = {}
    for f in frames:
        key = f.application or f"pid_{f.process_id}"
        groups.setdefault(key, []).append(f)
    return groups


def compute_gpu_estimate(ms_gpu_busy: float | None, ms_between_presents: float | None) -> float:
    """Compute estimated per-frame GPU utilization %.

    AppGPUEstimate% = (MsGPUBusy / MsBetweenPresents) * 100
    """
    if ms_gpu_busy is None or ms_between_presents is None:
        return -1.0
    if ms_between_presents <= 0:
        return -1.0
    return min(100.0, (ms_gpu_busy / ms_between_presents) * 100.0)
