import socket
import struct
import select
import threading
from concurrent.futures import ThreadPoolExecutor

from mcrcon import MCRcon, MCRconException


class SafeMCRcon(MCRcon):

    def __init__(self, host, password, port=25575, tlsmode=0, timeout=8):
        self.host = host
        self.password = password
        self.port = port
        self.tlsmode = tlsmode
        self.timeout = 0
        self.sock_timeout = timeout
        self.socket = None

    def connect(self):
        self.socket = socket.create_connection(
            (self.host, self.port), timeout=self.sock_timeout
        )
        if self.tlsmode > 0:
            import ssl

            ctx = ssl.create_default_context()
            if self.tlsmode > 1:
                ctx.check_hostname = False
                ctx.verify_mode = ssl.CERT_NONE
            self.socket = ctx.wrap_socket(self.socket, server_hostname=self.host)
        self.socket.settimeout(self.sock_timeout)
        self._send(3, self.password)

    def _read(self, length):
        if self.socket is None:
            raise MCRconException("Must connect before reading data")
        data = b""
        while len(data) < length:
            chunk = self.socket.recv(length - len(data))
            if not chunk:
                raise MCRconException("Connection closed by server")
            data += chunk
        return data

    def force_close(self):
        sock = self.socket
        self.socket = None
        if sock is None:
            return
        try:
            sock.shutdown(socket.SHUT_RDWR)
        except Exception:
            pass
        try:
            sock.close()
        except Exception:
            pass


_executor = None
_executor_lock = threading.Lock()


def get_executor() -> ThreadPoolExecutor:
    global _executor
    if _executor is not None:
        return _executor
    with _executor_lock:
        if _executor is None:
            _executor = ThreadPoolExecutor(
                max_workers=2, thread_name_prefix="airi_rcon"
            )
        return _executor


def shutdown_executor() -> None:
    global _executor
    with _executor_lock:
        ex = _executor
        _executor = None
    if ex is not None:
        ex.shutdown(wait=False, cancel_futures=True)
