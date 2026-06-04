# 部署指南

## 依赖环境

- Python 3.9+
- Google Chrome 浏览器（必须安装）

## 开发环境部署

### 1. 克隆项目

```bash
git clone <repo-url>
cd douyin-spark
```

### 2. 创建虚拟环境

```bash
python3 -m venv .venv
source .venv/bin/activate  # Linux/macOS
# 或
.venv\Scripts\activate  # Windows
```

### 3. 安装依赖

```bash
pip install -r requirements.txt
```

### 4. 安装 Playwright 浏览器

```bash
playwright install chromium
```

### 5. 初始化配置

首次运行会自动创建配置文件。

### 6. 启动方式

#### 方式一: Web 控制面板（推荐）

```bash
python web/app.py
```

浏览器打开 http://localhost:5000

#### 方式二: 命令行

首次配置登录:
```bash
python main.py --setup
```

日常运行:
```bash
python main.py
```

---

## macOS 一键安装

运行安装脚本:

```bash
bash install.sh
```

脚本会自动:
- 检查依赖
- 创建虚拟环境
- 安装 Python 依赖
- 安装 Playwright 浏览器
- 配置开机自启
- 打开 Web 控制面板

---

## 开机自启

### macOS (launchd)

安装脚本会自动配置。

手动配置:
1. 编辑 `com.douyin-spark.plist`
2. 复制到 `~/Library/LaunchAgents/`
3. 加载: `launchctl load ~/Library/LaunchAgents/com.douyin-spark.plist`

### Windows (任务计划程序)

1. 打开「任务计划程序」
2. 创建基本任务
3. 触发器: 登录时
4. 操作: 启动程序
5. 程序: `C:\path\to\.venv\Scripts\python.exe`
6. 参数: `web\app.py`
7. 起始于: `C:\path\to\douyin-spark`

---

## 打包

### macOS 打包

运行打包脚本:

```bash
bash build_macos.sh
```

输出:
- `dist/抖音续火花.app`: macOS 应用包
- `dist/抖音续火花-macOS.dmg`: DMG 安装包

### Windows 打包

使用 PyInstaller:

```bash
pip install pyinstaller
pyinstaller douyin_spark.spec
```

---

## Docker 部署

### 构建镜像

```bash
docker build -t douyin-spark .
```

### 运行容器

```bash
docker run -d \
  -p 5000:5000 \
  -v $(pwd)/config:/app/config \
  -v $(pwd)/auth:/app/auth \
  -v $(pwd)/logs:/app/logs \
  --name douyin-spark \
  douyin-spark
```

注意: Docker 中扫码登录较困难，建议本地配置好后复制配置。

---

## 常见部署问题

### 端口被占用

修改启动端口:
```bash
python web/app.py --port 5001
```

### Chrome 未找到

确保系统已安装 Google Chrome。

### 权限问题

确保对项目目录有读写权限。
