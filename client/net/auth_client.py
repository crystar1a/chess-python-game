import time
import socket

from client.net.tcp_client import TCPClient


class ConnectionUnavailable(OSError):
    pass


def exchange(host, port, message, deadline=5.0):
    """Run in a worker; caller owns the returned client."""
    try:
        client = TCPClient(host, port, timeout=1.5)
    except (OSError, socket.timeout) as exc:
        raise ConnectionUnavailable(str(exc)) from exc
    try:
        client.send(message)
        end = time.monotonic() + deadline
        while time.monotonic() < end:
            messages = client.poll_messages()
            if messages:
                return messages[0], client
            time.sleep(0.02)
        raise TimeoutError('Authentication timed out')
    except BaseException:
        client.close()
        raise
