"""CSV parser for PresentMon output stream."""

import csv
import io
import logging
from typing import Optional

from src.models import FrameData
from src.core.metrics_schema import (
    COLUMN_BY_PARSE_NAME,
    parse_value,
)

logger = logging.getLogger(__name__)


class CsvParser:
    """Parses PresentMon CSV output line-by-line."""

    def __init__(self):
        self._header: list[str] = []
        self._col_index: dict[str, int] = {}
        self._header_parsed = False
        self._frame_count = 0  # track frames for debug

    def parse_header(self, line: str) -> bool:
        """Parse the CSV header line. Returns True if successful."""
        if self._header_parsed:
            return True
        try:
            reader = csv.reader(io.StringIO(line))
            self._header = next(reader)
            self._col_index = {col.strip(): i for i, col in enumerate(self._header)}
            self._header_parsed = True
            logger.info(f"CSV header: {len(self._header)} columns")
            # Verify key columns exist
            for key_col in ["Application", "ProcessID"]:
                if key_col not in self._col_index:
                    logger.warning(f"Expected column '{key_col}' NOT FOUND in CSV header! Available: {list(self._col_index.keys())[:10]}...")
                else:
                    logger.info(f"Column '{key_col}' OK (idx={self._col_index[key_col]})")
            if "FrameTime" in self._col_index:
                logger.info(f"Column 'FrameTime' OK (idx={self._col_index['FrameTime']})")
            elif "MsBetweenPresents" in self._col_index:
                logger.info(f"Column 'MsBetweenPresents' OK (idx={self._col_index['MsBetweenPresents']})")
            else:
                logger.warning("No frame-time column found in CSV header.")
            return True
        except (StopIteration, csv.Error) as e:
            logger.error(f"Failed to parse CSV header: {e}")
            return False

    def parse_line(self, line: str) -> FrameData | None:
        """Parse a single CSV data line. Returns FrameData or None on error."""
        if not self._header_parsed:
            if not self.parse_header(line):
                return None
            # Header line parsed, not a data line
            return None

        try:
            reader = csv.reader(io.StringIO(line))
            row = next(reader)
        except (StopIteration, csv.Error):
            return None

        if len(row) < 2:  # too short to be useful
            return None

        # PresentMon may re-emit the CSV header mid-stream when tracking
        # multiple processes.  The first column of a header row is always
        # the literal string "Application" — no real process has this name.
        if self._header_parsed and row[0].strip() == "Application":
            return None

        frame = FrameData()

        for col_name, column in COLUMN_BY_PARSE_NAME.items():
            idx = self._col_index.get(col_name, -1)
            if idx < 0 or idx >= len(row):
                continue
            val = row[idx].strip()
            setattr(frame, column.field_name, parse_value(val, column))

        # Compute derived FPS only when the CSV did not contain an exported FPS column.
        if frame.fps is None:
            frame.fps = _compute_fps(frame)

        self._frame_count += 1
        if self._frame_count <= 5:
            logger.info(
                f"Frame #{self._frame_count}: app={frame.application}, pid={frame.process_id}, "
                f"fps={'N/A' if frame.fps is None else f'{frame.fps:.1f}'}, ms_between_presents={frame.ms_between_presents}, "
                f"display_latency={frame.display_latency}, "
                f"mem={frame.app_memory_mb}MB, cpu={frame.app_cpu_percent}%"
            )

        return frame


def _compute_fps(frame: FrameData) -> Optional[float]:
    """Derive instantaneous FPS from frame data.

    Returns None when no usable timing is available, so 'no data' stays
    distinct from a real measured value.
    """
    # Prefer ms_between_presents for FPS
    if frame.ms_between_presents and frame.ms_between_presents > 0:
        return 1000.0 / frame.ms_between_presents
    # Fallback to display latency
    if frame.display_latency and frame.display_latency > 0:
        return 1000.0 / frame.display_latency
    return None
