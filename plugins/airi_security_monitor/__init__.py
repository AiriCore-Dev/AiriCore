import asyncio
import json
import os
import socket
import time
from datetime import datetime
from pathlib import Path

from nonebot import get_driver, logger, on_fullmatch
from nonebot.permission import SUPERUSER

from .scanner import SEVERITY_RANK, scan_system
from utils.notification import get_notification_bot


driver = get_driver()
ROOT = Path(__file__).resolve().parents[2]
STATE_DIR = ROOT / "data" / "airi_security_monitor"
STATE_PATH = STATE_DIR / "state.json"
DEFAULT_WATCH_PATHS = (
    "/etc/systemd/system",
    "/run/systemd/system",
    "/etc/cron.d",
    "/etc/cron.daily",
    "/etc/cron.hourly",
    "/etc/cron.weekly",
    "/etc/cron.monthly",
    "/var/spool/cron",
    "/etc/ssh/sshd_config",
    "/etc/ssh/sshd_config.d",
    "/etc/passwd",
    "/etc/group",
    "/etc/shadow",
    "/etc/sudoers",
    "/etc/sudoers.d",
    "/etc/ld.so.preload",
    "/etc/pam.d",
    "/etc/polkit-1/rules.d",
    "/etc/polkit-1/localauthority",
    "/etc/dbus-1/system.d",
    "/etc/profile.d",
    "/root/.ssh/authorized_keys",
    "/root/.config/systemd",
    "/root/.bashrc",
    "/root/.profile",
    "/etc/profile",
    "/etc/bash.bashrc",
    "/root/autostart.sh",
    "/root/airi/haruki/launch.sh",
    "/root/airi/haruki/haruki.py",
    "/root/airi/frp_airi/frpc",
    "/etc/rc.local",
)
DEFAULT_LOG_PATHS = (
    "/var/log/auth.log",
    "/var/log/secure",
    "/opt/mcsmanager/web/logs/current.log",
    "/opt/mcsmanager/daemon/logs/current.log",
    "/opt/mcsmanager/daemon/data/InstanceLog/global0001.log",
    "/var/log/dpkg.log",
    "/var/log/apt/history.log",
)
DEFAULT_WRITABLE_ROOTS = (
    "/etc/systemd/system",
    "/etc/cron.d",
    "/var/spool/cron",
    "/root/airi",
    "/root/.config/systemd",
    "/usr/local/bin",
)
_task = None
_stop_event = None
_state = {}
_latest_findings = []
_last_scan_at = 0.0
_last_log_notice = {}


def _as_bool(value, default=True):
    if value is None:
        return default
    if isinstance(value, bool):
        return value
    return str(value).strip().lower() in {"1", "true", "yes", "on", "是", "启用"}


def _as_int(value, default, minimum, maximum):
    try:
        parsed = int(str(value).strip())
    except (TypeError, ValueError):
        parsed = default
    return max(minimum, min(maximum, parsed))


def _as_list(value, default):
    if value is None or value == "":
        return list(default)
    if isinstance(value, (list, tuple, set)):
        parsed_items = [str(item).strip() for item in value if str(item).strip()]
        return parsed_items or list(default)
    text = str(value).strip()
    try:
        parsed = json.loads(text)
    except (TypeError, ValueError):
        parsed = None
    if isinstance(parsed, list):
        parsed_items = [str(item).strip() for item in parsed if str(item).strip()]
        return parsed_items or list(default)
    return [item.strip() for item in text.split(",") if item.strip()]


def _config():
    config = driver.config
    return {
        "enabled": _as_bool(getattr(config, "security_monitor_enabled", True)),
        "interval": _as_int(getattr(config, "security_monitor_interval", 60), 60, 15, 86400),
        "cooldown": _as_int(getattr(config, "security_monitor_alert_cooldown", 3600), 3600, 60, 604800),
        "failed_threshold": _as_int(
            getattr(config, "security_monitor_failed_login_threshold", 20), 20, 3, 10000
        ),
        "recipient": str(getattr(config, "notification_account", "") or "").strip(),
        "watch_paths": _as_list(getattr(config, "security_monitor_watch_paths", None), DEFAULT_WATCH_PATHS),
        "log_paths": _as_list(getattr(config, "security_monitor_log_paths", None), DEFAULT_LOG_PATHS),
        "writable_roots": _as_list(
            getattr(config, "security_monitor_world_writable_roots", None), DEFAULT_WRITABLE_ROOTS
        ),
    }


def _empty_state():
    return {
        "initialized": False,
        "files": {},
        "listeners": {},
        "privileged": {},
        "log_offsets": {},
        "alerts": {},
    }


def _load_state():
    try:
        raw = json.loads(STATE_PATH.read_text(encoding="utf-8"))
    except (OSError, ValueError, TypeError):
        return _empty_state()
    if not isinstance(raw, dict):
        return _empty_state()
    state = _empty_state()
    state.update({key: raw.get(key, value) for key, value in state.items()})
    if not isinstance(state["files"], dict):
        state["files"] = {}
    if not isinstance(state["listeners"], dict):
        state["listeners"] = {}
    if not isinstance(state["log_offsets"], dict):
        state["log_offsets"] = {}
    if not isinstance(state["alerts"], dict):
        state["alerts"] = {}
    return state


def _save_state():
    try:
        STATE_DIR.mkdir(parents=True, exist_ok=True)
        temporary = STATE_PATH.with_suffix(".tmp")
        temporary.write_text(json.dumps(_state, ensure_ascii=False, sort_keys=True), encoding="utf-8")
        os.chmod(temporary, 0o600)
        os.replace(temporary, STATE_PATH)
        os.chmod(STATE_PATH, 0o600)
    except OSError as error:
        logger.warning(f"airi_security_monitor 状态保存失败: {error}")


def _prime_offsets(offsets, paths):
    primed = dict(offsets)
    for path in paths:
        try:
            info = Path(path).stat()
            primed[path] = {"inode": str(getattr(info, "st_ino", 0)), "position": info.st_size}
        except OSError:
            primed.setdefault(path, {})
    return primed


def _dedupe(findings):
    selected = {}
    for finding in findings:
        old = selected.get(finding.key)
        if old is None or SEVERITY_RANK.get(finding.severity, 0) > SEVERITY_RANK.get(old.severity, 0):
            selected[finding.key] = finding
    return sorted(selected.values(), key=lambda item: (-SEVERITY_RANK.get(item.severity, 0), item.key))


def _format_finding(finding):
    return f"【{finding.severity}】{finding.category}\n{finding.detail}\n建议：{finding.recommendation}"


def _message(findings, bot_id):
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    header = f"🚨 Airi 安全监控告警\n主机：{socket.gethostname()}\n时间：{now}\n通知 Bot：{bot_id}\n"
    body = "\n\n".join(_format_finding(finding) for finding in findings[:8])
    extra = "" if len(findings) <= 8 else f"\n\n其余 {len(findings) - 8} 条同轮告警已合并。"
    return (header + "\n" + body + extra)[:3900]


async def _send_findings(findings):
    global _state
    config = _config()
    if not findings:
        return
    now = time.time()
    alerts = _state.setdefault("alerts", {})
    pending = []
    for finding in findings:
        last = float(alerts.get(finding.key, 0) or 0)
        if now - last >= config["cooldown"]:
            pending.append(finding)
    if not pending:
        return
    if not config["recipient"].isdigit():
        for finding in pending:
            last = _last_log_notice.get(finding.key, 0.0)
            if now - last >= config["cooldown"]:
                logger.warning(f"airi_security_monitor 未配置有效 notification_account：{finding.detail}")
                _last_log_notice[finding.key] = now
        return
    bot = get_notification_bot()
    if bot is None:
        last = _last_log_notice.get("__notification_bot__", 0.0)
        if now - last >= config["cooldown"]:
            logger.warning("airi_security_monitor 找不到可用的通知 Bot")
            _last_log_notice["__notification_bot__"] = now
        return
    try:
        await bot.send_private_msg(user_id=int(config["recipient"]), message=_message(pending, bot.self_id))
    except Exception as error:
        logger.warning(f"airi_security_monitor 告警发送失败: {error}")
        return
    for finding in pending:
        alerts[finding.key] = now


async def _scan_once():
    global _state, _latest_findings, _last_scan_at
    config = _config()
    findings, files, listeners, log_offsets, privileged = await asyncio.to_thread(
        scan_system,
        config["watch_paths"],
        _state.get("files", {}),
        _state.get("listeners", {}),
        _state.get("log_offsets", {}),
        config["failed_threshold"],
        config["log_paths"],
        config["writable_roots"],
        _state.get("privileged", {}),
    )
    _state["files"] = files
    _state["listeners"] = listeners
    _state["privileged"] = privileged
    _state["log_offsets"] = log_offsets
    _state["initialized"] = True
    _latest_findings = _dedupe(findings)
    _last_scan_at = time.time()
    await _send_findings(_latest_findings)
    _save_state()


async def _monitor_loop():
    config = _config()
    while not _stop_event.is_set():
        try:
            await _scan_once()
        except asyncio.CancelledError:
            raise
        except Exception as error:
            logger.exception(f"airi_security_monitor 扫描失败: {error}")
        try:
            await asyncio.wait_for(_stop_event.wait(), timeout=config["interval"])
        except asyncio.TimeoutError:
            continue


def _status_text():
    config = _config()
    if not config["enabled"]:
        return "🛡️ airi_security_monitor 已禁用"
    if not _last_scan_at:
        return f"🛡️ airi_security_monitor 已启动，首次扫描尚未完成（周期 {config['interval']} 秒）"
    active = _latest_findings[:5]
    lines = [
        "🛡️ airi_security_monitor 运行中",
        f"扫描周期：{config['interval']} 秒",
        f"上次扫描：{datetime.fromtimestamp(_last_scan_at):%Y-%m-%d %H:%M:%S}",
        f"当前信号：{len(_latest_findings)} 条",
    ]
    lines.extend(f"{item.severity}｜{item.category}｜{item.detail}" for item in active)
    return "\n".join(lines)[:3800]


security_status = on_fullmatch("airisecurity", priority=5, block=True, permission=SUPERUSER)


@security_status.handle()
async def _():
    await security_status.finish(_status_text())


@driver.on_startup
async def _start_monitor():
    global _task, _stop_event, _state
    config = _config()
    if not config["enabled"]:
        logger.info("airi_security_monitor 已禁用")
        return
    _state = _load_state()
    if not _state.get("initialized"):
        _state["log_offsets"] = _prime_offsets(_state.get("log_offsets", {}), config["log_paths"])
    _stop_event = asyncio.Event()
    _task = asyncio.create_task(_monitor_loop())
    logger.info(f"airi_security_monitor 已启动，扫描周期 {config['interval']} 秒")


@driver.on_shutdown
async def _stop_monitor():
    global _task
    if _stop_event is not None:
        _stop_event.set()
    if _task is not None:
        _task.cancel()
        try:
            await _task
        except asyncio.CancelledError:
            pass
        except Exception:
            pass
    _save_state()
    _task = None
