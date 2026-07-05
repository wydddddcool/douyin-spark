# 抖音续火花 🔥

> 自动给抖音好友发消息，让火花永不熄灭。

⚠️ **当前状态说明（2026-07-05）**：
本项目仍在与抖音反爬虫对抗中。
- Web 控制面板、好友拉取、AI 消息生成、定时任务、加密、反风控随机策略：**已实现并单元测试通过**
- **端到端登录链路（首次扫码登录）**：作者本人最近一次成功登录为 2026-07-05 17:04；之后每次新设备/IP 启动扫码，抖音均要求短信二次验证。这是抖音服务端策略，非代码 bug，且单次扫码 + 短信验证后 state.json 长期有效（直至 sessionid 自然过期，约 2-4 周）。
- **Docker / ECS / 云端 headless 环境**：抖音对 headless Chrome 给出"假二维码"占位图（已确认 512x512 PNG，1-bit colormap，非真 QR token）。**不要在全新 ECS 容器里跑扫码登录**。
- **推荐用法**：在你**本地 Mac / Windows**（系统 Chrome，不是 headless）扫码登录一次，让 AI 把 `auth/state.json` 上传到 ECS / Docker；后续 ECS 直接加载 state.json 跳过扫码。

详细见文末 **「登录链路现状」** 一节。

---

## ✨ 特性

- 🤖 **Playwright + 系统 Chrome** — 不被抖音人机验证拦截（**注：人机验证检测在收紧，2026-07 起新会话可能要求短信验证**）
- 💬 **AI 消息生成** — 多 provider 链式下落（agnes → dashscope），失败自动退回本地消息池
- 🛡️ **反风控设计** — 随机打字延迟 + 好友间随机间隔 + 定时 jitter，避免分秒不差
- 👥 **好友列表可视化** — 一键拉取抖音会话列表（含头像、火花天数），勾选即同步为续火花目标
- 🔐 **API key 加密存储** — 基于机器特征绑定，跨机器无法解密
- 🖥️ **Web 控制面板** — Flask 单页，扫码登录、好友管理、定时任务、日志查看全在浏览器里
- 📦 **一键安装** — macOS bash / Windows bat / PyInstaller 打包 / Docker
- 🔁 **开机自启** — macOS launchd / Windows 计划任务，重启电脑照常运行

---

## 📊 对比同类项目

| 项目 | Stars | 自动化引擎 | 反风控 | 消息来源 | Web UI | 跨平台 | 加密 |
|---|---|---|---|---|---|---|---|
| **本项目** | — | Playwright + 系统 Chrome | ✅ 多层随机 | AI + 本地池 | ✅ Flask | ✅ 三平台 | ✅ 机器绑定 |
| [DkoBot/DouYingBot](https://github.com/DkoBot/DouYingBot) | 19 | Selenium + Edge | ❌ | 第三方 API（爱情公寓金句） | ❌ | ❌ Win only | ❌ |
| [ZXEB/douyin-spark-helper](https://github.com/ZXEB/douyin-spark-helper) | 0 | Selenium + Chrome | ❌ | 同上 | ✅ Vue | ⚠️ 部分 | ❌ |

---

## 📋 系统要求

| 系统 | 是否支持 |
|------|---------|
| macOS 12+（推荐） | ✅ 完整支持，一键安装 |
| Windows 10/11 | ⚠️ 需手动安装（见下方） |
| Linux | ⚠️ 需手动安装 |

**必须提前安装：**
- [Google Chrome](https://www.google.com/chrome/)（扫码登录必须用真实 Chrome）
- [Python 3.9 或更高版本](https://www.python.org/downloads/)

---

## 🚀 macOS 一键安装

```bash
# 1. 解压后进入目录
cd douyin-spark

# 2. 运行安装脚本（自动完成所有配置）
bash install.sh
```

安装脚本会自动：
- 创建 Python 虚拟环境
- 安装所有依赖
- 安装 Playwright 浏览器
- 注册开机自启服务（重启后自动运行）
- 打开浏览器控制面板

安装完成后浏览器自动打开 **http://localhost:5001**

---

## 🎯 首次配置（所有系统通用）

打开控制面板后：

1. **扫码登录**
   - 点击「扫码登录」按钮
   - Chrome 窗口弹出，用手机抖音 App「扫一扫」
   - 扫码成功后状态变为「已登录」

2. **拉取好友列表**（推荐）
   - 在「好友列表」区点「🔄 从抖音拉取好友列表」
   - 等待 15-30 秒，自动同步抖音会话列表（含头像、火花天数）
   - 勾选要续火花的好友，自动保存

3. **设置自动运行时间**
   - 在「定时设置」开启自动运行
   - 选择每天几点发送（建议早上 8-10 点）
   - 选择运行日期
   - 点「保存定时」

4. 完成！之后每天自动发送，重启电脑也不影响。

---

## 🖥️ Windows 手动安装

> Windows 不支持一键脚本，需要手动操作。

**第一步：安装 Python**

下载并安装 [Python 3.11](https://www.python.org/downloads/)，安装时勾选 **"Add Python to PATH"**。

**第二步：安装依赖**

解压压缩包后，在文件夹内右键 → 「在终端中打开」，输入：

```bat
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
playwright install chromium
```

**第三步：启动控制面板**

```bat
.venv\Scripts\activate
python web\app.py
```

浏览器打开 **http://localhost:5001**，按「首次配置」步骤操作。

**第四步：设置开机自启（可选）**

打开「任务计划程序」→ 创建基本任务：
- 触发器：登录时
- 操作：启动程序
- 程序：`C:\路径\douyin-spark\.venv\Scripts\python.exe`
- 参数：`web\app.py`
- 起始于：`C:\路径\douyin-spark`

---

## 📚 日常使用

| 操作 | 说明 |
|------|------|
| 控制面板 | http://localhost:5001 |
| 手动运行一次 | 点「立即运行」 |
| 查看日志 | 控制面板底部「运行日志」 |
| 修改好友列表 | 控制面板「好友列表」勾选，或「续火花目标」手输 |
| 修改定时时间 | 控制面板「定时设置」 |

---

## 🧹 卸载（macOS）

```bash
bash uninstall.sh
```

---

## ❓ 常见问题

**Q：提示「登录凭证已过期」**
重新点「扫码登录」，用手机扫一次码即可。一般每隔几周需要重新扫码一次。

**Q：找不到好友**
建议用「好友列表」可视化拉取功能勾选，避免手输昵称出错。手输时确认填写的是对方的**抖音昵称**（个人主页显示的名字），不是你给对方设的备注。

**Q：macOS 安装时提示「5001 端口被占用」**
说明服务已在运行，直接打开 http://localhost:5001 即可。如仍打不开，查看 `auth/web_port.txt` 文件里的实际端口。

**Q：消息发送了但好友没收到**
可能触发了抖音风控，换一天再试，或修改消息风格。本工具已内置随机打字、好友间随机间隔、定时 jitter，但极端情况下仍可能被风控。

**Q：AI 消息生成失败**
检查 `config/settings.yaml` 里的 `api_key` 是否有效。AI 失败时会自动退回本地消息池，不会中断续火花。

**Q：浏览器弹窗无法扫码**
命令行运行 `python main.py --setup` 作为应急方案。

---

## ⚠️ 注意事项

- 本工具仅供个人使用，请勿用于批量营销或骚扰他人
- 抖音可能随时更新页面结构，如遇问题请反馈
- 登录凭证（`auth/state.json`）包含账号信息，请勿分享给他人
- API key 已加密存储（基于本机特征绑定），但跨机器迁移需重新填写

---

## 🏷️ GitHub Topics

如果这个项目对你有帮助，欢迎给仓库加上这些 topics 让更多人发现：

```
douyin, automation, playwright, python, spark, bot, continuity, flask, apscheduler, anti-detection
```

仓库页面右侧齿轮 → Topics → 粘贴上面的关键词。

---

## 📖 文档

完整文档位于 [`docs/`](docs/) 目录：
- [架构总览](docs/architecture.md)
- [核心模块](docs/core-modules.md)
- [Web 应用](docs/web-app.md)
- [配置参考](docs/config.md)
- [部署指南](docs/deployment.md)
- [API 参考](docs/api-reference.md)
- [FAQ](docs/faq.md)
