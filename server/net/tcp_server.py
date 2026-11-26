import socket
import threading
import uuid
from concurrent.futures import ThreadPoolExecutor

from shared.protocol import DEFAULT_TCP_PORT, encode_frame, recv_frame


class TCPServer:
    def __init__(self, host='0.0.0.0', port=DEFAULT_TCP_PORT, on_message=None, on_disconnect=None):
        self.host = host
        self.port = port
        self.on_message = on_message or (lambda conn_id, msg: None)
        self.on_disconnect = on_disconnect or (lambda conn_id: None)
        self.connections = {}
        self._send_locks = {}
        self._lock = threading.RLock()
        self._listener = None
        self._thread = None
        self._executor = None
        self._closed = False

    def start(self):
        with self._lock:
            if self._listener is not None or self._closed:
                raise RuntimeError('Server already started or closed')
            listener = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            try:
                listener.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
                listener.bind((self.host, self.port))
                listener.listen()
                listener.settimeout(0.2)
            except BaseException:
                listener.close()
                raise
            self.port = listener.getsockname()[1]
            self._listener = listener
            self._executor = ThreadPoolExecutor()
            self._thread = threading.Thread(target=self._accept, daemon=True)
            self._thread.start()

    def _accept(self):
        while True:
            try:
                conn, _ = self._listener.accept()
            except socket.timeout:
                continue
            except OSError:
                break
            with self._lock:
                if self._closed:
                    conn.close()
                    break
                conn_id = uuid.uuid4().hex
                self.connections[conn_id] = conn
                self._send_locks[conn_id] = threading.Lock()
                self._executor.submit(self._receive, conn_id, conn)

    def _receive(self, conn_id, conn):
        try:
            while True:
                self.on_message(conn_id, recv_frame(conn))
        except (EOFError, OSError, ValueError):
            pass
        finally:
            with self._lock:
                self.connections.pop(conn_id, None)
                self._send_locks.pop(conn_id, None)
            conn.close()
            self.on_disconnect(conn_id)

    def send(self, conn_id, msg):
        frame = encode_frame(msg)
        with self._lock:
            conn = self.connections[conn_id]
            send_lock = self._send_locks[conn_id]
        with send_lock:
            conn.sendall(frame)

    def send_many(self, deliveries):
        for conn_id, msg in deliveries:
            self.send(conn_id, msg)

    def close(self):
        with self._lock:
            if self._closed:
                return
            self._closed = True
            listener = self._listener
            connections = list(self.connections.values())
        if listener:
            listener.close()
        for conn in connections:
            try:
                conn.shutdown(socket.SHUT_RDWR)
            except OSError:
                pass
            conn.close()
        if self._thread and self._thread is not threading.current_thread():
            self._thread.join()
        if self._executor:
            self._executor.shutdown(wait=False)
