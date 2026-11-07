# 发布指南（Release Guide）

## 怎么发版

1. 确认 `main` 分支状态良好（CI 绿）。
2. 打 tag 并推送：
   ```bash
   git tag v6.0.1 && git push origin v6.0.1
   ```
3. Actions 会自动跑 [release.yml](../.github/workflows/release.yml)：三平台并行打包 → 汇总 → 创建 GitHub Release 并挂产物。
4. 也可在 GitHub → Actions → Release → Run workflow 手动触发（dispatch），可填版本号；留空则用 `electron/package.json` 的 version。

## 产物清单

| 平台 | 文件 | 安装方式 |
| --- | --- | --- |
| Windows 10+ x64 | `*-setup.exe`（NSIS） | 双击安装，可选安装目录 |
| macOS 12+（Intel + Apple Silicon） | `*.dmg`（x64 与 arm64 各一份） | 打开 dmg，拖入 Applications |
| Linux x64（glibc 2.31+） | `*.AppImage` | `chmod +x` 后直接运行 |

每个 Release 均附 `SHA256SUMS.txt`，下载后请核对校验和。

## 用户需要装什么？

安装包已打包前端静态资源、后端代码与 Node/Electron 运行时，**无需安装 Node.js**。
但请注意：**当前版本仍需系统安装 Python 3.9+**，并在安装目录执行
`pip install -r requirements.txt`（后端依赖 cryptography、flask 等）。
Electron 启动时会 spawn 系统 `python`/`python3` 拉起 Flask 后端；PyInstaller 内嵌运行时在 roadmap 中，后续版本将免去 Python 依赖。

## 签名状态

三个平台产物均**未签名**：

- Windows：SmartScreen 弹窗时点「仍要运行」。
- macOS：无开发者证书跳过签名（`identity: null`），首次打开右键 →「打开」，或到「系统设置 → 隐私与安全性」放行。
- Linux AppImage：无需签名。

## 平台系统要求

- Windows：Windows 10 及以上，64 位。
- macOS：macOS 12 Monterey 及以上；Intel 与 Apple Silicon 均支持。
- Linux：x64，glibc ≥ 2.31（Ubuntu 20.04+ / Debian 11+）。

## 已知坑位（Troubleshooting）

- 启动报「启动 Flask 失败」→ 检查系统 Python 是否在 PATH，且已装 requirements.txt。
- Windows 端口占用 → 后端默认 5001，注意冲突。
- macOS 提示「已损坏」→ `xattr -cr /Applications/动态数据登记系统.app` 后重开。
