"""Test: ui_csv_analysis — CsvAnalysisDialog built from a REAL captured ImportResult."""

from src.core.csv_importer import ImportResult
from src.ui.dialogs.csv_analysis_dialog import CsvAnalysisDialog
from src.tests._factory import (
    load_real_frames, load_real_system_info, load_real_frames_by_app,
)


def run():
    result = ImportResult(
        system_info=load_real_system_info(),
        monitored_apps=list(load_real_frames_by_app().keys()),
        frames=load_real_frames(),
        file_path="real_capture.csv",
    )
    dlg = CsvAnalysisDialog(result)
    assert dlg is not None, "CsvAnalysisDialog"
    assert dlg._result is result, "dialog result ref"
    assert "stutter_frame_time" in dlg._cards, "stutter chart card"
    assert hasattr(dlg, "_stutter_result"), "stutter result"
    assert dlg._stutter_result.summaries, "stutter summaries"
