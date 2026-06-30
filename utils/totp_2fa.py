#!/usr/bin/env python3
"""
TOTP (Time-based One-Time Password) — RFC 6238 & RFC 4226
六位数字验证码，兼容 Microsoft Authenticator / Google Authenticator / Authy

用法:
    python totp_2fa.py                  # 自动生成密钥，实时显示验证码
    python totp_2fa.py JBSWY3DPEHPK3PXP # 使用已有密钥（Base32）
"""

import hmac
import hashlib
import time
import struct
import base64
import secrets
from urllib.parse import quote


# ══════════════════════════════════════════════════════
#  核心算法
# ══════════════════════════════════════════════════════

def _hotp(key: bytes, counter: int, digits: int = 6) -> str:
    """
    HMAC-Based One-Time Password (RFC 4226)

    步骤：
      1. 将 counter 打包为 8 字节大端整数
      2. 用 HMAC-SHA1 对其签名
      3. 动态截断 → 取 31 位整数 → 对 10^digits 取模

    Args:
        key     : 原始密钥字节
        counter : 计数器（对 TOTP 而言就是时间步编号）
        digits  : 验证码位数（通常为 6）

    Returns:
        左补零的 digits 位数字字符串
    """
    # Step 1: 生成消息
    msg = struct.pack(">Q", counter)

    # Step 2: HMAC-SHA1
    digest = hmac.new(key, msg, hashlib.sha1).digest()   # 20 字节

    # Step 3: 动态截断 (RFC 4226 §5.4)
    offset = digest[-1] & 0x0F                            # 低 4 位作偏移
    p = digest[offset: offset + 4]
    code = (
        (p[0] & 0x7F) << 24                               # 最高位置 0（忽略符号位）
        | (p[1] & 0xFF) << 16
        | (p[2] & 0xFF) << 8
        | (p[3] & 0xFF)
    )
    return str(code % (10 ** digits)).zfill(digits)


def totp(secret: str, digits: int = 6, period: int = 30, timestamp=None) -> str:
    """
    Time-Based One-Time Password (RFC 6238)

    Args:
        secret    : Base32 编码的密钥（空格与大小写均可）
        digits    : 验证码位数，默认 6
        period    : 时间步长（秒），Microsoft Authenticator 默认 30
        timestamp : 指定时间戳（浮点秒），None 表示使用当前时间

    Returns:
        当前时间窗口内有效的 OTP 字符串

    Example:
        >>> totp("JBSWY3DPEHPK3PXP")
        '123456'
    """
    raw_key = base64.b32decode(secret.upper().replace(" ", ""))
    t = time.time() if timestamp is None else timestamp
    counter = int(t) // period
    return _hotp(raw_key, counter, digits)


def totp_verify(secret: str, code: str, window: int = 1,
                digits: int = 6, period: int = 30) -> bool:
    """
    验证用户输入的 OTP，允许前后各 window 个时间窗口的容错
    （解决服务器与客户端时钟轻微不同步的问题）

    Args:
        secret : Base32 密钥
        code   : 用户输入的验证码（字符串）
        window : 容错窗口数，默认 1（即 ±30 秒）
        digits : 验证码位数
        period : 时间步长（秒）

    Returns:
        True 表示验证通过
    """
    now = time.time()
    for offset in range(-window, window + 1):
        candidate = totp(secret, digits, period, now + offset * period)
        if hmac.compare_digest(candidate, code.strip()):
            return True
    return False


# ══════════════════════════════════════════════════════
#  工具函数
# ══════════════════════════════════════════════════════

def generate_secret(byte_len: int = 20) -> str:
    """
    生成加密安全的随机 Base32 密钥

    Args:
        byte_len : 原始字节长度，默认 20（160 bit，符合 RFC 4226 推荐）

    Returns:
        Base32 字符串（长度 = ceil(byte_len / 5) * 8）
    """
    return base64.b32encode(secrets.token_bytes(byte_len)).decode()


def remaining_seconds(period: int = 30) -> int:
    """返回当前时间步窗口的剩余秒数"""
    return period - int(time.time()) % period


def otpauth_uri(secret: str, account: str, issuer: str,
                digits: int = 6, period: int = 30) -> str:
    """
    生成标准 otpauth:// URI

    将返回值通过任意 QR 码生成工具转成二维码，
    再用 Microsoft Authenticator 扫描即可完成绑定。

    格式: otpauth://totp/<label>?secret=<secret>&issuer=<issuer>&...
    """
    label = quote(f"{issuer}:{account}", safe="")
    params = (
        f"secret={secret}"
        f"&issuer={quote(issuer)}"
        f"&digits={digits}"
        f"&period={period}"
        f"&algorithm=SHA1"
    )
    return f"otpauth://totp/{label}?{params}"


# ══════════════════════════════════════════════════════
#  命令行演示
# ══════════════════════════════════════════════════════

def _progress_bar(remaining: int, total: int, width: int = 20) -> str:
    filled = round(remaining / total * width)
    return "█" * filled + "░" * (width - filled)


def live_display(secret: str, period: int = 30) -> None:
    """实时刷新显示当前 OTP 与剩余时间，按 Ctrl+C 退出"""
    print("\n  实时验证码（Ctrl+C 退出）")
    print("  " + "─" * 34)
    prev_code = None
    try:
        while True:
            code = totp(secret, period=period)
            rem  = remaining_seconds(period)
            bar  = _progress_bar(rem, period)

            if code != prev_code:
                print(f"\n  ✦ 新验证码 → \033[1;32m{code}\033[0m")
                prev_code = code

            print(f"\r  [{bar}] 剩余 {rem:2d}s ", end="", flush=True)
            time.sleep(0.5)
    except KeyboardInterrupt:
        print("\n\n  已退出。\n")


def main() -> None:
    import sys

    # 从命令行参数获取密钥，否则自动生成
    if len(sys.argv) > 1:
        secret = sys.argv[1].upper().replace(" ", "")
        print("  使用已有密钥。")
    else:
        secret = generate_secret()
        print("  已生成新密钥。")

    account = "Administrator"
    issuer  = "AiriCore Dev."

    uri = otpauth_uri(secret, account, issuer)

    print()
    print("╔══════════════════════════════════════════╗")
    print("║  TOTP 2FA — 兼容 Microsoft Authenticator  ║")
    print("╚══════════════════════════════════════════╝")
    print()
    print(f"  密钥 (Base32) : {secret}")
    print(f"  账户          : {account}")
    print(f"  发行方        : {issuer}")
    print()
    print("  ── 绑定到 Microsoft Authenticator ──────────")
    print(f"  OTP Auth URI  :")
    print(f"  {uri}")
    print()
    print("  💡 将上面的 URI 粘贴到以下任意工具生成 QR 码：")
    print("     • https://qr.io  /  https://www.qr-code-generator.com")
    print("     • python -c \"import qrcode; qrcode.make('<URI>').show()\"")
    print("     之后用 Microsoft Authenticator → 添加账户 → 扫描 QR 码")
    print()

    live_display(secret)


if __name__ == "__main__":
    main()
