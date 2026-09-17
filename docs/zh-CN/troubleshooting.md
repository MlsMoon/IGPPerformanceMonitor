# 排障

[English](../en/troubleshooting.md) · [简体中文](README.md) · [繁體中文](../zh-TW/troubleshooting.md) · [日本語](../ja/troubleshooting.md)

配合 [使用指南](user-guide.md) 使用。

## 管理员 / 「拒绝访问」

PresentMon 需要 ETW。提权失败时：

- 右键 EXE → **以管理员身份运行**
- 或把账户加入 **Performance Log Users**（计算机管理 → 本地用户和组 → 组），然后注销再登录
- 组策略或杀毒软件可能拦截 `ShellExecuteW("runas")`。请先打开已提权的命令提示符再运行

打包 EXE 声明了 `requireAdministrator`。Python 入口和 `Scripts\run_dev.bat` 会通过 UAC 重新拉起。

## 没有采集到帧

停止时的提示表示 PresentMon 跑过了，但没有解析到 present。

- 进程名必须是真正在呈现的那个（`game.exe`，不是商店启动器）
- 应用必须在 **渲染**。最小化的 Unity 编辑器或后台服务不会出帧
- 游戏启动后再点 **刷新进程列表**
- 独占全屏若一直为空，可改无边框窗口再试
- 无界面：看 `temp\igp_debug.log` 里的 PresentMon 标准错误

## GPU / 显存 / 功耗 / 温度是空的

这些序列需要 NVIDIA 后端（NVML，或封装 `nvidia-smi` 的 GPUtil）。

- 安装较新的 Game Ready / Studio 驱动
- AMD、Intel 显卡仍能从 PresentMon 得到 FPS 和帧时间
- 没有 GPU 后端时这些图默认隐藏——装好驱动后可在 视图 → 图表 里打开
- 分进程 GPU 可能 **短暂高于** 整机 GPU。这是两套 NVIDIA API，不是图画错了

空单元格是缺测（`None`），不是零。

## 叠加窗没有出现，或跟错窗口

- 必须正在采集；停止后叠加窗会隐藏
- **F9** 可能把它们全部压住了
- 跟踪的是 **最大的** 可见带标题窗口，会忽略很小的置顶工具窗
- 多窗口应用（Unity 编辑器、浏览器）：叠加窗跟最大的那块
- 目标最小化时叠加窗会藏起来，还原后再出现

## 点不到叠加窗

**视图 → 点击穿透** 会把鼠标交给游戏，此时叠加窗上右键无效。到视图菜单关掉穿透，或用 **F9** 隐藏叠加窗。

## 自我更新没反应 / 「开发模式」

帮助 → 检查更新 只在 **打包 EXE** 里有效。`python -m src.main` 一定会提示开发模式。

打包版检查失败：网络、GitHub 不可用，或公司代理拦截了 `github.com`。下载需要普通浏览器 User-Agent（程序已经带了）。

回退需要先前更新留下的旧版本。第一次安装没有可回退目标。

## 界面语言不对

菜单里没有语言项。

```bat
set IGP_LANG=en
set IGP_LANG=zh_CN
```

Windows 区域以 `zh` 开头时用简体中文。繁体中文系统在界面里同样映射到 `zh_CN`。`docs/zh-TW/` 只是文档。

改完 `IGP_LANG` 后请重启程序。

## 图表不见了

显隐会记住。到 **视图 → 图表** 或按 **Ctrl+J** 重新勾选。最大化一张卡片会暂时藏起其余卡片，点还原即可。

## 窗口太窄 / 名称被截断

过长的 GPU 名和进程名会 **省略显示**，好让窗口维持在大约 1000×680。把鼠标放到信息条或列表行上可看全名。

## 开销很大 / 采集很吵

不要在图形界面里监视整台机器。列表尽量短。`--all-processes` 只适合短时无界面采集。

解锁帧率的游戏在原始 FPS 上会跳；界面 EMA 只是观感。看卡顿请用帧时间或 1% Low。

## 深色模式下标题栏是白的

当前版本已处理：程序会给 DWM 标题栏上色，并且在「窗口置顶」之后重新应用（该选项会重建 HWND）。若仍看到白条，说明还是旧构建，请从 GitHub Releases 更新。

## 非管理员环境跑无界面，没有输出文件

`python -m src.main --headless` 会经 UAC 重新启动。提权后的进程继承不到原来的控制台，输出可能丢失。请用 `Scripts\capture_debug.bat`：它会自行提权，并且仍然写入 `temp\`。

## 仍未解决

1. 帮助 → 关于 — 记下版本和构建号（`yyyyMMdd-HHmmss-gitsha`）
2. 用 `--debug` 复现，并附上 `temp\igp_debug.log`
3. 在 [GitHub](https://github.com/MlsMoon/IGPPerformanceMonitor/issues) 开 issue

安全问题不要公开提 issue，见 [SECURITY.md](../../SECURITY.md)。
