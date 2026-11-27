"""Persist a player's reconnect token without storing it in plaintext on Windows."""
import ctypes
import hashlib
import json
import os
from pathlib import Path


SESSION_DIR = Path(__file__).resolve().parents[2] / '.sessions'


def _crypt(data, protect):
    if os.name != 'nt':
        raise OSError('Session storage is only available on Windows')
    from ctypes import wintypes

    class Blob(ctypes.Structure):
        _fields_ = [('size', wintypes.DWORD), ('data', ctypes.POINTER(ctypes.c_ubyte))]

    source = (ctypes.c_ubyte * len(data)).from_buffer_copy(data)
    src = Blob(len(data), source)
    dst = Blob()
    crypt32 = ctypes.windll.crypt32
    kernel32 = ctypes.windll.kernel32
    kernel32.LocalFree.argtypes = [ctypes.c_void_p]
    kernel32.LocalFree.restype = ctypes.c_void_p
    fn = crypt32.CryptProtectData if protect else crypt32.CryptUnprotectData
    if not fn(ctypes.byref(src), None, None, None, None, 1, ctypes.byref(dst)):
        raise OSError('Unable to protect reconnect session')
    try:
        return ctypes.string_at(dst.data, dst.size)
    finally:
        kernel32.LocalFree(dst.data)


def _path(username, room):
    key = hashlib.sha256((username.casefold() + '\0' + room.upper()).encode()).hexdigest()
    return SESSION_DIR / (key + '.bin')


def save_session(username, room, token, color):
    SESSION_DIR.mkdir(exist_ok=True)
    data = json.dumps({'token': token, 'color': color}).encode()
    _path(username, room).write_bytes(_crypt(data, True))


def load_session(username, room):
    try:
        data = json.loads(_crypt(_path(username, room).read_bytes(), False))
        if isinstance(data.get('token'), str) and data.get('color') in ('white', 'black'):
            return data
    except (OSError, ValueError, TypeError, AttributeError):
        pass
    return None


def room_request(username, room):
    room = room.strip().upper()
    session = load_session(username, room)
    return {'type': 'RESUME', 'token': session['token']} if session else {'type': 'JOIN_ROOM', 'room_code': room}


def delete_session(username, room):
    try:
        _path(username, room).unlink(missing_ok=True)
    except OSError:
        pass
