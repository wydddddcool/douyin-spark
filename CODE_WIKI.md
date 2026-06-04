# 抖音续火花 - Code Wiki

> 完整的项目技术文档和开发者指南

## 目录

- [项目概述](./docs/overview.md)
- [架构设计](./docs/architecture.md)
- [核心模块](./docs/core-modules.md)
  - [认证模块 (core/auth.py)](./docs/core-modules.md#认证模块-coreauthpy)
  - [浏览器模块 (core/browser.py)](./docs/core-modules.md#浏览器模块-corebrowserpy)
  - [消息模块 (core/message.py)](./docs/core-modules.md#消息模块-coremessagepy)
  - [任务模块 (core/tasks.py)](./docs/core-modules.md#任务模块-coretaskspy)
- [工具模块](./docs/utils.md)
- [Web控制面板](./docs/web-app.md)
- [API接口文档](./docs/api-reference.md)
- [配置文件说明](./docs/config.md)
- [部署指南](./docs/deployment.md)
- [常见问题](./docs/faq.md)

---

## 快速开始

### 项目简介

抖音续火花是一个自动化工具，用于保持抖音好友之间的火花（连续聊天天数）。通过自动化方式，在指定时间发送定制化的问候消息，确保火花永不熄灭。

### 主要功能

- 🔐 扫码登录，安全保存登录凭证
- 💬 每日自动发送定制化问候消息
- 📅 灵活的定时任务配置
- 🌐 友好的Web控制面板
- 📱 支持多账号管理
- 🎨 每日不同风格的消息模板

### 技术栈

- **核心框架**: Python 3.9+
- **自动化工具**: Playwright
- **Web框架**: Flask
- **定时任务**: APScheduler
- **配置管理**: YAML
- **打包工具**: PyInstaller
- **容器化**: Docker

---

## 项目结构

```
douyin-spark/
├── auth/                    # 认证相关数据（gitignore）
├── build/                   # PyInstaller构建目录
├── config/                  # 配置文件目录
│   └── settings.yaml        # 主配置文件（gitignore）
├── core/                    # 核心功能模块
│   ├── __init__.py
│   ├── auth.py              # 认证模块
│   ├── browser.py           # 浏览器控制
│   ├── message.py           # 消息生成
│   └── tasks.py             # 任务执行
├── dist/                    # 打包输出目录
├── docs/                    # Code Wiki文档目录
├── logs/                    # 日志目录（gitignore）
├── web/                     # Web控制面板
│   ├── templates/
│   │   └── index.html       # Web前端页面
│   └── app.py               # Flask后端
├── utils/                   # 工具模块
│   ├── __init__.py
│   ├── logger.py            # 日志工具
│   └── paths.py             # 路径管理
├── main.py                  # 命令行入口
├── launcher.py              # 桌面应用入口
├── requirements.txt         # Python依赖
├── douyin_spark.spec        # PyInstaller配置
├── install.sh               # macOS一键安装
├── uninstall.sh             # 卸载脚本
├── build_macos.sh           # macOS打包脚本
├── Dockerfile               # Docker配置
└── README.md                # 用户说明文档
```

---

## 下一步

请继续阅读 [项目概述](./docs/overview.md) 了解更多详细信息。
