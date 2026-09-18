# IGP Performance Monitor

<p align="center">
  <img src="../../assets/logo.png" alt="IGP Performance Monitor" width="128" height="128">
</p>

<p align="center">
  Windows 桌面端实时图形性能监视器。
</p>

<p align="center">
  <a href="https://github.com/MlsMoon/IGPPerformanceMonitor/releases/latest"><strong>下载</strong></a>
  &nbsp;·&nbsp;
  <a href="user-guide.md"><strong>使用指南</strong></a>
  &nbsp;·&nbsp;
  <a href="troubleshooting.md"><strong>排障</strong></a>
  &nbsp;·&nbsp;
  <a href="../../CHANGELOG.zh-CN.md"><strong>更新记录</strong></a>
</p>

<p align="center">
  <a href="../en/README.md">English</a>
  ·
  <a href="README.md">简体中文</a>
  ·
  <a href="../zh-TW/README.md">繁體中文</a>
  ·
  <a href="../ja/README.md">日本語</a>
</p>

<p align="center">
  <a href="https://github.com/MlsMoon/IGPPerformanceMonitor/actions/workflows/ci.yml"><img alt="CI" src="https://github.com/MlsMoon/IGPPerformanceMonitor/actions/workflows/ci.yml/badge.svg"></a>
  <a href="https://github.com/MlsMoon/IGPPerformanceMonitor/releases/latest"><img alt="Release" src="https://img.shields.io/github/v/release/MlsMoon/IGPPerformanceMonitor"></a>
  <a href="user-guide.md"><img alt="使用指南" src="https://img.shields.io/badge/docs-%E4%BD%BF%E7%94%A8%E6%8C%87%E5%8D%97-c41e3a"></a>
  <a href="../../LICENSE"><img alt="License: MIT" src="https://img.shields.io/badge/License-MIT-blue.svg"></a>
</p>

程序封装 [Intel PresentMon](https://github.com/GameTechDev/PresentMon) 2.4.1，为每一帧补上系统 / 进程指标（CPU、内存、NVIDIA GPU / 显存），并用 PyQt5 绘制实时图表。

**需要管理员权限**（或加入 Windows「Performance Log Users」组）。PresentMon 使用 ETW。

程序界面支持英语和简体中文。本目录是简体中文手册。

## 安装

从 [GitHub Releases](https://github.com/MlsMoon/IGPPerformanceMonitor/releases/latest) 下载最新安装包或便携版 EXE：

| 资源 | 用途 |
|---|---|
| `IGPPerformanceMonitor-Setup-x.y.z.exe` | 推荐。安装到 Program Files，带开始菜单快捷方式和卸载程序，会请求管理员权限。 |
| `IGPPerformanceMonitor.exe` | 单文件便携版（应用内更新也使用这个包）。 |
| `auto_updater.exe` | 帮助 → 检查更新 用的内部替换程序，不要手动运行。 |

打包版启动后会向 GitHub Releases 检查更新，也可以回退到上一份已发布版本。

## 文档

| | 链接 |
|---|---|
| 采集、读图、导出 CSV、叠加窗 | **[使用指南](user-guide.md)** |
| 出问题时 | **[排障](troubleshooting.md)** |
| 版本变化 | **[更新记录](../../CHANGELOG.zh-CN.md)** |
| 其他语言 | [文档目录](../README.md) |

同一套使用指南也在应用内 **帮助 → 用户手册**。

## 功能

- 同时监视多个进程
- 实时图表：帧率、帧时间、CPU / GPU / 内存 / 显存，分应用与整机
- 置顶叠加窗，跟随目标窗口
- CSV 导出 / 导入，离线卡顿分析
- 界面英语 / 简体中文（`IGP_LANG=en` 或 `zh_CN`）
- 深色 / 浅色主题
- 从 GitHub Releases 应用内更新（SHA256 校验）

## 运行环境

- Windows 10 或 11（64 位）
- 管理员，或「Performance Log Users」组成员
- 目标程序必须真正在呈现帧（后台服务不行）
- GPU / 显存 / 功耗 / 温度图建议 NVIDIA（NVML）。AMD、Intel 显卡仍可通过 PresentMon 得到帧时间与帧率

## 从源码运行

```bat
pip install -r requirements.txt
Scripts\run_dev.bat
```

```bat
python -m src.main --debug
```

无界面采集（需管理员）。优先用 `Scripts\capture_debug.bat`，这样 UAC 提权后仍会写入 `temp\`：

```bat
Scripts\capture_debug.bat --process-name Unity.exe --timed 10
python -m src.main --headless --process-name Unity.exe --timed 10
```

## 构建

```bat
pip install -r requirements-dev.txt
Scripts\build.bat
Scripts\build_installer.bat
python Scripts\generate_manifest.py
```

产物在 `dist\`：

- `IGPPerformanceMonitor.exe`
- `auto_updater.exe`
- `IGPPerformanceMonitor-Setup-<version>.exe`（需要 [Inno Setup 6](https://jrsoftware.org/isinfo.php)）
- `app_manifest.json`（GitHub Release 元数据）

默认分支是 **`develop`**。稳定化与标签在 **`release`**。两条分支都受保护。

在 `release` 上打与 `VERSION` 一致的附注标签 `vX.Y.Z` 会跑 `.github/workflows/release.yml`，把上述文件发到 GitHub Release。

## 测试

```bat
python Scripts/check.py
python -m src.main -t ui
python -m src.main -t update
python -m src.tests
```

采集自检需要管理员：`Scripts\selfcheck.bat capture -a App.exe -s 8`。详见 `.claude/skills/test-after-changes/SKILL.md`。

## 贡献与安全

- [CONTRIBUTING.md](../../CONTRIBUTING.md)
- [SECURITY.md](../../SECURITY.md)
- [CODE_OF_CONDUCT.md](../../CODE_OF_CONDUCT.md)
- [CHANGELOG.zh-CN.md](../../CHANGELOG.zh-CN.md)

## 许可

MIT。PresentMon 按 Intel 自己的许可随包分发，见 [第三方声明](../../THIRD_PARTY_NOTICES.md)。
