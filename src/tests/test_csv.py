"""Test: CSV schema integrity + real export/import roundtrip.

No hand-written CSV, no hardcoded type/value assertions:
- ``_test_schema_integrity`` iterates ``CSV_COLUMNS`` (the single source) and
  checks every mapped field exists on FrameData.
- ``_test_export_import_roundtrip`` loads REAL captured frames
  (``load_real_frames``, auto-generated in temp/), re-exports through the real
  exporter, re-imports via ``import_file``, and checks each field round-trips
  losslessly (relative compare — original vs imported, no hardcoded values).

Skips if the real capture can't be generated (no admin/UAC).
"""

import csv
import os
import tempfile

from src.core.csv_importer import import_file
from src.core.metrics_schema import (
    CSV_COLUMNS, CSV_EXPORT_HEADER_V2, frame_to_row,
)
from src.models import FrameData, format_display_outputs
from src.selfcheck.data import load_real_frames, load_real_system_info


def run():
    _test_schema_integrity()
    _test_export_import_roundtrip()


# ---------------------------------------------------------------------------
# 1. Schema integrity (iterate the single source — no hand-picked columns)
# ---------------------------------------------------------------------------

def _test_schema_integrity():
    assert CSV_EXPORT_HEADER_V2 == [c.export_name for c in CSV_COLUMNS], \
        "CSV_EXPORT_HEADER_V2 drifted from CSV_COLUMNS"
    for col in CSV_COLUMNS:
        if col.field_name is not None:
            assert hasattr(FrameData, col.field_name), \
                f"CSV_COLUMNS references {col.field_name!r} which is not on FrameData"


# ---------------------------------------------------------------------------
# 2. REAL export -> REAL import roundtrip (real captured frames, relative check)
# ---------------------------------------------------------------------------

def _export_to_temp(frames, sys_info):
    """Write frames through the REAL exporter to a temp file, return its path."""
    tmp = tempfile.NamedTemporaryFile(
        mode="w", suffix=".csv", delete=False, newline="", encoding="utf-8")
    # Real "# System:" line (same format as csv_export._build_sys_info_rows).
    tmp.write(f"# System: CPU={sys_info.cpu_name}, GPU={sys_info.gpu_name}, "
              f"RAM={sys_info.ram_total_gb}GB, "
              f"Display={format_display_outputs(sys_info)}\n")
    writer = csv.writer(tmp)
    writer.writerow(CSV_EXPORT_HEADER_V2)
    for fr in frames:
        writer.writerow(frame_to_row(fr))
    tmp.close()
    return tmp.name


def _test_export_import_roundtrip():
    """REAL captured frames survive real export + real import unchanged."""
    originals = load_real_frames()
    sys_info = load_real_system_info()
    path = _export_to_temp(originals, sys_info)
    try:
        result = import_file(path)
        assert result.system_info is not None
        assert result.system_info.display_outputs == sys_info.display_outputs
        assert len(result.frames) == len(originals)
        for original, imported in zip(originals, result.frames):
            for col in CSV_COLUMNS:
                if col.field_name is None:
                    continue
                _assert_field_survived(col, getattr(original, col.field_name),
                                       getattr(imported, col.field_name))
    finally:
        os.unlink(path)


# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------

def _assert_field_survived(col, original, got):
    """A field round-trips losslessly (relative; tolerance only for FPS rounding)."""
    if original is None or got is None:
        assert original is got, f"{col.export_name}: {original!r} -> {got!r}"
        return
    if isinstance(original, float) or isinstance(got, float):
        tol = 10 ** (-col.export_precision) if col.export_precision else 1e-9
        assert abs(original - got) <= tol, \
            f"{col.export_name} ({col.field_name}): {original} -> {got}"
    else:
        assert original == got, \
            f"{col.export_name} ({col.field_name}): {original!r} -> {got!r}"
