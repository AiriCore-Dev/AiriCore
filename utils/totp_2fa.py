
import hmac
import hashlib
import time
import struct
import base64
import secrets
from urllib.parse import quote



def _hotp(key: bytes, counter: int, digits: int = 6) -> str:
    msg = struct.pack(">Q", counter)

    digest = hmac.new(key, msg, hashlib.sha1).digest()

    offset = digest[-1] & 0x0F
    p = digest[offset: offset + 4]
    code = (
        (p[0] & 0x7F) << 24
        | (p[1] & 0xFF) << 16
        | (p[2] & 0xFF) << 8
        | (p[3] & 0xFF)
    )
    return str(code % (10 ** digits)).zfill(digits)


def totp(secret: str, digits: int = 6, period: int = 30, timestamp=None) -> str:
    raw_key = base64.b32decode(secret.upper().replace(" ", ""))
    t = time.time() if timestamp is None else timestamp
    counter = int(t) // period
    return _hotp(raw_key, counter, digits)


def totp_verify(secret: str, code: str, window: int = 1,
                digits: int = 6, period: int = 30) -> bool:
    now = time.time()
    for offset in range(-window, window + 1):
        candidate = totp(secret, digits, period, now + offset * period)
        if hmac.compare_digest(candidate, code.strip()):
            return True
    return False



def generate_secret(byte_len: int = 20) -> str:
    return base64.b32encode(secrets.token_bytes(byte_len)).decode()


def remaining_seconds(period: int = 30) -> int:
    return period - int(time.time()) % period


def otpauth_uri(secret: str, account: str, issuer: str,
                digits: int = 6, period: int = 30) -> str:
    label = quote(f"{issuer}:{account}", safe="")
    params = (
        f"secret={secret}"
        f"&issuer={quote(issuer)}"
        f"&digits={digits}"
        f"&period={period}"
        f"&algorithm=SHA1"
    )
    return f"otpauth://totp/{label}?{params}"



def _progress_bar(remaining: int, total: int, width: int = 20) -> str:
    filled = round(remaining / total * width)
    return "█" * filled + "░" * (width - filled)


def live_display(secret: str, period: int = 30) -> None:
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
