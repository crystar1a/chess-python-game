import json
import struct
from enum import Enum


DEFAULT_TCP_PORT = 8765
MAX_FRAME = 65536


class MessageType(str, Enum):
    AUTH_GUEST = 'AUTH_GUEST'
    AUTH_SUBMIT = 'AUTH_SUBMIT'
    AUTH_REGISTER = 'AUTH_REGISTER'
    AUTH_TOKEN = 'AUTH_TOKEN'
    AUTH_OK = 'AUTH_OK'
    AUTH_NEEDS_REGISTER = 'AUTH_NEEDS_REGISTER'
    AUTH_ERROR = 'AUTH_ERROR'
    CREATE_ROOM = 'CREATE_ROOM'
    JOIN_ROOM = 'JOIN_ROOM'
    LIST_ROOMS = 'LIST_ROOMS'
    ROOM_LIST = 'ROOM_LIST'
    RESUME = 'RESUME'
    WELCOME = 'WELCOME'
    GAME_START = 'GAME_START'
    MOVE_REQUEST = 'MOVE_REQUEST'
    MOVE_ACCEPTED = 'MOVE_ACCEPTED'
    MOVE_REJECTED = 'MOVE_REJECTED'
    ROOM_STATE = 'ROOM_STATE'
    RESIGN = 'RESIGN'
    DRAW_OFFER = 'DRAW_OFFER'
    DRAW_ACCEPT = 'DRAW_ACCEPT'
    REMATCH_REQUEST = 'REMATCH_REQUEST'
    REMATCH_ACCEPT = 'REMATCH_ACCEPT'
    REMATCH_DECLINE = 'REMATCH_DECLINE'
    CHAT_SEND = 'CHAT_SEND'
    CHAT_MESSAGE = 'CHAT_MESSAGE'
    CHAT_REJECTED = 'CHAT_REJECTED'
    PING = 'PING'
    PONG = 'PONG'
    ERROR = 'ERROR'


def make_message(msg_type: str, **fields) -> dict:
    return {'type': msg_type.value if isinstance(msg_type, MessageType) else msg_type, **fields}


def encode_frame(message: dict) -> bytes:
    if not isinstance(message, dict):
        raise ValueError('Message must be a dictionary')
    payload = json.dumps(message, ensure_ascii=False, allow_nan=False).encode('utf-8')
    if len(payload) > MAX_FRAME:
        raise ValueError('Frame exceeds maximum size')
    return struct.pack('!I', len(payload)) + payload


def recv_exact(sock, num_bytes) -> bytes:
    if num_bytes < 0:
        raise ValueError('Byte count cannot be negative')
    data = bytearray()
    while len(data) < num_bytes:
        chunk = sock.recv(num_bytes - len(data))
        if not chunk:
            raise EOFError('Connection closed before frame was complete')
        data.extend(chunk)
    return bytes(data)


def recv_frame(sock) -> dict:
    size = struct.unpack('!I', recv_exact(sock, 4))[0]
    if size == 0 or size > MAX_FRAME:
        raise ValueError('Invalid frame size')
    try:
        def invalid_constant(value):
            raise ValueError(f'Invalid JSON constant: {value}')

        message = json.loads(recv_exact(sock, size).decode('utf-8'), parse_constant=invalid_constant)
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ValueError('Invalid JSON payload') from exc
    if not isinstance(message, dict):
        raise ValueError('Message must be a dictionary')
    return message
