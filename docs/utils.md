# 工具模块

## utils/paths.py - 路径管理

### 设计目标

统一管理项目路径，适配开发模式和打包后的 frozen 模式。

### 核心常量

#### `APP_NAME`
应用名称
```python
APP_NAME = "抖音续火花"
```

#### `BUNDLE_DIR`
打包资源目录（只读）
- frozen 模式：`sys._MEIPASS` 或可执行文件所在目录
- 开发模式：项目根目录

#### `DATA_DIR`
用户数据目录（可写）
- macOS: `~/Library/Application Support/抖音续火花`
- Windows: `%APPDATA%\抖音续火花`
- Linux: `~/.local/share/抖音续火花`
- 开发模式：项目根目录

#### 子目录常量
```python
CONFIG_DIR = os.path.join(DATA_DIR, "config")
CONFIG_PATH = os.path.join(CONFIG_DIR, "settings.yaml")

AUTH_DIR = os.path.join(DATA_DIR, "auth")
STATE_PATH = os.path.join(AUTH_DIR, "state.json")
QRCODE_PATH = os.path.join(AUTH_DIR, "qrcode.png")
BROWSER_DATA_DIR = os.path.join(AUTH_DIR, "browser_data")

LOG_DIR = os.path.join(DATA_DIR, "logs")
```

#### 资源文件（只读）
```python
DEFAULT_CONFIG_BUNDLED = os.path.join(BUNDLE_DIR, "config", "settings.yaml")
WEB_TEMPLATES_DIR = os.path.join(BUNDLE_DIR, "web", "templates")
WEB_STATIC_DIR = os.path.join(BUNDLE_DIR, "web", "static")
```

### 核心函数

#### `ensure_user_dirs() -> None`
确保所有用户数据目录存在。

#### `ensure_default_config() -> None`
首次运行时从 bundle 复制默认配置到用户数据目录。

---

## utils/logger.py - 日志管理

### 核心函数

#### `setup_logger(name: str = "douyin-spark") -> logging.Logger`
配置并返回 logger 实例。

### 日志配置

- **控制台输出**
  - 级别: INFO
  - 格式: `[时间] 级别 | 消息`

- **文件输出**
  - 级别: DEBUG
  - 格式: `[时间] 级别 | 模块 | 文件:行号 | 消息`
  - 文件名: `logs/spark_YYYYMMDD.log`

### 使用示例

```python
from utils.logger import setup_logger

logger = setup_logger("my_module")
logger.debug("调试信息")
logger.info("普通信息")
logger.warning("警告")
logger.error("错误")
```
