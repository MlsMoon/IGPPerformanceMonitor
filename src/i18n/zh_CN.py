"""Chinese (Simplified) translations."""

TRANSLATIONS: dict[str, str] = {
    # main.py
    "admin_required_title": "需要管理员权限",
    "admin_required_text": (
        "IGP 性能监控器需要管理员权限才能运行。\n\n"
        '请右键 IGPPerformanceMonitor.exe 选择 [以管理员身份运行]，\n'
        "或在管理员命令提示符中启动。"
    ),
    "admin_required_detail": (
        "PresentMon 通过 Windows ETW（事件跟踪）捕获图形性能数据，\n"
        '需要管理员权限或加入 Performance Log Users 用户组。'
    ),
    "elevation_failed": "提权失败",
    "elevation_failed_text": "无法获取管理员权限：{}",

    # main_window.py
    "window_title": "IGP 性能监控器",
    "status_ready": "就绪",
    "status_ready_hint": "就绪 — 添加进程后点击开始",
    "status_capturing": "采集中... {} 帧 | {:.0f} 秒",
    "status_capture_running": "采集中...",
    "status_capture_stopped": "采集已停止",
    "status_error": "错误：{}",
    "no_processes_title": "未添加进程",
    "no_processes_text": (
        "请至少添加一个要监控的进程名称。\n\n"
        "留空将捕获所有进程（不建议用于实时监控）。"
    ),
    "capture_error_title": "采集错误",
    "export_csv_action": "导出 CSV...",
    "toolbar_main": "主工具栏",
    "always_on_top": "窗口总在最前",

    # process_panel.py
    "process_selection": "进程选择",
    "placeholder_process": "输入进程名称（例如：game.exe）",
    "btn_add": "添加",
    "btn_remove": "移除选中",
    "btn_start": "▶ 开始采集",
    "btn_stop": "■ 停止",
    "label_auto_stop": "自动停止（秒，0=不限）：",
    "placeholder_search": "搜索进程...",
    "available_processes": "可用进程",
    "monitored_processes": "监控进程",
    "tooltip_add": "加入监控",
    "tooltip_remove": "移出监控",
    "btn_refresh": "刷新进程列表",

    # monitor_view.py
    "live_statistics": "实时统计",
    "fps_over_time": "FPS 时间曲线",
    "frame_time": "帧时间",
    "label_fps": "FPS",
    "label_elapsed_time": "已用时间",
    "label_frame_time_ms": "帧时间",
    "stat_frames": "帧数",
    "stat_avg_fps": "平均 FPS",
    "stat_1p_low": "1% 低帧",
    "stat_5p_low": "5% 低帧",
    "stat_min_max": "最低/最高",
    "stat_avg_ft": "平均帧时间",
    "stat_avg_cpu": "平均 CPU",
    "stat_avg_gpu": "平均 GPU",
    "no_data_placeholder": "暂无数据 — 开始采集后显示统计",
    "performance_charts": "性能图表",
    "monitored_apps_label": "监控应用：{}",
    "label_memory_mb": "内存",
    "label_cpu_percent": "CPU",
    "cpu_cores_suffix": "核",
    "label_gpu_percent": "GPU",
    "total_cpu": "总 CPU",
    "total_gpu": "总 GPU",
    "vram": "显存",
    "label_vram_percent": "显存 %",
    "stat_avg_mem": "平均内存",
    "stat_avg_cpu_app": "平均应用 CPU",
    "stat_avg_gpu_app": "平均应用 GPU",
    "stat_avg_vram": "平均显存",
    "stat_no_frames": "无帧",
    "hint_idle_apps": "灰显的应用尚未产生帧——可能未在渲染。",
    "chart_maximize": "放大",
    "chart_restore": "还原",
    "chart_hide": "隐藏",
    "chart_autosize": "自适应",
    "menu_charts": "图表",
    "menu_dark_mode": "深色模式",
    "label_cpu_cores_percent": "CPU 各核心",
    "label_app_cpu_cores": "应用 CPU 核心",
    "label_app_vram_mb": "应用显存",
    "label_system_ram_gb": "系统内存",
    "label_gpu_power_w": "GPU 功耗",
    "label_gpu_temp_c": "GPU 温度",
    "label_core": "核心",
    "charts_panel": "显示 / 隐藏图表",
    "menu_charts_panel": "图表面板",

    # csv_export.py
    "export_title": "导出到 CSV",
    "capture_summary": "采集摘要",
    "total_frames": "总帧数",
    "duration": "持续时间",
    "seconds_unit": "秒",
    "export_scope": "导出范围",
    "all_frames": "所有采集的帧",
    "per_process": "按进程分开（每个进程单独文件）",
    "options": "选项",
    "include_header": "包含 CSV 表头",
    "include_stats": "在文件末尾包含汇总统计",
    "btn_cancel": "取消",
    "btn_export": "导出...",
    "no_data_title": "无数据",
    "no_data_text": "没有可导出的帧数据。",
    "select_dir": "选择导出目录",
    "export_complete": "导出完成",
    "export_complete_multi": "已导出 {} 个文件到：\n{}",
    "export_complete_single": "已导出到：\n{}",
    "save_csv": "保存 CSV",
    "csv_filter": "CSV 文件 (*.csv)",
    "default_filename": "igpmon-export.csv",
    "summary_title": "汇总统计",
    "summary_process": "进程",
    "summary_total_frames": "总帧数",
    "summary_avg_fps": "平均 FPS",
    "summary_min_fps": "最低 FPS",
    "summary_max_fps": "最高 FPS",
    "summary_1p_low": "1% Low (P99)",
    "summary_5p_low": "5% Low (P95)",

    # wrapper
    "wrapper_starting": "正在启动 PresentMon，等待帧数据...",
    "wrapper_stopped": "PresentMon 已正常停止。",
    "wrapper_access_denied": "访问被拒绝。请以管理员身份运行或加入 'Performance Log Users' 组。",
    "wrapper_not_found": "找不到 PresentMon 可执行文件：{}",
    "wrapper_no_config": "未设置配置。",
    "wrapper_exit_error": "PresentMon 异常退出，代码 {}：{}",

    # menu bar
    "menu_file": "文件",
    "menu_view": "视图",
    "menu_help": "帮助",
    "menu_import_csv": "导入 CSV...",
    "menu_check_update": "检查更新...",
    "menu_version_history": "历史版本",
    "rollback_title": "版本回退",
    "rollback_text": "当前版本：{}\n回退到：{}？\n\n将下载并替换 exe（含更新器）。",
    "rollback_no_previous": "没有可回退的历史版本。",
    "rollback_progress": "回退中 — {}",
    "menu_about": "关于...",
    "menu_github": "在 GitHub 上查看",

    # update
    "update_check_title": "更新检查",
    "update_dev_mode": "当前为开发模式（{}）。\n\n自更新仅在打包的 EXE 中可用。",
    "update_checking": "正在检查更新...",
    "update_check_failed": "检查更新失败：\n{}",
    "update_up_to_date": "已是最新版本（{}）。",
    "update_available_title": "发现新版本",
    "update_available_text": "当前版本：{}\n新版本：{}\n\n是否下载并安装？",
    "update_progress": "更新中 — {}",
    "update_installing": "正在安装更新，即将重启...",
    "update_install_failed": "安装失败：\n{}",
    "about_title": "关于 IGP 性能监控器",
    "about_text": (
        "<b>IGP 性能监控器</b><br><br>"
        "版本：{}<br><br>"
        "基于 Intel PresentMon 的实时图形性能监控工具。<br>"
        "支持 FPS、帧时间、CPU、GPU、显存及逐进程指标。<br><br>"
        "开源地址：https://github.com/MlsMoon/IGPPerformanceMonitor"
    ),

    # csv_analysis_dialog.py
    "analysis_title": "CSV 分析",
    "analysis_no_data": "所选文件中无有效帧数据。",
    "import_file_path": "文件",
    "import_file_filter": "CSV 文件 (*.csv)",
    "total_ram": "总内存",

    # changelog dialog
    "changelog_title": "更新记录",
    "menu_changelog": "更新记录",
    "changelog_empty": "暂无更新记录。",
    "btn_close": "关闭",

    # Shortcuts / overlay / 0-frame warning (Tier 0)
    "menu_shortcuts": "快捷键...",
    "shortcuts_title": "键盘快捷键",
    "menu_capture_toggle": "开始/停止采集",
    "menu_overlay_toggle": "显示/隐藏悬浮窗",
    "menu_click_through": "鼠标穿透",
    "sc_capture": "开始 / 停止采集",
    "sc_overlay": "显示 / 隐藏悬浮窗",
    "sc_click_through": "切换悬浮窗鼠标穿透（菜单）",
    "sc_theme": "切换深色 / 浅色主题",
    "sc_export": "导出 CSV",
    "sc_import": "导入 CSV",
    "sc_charts_panel": "显示 / 隐藏图表面板",
    "sc_always_top": "切换窗口置顶",
    "sc_shortcuts": "打开快捷键窗口",
    "ov_frametime": "帧时间",
    "ov_mem": "内存",
    "ov_sys_cpu": "系统CPU",
    "ov_close": "关闭悬浮窗",
    "ov_na": "N/A",
    "ov_dash": "--",
    "warn_no_frames_title": "未采集到帧",
    "warn_no_frames_text": (
        "本次采集未捕获到任何帧。\n\n"
        "请确认进程名正确，且目标应用正在渲染（非后台服务）。"
    ),
}
