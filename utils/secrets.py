"""API key 等敏感信息加密存储 — 基于机器特征派生密钥的 Fernet 对称加密

设计要点：
- 密钥派生自本机 MAC + 用户名 + hostname，跨机器无法解密
- 密文以 `enc:` 前缀 + base64 形式存到 settings.yaml，明文向后兼容
- Web 面板保存 api_key 时自动加密；读取时自动解密
- 首次加载老明文配置时自动迁移为密文（不在读取时迁移，避免意外写文件）
"""

import base64
import hashlib
import os
import platform
import socket
import uuid
from typing import Optional

from utils.logger import setup_logger

logger = setup_logger("secrets")

# 密文前缀，明文不会被当作密文处理
ENC_PREFIX = "enc:"

# Fernet key 必须是 32 字节 base64-urlsafe 字符串
# 派生自机器特征，保证跨机器不可解密、本机稳定


def _machine_fingerprint() -> str:
    """收集本机特征，返回稳定字符串"""
    parts = []

    # MAC 地址（取第一个非本地回环）
    try:
        mac = uuid.getnode()
        parts.append(f"mac={mac:012x}")
    except Exception:
        pass

    # 用户名
    try:
        parts.append(f"user={os.getlogin()}")
    except Exception:
        try:
            parts.append(f"user={os.environ.get('USER') or os.environ.get('USERNAME', '')}")
        except Exception:
            pass

    # hostname
    try:
        parts.append(f"host={socket.gethostname()}")
    except Exception:
        pass

    # 系统
    try:
        parts.append(f"os={platform.system()}-{platform.release()}")
    except Exception:
        pass

    return "|".join(parts)


def _derive_key() -> bytes:
    """基于机器特征派生 Fernet 密钥"""
    fp = _machine_fingerprint()
    # PBKDF2 派生 32 字节密钥
    dk = hashlib.pbkdf2_hmac(
        "sha256",
        fp.encode("utf-8"),
        b"douyin-spark-static-salt",  # 静态盐，主要安全靠机器特征
        iterations=100_000,
        dklen=32,
    )
    return base64.urlsafe_b64encode(dk)


def encrypt(plaintext: str) -> str:
    """加密明文，返回 enc: 前缀 + base64 密文"""
    if not plaintext:
        return ""
    if plaintext.startswith(ENC_PREFIX):
        return plaintext  # 已加密，幂等
    try:
        from cryptography.fernet import Fernet
        key = _derive_key()
        f = Fernet(key)
        cipher = f.encrypt(plaintext.encode("utf-8"))
        return ENC_PREFIX + cipher.decode("ascii")
    except Exception as e:
        logger.warning("加密失败，保留明文: %s", e)
        return plaintext


def decrypt(stored: Optional[str]) -> str:
    """解密；非 enc: 前缀的明文直接返回（向后兼容）"""
    if not stored:
        return ""
    if not stored.startswith(ENC_PREFIX):
        return stored  # 明文，向后兼容
    try:
        from cryptography.fernet import Fernet
        key = _derive_key()
        f = Fernet(key)
        cipher = stored[len(ENC_PREFIX):].encode("ascii")
        return f.decrypt(cipher).decode("utf-8")
    except Exception as e:
        logger.warning("解密失败（可能是机器变更）: %s", e)
        return ""


def is_encrypted(stored: Optional[str]) -> bool:
    """判断存储值是否已加密"""
    return bool(stored) and stored.startswith(ENC_PREFIX)
