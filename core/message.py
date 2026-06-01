"""消息模板引擎 — 模板变量替换 + 每日风格系统"""

from datetime import datetime
from typing import Optional

# 每日不同风格（按星期几，0=周一）
MESSAGE_STYLES: dict[int, str] = {
    0: "{period}好 {target} ☀️",
    1: "早安 {target}，周二加油鸭 🦆",
    2: "滴！{target}的火花卡，请查收 📇",
    3: "{period}好呀 {target}，今天也要开心哦 ✨",
    4: "{target}，快周末啦 🎉",
    5: "周末愉快 {target}！☕️",
    6: "{target}周日早安，新的一周又开始啦 🌅",
}

PERIOD_MAP = {
    "morning": "早上",
    "noon": "中午",
    "afternoon": "下午",
    "evening": "晚上",
}

WEEKDAY_CN = ["星期一", "星期二", "星期三", "星期四", "星期五", "星期六", "星期日"]


def _get_period(hour: Optional[int] = None) -> str:
    """根据当前时间返回时段 """
    if hour is None:
        hour = datetime.now().hour
    if hour < 11:
        return "morning"
    if hour < 13:
        return "noon"
    if hour < 18:
        return "afternoon"
    return "evening"


def build_message(
    target: str,
    template: Optional[str] = None,
    use_daily_style: bool = True,
) -> str:
    """构建发送消息

    Args:
        target: 好友昵称
        template: 自定义模板（含 {target}, {period}, {date}, {weekday} 变量）
        use_daily_style: 是否启用每日不同风格

    Returns:
        渲染后的消息文本
    """
    now = datetime.now()
    weekday = now.weekday()
    period_key = _get_period()

    if use_daily_style:
        msg = MESSAGE_STYLES.get(weekday, MESSAGE_STYLES[0])
    elif template:
        msg = template
    else:
        msg = "{period}好 {target} ☀️"

    replacements = {
        "{target}": target,
        "{date}": f"{now.month}月{now.day}日",
        "{weekday}": WEEKDAY_CN[weekday],
        "{period}": PERIOD_MAP.get(period_key, ""),
    }

    for key, val in replacements.items():
        msg = msg.replace(key, val)

    return msg.strip()
