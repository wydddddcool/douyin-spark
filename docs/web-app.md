# Web 控制面板 (web/app.py)

## 模块概述

Web 控制面板是用户与系统交互的主要界面，提供扫码登录、好友管理、定时配置、日志查看等功能。

## 全局状态

### `_runtime`

运行时状态字典

```python
_runtime = {
    "running": False,           # 任务是否正在运行
    "last_result": None,       # 上次运行结果
    "last_run": None,          # 上次运行时间
    "setup_status": None,       # 扫码登录状态
    "setup_thread": None,        # 扫码登录线程
}
```

### `_scheduler`

APScheduler 后台调度器，用于定时任务。

### `_SPARK_JOB_ID`

定时任务 ID，固定值 `"douyin_spark_daily"`。

---

## 工具函数

### `_load_config() -> dict`

加载配置文件。

### `_save_config(cfg: dict)

保存配置文件。

### `_has_auth() -> bool`

检查是否有有效的登录凭证。

### `_get_recent_logs(n: int = 50) -> list[str]`

读取最近的日志。

---

## 定时调度

### `_apply_schedule()`

根据配置更新调度器中的定时任务。

**流程**:
1. 移除旧任务
2. 如果定时未启用 → 返回
3. 解析时间字符串 (HH:MM)
4. 转换用户选择的星期
5. 添加新的 Cron 任务

### `_next_run_time() -> str | None`

返回下次定时运行时间的字符串。

---

## 后台任务

### `_run_spark_task()`

后台执行续火花任务。

**执行流程**:
1. 设置 `running=True`
2. 加载配置
3. 遍历账号
4. 启动浏览器
5. 调用 `run_tasks()`
6. 保存结果
7. 设置 `running=False`

### `_run_setup_task()`

后台执行扫码登录。

**执行流程**:
1. 设置 `setup_status="starting"`
2. 创建持久化浏览器上下文
3. 调用 `wait_for_qrcode_and_login()`
4. 更新 `setup_status` 设为成功或失败

---

## 路由

### `GET /`

主页，渲染 `index.html` 模板。

### `GET /api/status`

获取系统状态。

**返回 JSON:
```json
{
    "has_auth": bool,
    "running": bool,
    "last_run": str | null,
    "last_result": any,
    "setup_status": str | null,
    "accounts_count": int,
    "targets_count": int,
    "next_run": str | null
}
```

### `GET /api/config`

获取配置（脱敏）。

### `POST /api/config`

保存配置。

### `POST /api/targets`

更新好友列表。

### `POST /api/run`

手动触发续火花。

### `POST /api/setup`

触发扫码登录。

### `GET /api/qrcode`

获取二维码图片。

### `GET /api/logs`

获取日志。

**Query 参数:
- `n`: 日志行数，默认 50

### `GET /api/schedule`

获取定时配置。

### `POST /api/schedule`

保存定时配置并更新调度器。

### `GET /api/preview-message`

预览当前时段的消息。

**Query 参数:
- `target`: 好友昵称，默认 "好友"

---

## 启动

### `main()`

启动 Flask 服务。

**命令行参数**:
- `--port`: 端口号，默认 5001
- `--host`: 监听地址，默认 0.0.0.0

---

## 线程安全

- Flask 请求和后台任务共享 `_runtime` 全局变量，没有加锁，通过简单的布尔值更新是线程安全的。

---
