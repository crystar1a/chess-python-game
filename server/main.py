import threading

from server.net.tcp_server import TCPServer
from server.rooms import RoomManager
from server.auth import AuthService, UserStore


def main():
    store = UserStore()
    rooms = RoomManager(AuthService(store))
    # Serialize routing and delivery so simultaneous requests retain server order.
    lock = threading.RLock()

    def on_message(conn_id, message):
        with lock:
            server.send_many(rooms.handle_message(conn_id, message))

    def on_disconnect(conn_id):
        with lock:
            server.send_many(rooms.on_disconnect(conn_id))

    server = TCPServer(host='0.0.0.0', port=8765,
                       on_message=on_message, on_disconnect=on_disconnect)
    server.start()
    print(f'TCP server listening on port {server.port}', flush=True)
    try:
        wake = threading.Event()
        while not wake.wait(0.1):
            with lock:
                server.send_many(rooms.check_timeouts())
    except KeyboardInterrupt:
        pass
    finally:
        server.close()
        store.close()


if __name__ == '__main__':
    main()
