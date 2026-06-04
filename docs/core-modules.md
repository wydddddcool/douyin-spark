# 核心模块

本文档详细介绍 `core/` 目录下的各个核心功能模块。

---

## 认证模块 (core/auth.py)

### 模块概述

负责处理抖音账号的登录认证相关功能，包括扫码登录、登录状态检测等。

### 核心函数

#### `is_logged_in(page: Page, save_debug: bool = False) -> bool`

**功能**: 检测当前页面是否已登录

**参数**:
- `page`: Playwright Page 对象
- `save_debug`: 是否在未登录时保存调试截图

**返回值**: `True 表示已登录，False 表示未登录

**实现逻辑**:
1. 检查 URL 是否包含登录相关路径
2. 等待会话列表元素出现
3. 尝试多种 selector 策略
4. 如果未找到且 `save_debug=True`，保存调试截图

---

#### `_find_qrcode(page: Page) -> bool`

**功能**: 在页面上查找二维码并截图保存

**参数**:
- `page`: Playwright Page 对象

**返回值**: `True` 表示找到并保存成功

**Selector 策略**:
```python
qrcode_selectors = [
    'div[data-e2e="qrcode-login-container"] img',
    'img[class*="qrcode"]',
    'img[alt*="扫码"]',
    'img[alt*="二维码"]',
    'canvas[class*="qrcode"]',
    '[class*="qrcode"] img',
    '[class*="login-qrcode"] img',
    '[class*="loginContainer"] img',
    '[class*="modal"] img',
    '[class*="dialog"] img',
    'img[src*="qrcode"]',
    'img[src*="qr"]',
]
```

---

#### `_find_qrcode_from_all_images(page: Page) -> bool`

**功能**: 兜底方案，遍历页面所有图片，查找疑似二维码的图片

**判断标准**:
- 图片可见
- 宽高在 120-400px 之间
- 宽高比接近 1:1

---

#### `wait_for_qrcode_and_login(page: Page, context: BrowserContext, state_path: str) -> bool`

**功能**: 完整的扫码登录流程

**流程**:
```
1. 访问抖音聊天页
   ↓
2. 检查是否已登录 → 是则直接保存 state
   ↓ (未登录
   ↓
3. 查找二维码 → 截图保存
   ↓
4. 等待用户扫码 (最多 120 秒
   ↓
5. 检测登录成功 → 保存 state.json
```

**参数**:
- `page`: Playwright Page 对象
- `context`: Playwright BrowserContext 对象
- `state_path`: 保存 state 的路径

**返回值**: 登录是否成功

---

#### `check_login(page: Page) -> bool`

**功能**: 导航到聊天页并检查登录状态

**参数**:
- `page`: Playwright Page 对象

**返回值**: 登录状态是否有效

---

## 浏览器模块 (core/browser.py)

### 模块概述

负责浏览器的启动、上下文创建、反检测等功能。

### 常量

#### `UA` (User-Agent)
```python
UA = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/131.0.0.0 Safari/537.36"
)
```

---

### 核心函数

#### `get_browser(p: Playwright, headless: bool = True) -> Browser`

**功能**: 启动浏览器实例

**参数**:
- `p`: Playwright 对象
- `headless`: 是否无头模式

**返回值**: Browser 对象

**关键特性**:
- 使用 `channel="chrome"` → 使用系统 Chrome
- 禁用自动化控制特征
- 禁用沙箱（安全考虑）
- 禁用 /dev/shm 使用（Docker 兼容

**代码**:
```python
return p.chromium.launch(
    channel="chrome",
    headless=headless,
    args=[
        "--disable-blink-features=AutomationControlled",
        "--no-sandbox",
        "--disable-dev-shm-usage",
    ],
)
```

---

#### `create_context(browser: Browser, storage_state: Optional[str] = None) -> BrowserContext`

**功能**: 创建浏览器上下文

**参数**:
- `browser`: Browser 对象
- `storage_state`: 可选，已保存的 state 文件路径

**返回值**: BrowserContext 对象

**配置**:
- 视口: 1920x1080
- 语言: zh-CN
- 时区: Asia/Shanghai
- User-Agent: 自定义 UA
- 注入反检测 JS

---

#### `create_persistent_context(p: Playwright, headless: bool = False) -> BrowserContext`

**功能**: 创建持久化浏览器上下文（用于首次登录）

**参数**:
- `p`: Playwright 对象
- `headless`: 是否无头模式

**返回值**: BrowserContext 对象

**特点**:
- 使用系统 Chrome（`channel="chrome"`
- 持久化用户数据目录
- 行为更像真实用户

---

#### `_inject_stealth(context: BrowserContext) -> None`

**功能**: 注入反检测 JavaScript 脚本

**注入内容**:
1. 隐藏 `navigator.webdriver`
2. 设置语言为 `['zh-CN', 'zh', 'en']`
3. 模拟插件列表
4. 伪造 `window.chrome`
5. 伪造 `permissions` API
6. 伪装 WebGL 供应商
7. 隐藏无头特征

---

#### `save_state(context: BrowserContext, path: str) -> None`

**功能**: 保存浏览器上下文状态

**参数**:
- `context`: BrowserContext 对象
- `path`: 保存路径

---

## 消息模块 (core/message.py)

### 模块概述

负责生成每日不同风格的问候消息。

### 常量

#### `MESSAGE_STYLES`
按星期几的不同消息风格

```python
MESSAGE_STYLES = {
    0: "{period}好 {target} ☀️",      # 周一
    1: "早安 {target}，周二加油鸭 🦆",  # 周二
    2: "滴！{target}的火花卡，请查收 📇",  # 周三
    3: "{period}好呀 {target}，今天也要开心哦 ✨",  # 周四
    4: "{target}，快周末啦 🎉",  # 周五
    5: "周末愉快 {target}！☕️",  # 周六
    6: "{target}周日早安，新的一周又开始啦 🌅",  # 周日
}
```

---

#### `PERIOD_MAP`
时段映射表

```python
PERIOD_MAP = {
    "morning": "早上",
    "noon": "中午",
    "afternoon": "下午",
    "evening": "晚上",
}
```

---

#### `WEEKDAY_CN`
中文星期

```python
WEEKDAY_CN = ["星期一", "星期二", "星期三", "星期四", "星期五", "星期六", "星期日"]
```

---

### 核心函数

#### `_get_period(hour: Optional[int] = None) -> str`

**功能**: 根据当前小时返回时段

**参数**:
- `hour`: 可选，指定小时（默认当前时间）

**返回值**: 时段字符串

**时段划分**:
- < 11: morning
- 11-13: noon
- 13-18: afternoon
- >=18: evening

---

#### `build_message(target: str, template: Optional[str] = None, use_daily_style: bool = True) -> str`

**功能**: 构建发送消息

**参数**:
- `target`: 好友昵称
- `template`: 可选，自定义模板
- `use_daily_style`: 是否使用每日风格

**支持的模板变量**:
- `{target}`: 好友昵称
- `{date}`: 日期（如 "1月1日"）
- `{weekday}`: 星期几
- `{period}`: 时段（早上/中午/下午/晚上）

**返回值**: 渲染后的消息文本

---

## 任务模块 (core/tasks.py)

### 模块概述

核心任务执行模块，负责查找好友、发送消息等核心业务逻辑。

### 常量

#### `CHAT_URL`
抖音聊天页面 URL
```python
CHAT_URL = "https://www.douyin.com/chat"
```

#### `MAX_SCROLLS`
最大滚动次数
```python
MAX_SCROLLS = 30
```

---

### 核心函数

#### `scroll_conversation_list(page: Page) -> bool`

**功能**: 向下滚动会话列表

**参数**:
- `page`: Playwright Page 对象

**返回值**: `True` 表示还有更多内容可滚动

**滚动策略**:
- 尝试多种滚动容器 selector
- 检查滚动前后位置变化判断是否还有更多

---

#### `find_target_on_page(page: Page, target_name: str) -> bool`

**功能**: 在当前页面查找目标好友并点击

**参数**:
- `page`: Playwright Page 对象
- `target_name`: 目标好友昵称

**返回值**: 是否找到并点击

**查找策略**:
```python
strategies = [
    lambda: page.get_by_text(target_name, exact=True).first,
    lambda: page.locator(f'text="{target_name}"').first,
    lambda: page.locator(f':text-is("{target_name}")').first,
]
```

---

#### `list_all_visible_conversations(page: Page) -> list[str]`

**功能**: 列出当前可见的所有会话（调试用）

**参数**:
- `page`: Playwright Page 对象

**返回值**: 会话名称列表

---

#### `find_and_send(page: Page, targets: list[str], cfg: dict, state_path: str) -> tuple[list[str], list[str]]

**功能**: 查找好友并发送消息

**参数**:
- `page`: Playwright Page 对象
- `targets`: 目标好友列表
- `cfg`: 消息配置
- `state_path`: state 路径

**返回值**: `(已发送列表, 未找到列表)`

**执行流程**:
```
1. 等待会话列表加载
   ↓
2. 列出可见会话（调试）
   ↓
3. 循环：
   ├─ 查找当前可见的好友
   ├─ 找到 → 发送 → 加入已发送
   ├─ 未找到 → 尝试滚动
   └─ 继续
   ↓
4. 返回结果
```

---

#### `_do_send(page: Page, target: str, cfg: dict) -> bool`

**功能**: 在已打开的会话中发送消息

**参数**:
- `page`: Playwright Page 对象
- `target`: 好友昵称
- `cfg`: 消息配置

**返回值**: 发送是否成功

**发送流程**:
```
1. 构建消息
   ↓
2. 查找输入框
   ↓
3. 点击输入框
   ↓
4. 全选删除旧内容
   ↓
5. 输入新消息
   ↓
6. 按 Enter 发送
```

**输入框查找策略**:
```python
input_selectors = [
    '[class*="messageEditor"] [contenteditable="true"]',
    '[class*="chatInput"] [contenteditable="true"]',
    '[contenteditable="true"]',
    'div[role="textbox"]',
    '[class*="inputArea"] [contenteditable="true"]',
]
```

---

#### `run_tasks(page: Page, context: BrowserContext, account_cfg: dict, msg_cfg: dict, state_path: str) -> bool

**功能**: 执行完整的续火花任务

**参数**:
- `page`: Playwright Page 对象
- `context`: BrowserContext 对象
- `account_cfg`: 账号配置
- `msg_cfg`: 消息配置
- `state_path`: state 路径

**返回值**: 任务是否全部成功

**执行步骤**:
```
1. 导航到聊天页
   ↓
2. 检查登录状态
   ↓
3. 查找并发送消息
   ↓
4. 刷新 state
   ↓
5. 返回结果
```

---

## 模块间关系图

```
┌─────────────────────────────────────────────────────────────┐
│                      core/tasks.py                        │
│  ┌─────────────────────────────────────────────────┐  │
│  │  run_tasks()                                   │  │
│  │  ├─→ core/auth.py: is_logged_in()          │  │
│  │  ├─→ core/message.py: build_message()       │  │
│  │  ├─→ find_and_send()                       │  │
│  │  │   ├─→ find_target_on_page()              │  │
│  │  │   └─→ _do_send()                        │  │
│  │  └─→ 保存 state                              │  │
│  └─────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────┘
         │                    │
         ▼                    ▼
┌──────────────────┐  ┌──────────────────┐
│  core/auth.py   │  │  core/message.py │
│  - 登录检测    │  │  - 消息生成      │
│  - 扫码登录     │  │  - 模板渲染      │
└──────────────────┘  └──────────────────┘
         │
         ▼
┌──────────────────┐
│ core/browser.py│
│  - 浏览器启动  │
│  - 反检测      │
└──────────────────┘
```
