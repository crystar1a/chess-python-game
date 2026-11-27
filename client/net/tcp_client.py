import queue
import socket
import threading
import time

from shared.protocol import DEFAULT_TCP_PORT, encode_frame, recv_frame


class TCPClient:
    def __init__(self, host, port=DEFAULT_TCP_PORT, timeout=None):
        self.host, self.port = host, port
        self._socket = socket.create_connection((host, port), timeout=timeout)
        self._socket.settimeout(None)
        self._messages = queue.Queue()
        self._send_lock = threading.Lock()
        self._closed = threading.Event()
        self._token = None
        self._last_pong = time.monotonic()
        self._thread = threading.Thread(target=self._receive, daemon=True)
        self._heartbeat = threading.Thread(target=self._ping, daemon=True)
        self._thread.start()
        self._heartbeat.start()

    def enable_reconnect(self, token):
        self._token = token

    def _receive(self):
        while not self._closed.is_set():
            sock = self._socket
            try:
                while not self._closed.is_set():
                    message = recv_frame(sock)
                    if message.get('type') == 'PONG':
                        self._last_pong = time.monotonic()
                    else:
                        self._messages.put(message)
            except (EOFError, OSError, ValueError):
                pass
            finally:
                sock.close()
            if self._closed.is_set() or not self._token:
                return
            self._messages.put({'type': 'RECONNECTING'})
            deadline = time.monotonic() + 75
            while not self._closed.wait(2):
                if time.monotonic() >= deadline:
                    self._messages.put({'type': 'ERROR', 'reason': 'resume_expired'})
                    return
                candidate = None
                try:
                    candidate = socket.create_connection((self.host, self.port), timeout=2)
                    candidate.settimeout(3)
                    candidate.sendall(encode_frame({'type': 'RESUME', 'token': self._token}))
                    message = recv_frame(candidate)
                    if message.get('type') != 'GAME_START':
                        candidate.close()
                        continue
                    candidate.settimeout(None)
                    with self._send_lock:
                        if self._closed.is_set():
                            candidate.close()
                            return
                        self._socket = candidate
                        self._last_pong = time.monotonic()
                    self._messages.put(message)
                    break
                except (OSError, EOFError, ValueError):
                    if candidate:
                        candidate.close()

    def _ping(self):
        while not self._closed.wait(3):
            if time.monotonic() - self._last_pong > 12:
                try:
                    self._socket.shutdown(socket.SHUT_RDWR)
                except OSError:
                    pass
                continue
            try:
                self.send({'type': 'PING'})
            except OSError:
                pass

    def send(self, msg):
        frame = encode_frame(msg)
        with self._send_lock:
            self._socket.sendall(frame)

    def poll_messages(self) -> list[dict]:
        messages = []
        while True:
            try:
                messages.append(self._messages.get_nowait())
            except queue.Empty:
                return messages

    def close(self):
        self._closed.set()
        try:
            self._socket.shutdown(socket.SHUT_RDWR)
        except OSError:
            pass
        self._socket.close()
        if self._thread is not threading.current_thread():
            self._thread.join(timeout=4)
