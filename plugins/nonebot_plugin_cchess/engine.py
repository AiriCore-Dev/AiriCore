import asyncio
import re
import sys
from pathlib import Path

from .move import Move


class EngineError(Exception):
    def __init__(self, message: str):
        self.message = message


class UCCIEngine:
    def __init__(self, engine_path: Path):
        self.engine_path = engine_path.resolve()

    async def open(self):
        if not self.engine_path.exists():
            raise EngineError("找不到UCCI引擎！")
        if self.engine_path.suffix == ".py":
            program, *args = sys.executable, str(self.engine_path)
        else:
            program, args = str(self.engine_path), []
        self._process = await asyncio.create_subprocess_exec(
            program,
            *args,
            stdin=asyncio.subprocess.PIPE,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        self.stdin = self._process.stdin
        self.stdout = self._process.stdout
        try:
            await self.start()
        except Exception:
            self.close()
            raise

    def close(self):
        process = getattr(self, "_process", None)
        if process is None:
            return
        self._process = None
        self.stdin = None
        self.stdout = None
        try:
            self.stdin = process.stdin
            self.stop()
        except Exception:
            pass
        finally:
            self.stdin = None
        if process.returncode is None:
            try:
                process.kill()
            except ProcessLookupError:
                pass
            except Exception:
                pass
        try:
            asyncio.get_running_loop().create_task(self._reap(process))
        except RuntimeError:
            pass

    @staticmethod
    async def _reap(process):
        try:
            await asyncio.wait_for(process.wait(), timeout=10)
        except Exception:
            pass
        for pipe in (process.stdin, process.stdout, process.stderr):
            transport = getattr(pipe, "_transport", None)
            if transport is None:
                transport = getattr(pipe, "transport", None)
            if transport is not None:
                try:
                    transport.close()
                except Exception:
                    pass

    def send_line(self, line: str):
        assert self.stdin is not None
        self.stdin.write(f"{line}\n".encode())

    async def read_line(self, timeout: int = 10) -> str:
        assert self.stdout is not None
        try:
            line = await asyncio.wait_for(self.stdout.readline(), timeout)
        except asyncio.TimeoutError:
            raise EngineError("读取引擎输出超时")
        if not line:
            raise EngineError("UCCI引擎已退出")
        return line.decode("utf-8").strip()

    async def read_lines(self, endword: str) -> list[str]:
        lines = []
        while True:
            line = await self.read_line()
            lines.append(line)
            if line.startswith(endword):
                break
        return lines

    async def start(self):
        self.send_line("ucci")
        await self.read_lines("ucciok")

    def stop(self):
        self.send_line("quit")

    async def bestmove(self, position: str, time: int = 500, depth: int = 10) -> Move:
        self.send_line(position)
        self.send_line(f"go time {time} depth {depth}")
        lines = await self.read_lines("bestmove")
        if not lines:
            raise EngineError("引擎无法获取合适的着法")
        match = re.search(r"bestmove ([a-zA-Z]\d[a-zA-Z]\d)", lines[-1])
        if not match:
            raise EngineError("引擎返回的结果形式不正确")
        return Move.from_ucci(match.group(1))
