"""English translations."""

TRANSLATIONS: dict[str, str] = {
    # main.py
    "admin_required_title": "Administrator Required",
    "admin_required_text": (
        "IGP Performance Monitor requires Administrator privileges to run.\n\n"
        'Right-click IGPPerformanceMonitor.exe and select "Run as Administrator",\n'
        "or run from an Administrator command prompt."
    ),
    "admin_required_detail": (
        "PresentMon uses Windows ETW (Event Tracing for Windows) to capture "
        "graphics performance data, which requires Administrator privileges "
        "or membership in the \"Performance Log Users\" group."
    ),
    "elevation_failed": "Elevation Failed",
    "elevation_failed_text": "Failed to request administrator privileges: {}",

    # main_window.py
    "window_title": "IGP Performance Monitor",
    "window_title_dev": "{}  [dev]",
    "dev_badge": "DEV",
    "status_ready": "Ready",
    "status_ready_hint": "Ready — add processes and click Start",
    "status_capturing": "Capturing... {} frames | {:.0f}s elapsed",
    "status_capture_running": "Capture running...",
    "status_capture_stopped": "Capture stopped",
    "status_error": "Error: {}",
    "no_processes_title": "No Processes",
    "no_processes_text": (
        "Please add at least one process name to monitor.\n\n"
        "Leave empty to capture ALL processes (not recommended for live monitoring)."
    ),
    "capture_error_title": "Capture Error",
    "export_csv_action": "Export CSV...",
    "toolbar_main": "Main",
    "always_on_top": "Always on Top",

    # process_panel.py
    "process_selection": "Process Selection",
    "placeholder_process": "Enter process name (e.g., game.exe)",
    "btn_add": "Add",
    "btn_remove": "Remove Selected",
    "btn_start": "▶ Start Capture",
    "btn_stop": "■ Stop",
    "label_auto_stop": "Auto-stop after (seconds, 0=unlimited):",
    "placeholder_search": "Search processes...",
    "available_processes": "Available Processes",
    "monitored_processes": "Monitored Processes",
    "tooltip_add": "Add to monitored",
    "tooltip_remove": "Remove from monitored",
    "btn_refresh": "Refresh Process List",

    # monitor_view.py
    "live_statistics": "Live Statistics",
    "fps_over_time": "FPS Over Time",
    "frame_time": "Frame Time",
    "label_fps": "FPS",
    "label_elapsed_time": "Elapsed Time",
    "label_frame_time_ms": "Frame Time",
    "stat_frames": "Frames",
    "stat_avg_fps": "Avg FPS",
    "stat_1p_low": "1% Low",
    "stat_5p_low": "5% Low",
    "stat_min_max": "Min/Max",
    "stat_avg_ft": "Avg FT",
    "stat_avg_cpu": "Avg CPU",
    "stat_avg_gpu": "Avg GPU",
    "no_data_placeholder": "No data — start capture to see statistics",
    "performance_charts": "Performance Charts",
    "monitored_apps_label": "Monitored: {}",
    "label_memory_mb": "Memory",
    "label_cpu_percent": "CPU",
    "cpu_cores_suffix": " cores",
    "label_gpu_percent": "GPU",
    "total_cpu": "Total CPU",
    "total_gpu": "Total GPU",
    "vram": "VRAM",
    "label_vram_percent": "VRAM %",
    "stat_avg_mem": "Avg Memory",
    "stat_avg_cpu_app": "Avg App CPU",
    "stat_avg_gpu_app": "Avg App GPU",
    "stat_avg_vram": "Avg VRAM",
    "stat_no_frames": "no frames",
    "hint_idle_apps": "Greyed apps produced no frames yet — they may not be rendering.",
    "chart_maximize": "Maximize",
    "chart_restore": "Restore",
    "chart_hide": "Hide",
    "chart_autosize": "AutoSize",
    "menu_charts": "Charts",
    "menu_dark_mode": "Dark Mode",
    "label_cpu_cores_percent": "CPU Cores",
    "label_app_cpu_cores": "App CPU Cores",
    "label_app_vram_mb": "App VRAM",
    "label_system_ram_gb": "System RAM",
    "label_gpu_power_w": "GPU Power",
    "label_gpu_temp_c": "GPU Temp",
    "label_core": "Core",
    "charts_panel": "Show / hide charts",
    "menu_charts_panel": "Charts Panel",
    "system_info_panel": "System info",

    # csv_export.py
    "export_title": "Export to CSV",
    "capture_summary": "Capture Summary",
    "total_frames": "Total frames",
    "duration": "Duration",
    "seconds_unit": "seconds",
    "export_scope": "Export Scope",
    "all_frames": "All captured frames",
    "per_process": "Per-process (separate file for each)",
    "options": "Options",
    "include_header": "Include CSV header",
    "include_stats": "Include summary statistics at end of file",
    "btn_cancel": "Cancel",
    "btn_export": "Export...",
    "no_data_title": "No Data",
    "no_data_text": "No frame data to export.",
    "select_dir": "Select Export Directory",
    "export_complete": "Export Complete",
    "export_complete_multi": "Exported {} file(s) to:\n{}",
    "export_complete_single": "Exported to:\n{}",
    "save_csv": "Save CSV",
    "csv_filter": "CSV Files (*.csv)",
    "default_filename": "igpmon-export.csv",
    "summary_title": "Summary Statistics",
    "summary_process": "Process",
    "summary_total_frames": "Total Frames",
    "summary_avg_fps": "Avg FPS",
    "summary_min_fps": "Min FPS",
    "summary_max_fps": "Max FPS",
    "summary_1p_low": "1% Low (P99)",
    "summary_5p_low": "5% Low (P95)",

    # wrapper
    "wrapper_starting": "Starting PresentMon, waiting for frames...",
    "wrapper_stopped": "PresentMon stopped normally.",
    "wrapper_access_denied": "Access denied. Run as Administrator or join 'Performance Log Users' group.",
    "wrapper_not_found": "PresentMon executable not found: {}",
    "wrapper_no_config": "No configuration set.",
    "wrapper_exit_error": "PresentMon exited with code {}: {}",

    # menu bar
    "menu_file": "File",
    "menu_view": "View",
    "menu_help": "Help",
    "menu_import_csv": "Import CSV...",
    "menu_check_update": "Check for Updates...",
    "menu_version_history": "Version History",
    "rollback_title": "Version Rollback",
    "rollback_text": "Current version: {}\nRollback to: {}?\n\nThis downloads and replaces the exe (and updater).",
    "rollback_no_previous": "No previous version is available for rollback.",
    "rollback_progress": "Rolling back — {}",
    "menu_about": "About...",
    "menu_github": "View on GitHub",

    # update
    "update_check_title": "Update Check",
    "update_dev_mode": "Running in dev mode ({}).\n\nSelf-update is only available in the packaged EXE.",
    "update_checking": "Checking for updates...",
    "update_check_failed": "Failed to check for updates:\n{}",
    "update_up_to_date": "You are up to date ({}).",
    "update_available_title": "Update Available",
    "update_available_text": "Current version: {}\nNew version: {}\n\nDownload and install now?",
    "update_progress": "Updating — {}",
    "update_stage_app": "Downloading the application...",
    "update_stage_updater": "Downloading the updater...",
    "update_stage_verify": "Verifying the download...",
    "update_stage_install": "Starting the installer...",
    "update_stage_cancelling": "Cancelling...",
    "update_progress_bytes": "{} of {}  ({}%)",
    "update_installing": "Installing update, restarting...",
    "update_install_failed": "Install failed:\n{}",
    "about_title": "About IGP Performance Monitor",
    "about_text": (
        "<b>IGP Performance Monitor</b><br><br>"
        "Version: {}<br><br>"
        "Real-time graphics performance monitoring powered by Intel PresentMon.<br>"
        "Supports FPS, frame time, CPU, GPU, VRAM, and per-process metrics.<br><br>"
        "Open source: https://github.com/MlsMoon/IGPPerformanceMonitor"
    ),

    # csv_analysis_dialog.py
    "analysis_title": "CSV Analysis",
    "analysis_no_data": "No valid frame data found in the selected file.",
    "import_file_path": "File",
    "import_file_filter": "CSV Files (*.csv)",
    "total_ram": "Total RAM",

    # changelog dialog
    "changelog_title": "Changelog",
    "menu_changelog": "Changelog",
    "changelog_empty": "No changelog entries yet.",
    "btn_close": "Close",
    "menu_user_manual": "User Manual",
    "user_manual_title": "User Manual",
    "user_manual_page_guide": "User guide",
    "user_manual_page_troubleshooting": "Troubleshooting",
    "user_manual_empty": "The user manual is not available in this build.",

    # shortcuts / overlay / 0-frame warnings (Tier 0)
    "menu_shortcuts": "Keyboard Shortcuts...",
    "shortcuts_title": "Keyboard Shortcuts",
    "menu_capture_toggle": "Start/Stop Capture",
    "menu_overlay_toggle": "Show/Hide Overlays",
    "menu_click_through": "Click-through",
    "sc_capture": "Start / Stop capture",
    "sc_overlay": "Show / Hide overlays",
    "sc_click_through": "Toggle overlay click-through (menu)",
    "sc_theme": "Toggle dark / light theme",
    "sc_export": "Export CSV",
    "sc_import": "Import CSV",
    "sc_charts_panel": "Show / Hide charts panel",
    "sc_always_top": "Toggle always-on-top",
    "sc_shortcuts": "Open this shortcuts window",
    "ov_frametime": "Frame Time",
    "ov_mem": "Memory",
    "ov_sys_cpu": "System CPU",
    "ov_close": "Close overlay",
    "ov_na": "N/A",
    "ov_dash": "--",
    "warn_no_frames_title": "No Frames Captured",
    "warn_no_frames_text": (
        "No frames were captured in this session.\n\n"
        "Check that the process name is correct and the target app is "
        "rendering (not a background service)."
    ),
}
