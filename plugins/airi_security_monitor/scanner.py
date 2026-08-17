import hashlib
import os
import re
import stat
from dataclasses import dataclass
from pathlib import Path

try:
    import psutil
except ImportError:
    psutil = None


@dataclass(frozen=True)
class Finding:
    severity: str
    category: str
    key: str
    detail: str
    recommendation: str


SEVERITY_RANK = {"低": 1, "中": 2, "高": 3, "严重": 4}
MINER_TOKENS = (
    "xmrig",
    "minerd",
    "cpuminer",
    "kworkerd",
    "kdevtmpfsi",
    "kinsing",
    "watchbog",
    "s3miner",
    "cryptonight",
    "stratum+tcp",
    "stratum+ssl",
    "c3pool",
    "nanopool",
    "nicehash",
    "miningpoolhub",
)
MINING_PORTS = {3333, 3334, 4444, 5555, 7777, 8333, 14444, 45560}
DOWNLOAD_SHELL_RE = re.compile(
    r"(?:curl|wget|fetch)\b[^\n;|]*https?://[^\n;|]+(?:\||;|&&)\s*(?:ba)?sh\b",
    re.IGNORECASE,
)
REMOTE_EXEC_RE = re.compile(
    r"(?:curl|wget|fetch)\b[^\n;|]*https?://|base64\s+(?:-d|--decode)|/dev/tcp/|nc\s+-[el]",
    re.IGNORECASE,
)
ACCOUNT_CHANGE_RE = re.compile(
    r"\b(?:useradd|adduser|userdel|deluser|usermod|groupadd|groupdel|passwd)\b",
    re.IGNORECASE,
)
FAILED_LOGIN_RE = re.compile(r"Failed\s+password\s+for(?:\s+invalid\s+user)?\s+\S+\s+from\s+(\S+)", re.IGNORECASE)


def _finding(severity, category, key, detail, recommendation):
    return Finding(severity, category, key, detail, recommendation)


def _joined_process(process):
    values = [process.get("name"), process.get("exe")]
    values.extend(process.get("cmdline") or [])
    return " ".join(str(value) for value in values if value).strip()


def find_process_findings(processes):
    findings = []
    for process in processes:
        text = _joined_process(process).lower()
        name = str(process.get("name") or "").lower()
        username = str(process.get("username") or "").lower()
        pid = process.get("pid", "?")
        miner = next((token for token in MINER_TOKENS if token in text), None)
        if miner:
            findings.append(
                _finding(
                    "严重",
                    "运行进程",
                    f"miner:{miner}",
                    f"PID {pid} 正在运行疑似挖矿进程，命令行为：{text[:420]}",
                    "立即隔离主机，终止进程并检查其父进程、启动项和下载来源",
                )
            )
        ancestors = " ".join(str(item).lower() for item in process.get("ancestors") or [])
        if username == "root" and name in {"bash", "sh", "zsh", "dash", "fish"} and (
            "mcsmanager" in ancestors or "mcsm" in ancestors
        ):
            findings.append(
                _finding(
                    "严重",
                    "运行进程",
                    "mcsm-root-shell",
                    f"PID {pid} 是由 MCSManager 链路创建的 root shell，命令行为：{text[:360]}",
                    "停止并隔离管理面板，核查面板审计日志和该 shell 的全部子进程",
                )
            )
        if DOWNLOAD_SHELL_RE.search(text):
            findings.append(
                _finding(
                    "严重",
                    "运行进程",
                    f"remote-shell:{hashlib.sha256(text.encode()).hexdigest()[:16]}",
                    f"发现在线下载后直接交给 shell 执行的命令：PID {pid} {text[:420]}",
                    "立即隔离主机，检查下载内容、父进程和同一时间段日志",
                )
            )
    return findings


def find_unit_findings(units):
    findings = []
    for name, content in units.items():
        lowered = str(content).lower()
        if any(token in lowered or token in str(name).lower() for token in MINER_TOKENS):
            findings.append(
                _finding(
                    "严重",
                    "systemd 持久化",
                    f"unit:{name}",
                    f"systemd 单元 {name} 含有疑似挖矿或矿池特征",
                    "停止并禁用该单元，保留文件和日志后进行取证",
                )
            )
        if DOWNLOAD_SHELL_RE.search(content) or REMOTE_EXEC_RE.search(content):
            findings.append(
                _finding(
                    "严重",
                    "systemd 持久化",
                    f"unit:{name}",
                    f"systemd 单元 {name} 含有远程下载、解码或网络反弹执行特征",
                    "停止并禁用该单元，核查 ExecStart 指向的文件和创建者",
                )
            )
    return findings


def find_persistence_findings(files):
    findings = []
    for path, content in files.items():
        if not content.strip():
            continue
        if str(path) == "/etc/ld.so.preload":
            findings.append(
                _finding(
                    "严重",
                    "动态链接持久化",
                    "ld-preload",
                    "/etc/ld.so.preload 包含内容，可能劫持所有动态链接程序",
                    "立即隔离主机并核对其中每个库文件的来源和校验值",
                )
            )
        if any(token in content.lower() for token in MINER_TOKENS) or DOWNLOAD_SHELL_RE.search(content) or REMOTE_EXEC_RE.search(content):
            findings.append(
                _finding(
                    "严重",
                    "启动项或定时任务",
                    f"persistence:{path}",
                    f"持久化配置 {path} 含有远程执行、下载或矿池特征",
                    "禁用相关启动项前先保留证据，核查文件权限、创建时间和操作者",
                )
            )
    return findings


def find_auth_findings(lines, failed_threshold=20):
    findings = []
    failed = {}
    for line in lines:
        failed_match = FAILED_LOGIN_RE.search(line)
        if failed_match:
            source = failed_match.group(1)
            failed[source] = failed.get(source, 0) + 1
        if ACCOUNT_CHANGE_RE.search(line):
            findings.append(
                _finding(
                    "高",
                    "账户变更",
                    "account-change",
                    f"认证日志出现账户或口令管理操作：{line.strip()[-420:]}",
                    "核对操作者、终端和变更目标，检查新增账户、组成员与 SSH 密钥",
                )
            )
    for source, count in failed.items():
        if count >= failed_threshold:
            findings.append(
                _finding(
                    "高",
                    "认证日志",
                    f"ssh-burst:{source}",
                    f"来源 {source} 在本次日志窗口出现 {count} 次 SSH 失败认证",
                    "确认是否为可信扫描器；否则限制来源网段并轮换暴露服务凭据",
                )
            )
    return findings


def _ancestor_names(proc, process_map, info_map):
    result = []
    current = process_map.get(proc.pid)
    seen = set()
    while current and current.pid not in seen:
        seen.add(current.pid)
        parent_pid = info_map.get(current.pid, {}).get("ppid")
        parent = process_map.get(parent_pid)
        if parent is None:
            break
        result.append(str(info_map.get(parent.pid, {}).get("name") or ""))
        current = parent
    return result


def collect_processes():
    if psutil is None:
        return []
    process_map = {}
    info_map = {}
    for proc in psutil.process_iter(["pid", "ppid", "name", "exe", "cmdline", "username"]):
        try:
            info = proc.info
            process_map[proc.pid] = proc
            info_map[proc.pid] = info
        except (psutil.Error, OSError, AttributeError):
            continue
    result = []
    for proc in list(process_map.values()):
        try:
            info = info_map[proc.pid]
            result.append(
                {
                    **info,
                    "ancestors": _ancestor_names(proc, process_map, info_map),
                }
            )
        except (psutil.Error, OSError, AttributeError):
            continue
    return result


def collect_units(directories=("/etc/systemd/system", "/run/systemd/system")):
    units = {}
    suffixes = {".service", ".timer", ".path", ".socket", ".mount", ".target"}
    for directory in directories:
        root = Path(directory)
        if not root.is_dir():
            continue
        try:
            entries = (path for path in root.rglob("*") if path.suffix in suffixes)
        except OSError:
            continue
        for path in entries:
            try:
                if path.is_file() and path.stat().st_size <= 2 * 1024 * 1024:
                    units[str(path.relative_to(root))] = path.read_text(encoding="utf-8", errors="replace")
            except (OSError, UnicodeError, ValueError):
                continue
    return units


def collect_privileged_files(roots=("/bin", "/sbin", "/usr/bin", "/usr/sbin", "/usr/local/bin", "/root/airi")):
    result = {}
    for raw_root in roots:
        root = Path(raw_root)
        if not root.exists():
            continue
        try:
            iterator = root.rglob("*") if root.is_dir() else (root,)
            for path in iterator:
                try:
                    info = path.lstat()
                    if not stat.S_ISREG(info.st_mode):
                        continue
                    capability = ""
                    if hasattr(os, "getxattr"):
                        try:
                            capability = hashlib.sha256(os.getxattr(path, "security.capability")).hexdigest()
                        except OSError:
                            capability = ""
                    if not (info.st_mode & (stat.S_ISUID | stat.S_ISGID)) and not capability:
                        continue
                    result[str(path)] = ":".join(
                        (
                            str(info.st_mode),
                            str(info.st_uid),
                            str(info.st_gid),
                            str(info.st_size),
                            str(info.st_mtime_ns),
                            capability,
                        )
                    )
                except OSError:
                    continue
        except OSError:
            continue
    return result


def find_privileged_changes(previous, current):
    findings = []
    for path in sorted(set(previous) | set(current)):
        if previous.get(path) == current.get(path):
            continue
        action = "新增或获得特权" if path not in previous else "发生变化"
        if path not in current:
            action = "删除"
        findings.append(
            _finding(
                "高",
                "特权文件完整性",
                f"privileged:{path}",
                f"特权文件{action}：{path}",
                "核对软件包来源和变更时间，确认不是未授权的 SUID/SGID 或 capabilities 修改",
            )
        )
    return findings


def find_module_findings(modules):
    suspicious = {"diamorphine", "reptile", "rootkit", "kinsing", "xmr", "hide"}
    findings = []
    for name in modules:
        lowered = str(name).lower()
        if any(token in lowered for token in suspicious):
            findings.append(
                _finding(
                    "严重",
                    "内核模块",
                    f"module:{name}",
                    f"发现名称疑似隐藏或挖矿的内核模块：{name}",
                    "保留内存和磁盘证据后隔离主机，不能仅通过卸载模块恢复信任",
                )
            )
    return findings


def collect_modules():
    try:
        return [line.split()[0] for line in Path("/proc/modules").read_text(errors="replace").splitlines() if line.split()]
    except OSError:
        return []


def _file_fingerprint(path):
    try:
        stat_result = path.lstat()
    except OSError:
        return None
    mode = stat_result.st_mode
    data_hash = ""
    if stat.S_ISREG(mode) and stat_result.st_size <= 4 * 1024 * 1024:
        digest = hashlib.sha256()
        try:
            with path.open("rb") as stream:
                while True:
                    chunk = stream.read(1024 * 1024)
                    if not chunk:
                        break
                    digest.update(chunk)
            data_hash = digest.hexdigest()
        except OSError:
            data_hash = "unreadable"
    return ":".join(
        (
            str(stat_result.st_mode),
            str(stat_result.st_uid),
            str(stat_result.st_gid),
            str(stat_result.st_size),
            str(stat_result.st_mtime_ns),
            data_hash,
        )
    )


def collect_files(paths, max_depth=3):
    result = {}
    for raw_path in paths:
        path = Path(raw_path)
        try:
            if path.is_file() or path.is_symlink():
                fingerprint = _file_fingerprint(path)
                if fingerprint is not None:
                    result[str(path)] = fingerprint
                continue
            if not path.is_dir():
                continue
            base_depth = len(path.parts)
            for candidate in path.rglob("*"):
                try:
                    if len(candidate.parts) - base_depth > max_depth:
                        continue
                    if candidate.is_dir() and not candidate.is_symlink():
                        continue
                    fingerprint = _file_fingerprint(candidate)
                    if fingerprint is not None:
                        result[str(candidate)] = fingerprint
                except OSError:
                    continue
        except OSError:
            continue
    return result


def collect_text_files(paths, max_depth=3):
    result = {}
    for raw_path in paths:
        path = Path(raw_path)
        candidates = []
        try:
            if path.is_file() or path.is_symlink():
                candidates.append(path)
            elif path.is_dir():
                base_depth = len(path.parts)
                candidates.extend(
                    candidate
                    for candidate in path.rglob("*")
                    if len(candidate.parts) - base_depth <= max_depth and candidate.is_file()
                )
        except OSError:
            continue
        for candidate in candidates:
            try:
                if candidate.stat().st_size <= 512 * 1024:
                    result[str(candidate)] = candidate.read_text(encoding="utf-8", errors="replace")
            except (OSError, UnicodeError):
                continue
    return result


def find_file_changes(previous, current):
    findings = []
    for path in sorted(set(previous) | set(current)):
        old = previous.get(path)
        new = current.get(path)
        if old == new:
            continue
        if old is None:
            action = "新增"
        elif new is None:
            action = "删除"
        else:
            action = "修改"
        findings.append(
            _finding(
                "高",
                "关键文件完整性",
                f"file:{path}",
                f"关键路径文件{action}：{path}",
                "核对变更来源、内容和权限；不确认前不要继续信任该主机",
            )
        )
    return findings


def collect_listeners():
    listeners = {}
    if psutil is None:
        return listeners
    try:
        connections = psutil.net_connections(kind="inet")
    except (psutil.Error, OSError):
        return listeners
    for connection in connections:
        if connection.status != psutil.CONN_LISTEN:
            continue
        address = connection.laddr
        ip = getattr(address, "ip", None) or (address[0] if address else "?")
        port = getattr(address, "port", None) or (address[1] if address else "?")
        pid = connection.pid
        process_name = "未知"
        if pid:
            try:
                process_name = psutil.Process(pid).name()
            except (psutil.Error, OSError):
                pass
        listeners[f"{ip}:{port}"] = {"pid": pid, "process": process_name}
    return listeners


def collect_connections():
    connections = []
    if psutil is None:
        return connections
    try:
        active = psutil.net_connections(kind="inet")
    except (psutil.Error, OSError):
        return connections
    for connection in active:
        if connection.status != psutil.CONN_ESTABLISHED or not connection.raddr:
            continue
        local = connection.laddr
        remote = connection.raddr
        local_ip = getattr(local, "ip", None) or (local[0] if local else "?")
        local_port = getattr(local, "port", None) or (local[1] if local else "?")
        remote_ip = getattr(remote, "ip", None) or (remote[0] if remote else "?")
        remote_port = getattr(remote, "port", None) or (remote[1] if remote else "?")
        process_name = "未知"
        command = ""
        if connection.pid:
            try:
                process = psutil.Process(connection.pid)
                process_name = process.name()
                command = " ".join(process.cmdline()[:8])
            except (psutil.Error, OSError):
                pass
        connections.append(
            {
                "pid": connection.pid,
                "process": process_name,
                "command": command,
                "local": f"{local_ip}:{local_port}",
                "remote": f"{remote_ip}:{remote_port}",
                "remote_port": int(remote_port) if str(remote_port).isdigit() else 0,
            }
        )
    return connections


def find_connection_findings(connections):
    findings = []
    for connection in connections:
        remote_port = connection.get("remote_port", 0)
        command = str(connection.get("command") or "").lower()
        if remote_port not in MINING_PORTS and not any(token in command for token in MINER_TOKENS):
            continue
        findings.append(
            _finding(
                "高",
                "网络外联",
                f"outbound:{connection.get('pid')}:{connection.get('remote')}",
                f"进程 {connection.get('process', '未知')}（PID {connection.get('pid', '?')}）连接可疑外部端点 {connection.get('remote')}，命令行为：{command[:320]}",
                "确认外联目标和进程来源；若不是业务必需，立即隔离并阻断该连接",
            )
        )
    return findings


def find_listener_changes(previous, current):
    findings = []
    for endpoint in sorted(set(current) - set(previous)):
        info = current[endpoint]
        findings.append(
            _finding(
                "中",
                "网络监听",
                f"listener:{endpoint}",
                f"发现新的监听端点 {endpoint}，进程 {info.get('process', '未知')}，PID {info.get('pid', '?')}",
                "确认该端口和服务是否为预期；不需要的监听应绑定管理网段或关闭",
            )
        )
    return findings


def read_log_delta(path, offset):
    target = Path(path)
    try:
        info = target.stat()
        inode = str(getattr(info, "st_ino", 0))
        old_inode = str(offset.get("inode", ""))
        position = int(offset.get("position", 0) or 0)
        if old_inode != inode or position > info.st_size:
            position = 0
        with target.open("r", encoding="utf-8", errors="replace") as stream:
            stream.seek(position)
            data = stream.read(256 * 1024)
            position = stream.tell()
        return data.splitlines(), {"inode": inode, "position": position}
    except (OSError, ValueError):
        return [], offset


def find_log_findings(lines):
    findings = []
    for line in lines:
        lowered = line.lower()
        if any(token in lowered for token in MINER_TOKENS) or DOWNLOAD_SHELL_RE.search(line) or REMOTE_EXEC_RE.search(line):
            findings.append(
                _finding(
                    "严重",
                    "应用日志行为",
                    f"log-threat:{hashlib.sha256(line.strip().encode()).hexdigest()[:16]}",
                    f"应用日志出现高风险命令或矿池特征：{line.strip()[-420:]}",
                    "立即保留日志并隔离主机，核查执行者、父进程和落地文件",
                )
            )
    return findings


def scan_system(
    paths,
    previous_files,
    previous_listeners,
    log_offsets,
    failed_threshold=20,
    log_paths=None,
    previous_privileged=None,
):
    findings = []
    processes = collect_processes()
    findings.extend(find_process_findings(processes))
    findings.extend(find_connection_findings(collect_connections()))
    findings.extend(find_module_findings(collect_modules()))
    units = collect_units()
    findings.extend(find_unit_findings(units))
    findings.extend(find_persistence_findings(collect_text_files(paths)))
    current_files = collect_files(paths)
    if previous_files:
        findings.extend(find_file_changes(previous_files, current_files))
    listeners = collect_listeners()
    if previous_listeners:
        findings.extend(find_listener_changes(previous_listeners, listeners))
    privileged = collect_privileged_files()
    if previous_privileged:
        findings.extend(find_privileged_changes(previous_privileged, privileged))
    auth_lines = []
    next_offsets = {}
    configured_logs = list(log_paths or ("/var/log/auth.log", "/var/log/secure"))
    auth_paths = [path for path in configured_logs if Path(path).name in {"auth.log", "secure"}]
    app_paths = [path for path in configured_logs if path not in auth_paths]
    for path in auth_paths:
        lines, next_offset = read_log_delta(path, log_offsets.get(path, {}))
        auth_lines.extend(lines)
        next_offsets[path] = next_offset
    findings.extend(find_auth_findings(auth_lines, failed_threshold))
    for path in app_paths:
        lines, next_offset = read_log_delta(path, log_offsets.get(path, {}))
        next_offsets[path] = next_offset
        findings.extend(find_log_findings(lines))
    return findings, current_files, listeners, next_offsets, privileged
