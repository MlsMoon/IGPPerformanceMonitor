# Changelog

## Unreleased

- Open-sourced the project (MIT) with English README, contributing, and security docs.
- Self-update now follows GitHub Releases (`app_manifest.json` on the latest release), not object storage.
- Added a Windows installer (`IGPPerformanceMonitor-Setup-x.y.z.exe`, Inno Setup) and GitHub Actions CI/Release workflows.
- Replaced the app icon (window, EXE, installer, README).
- Project workflow skills and source comments are English.

## 0.2.4
- **新增 App VRAM 图表与 CSV 字段**：实时图表和导出数据现在包含单应用显存占用（AppVramMB），并修复平均 App VRAM 统计为空的问题。
- **更新回滚能力**：版本历史支持保留当前版本与上一个版本，便于更新后回退。
- **指标校验增强**：修复 WDDM 环境下 App VRAM 图表为空的问题，并加强 metrics 验证链路。
- **Tier 0 体验改进**：新增快捷键、悬浮窗点击穿透与中英文文案、窗口/进程选择持久化，以及 0 帧采集提示。
- **高 FPS 图表修复**：按时间窗口裁剪历史数据，避免高帧率场景下曲线前段被错误截断。

## 0.2.3
- **UI 美化（精炼现代深色）**：3 层表面（window/panel/card）层次更清晰 + 卡片柔和投影(elevation)、统一圆角(10/8/6)与间距、输入框内嵌底色、焦点环、滚动条/分割条对比增强、悬停十字线彩色圆点提示、plot 四轴统一样式。
- **浅色主题修复**：面板/卡片分层可见（此前 panel_bg==card_bg，卡片在白底上不可辨）。
- **悬浮窗主题化**：去硬编码配色，跟随明暗主题切换（修复此前 overlay 永远黑色的 CLAUDE.md 违规）。

## 0.2.2
- **采集按钮二合一**：开始/停止采集合并为单一切换按钮（空闲显示绿色「开始采集」，采集中显示红色「停止」），减少按钮占用。
- **停止采集后图表横轴定格**：停止采集后横轴不再随墙钟空转滑动，曲线停在最后位置；再次开始采集时从零重新滚动。
- **图表列数自适应**：性能图表网格列数随窗口宽度自适应（1–4 列），宽屏一屏可看更多图。
- **内嵌图表显隐面板**：图表区上方可直接勾选显隐各图表，仍可从 View → 图表面板 控制展开/收起。
- **采集前显示系统信息**：开始采集前即在顶部显示 CPU/GPU/RAM/显示器信息，无需等待首帧。

## 0.2.1
- **采集链路架构收敛**：GUI 与 headless 统一复用 `CaptureSession` 生命周期，降低两种模式行为漂移风险。
- **动态 PID 跟踪**：采样器会补采晚启动/重启的目标进程，并从 PresentMon 实际出帧 PID 回填进程指标，减少 App CPU/内存/GPU 长期为空的情况。
- **CSV 字段 schema 统一**：导入、导出和 roundtrip 测试共用同一字段定义，保留 PresentMon 2.4.1 短列名与旧列名兼容。
- **1080p 与小屏图表优化**：性能图表改为滚动长面板，默认 11 张图仍可见；小屏/双屏拖动时自动收敛坐标轴刻度，避免图表被压扁或刻度文字挤压。
- **图表显隐面板不再启动自动弹出**：仍可从 View → 图表面板打开，但不会默认遮挡首屏图表。

## 0.2.0
- **更新记录窗口重构**：左侧版本列表 + 右侧内容，点击版本切换显示，跟随明暗主题。
- **性能图表重新设计**：自适应明暗主题、实时数据徽章（当前值叠加在曲线上）、悬停十字线追踪。
- **新增 CPU 指标**：CPU 总占用比例（占系统总 CPU 的百分比）和逻辑核心数，在悬浮窗和导出 CSV 中可见。
- **进程搜索防抖**：修复快速输入时界面卡顿，搜索 300ms 防抖 + 批量更新进程列表。
- **修复多应用监控**：同进程名多个实例各自独立悬浮窗；空闲应用不再从列表中消失。
- **修复列表选中颜色**：明暗主题下选中行文字/背景色可读，失焦时保持选中态颜色。
- **按进程名分别存储历史**：切换监控应用时图表 CPU/内存/GPU 曲线不再混入上一应用的数据。
- **Theme 系统完善**：新增 `selection_text` 字段，统一选中态文字颜色，修复 libpng iCCP 警告。
- **测试套件重构**：拆分为 12 个独立文件（模型 / i18n / 数据存储 / CSV 解析 / 筛选 / 系统指标 / 主题 / UI 冒烟），覆盖更完整。
- **开发工具**：新增 dev-guide 分模块开发指南、release 发版自动化技能。

## 0.1.3
- 内存口径对齐任务管理器：改用 USS（私有工作集），失败回退 RSS；CPU/GPU/VRAM 口径本就与任务管理器一致，保持不变。
- 修复 CSV 导入分析时 CPU/内存/显存为空：导入器现在正确读回导出的 enriched 列。
- CSV 分析视图重构为离线数据可视化：摘要卡 + Performance / System Metrics / Data Quality 三个 Tab，含覆盖率与异常点表。
- 修复主程序退出后悬浮窗未关闭：新增 overlay shutdown，停止定时器并清理。
- 保留导出 CSV 中的 FPS 原值；仅当无 FPS 列时才按帧间隔推导。

## 0.1.2
- 修复线上 `app_manifest.json` 带 UTF-8 BOM 导致客户端检查更新失败的问题。
- 上传脚本生成无 BOM manifest，后续发布不会再触发 `Invalid JSON`。
- 新增启动自动检查更新：打包版启动后静默检查，有更新时才提示安装。

## 0.1.1
- 发布 semver 迁移后的首个可更新版本（0.1.0 → 0.1.1），用于验证自更新链路。
- 修复版本号系统：VERSION 单一源、构建元数据拆分、semver 解析比较、防降级逻辑不再使用字符串比较。
- 新增更新记录窗口，可从帮助菜单查看 CHANGELOG.md。

## 0.1.0
- 独立采样器修复 CPU 数据丢失（TotalCPU%/AppCPU% 不再为 0/NA）
- 缺失值统一为 None，导出/统计/渲染全部 None-aware（真 0 保留、缺失写 NA）
- 图表交互：放大/自适应/隐藏按钮、双击放大、右键菜单、视图菜单显隐、FPS EMA 平滑
- Headless 采集模式（`--headless` 输出 CSV + 统计 + system 头）
- 悬浮窗重构：流畅跟随（缓存 HWND 轮询）、主窗口识别、最小化隐藏、FPS 平滑
- 提权三入口（main.py runas / bat 自提权 / exe uac_admin）与 temp 目录整理
- 版本号系统改为 semver（VERSION 单一源 + 解析比较），新增 Changelog 窗口
