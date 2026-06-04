# 配置文件说明

## 配置文件位置

- **开发模式: `config/settings.yaml`

- **打包模式: `~/Library/Application Support/抖音续火花/config/settings.yaml` (macOS)

## 配置文件结构

```yaml
accounts:
  - name: 我的主号
    state_file: auth/state.json
    targets:
      - 好友A
      - 好友B
      - 好友C
message:
  use_daily_style: true
  template: null
runtime:
  headless: true
  log_level: INFO
  browser_timeout: 120000
  message_delay: 3.0
schedule:
  enabled: true
  time: "08:00"
  days:
    - 1
    - 2
    - 3
    - 4
    - 5
    - 6
    - 7
```

---

## 配置项说明

### accounts

账号配置数组。

#### accounts[].name
账号名称，用于显示。

#### accounts[].state_file
登录凭证文件路径，相对项目根目录或绝对路径。

#### accounts[].targets
需要续火花的好友昵称列表。

---

### message

消息配置。

#### message.use_daily_style
是否使用每日不同风格的消息，布尔值。

#### message.template
自定义消息模板，支持变量替换:
- `{target}`: 好友昵称
- `{date}`: 日期
- `{weekday}`: 星期几
- `{period}`: 时段

---

### runtime

运行时配置。

#### runtime.headless
是否无头模式运行浏览器，布尔值。

#### runtime.log_level
日志级别，可选值: DEBUG, INFO, WARNING, ERROR。

#### runtime.browser_timeout
浏览器操作超时时间，毫秒。

#### runtime.message_delay
消息发送延迟，秒。

---

### schedule

定时任务配置。

#### schedule.enabled
是否启用定时任务，布尔值。

#### schedule.time
每日发送时间，格式 "HH:MM"。

#### schedule.days
每周哪些天运行，数组，1=周一，7=周日。
