# API 接口文档

## 基础信息

- **Base URL**: `http://localhost:5000` (默认端口可能不同
- **Content-Type**: `application/json`

---

## 接口列表

### 1. 获取系统状态

**接口**: `GET /api/status`

**响应示例:
```json
{
    "has_auth": true,
    "running": false,
    "last_run": "2024-01-01 08:00:00",
    "last_result": { ... },
    "setup_status": null,
    "accounts_count": 1,
    "targets_count": 3,
    "next_run": "2024-01-02 08:00:00"
}
```

字段说明:
- `has_auth`: 是否有登录凭证
- `running`: 任务是否运行中
- `last_run`: 上次运行时间
- `last_result`: 上次运行结果
- `setup_status`: 扫码登录状态
- `accounts_count`: 账号数量
- `targets_count`: 好友总数
- `next_run`: 下次运行时间

---

### 2. 获取配置

**接口**: `GET /api/config`

**响应示例**:
```json
{
    "accounts": [
        {
            "name": "我的主号",
            "targets": ["好友A", "好友B", "好友C"]
        }
    ],
    "message": {
        "use_daily_style": true,
        "template": null
    },
    "runtime": {
        "headless": true
    }
}
```

---

### 3. 保存配置

**接口**: `POST /api/config`

**请求体**:
```json
{
    "accounts": [
        {
            "name": "我的主号",
            "targets": ["好友A", "好友B"]
        }
    ],
    "message": {
        "use_daily_style": true
    }
}
```

**响应**:
```json
{
    "ok": true
}
```

---

### 4. 更新好友列表

**接口**: `POST /api/targets`

**请求体**:
```json
{
    "targets": ["好友A", "好友B", "好友C"]
}
```

**响应**:
```json
{
    "ok": true
}
```

---

### 5. 手动运行

**接口**: `POST /api/run`

**响应**:
```json
{
    "ok": true,
    "message": "任务已启动"
}
```

---

### 6. 扫码登录

**接口**: `POST /api/setup`

**响应**:
```json
{
    "ok": true,
    "message": "正在打开登录页，请在弹出窗口中扫码"
}
```

---

### 7. 获取二维码

**接口**: `GET /api/qrcode`

**响应**: 图片 (image/png

---

### 8. 获取日志

**接口**: `GET /api/logs`

**Query 参数**:
- `n`: 行数，默认 50

**响应**:
```json
{
    "logs": [
        "[2024-01-01 08:00:00] INFO | main | 开始处理账号...",
        "...",
    ]
}
```

---

### 9. 获取定时配置

**接口**: `GET /api/schedule`

**响应**:
```json
{
    "enabled": true,
    "time": "08:00",
    "days": [1, 2, 3, 4, 5, 6, 7],
    "next_run": "2024-01-02 08:00:00"
}
```

`days` 说明:
- 1 = 周一
- 7 = 周日

---

### 10. 保存定时配置

**接口**: `POST /api/schedule`

**请求体**:
```json
{
    "enabled": true,
    "time": "08:00",
    "days": [1, 2, 3, 4, 5]
}
```

**响应**:
```json
{
    "ok": true,
    "next_run": "2024-01-02 08:00:00"
}
```

---

### 11. 预览消息

**接口**: `GET /api/preview-message`

**Query 参数**:
- `target`: 好友昵称，默认 "好友"

**响应**:
```json
{
    "message": "早上好 好友 ☀️"
}
```
