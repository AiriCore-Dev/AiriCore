import os
import subprocess
import sys
import time

RESTART_DELAY = 2
STOP_WINDOW = 5
TERM_GRACE = 5


def _shutdown_grace():
    try:
        value = int(os.environ.get("AIRI_SHUTDOWN_GRACE", "30"))
    except ValueError:
        return 30
    return value if value > 0 else 1


SHUTDOWN_GRACE = _shutdown_grace()


def _wait(proc, timeout):
    deadline = time.monotonic() + timeout
    while True:
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            return proc.poll(), False
        try:
            return proc.wait(timeout=min(remaining, 1)), False
        except subprocess.TimeoutExpired:
            continue
        except KeyboardInterrupt:
            return proc.poll(), True


def _force_kill(proc):
    proc.kill()
    try:
        proc.wait(timeout=TERM_GRACE)
    except subprocess.TimeoutExpired:
        pass
    print("AiriCore 已被强制结束, 未保存的数据可能丢失")


def _graceful_stop(proc):
    print(f"收到 Ctrl+C, 正在优雅关闭 AiriCore (最多等待 {SHUTDOWN_GRACE} 秒)...")
    code, interrupted = _wait(proc, SHUTDOWN_GRACE)
    if code is not None:
        print(f"AiriCore 已关闭 (退出码 {code})")
        return False
    if interrupted:
        print("再次收到 Ctrl+C, 跳过等待, 强制结束 AiriCore...")
        _force_kill(proc)
        return True
    print(f"等待 {SHUTDOWN_GRACE} 秒仍未关闭, 发送终止信号...")
    proc.terminate()
    code, interrupted = _wait(proc, TERM_GRACE)
    if code is None:
        _force_kill(proc)
        return True
    print(f"AiriCore 已终止 (退出码 {code})")
    return interrupted


def _sleep(delay):
    try:
        time.sleep(delay)
    except KeyboardInterrupt:
        return True
    return False


while True:
    proc = subprocess.Popen([sys.executable, "bot.py"])
    try:
        proc.wait()
    except KeyboardInterrupt:
        if _graceful_stop(proc):
            print("已退出 airi.py")
            break
        print(f"{STOP_WINDOW} 秒内再按一次 Ctrl+C 即退出 airi.py, 否则自动重新启动...")
        if _sleep(STOP_WINDOW):
            print("已退出 airi.py")
            break
        print("正在重新启动 AiriCore...")
        continue
    print(f"AiriCore 已退出, {RESTART_DELAY} 秒后重新启动 (按 Ctrl+C 可退出 airi.py)...")
    if _sleep(RESTART_DELAY):
        print("已退出 airi.py")
        break
