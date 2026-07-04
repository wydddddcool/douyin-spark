"""消息生成 — 口语化消息池随机抽取 + 最近历史去重 + 老模板兼容

设计要点：
- 消息池全部不带昵称（部分消息会发到群聊，带昵称会暴露脚本痕迹）
- 每次从「当前时段池 + 通用池 + 当天特色池」随机抽，避开最近发过的几条
- AI 生成启用时优先走 AI（见 core/ai_message.py），失败自动退回消息池
- 老配置兼容：use_daily_style=False 且配了自定义 template 时仍走变量替换
"""

import json
import os
import random
from datetime import datetime
from typing import Optional

from utils.paths import AUTH_DIR
from utils.logger import setup_logger

logger = setup_logger("message")

HISTORY_PATH = os.path.join(AUTH_DIR, "sent_history.json")
HISTORY_SIZE = 7  # 最近 N 条不重复

# ─── 消息池（口语化短句，不带昵称） ──────────────────────────

POOL_GENERAL = [
    "火花还在吗",
    "续上续上",
    "滴 打卡",
    "冒个泡",
    "哈喽哈喽",
    "在忙啥呢",
    "干嘛呢",
    "最近咋样",
    "吃了没",
    "摸鱼了没",
    "忙不忙呀",
    "还活着没哈哈",
    "出来冒个泡",
    "签到～",
    "日常报到",
    "今天过得咋样",
    "嘿嘿 来了",
]

POOL_MORNING = [
    "早",
    "早早早",
    "早安",
    "早上好",
    "起了没",
    "醒了没",
    "早呀",
    "早安打卡",
    "新的一天冲鸭",
    "今天也要元气满满",
    "早 吃早饭了没",
    "美好的一天又开始了",
]

POOL_NOON = [
    "午安",
    "吃饭了没",
    "中午吃啥",
    "干饭了干饭了",
    "午休了没",
    "中午好呀",
    "恰饭时间到",
    "今天中午吃的啥",
]

POOL_AFTERNOON = [
    "下午好",
    "有点困",
    "好困啊下午",
    "撑住 快下班了",
    "摸鱼时间",
    "下午也要加油哦",
    "来杯咖啡不",
    "下午茶时间",
]

POOL_EVENING = [
    "晚上好",
    "下班了没",
    "吃晚饭了吗",
    "今天累不累",
    "忙完了没",
    "晚饭吃的啥",
    "今天辛苦啦",
    "早点休息哦",
    "晚安～",
    "睡前冒个泡",
]

# 特定星期几额外混入（0=周一 … 6=周日）
POOL_WEEKDAY_EXTRA: dict[int, list[str]] = {
    0: ["周一加油", "又是周一", "新的一周开始啦"],
    4: ["周五了！", "明天周末啦", "周五快乐", "终于周五了"],
}

PERIOD_POOLS = {
    "morning": POOL_MORNING,
    "noon": POOL_NOON,
    "afternoon": POOL_AFTERNOON,
    "evening": POOL_EVENING,
}

PERIOD_MAP = {
    "morning": "早上",
    "noon": "中午",
    "afternoon": "下午",
    "evening": "晚上",
}

WEEKDAY_CN = ["星期一", "星期二", "星期三", "星期四", "星期五", "星期六", "星期日"]


def _get_period(hour: Optional[int] = None) -> str:
    """根据当前时间返回时段"""
    if hour is None:
        hour = datetime.now().hour
    if hour < 11:
        return "morning"
    if hour < 13:
        return "noon"
    if hour < 18:
        return "afternoon"
    return "evening"


# ─── 发送历史（避免短期重复） ────────────────────────────────


def load_history() -> list[str]:
    """读取最近发过的消息列表，文件不存在/损坏时返回空"""
    try:
        with open(HISTORY_PATH, "r", encoding="utf-8") as f:
            data = json.load(f)
        recent = data.get("recent", [])
        return [m for m in recent if isinstance(m, str)]
    except Exception:
        return []


def record_sent(msg: str) -> None:
    """发送成功后记录消息，保留最近 HISTORY_SIZE 条"""
    try:
        recent = load_history()
        recent.append(msg)
        recent = recent[-HISTORY_SIZE:]
        os.makedirs(AUTH_DIR, exist_ok=True)
        with open(HISTORY_PATH, "w", encoding="utf-8") as f:
            json.dump({"recent": recent}, f, ensure_ascii=False, indent=2)
    except Exception as e:
        logger.warning("写入发送历史失败: %s", e)


# ─── 消息池抽取 ──────────────────────────────────────────────


def pick_pool_message(now: Optional[datetime] = None) -> str:
    """从消息池随机抽一条，避开最近发过的"""
    if now is None:
        now = datetime.now()

    pool = list(POOL_GENERAL)
    pool += PERIOD_POOLS.get(_get_period(now.hour), [])
    pool += POOL_WEEKDAY_EXTRA.get(now.weekday(), [])

    recent = set(load_history())
    candidates = [m for m in pool if m not in recent]
    if not candidates:
        candidates = pool  # 全被排除时退回完整池（防御，正常不会发生）

    return random.choice(candidates)


# ─── 对外入口 ────────────────────────────────────────────────


def build_message(
    target: str,
    template: Optional[str] = None,
    use_daily_style: bool = True,
) -> str:
    """构建发送消息（不写历史，预览安全）

    - use_daily_style=False 且配置了自定义 template → 老的变量替换逻辑
    - 其余情况 → 消息池随机抽取
    """
    if not use_daily_style and template:
        now = datetime.now()
        replacements = {
            "{target}": target,
            "{date}": f"{now.month}月{now.day}日",
            "{weekday}": WEEKDAY_CN[now.weekday()],
            "{period}": PERIOD_MAP.get(_get_period(), ""),
        }
        msg = template
        for key, val in replacements.items():
            msg = msg.replace(key, val)
        return msg.strip()

    return pick_pool_message()


def compose_message(target: str, msg_cfg: dict) -> str:
    """统一生成入口：AI（启用时，内部含多 provider 下落）→ 消息池/模板

    msg_cfg 即 settings.yaml 的 message 段。
    """
    ai_cfg = (msg_cfg or {}).get("ai", {})
    if ai_cfg.get("enabled"):
        from core.ai_message import generate_ai_message

        msg = generate_ai_message(ai_cfg, recent=load_history())
        if msg:
            return msg
        logger.info("AI 生成不可用，退回本地消息池")

    return build_message(
        target=target,
        template=(msg_cfg or {}).get("template"),
        use_daily_style=(msg_cfg or {}).get("use_daily_style", True),
    )
