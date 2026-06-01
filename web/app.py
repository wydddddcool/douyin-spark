"""Web 控制面板 — Flask 后端"""

import os
import sys
import threading
from datetime import datetime

import yaml
from flask import Flask, jsonify, render_template, request, send_file
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger

# 把项目根目录加入 path
ROOT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT_DIR)

app = Flask(__name__, template_folder="templates", static_folder="static")

CONFIG_PATH = os.path.join(ROOT_DIR, "config", "settings.yaml")
AUTH_DIR = os.path.join(ROOT_DIR, "auth")
LOG_DIR = os.path.join(ROOT_DIR, "logs")

# 全局状态
_runtime = {
    "running": False,
    "last_result": None,
    "last_run": None,
    "setup_status": None,  # None / "waiting_scan" / "success" / "failed"
    "setup_thread": None,
}

# 定时调度器（单例）
_scheduler = BackgroundScheduler(timezone="Asia/Shanghai")
_SPARK_JOB_ID = "douyin_spark_daily"


# ─── 工具函数 ──────────────────────────────────────────────


def _load_config() -> dict:
    if not os.path.exists(CONFIG_PATH):
        return {}
    with open(CONFIG_PATH, "r", encoding="utf-8") as f:
        return yaml.safe_load(f) or {}


def _save_config(cfg: dict):
    os.makedirs(os.path.dirname(CONFIG_PATH), exist_ok=True)
    with open(CONFIG_PATH, "w", encoding="utf-8") as f:
        yaml.dump(cfg, f, allow_unicode=True, default_flow_style=False)


def _has_auth() -> bool:
    """检查是否有有效的登录凭证"""
    cfg = _load_config()
    for account in cfg.get("accounts", []):
        state_file = account.get("state_file", "auth/state.json")
        full_path = os.path.join(ROOT_DIR, state_file) if not os.path.isabs(state_file) else state_file
        if os.path.exists(full_path):
            return True
    return False


def _get_recent_logs(n: int = 50) -> list[str]:
    """读取最近的日志"""
    os.makedirs(LOG_DIR, exist_ok=True)
    logs = []
    # 找到最新的日志文件
    log_files = sorted(
        [f for f in os.listdir(LOG_DIR) if f.endswith(".log")],
        reverse=True,
    )
    if not log_files:
        return ["暂无日志"]
    latest = os.path.join(LOG_DIR, log_files[0])
    with open(latest, "r", encoding="utf-8") as f:
        lines = f.readlines()
    return [line.strip() for line in lines[-n:]]


# ─── 定时调度 ──────────────────────────────────────────────


def _apply_schedule():
    """根据配置更新调度器中的定时任务（可重复调用）"""
    cfg = _load_config()
    sched_cfg = cfg.get("schedule", {})

    # 先移除旧任务
    if _scheduler.get_job(_SPARK_JOB_ID):
        _scheduler.remove_job(_SPARK_JOB_ID)

    if not sched_cfg.get("enabled", False):
        return

    time_str = sched_cfg.get("time", "08:00")
    try:
        hour, minute = map(int, time_str.split(":"))
    except (ValueError, AttributeError):
        hour, minute = 8, 0

    # user days: 1=周一 … 7=周日 → APScheduler day_of_week: 0=周一 … 6=周日
    days = sched_cfg.get("days", list(range(1, 8)))
    dow = ",".join(str(d - 1) for d in days)

    _scheduler.add_job(
        _run_spark_task,
        CronTrigger(day_of_week=dow, hour=hour, minute=minute, timezone="Asia/Shanghai"),
        id=_SPARK_JOB_ID,
        replace_existing=True,
    )


def _next_run_time() -> str | None:
    """返回下次定时运行时间的字符串，未配置则返回 None"""
    job = _scheduler.get_job(_SPARK_JOB_ID)
    if job and job.next_run_time:
        return job.next_run_time.strftime("%Y-%m-%d %H:%M")
    return None


# ─── 后台任务 ──────────────────────────────────────────────


def _run_spark_task():
    """后台执行续火花任务"""
    global _runtime
    _runtime["running"] = True
    _runtime["last_result"] = None

    try:
        from core.browser import get_browser, create_context
        from core.tasks import run_tasks
        from playwright.sync_api import sync_playwright

        cfg = _load_config()
        accounts = cfg.get("accounts", [])
        msg_cfg = cfg.get("message", {})

        results = []
        with sync_playwright() as p:
            for account in accounts:
                name = account.get("name", "未命名")
                state_path = account.get("state_file", "auth/state.json")
                full_state = (
                    os.path.join(ROOT_DIR, state_path)
                    if not os.path.isabs(state_path)
                    else state_path
                )

                if not os.path.exists(full_state):
                    results.append({"account": name, "status": "no_auth"})
                    continue

                browser = get_browser(p, headless=True)
                context = create_context(browser, storage_state=full_state)
                page = context.new_page()

                try:
                    success = run_tasks(page, context, account, msg_cfg, full_state)
                    results.append({"account": name, "status": "ok" if success else "partial"})
                except Exception as e:
                    results.append({"account": name, "status": "error", "error": str(e)})
                finally:
                    page.close()
                    browser.close()

        _runtime["last_result"] = results
        _runtime["last_run"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    except Exception as e:
        _runtime["last_result"] = [{"account": "error", "status": "error", "error": str(e)}]
        _runtime["last_run"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    finally:
        _runtime["running"] = False


def _run_setup_task():
    """后台执行扫码登录（使用持久化浏览器上下文）"""
    global _runtime
    _runtime["setup_status"] = "waiting_scan"

    try:
        from core.auth import wait_for_qrcode_and_login
        from core.browser import create_persistent_context
        from playwright.sync_api import sync_playwright

        cfg = _load_config()
        account = cfg["accounts"][0]
        state_path = account.get("state_file", "auth/state.json")
        full_state = (
            os.path.join(ROOT_DIR, state_path)
            if not os.path.isabs(state_path)
            else state_path
        )

        with sync_playwright() as p:
            context = create_persistent_context(p, headless=False)
            page = context.pages[0] if context.pages else context.new_page()

            success = wait_for_qrcode_and_login(page, context, full_state)

            page.close()
            context.close()

        _runtime["setup_status"] = "success" if success else "failed"

    except Exception as e:
        _runtime["setup_status"] = f"error: {e}"


# ─── 路由 ──────────────────────────────────────────────────


@app.route("/")
def index():
    return render_template("index.html")


@app.route("/api/status")
def api_status():
    cfg = _load_config()
    accounts = cfg.get("accounts", [])
    targets_count = sum(len(a.get("targets", [])) for a in accounts)
    return jsonify(
        {
            "has_auth": _has_auth(),
            "running": _runtime["running"],
            "last_run": _runtime.get("last_run"),
            "last_result": _runtime.get("last_result"),
            "setup_status": _runtime.get("setup_status"),
            "accounts_count": len(accounts),
            "targets_count": targets_count,
            "next_run": _next_run_time(),
        }
    )


@app.route("/api/config", methods=["GET"])
def api_get_config():
    cfg = _load_config()
    # 不暴露敏感信息
    safe_cfg = {
        "accounts": [
            {
                "name": a.get("name", ""),
                "targets": a.get("targets", []),
            }
            for a in cfg.get("accounts", [])
        ],
        "message": cfg.get("message", {}),
        "runtime": cfg.get("runtime", {}),
    }
    return jsonify(safe_cfg)


@app.route("/api/config", methods=["POST"])
def api_save_config():
    data = request.json
    cfg = _load_config()

    if "accounts" in data:
        for i, acc in enumerate(data["accounts"]):
            if i < len(cfg.get("accounts", [])):
                if "targets" in acc:
                    cfg["accounts"][i]["targets"] = acc["targets"]
                if "name" in acc:
                    cfg["accounts"][i]["name"] = acc["name"]

    if "message" in data:
        cfg["message"] = data["message"]

    _save_config(cfg)
    return jsonify({"ok": True})


@app.route("/api/targets", methods=["POST"])
def api_update_targets():
    """更新好友列表"""
    data = request.json
    targets = data.get("targets", [])

    cfg = _load_config()
    if cfg.get("accounts") and len(cfg["accounts"]) > 0:
        cfg["accounts"][0]["targets"] = targets
        _save_config(cfg)
        return jsonify({"ok": True})
    return jsonify({"ok": False, "error": "没有账号配置"}), 400


@app.route("/api/run", methods=["POST"])
def api_run():
    """手动触发续火花"""
    if _runtime["running"]:
        return jsonify({"ok": False, "error": "任务正在运行中"})

    t = threading.Thread(target=_run_spark_task, daemon=True)
    t.start()
    return jsonify({"ok": True, "message": "任务已启动"})


@app.route("/api/setup", methods=["POST"])
def api_setup():
    """触发扫码登录"""
    if _runtime.get("setup_status") == "waiting_scan":
        return jsonify({"ok": False, "error": "已在等待扫码中"})

    _runtime["setup_status"] = "starting"
    t = threading.Thread(target=_run_setup_task, daemon=True)
    t.start()
    return jsonify({"ok": True, "message": "正在打开登录页，请在弹出窗口中扫码"})


@app.route("/api/qrcode")
def api_qrcode():
    """获取二维码截图"""
    qr_path = os.path.join(AUTH_DIR, "qrcode.png")
    if os.path.exists(qr_path):
        return send_file(qr_path, mimetype="image/png")
    return "", 404


@app.route("/api/logs")
def api_logs():
    n = request.args.get("n", 50, type=int)
    return jsonify({"logs": _get_recent_logs(n)})


@app.route("/api/schedule", methods=["GET"])
def api_get_schedule():
    """获取定时配置"""
    cfg = _load_config()
    sched_cfg = cfg.get("schedule", {"enabled": False, "time": "08:00", "days": list(range(1, 8))})
    return jsonify({**sched_cfg, "next_run": _next_run_time()})


@app.route("/api/schedule", methods=["POST"])
def api_save_schedule():
    """保存定时配置并立即更新调度器"""
    data = request.json
    cfg = _load_config()
    cfg["schedule"] = {
        "enabled": bool(data.get("enabled", False)),
        "time": data.get("time", "08:00"),
        "days": data.get("days", list(range(1, 8))),
    }
    _save_config(cfg)
    _apply_schedule()
    return jsonify({"ok": True, "next_run": _next_run_time()})


@app.route("/api/preview-message")
def api_preview_message():
    """预览当前时段的消息"""
    from core.message import build_message

    target = request.args.get("target", "好友")
    cfg = _load_config()
    msg_cfg = cfg.get("message", {})
    msg = build_message(
        target=target,
        template=msg_cfg.get("template"),
        use_daily_style=msg_cfg.get("use_daily_style", True),
    )
    return jsonify({"message": msg})


# ─── 启动 ──────────────────────────────────────────────────


def main():
    import argparse

    parser = argparse.ArgumentParser(description="抖音续火花 — 控制面板")
    parser.add_argument("--port", type=int, default=5000, help="端口号")
    parser.add_argument("--host", default="0.0.0.0", help="监听地址")
    args = parser.parse_args()

    os.makedirs(AUTH_DIR, exist_ok=True)
    os.makedirs(LOG_DIR, exist_ok=True)

    # 启动调度器并应用配置中的定时任务
    _scheduler.start()
    _apply_schedule()

    print(f"\n  抖音续火花 — 控制面板")
    print(f"  打开浏览器访问: http://localhost:{args.port}\n")
    app.run(host=args.host, port=args.port, debug=False)

    _scheduler.shutdown()


if __name__ == "__main__":
    main()
