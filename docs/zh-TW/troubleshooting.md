# 疑難排解

[English](../en/troubleshooting.md) · [简体中文](../zh-CN/troubleshooting.md) · [繁體中文](README.md) · [日本語](../ja/troubleshooting.md)

請搭配 [使用指南](user-guide.md) 使用。

## 系統管理員 / 「拒絕存取」

PresentMon 需要 ETW。提權失敗時：

- 以滑鼠右鍵按 EXE → **以系統管理員身分執行**
- 或把帳戶加入 **Performance Log Users**（電腦管理 → 本機使用者和群組 → 群組），然後登出再登入
- 群組原則或防毒軟體可能攔截 `ShellExecuteW("runas")`。請先開啟已提權的命令提示字元再執行

套件 EXE 宣告了 `requireAdministrator`。Python 進入點與 `Scripts\run_dev.bat` 會透過 UAC 重新啟動。

## 沒有擷取到幀

停止時的提示表示 PresentMon 有執行，但沒有解析到 present。

- 處理程序名稱必須是真正在呈現的那個（`game.exe`，不是商店啟動器）
- 應用程式必須在 **繪製**。最小化的 Unity 編輯器或背景服務不會出幀
- 遊戲啟動後再按 **重新整理處理程序清單**
- 獨佔全螢幕若一直是空的，可改無框視窗再試
- 無介面：查看 `temp\igp_debug.log` 裡的 PresentMon 標準錯誤

## GPU / 顯示記憶體 / 功耗 / 溫度是空的

這些序列需要 NVIDIA 後端（NVML，或封裝 `nvidia-smi` 的 GPUtil）。

- 安裝較新的 Game Ready / Studio 驅動程式
- AMD、Intel 顯示卡仍能從 PresentMon 取得 FPS 與幀時間
- 沒有 GPU 後端時這些圖預設隱藏——裝好驅動程式後可在 檢視 → 圖表 開啟
- 分處理程序 GPU 可能 **短暫高於** 整機 GPU。這是兩套 NVIDIA API，不是圖畫錯

空白儲存格是缺測（`None`），不是零。

## 疊加視窗沒有出現，或跟錯視窗

- 必須正在擷取；停止後疊加視窗會隱藏
- **F9** 可能把它們全部壓住了
- 追蹤的是 **最大的** 可見且有標題的視窗，會忽略很小的置頂工具視窗
- 多視窗應用程式（Unity 編輯器、瀏覽器）：疊加視窗跟最大的那一塊
- 目標最小化時疊加視窗會藏起來，還原後再出現

## 點不到疊加視窗

**設定 → 點選穿透** 會把滑鼠交給遊戲，此時疊加視窗上按右鍵無效。到設定功能表關閉穿透，或用 **F9** 隱藏疊加視窗。

## 自我更新沒反應 / 「開發模式」

說明 → 檢查更新 只在 **套件 EXE** 裡有效。`python -m src.main` 一定會提示開發模式。

套件版檢查失敗：網路、GitHub 無法使用，或公司 Proxy 攔截了 `github.com`。下載需要一般瀏覽器 User-Agent（程式已經帶了）。

還原需要先前更新留下的舊版本。第一次安裝沒有可還原目標。

## 介面語言不對

**設定 → 語言** 可在英語與簡體中文之間切換，不必重啟行程。下次啟動時 `IGP_LANG` 仍優先。

```bat
set IGP_LANG=en
set IGP_LANG=zh_CN
```

尚未儲存語言時，Windows 地區以 `zh` 開頭則使用簡體中文。繁體中文系統在**程式介面**同樣對應到 `zh_CN`。`docs/zh-TW/` 只是文件。

## 圖表不見了

顯示隱藏會記住。到 **檢視 → 圖表** 或按 **Ctrl+J** 重新勾選。最大化一張卡片會暫時藏起其餘卡片，按還原即可。

## 視窗太窄 / 名稱被截斷

過長的 GPU 名稱與處理程序名稱會 **省略顯示**，好讓視窗維持在大約 1000×680。將滑鼠移到資訊列或清單列上可看全名。

## 負擔很大 / 擷取很吵

不要在圖形介面裡監視整台電腦。清單盡量短。`--all-processes` 只適合短時間無介面擷取。

無上限幀率的遊戲在原始 FPS 上會跳動；介面 EMA 只是觀感。看卡頓請用幀時間或 1% Low。

## 深色模式下標題列是白的

目前版本已處理：程式會為 DWM 標題列上色，並且在「視窗置頂」之後重新套用（該選項會重建 HWND）。若仍看到白條，表示還是舊建置，請從 GitHub Releases 更新。

## 非系統管理員環境跑無介面，沒有輸出檔

`python -m src.main --headless` 會經 UAC 重新啟動。提權後的處理程序繼承不到原來的主控台，輸出可能遺失。請使用 `Scripts\capture_debug.bat`：它會自行提權，並且仍然寫入 `temp\`。

## 仍未解決

1. 說明 → 關於 — 記下版本與建置編號（`yyyyMMdd-HHmmss-gitsha`）
2. 用 `--debug` 重現，並附上 `temp\igp_debug.log`
3. 在 [GitHub](https://github.com/MlsMoon/IGPPerformanceMonitor/issues) 開 issue

安全性問題請勿公開提 issue，見 [SECURITY.md](../../SECURITY.md)。
