import queue
import socket
import threading

from shared.protocol import DEFAULT_TCP_PORT, encode_frame, recv_frame


class TCPClient:
    def __init__(self, host, port=DEFAULT_TCP_PORT):
        self._socket = socket.create_connection((host, port))
        self._messages = queue.Queue()
        self._send_lock = threading.Lock()
        self._thread = threading.Thread(target=self._receive, daemon=True)
        self._thread.start()

    def _receive(self):
        try:
            while True:
                self._messages.put(recv_frame(self._socket))
        except (EOFError, OSError, ValueError):
            pass
        finally:
            self._socket.close()

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
        try:
            self._socket.shutdown(socket.SHUT_RDWR)
        except OSError:
            pass
        self._socket.close()
        if self._thread is not threading.current_thread():
            self._thread.join()
