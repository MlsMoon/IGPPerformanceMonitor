# IGP Performance Monitor

[English](../en/README.md) · [简体中文](../zh-CN/README.md) · [繁體中文](README.md) · [日本語](../ja/README.md)

[使用指南](user-guide.md) · [疑難排解](troubleshooting.md) · [所有語言](../README.md)

[![CI](https://github.com/MlsMoon/IGPPerformanceMonitor/actions/workflows/ci.yml/badge.svg)](https://github.com/MlsMoon/IGPPerformanceMonitor/actions/workflows/ci.yml)
[![Release](https://img.shields.io/github/v/release/MlsMoon/IGPPerformanceMonitor)](https://github.com/MlsMoon/IGPPerformanceMonitor/releases/latest)
[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](../../LICENSE)

Windows 桌面即時圖形效能監視器。程式封裝 [Intel PresentMon](https://github.com/GameTechDev/PresentMon) 2.4.1，為每一幀補上系統 / 處理程序指標（CPU、記憶體、NVIDIA GPU / 顯示記憶體），並以 PyQt5 繪製即時圖表。

<p align="center">
  <img src="../../assets/logo.png" alt="IGP Performance Monitor" width="128" height="128">
</p>

**需要系統管理員權限**（或加入 Windows「Performance Log Users」群組）。PresentMon 使用 ETW。

程式介面支援英語與簡體中文。本目錄是繁體中文手冊。

## 安裝

從 [GitHub Releases](https://github.com/MlsMoon/IGPPerformanceMonitor/releases/latest) 下載最新安裝程式或可攜版 EXE：

| 資源 | 用途 |
|---|---|
| `IGPPerformanceMonitor-Setup-x.y.z.exe` | 建議使用。安裝到 Program Files，含開始功能表捷徑與解除安裝程式，會要求系統管理員權限。 |
| `IGPPerformanceMonitor.exe` | 單檔可攜版（應用程式內更新也使用此套件）。 |
| `auto_updater.exe` | 說明 → 檢查更新 使用的內部替換程式，請勿手動執行。 |

套件版啟動後會向 GitHub Releases 檢查更新，也可以還原到上一份已發布版本。

擷取、讀圖、匯出 CSV、疊加視窗：見 **[使用指南](user-guide.md)**。

## 功能

- 同時監視多個處理程序
- 即時圖表：幀率、幀時間、CPU / GPU / 記憶體 / 顯示記憶體，分應用與整機
- 置頂疊加視窗，跟隨目標視窗
- CSV 匯出 / 匯入，離線卡頓分析
- 介面英語 / 簡體中文（`IGP_LANG=en` 或 `zh_CN`）
- 深色 / 淺色主題
- 從 GitHub Releases 應用程式內更新（SHA256 驗證）

## 執行環境

- Windows 10 或 11（64 位元）
- 系統管理員，或「Performance Log Users」群組成員
- 目標程式必須真正在呈現幀（背景服務不行）
- GPU / 顯示記憶體 / 功耗 / 溫度圖建議使用 NVIDIA（NVML）。AMD、Intel 顯示卡仍可透過 PresentMon 取得幀時間與幀率

## 從原始碼執行

```bat
pip install -r requirements.txt
Scripts\run_dev.bat
```

```bat
python -m src.main --debug
```

無介面擷取（需系統管理員）。請優先使用 `Scripts\capture_debug.bat`，這樣 UAC 提權後仍會寫入 `temp\`：

```bat
Scripts\capture_debug.bat --process-name Unity.exe --timed 10
python -m src.main --headless --process-name Unity.exe --timed 10
```

## 建置

```bat
pip install -r requirements-dev.txt
Scripts\build.bat
Scripts\build_installer.bat
python Scripts\generate_manifest.py
```

產物在 `dist\`：

- `IGPPerformanceMonitor.exe`
- `auto_updater.exe`
- `IGPPerformanceMonitor-Setup-<version>.exe`（需要 [Inno Setup 6](https://jrsoftware.org/isinfo.php)）
- `app_manifest.json`（GitHub Release 中繼資料）

預設分支是 **`develop`**。穩定化與標籤在 **`release`**。兩條分支都受保護。

在 `release` 上打與 `VERSION` 一致的附註標籤 `vX.Y.Z` 會執行 `.github/workflows/release.yml`，將上述檔案發佈到 GitHub Release。

## 測試

```bat
python -m src.tests
```

離螢幕 Qt 會自動設定。詳見 `.claude/skills/test-after-changes/SKILL.md` 與 `.claude/skills/test-design/SKILL.md`。

## 貢獻與安全性

- [CONTRIBUTING.md](../../CONTRIBUTING.md)
- [SECURITY.md](../../SECURITY.md)
- [CODE_OF_CONDUCT.md](../../CODE_OF_CONDUCT.md)
- [CHANGELOG.md](../../CHANGELOG.md)

## 授權

MIT。PresentMon 依 Intel 自己的授權隨附，見 [第三方聲明](../../THIRD_PARTY_NOTICES.md)。
