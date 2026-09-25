import asyncio
import struct
from dataclasses import dataclass
from pathlib import Path

from google.protobuf import descriptor_pb2, descriptor_pool, message_factory
from google.protobuf.message import DecodeError


MAX_PAYLOAD = 4 * 1024 * 1024
HEADER = struct.Struct('>iqHBBBqqH')
_pool = descriptor_pool.DescriptorPool()
_files = descriptor_pb2.FileDescriptorSet.FromString(
    (Path(__file__).parent / 'assets/protocol.desc').read_bytes()
)
for _file in _files.file:
    _pool.Add(_file)


class QueryError(ValueError):
    pass


class ProtocolError(QueryError):
    pass


@dataclass(frozen=True)
class Frame:
    command: int
    session: int
    sequence: int
    payload: bytes
    error: int = 0
    version: tuple = (1, 0, 0)
    down_sequence: int = 0


def message(name, **values):
    qualified = name if '.' in name else f'protocol.{name}'
    return message_factory.GetMessageClass(_pool.FindMessageTypeByName(qualified))(**values)


def decode(name, payload):
    try:
        result = message(name)
        result.ParseFromString(payload)
        return result
    except DecodeError:
        raise ProtocolError('游戏返回的数据无法解析，请联系管理员更新插件') from None


def encode_frame(frame):
    if len(frame.payload) > MAX_PAYLOAD:
        raise ProtocolError('游戏数据包超过大小限制')
    return HEADER.pack(
        len(frame.payload), frame.session, frame.command, *frame.version,
        frame.sequence, frame.down_sequence, frame.error
    ) + frame.payload


async def read_frame(reader):
    try:
        size, session, command, a, b, c, sequence, down, error = HEADER.unpack(
            await reader.readexactly(HEADER.size)
        )
        if not 0 <= size <= MAX_PAYLOAD:
            raise ProtocolError('游戏数据包长度异常')
        payload = await reader.readexactly(size)
    except asyncio.IncompleteReadError:
        raise ProtocolError('游戏连接已断开，请稍后重试') from None
    if (a, b) > (1, 0):
        raise ProtocolError('游戏通信协议已更新，请联系管理员更新插件')
    return Frame(command, session, sequence, payload, error, (a, b, c), down)
