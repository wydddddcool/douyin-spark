"""AI 消息生成 — OpenAI 兼容 chat completions，多 provider 链式下落

零第三方依赖（标准库 urllib），任何一层失败自动尝试下一个 provider，
全部失败返回 None（由调用方退回本地消息池）。
"""

import json
import urllib.error
import urllib.request
from datetime import datetime
from typing import Optional

from core.message import PERIOD_MAP, WEEKDAY_CN, _get_period
from utils.logger import setup_logger

logger = setup_logger("ai_message")

TIMEOUT = 15  # 秒
MAX_CHARS = 40  # 产出超过此长度视为失败（要求 ≤30 字，留 emoji 余量）

PROMPT_TEMPLATE = """你在帮我给抖音好友发一条日常的「续火花」消息（每天随便聊一句保持互动用的）。

要求：
- 一条简短口语化的话，不超过 30 个字，像朋友间随口一句
- 自然随意，可以带点幽默，emoji 可用可不用
- 不要太正式，不要像客服，不要落款，不要用引号包裹
- 这条消息可能发到群里，所以不要带任何人名或称呼
- 直接输出消息内容本身，不要任何解释

今天是{date} {weekday}，现在是{period}（仅供参考，不必提及）。
{recent_part}"""


def _build_prompt(recent: list[str]) -> str:
    now = datetime.now()
    recent_part = ""
    if recent:
        recent_part = "最近发过这些，换个说法别重复：" + "、".join(f"「{m}」" for m in recent[-7:])
    return PROMPT_TEMPLATE.format(
        date=f"{now.month}月{now.day}日",
        weekday=WEEKDAY_CN[now.weekday()],
        period=PERIOD_MAP.get(_get_period(), ""),
        recent_part=recent_part,
    )


def _clean(text: str) -> str:
    """清洗模型输出：取第一行、剥掉包裹引号"""
    for line in text.strip().splitlines():
        line = line.strip()
        if line:
            text = line
            break
    for left, right in [('"', '"'), ("“", "”"), ("「", "」"), ("'", "'"), ("‘", "’")]:
        if len(text) > 1 and text.startswith(left) and text.endswith(right):
            text = text[1:-1].strip()
    return text


def _call_provider(provider: dict, prompt: str) -> Optional[str]:
    """调用单个 provider，返回清洗后的消息；失败抛异常或返回 None"""
    from utils.secrets import decrypt

    url = provider["base_url"].rstrip("/") + "/chat/completions"
    # api_key 可能是 enc: 前缀的密文（机器绑定加密），自动解密
    api_key = decrypt(provider.get("api_key", ""))
    if not api_key:
        logger.warning("provider %s 没有 api_key", provider.get("name", "?"))
        return None

    payload = {
        "model": provider["model"],
        "messages": [{"role": "user", "content": prompt}],
        "temperature": 1.1,
        "max_tokens": 100,
    }
    req = urllib.request.Request(
        url,
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "Authorization": "Bearer " + api_key,
            "Content-Type": "application/json",
        },
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=TIMEOUT) as resp:
        data = json.loads(resp.read().decode("utf-8"))

    content = data["choices"][0]["message"].get("content") or ""
    msg = _clean(content)
    if not msg:
        logger.warning("provider %s 返回空内容", provider.get("name", "?"))
        return None
    if len(msg) > MAX_CHARS:
        logger.warning("provider %s 产出超长(%d字)，丢弃: %s", provider.get("name", "?"), len(msg), msg)
        return None
    return msg


def generate_ai_message(ai_cfg: dict, recent: Optional[list[str]] = None) -> Optional[str]:
    """按 providers 顺序尝试生成，全部失败返回 None"""
    providers = ai_cfg.get("providers", [])
    if not providers:
        return None

    prompt = _build_prompt(recent or [])

    for provider in providers:
        name = provider.get("name", "?")
        # api_key 可能是加密存储的，先用 decrypt 拿到明文判断是否非空
        from utils.secrets import decrypt
        api_key_plain = decrypt(provider.get("api_key", ""))
        if not (provider.get("base_url") and api_key_plain and provider.get("model")):
            logger.warning("provider %s 配置不完整，跳过", name)
            continue
        try:
            msg = _call_provider(provider, prompt)
            if msg:
                logger.info("AI 消息生成成功 (provider=%s): %s", name, msg)
                return msg
        except urllib.error.HTTPError as e:
            logger.warning("provider %s HTTP %s: %s", name, e.code, e.read()[:200])
        except Exception as e:
            logger.warning("provider %s 调用失败: %s", name, e)

    return None
