import os
from dataclasses import dataclass

import psutil
import cpuinfo


@dataclass
class CPUInfo:
    core: int
    """CPU 物理核心数"""
    usage: float
    """CPU 占用百分比，取值范围(0,100]"""
    freq: float
    """CPU 的时钟速度（单位：GHz）"""

    @classmethod
    def get_cpu_info(cls):
        cpu_core = psutil.cpu_count(logical=False)
        cpu_usage = psutil.cpu_percent(interval=0.3)
        cpu_freq = 0.0
        try:
            freq = psutil.cpu_freq()
            if freq is not None and freq.current:
                cpu_freq = round(freq.current / 1000, 2)
        except Exception:
            cpu_freq = 0.0
        if not cpu_freq:
            try:
                hz = cpuinfo.get_cpu_info().get("hz_advertised", [0])[0]
                cpu_freq = round(hz / 1_000_000_000, 2) if hz else 0.0
            except Exception:
                cpu_freq = 0.0

        if cpu_core is None:
            try:
                cpu_core = cpuinfo.get_cpu_info()["count"]
            except Exception:
                cpu_core = psutil.cpu_count(logical=True) or 1

        return CPUInfo(core=cpu_core, usage=cpu_usage, freq=cpu_freq)


@dataclass
class RAMInfo:

    total: float
    """RAM 总量"""
    usage: float
    """当前 RAM 占用量/GB"""

    @classmethod
    def get_ram_info(cls):
        ram_total = round(psutil.virtual_memory().total / (1024**3), 2)
        ram_usage = round(psutil.virtual_memory().used / (1024**3), 2)

        return RAMInfo(total=ram_total, usage=ram_usage)


@dataclass
class SwapMemory:

    total: float
    """Swap 总量"""
    usage: float
    """当前 Swap 占用量/GB"""

    @classmethod
    def get_swap_info(cls):
        swap_total = round(psutil.swap_memory().total / (1024**3), 2)
        swap_usage = round(psutil.swap_memory().used / (1024**3), 2)

        return SwapMemory(total=swap_total, usage=swap_usage)


@dataclass
class DiskInfo:

    total: float
    """硬盘总量"""
    usage: float
    """当前硬盘占用量/GB"""

    @classmethod
    def get_disk_info(cls):
        path = os.path.abspath(os.sep)
        try:
            usage = psutil.disk_usage(path)
            disk_total = round(usage.total / (1024**3), 2)
            disk_usage = round(usage.used / (1024**3), 2)
        except Exception:
            disk_total = 0.0
            disk_usage = 0.0

        return DiskInfo(total=disk_total, usage=disk_usage)


def get_status_info() -> tuple[CPUInfo, RAMInfo, SwapMemory, DiskInfo]:
    cpu_info = CPUInfo.get_cpu_info()
    ram_info = RAMInfo.get_ram_info()
    swap_info = SwapMemory.get_swap_info()
    disk_info = DiskInfo.get_disk_info()

    return cpu_info, ram_info, swap_info, disk_info
