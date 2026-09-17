# Documentation

User-facing manuals for **IGP Performance Monitor**. Pick a language, then open the page you need.

The same guide is in the app: **Help → User Manual**. The packaged EXE and the installer both include this `docs/` tree. The UI locale (`en` / `zh_CN`) picks `en/` or `zh-CN/`; `zh-TW` and `ja` stay readable here and via in-manual language links.

界面语言目前只有英语和简体中文（`IGP_LANG=en` 或 `zh_CN`）。文档比界面多两种语言，方便阅读。

Contributor / agent notes stay in English at the repo root: [CLAUDE.md](../CLAUDE.md), [CONTRIBUTING.md](../CONTRIBUTING.md), and `.claude/skills/`.

## Languages

| Language | README | User guide | Troubleshooting |
|---|---|---|---|
| English | [README](en/README.md) | [User guide](en/user-guide.md) | [Troubleshooting](en/troubleshooting.md) |
| 简体中文 | [README](zh-CN/README.md) | [使用指南](zh-CN/user-guide.md) | [排障](zh-CN/troubleshooting.md) |
| 繁體中文 | [README](zh-TW/README.md) | [使用指南](zh-TW/user-guide.md) | [疑難排解](zh-TW/troubleshooting.md) |
| 日本語 | [README](ja/README.md) | [ユーザーガイド](ja/user-guide.md) | [トラブルシューティング](ja/troubleshooting.md) |

English is the canonical copy. Other locales follow the same headings so they stay in sync.

## What each page covers

| Page | Audience | Contents |
|---|---|---|
| `README.md` | Anyone landing on the project | What the app is, install assets, features, run-from-source, license |
| `user-guide.md` | People using the packaged app | First capture, window, charts, overlay, CSV, updates, shortcuts, CLI, metric glossary |
| `troubleshooting.md` | When something fails | Admin / ETW, no frames, GPU, overlay, language, updates |

## Directory

```
docs/
  README.md                 This index
  en/                       English (canonical)
  zh-CN/                    Simplified Chinese
  zh-TW/                    Traditional Chinese
  ja/                       Japanese
```

Folder names are BCP 47 language tags. Each locale uses the same three filenames.

To add a language: copy `en/`, translate, and add a row to the table above plus language links at the top of every README.

## Related repo files (not localized)

| File | Role |
|---|---|
| [README.md](../README.md) | GitHub landing page (English) |
| [CHANGELOG.md](../CHANGELOG.md) | Release notes shown in Help → Changelog |
| [CONTRIBUTING.md](../CONTRIBUTING.md) | How to change `src/` |
| [SECURITY.md](../SECURITY.md) | Vulnerability reporting |
| [THIRD_PARTY_NOTICES.md](../THIRD_PARTY_NOTICES.md) | PresentMon / Qt licenses |
