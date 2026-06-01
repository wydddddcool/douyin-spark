#!/usr/bin/env python3
"""
抖音自动续火花脚本

用法:
    python main.py --setup      # 首次配置：扫码登录保存凭证
    python main.py              # 日常运行：自动发送续火消息
"""

import argparse
import os
import sys
import yaml
from playwright.sync_api import sync_playwright

from core.browser import get_browser, create_context, create_persistent_context
from core.auth import wait_for_qrcode_and_login
from core.tasks import run_tasks
from utils.logger import setup_logger

logger = setup_logger("main")

CONFIG_PATH = "config/settings.yaml"


def load_config(path: str) -> dict:
    """加载 YAML 配置文件"""
    if not os.path.exists(path):
        logger.error("配置文件不存在: %s", path)
        logger.error("请复制 config/settings.yaml 并按提示填写")
        sys.exit(1)

    with open(path, "r", encoding="utf-8") as f:
        cfg = yaml.safe_load(f)

    if not cfg:
        logger.error("配置文件为空")
        sys.exit(1)
    if not cfg.get("accounts"):
        logger.error("配置文件中没有账号信息 (accounts)")
        sys.exit(1)

    return cfg


def cmd_setup(cfg: dict):
    """--setup 模式：扫码登录（使用持久化浏览器上下文，更像真人）"""
    accounts = cfg["accounts"]
    account = accounts[0]
    state_path = account.get("state_file", "auth/state.json")

    logger.info("=" * 40)
    logger.info("抖音续火花 — 首次配置")
    logger.info("=" * 40)

    with sync_playwright() as p:
        # 使用持久化 context：有真实用户数据目录，不容易被反爬识别
        context = create_persistent_context(p, headless=False)
        page = context.pages[0] if context.pages else context.new_page()

        success = wait_for_qrcode_and_login(page, context, state_path)

        page.close()
        context.close()

    if success:
        logger.info("\n✅ 配置完成！现在可以运行 python main.py 自动续火花了")
    else:
        logger.error("\n❌ 配置失败")
        sys.exit(1)


def cmd_run(cfg: dict):
    """默认模式：自动续火花"""
    accounts = cfg["accounts"]
    msg_cfg = cfg.get("message", {})

    for account in accounts:
        name = account.get("name", "未命名")
        state_path = account.get("state_file", "auth/state.json")

        if not os.path.exists(state_path):
            logger.error("[%s] 登录凭证不存在，请先运行: python main.py --setup", name)
            continue

        logger.info("=" * 40)
        logger.info("开始处理账号: %s", name)
        logger.info("=" * 40)

        success = False
        with sync_playwright() as p:
            browser = get_browser(p, headless=cfg.get("runtime", {}).get("headless", True))
            context = create_context(browser, storage_state=state_path)
            page = context.new_page()

            try:
                success = run_tasks(page, context, account, msg_cfg, state_path)
            except Exception as e:
                logger.error("执行出错: %s", e)
                import traceback
                logger.debug(traceback.format_exc())
            finally:
                page.close()
                browser.close()

        if success:
            logger.info("[%s] ✅ 任务完成", name)
        else:
            logger.warning("[%s] ⚠️ 部分任务未完成", name)


def main():
    parser = argparse.ArgumentParser(description="抖音自动续火花脚本")
    parser.add_argument("--setup", action="store_true", help="首次扫码登录配置")
    args = parser.parse_args()

    cfg = load_config(CONFIG_PATH)

    # 确保 auth 目录存在
    os.makedirs("auth", exist_ok=True)

    if args.setup:
        cmd_setup(cfg)
    else:
        cmd_run(cfg)


if __name__ == "__main__":
    main()
