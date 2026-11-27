import socket
import struct
import threading
import unittest
import queue
import time

from shared.protocol import MAX_FRAME, MessageType, encode_frame, make_message, recv_exact, recv_frame
from client.net.tcp_client import TCPClient
from server.net.tcp_server import TCPServer
from server.rooms import RoomManager


class ProtocolTests(unittest.TestCase):
    def setUp(self):
        self.sender, self.receiver = socket.socketpair()
        self.addCleanup(self.sender.close)
        self.addCleanup(self.receiver.close)
        self.receiver.settimeout(3)

    def test_utf8_and_message_type(self):
        message = make_message(MessageType.CREATE_ROOM, name='Người chơi Việt Nam')
        self.sender.sendall(encode_frame(message))
        self.assertEqual(recv_frame(self.receiver), {'type': 'CREATE_ROOM', 'name': 'Người chơi Việt Nam'})

    def test_fragmentation(self):
        message = {'text': 'Xin chào', 'n': 42}
        frame = encode_frame(message)
        def send_parts():
            for i in range(0, len(frame), 2):
                self.sender.sendall(frame[i:i + 2])
        thread = threading.Thread(target=send_parts)
        thread.start()
        try:
            self.assertEqual(recv_frame(self.receiver), message)
        finally:
            thread.join(3)

    def test_coalescing(self):
        messages = [{'n': n} for n in range(3)]
        self.sender.sendall(b''.join(encode_frame(m) for m in messages))
        self.assertEqual([recv_frame(self.receiver) for _ in messages], messages)

    def test_invalid_lengths(self):
        for size in (0, MAX_FRAME + 1):
            with self.subTest(size=size):
                self.sender.sendall(struct.pack('!I', size))
                with self.assertRaises(ValueError):
                    recv_frame(self.receiver)

    def test_invalid_payloads(self):
        for payload in (b'{invalid', b'[]', b'null', b'\xff', b'{"n":NaN}'):
            with self.subTest(payload=payload):
                self.sender.sendall(struct.pack('!I', len(payload)) + payload)
                with self.assertRaises(ValueError):
                    recv_frame(self.receiver)

    def test_eof_in_header_and_payload(self):
        for data in (b'\x00\x00', struct.pack('!I', 8) + b'{}'):
            with self.subTest(data=data):
                sender, receiver = socket.socketpair()
                with sender, receiver:
                    sender.sendall(data)
                    sender.shutdown(socket.SHUT_WR)
                    with self.assertRaises(EOFError):
                        recv_frame(receiver)

    def test_recv_exact_zero(self):
        self.assertEqual(recv_exact(self.receiver, 0), b'')

    def test_encode_limit_and_type(self):
        with self.assertRaises(ValueError):
            encode_frame({'data': 'x' * MAX_FRAME})
        with self.assertRaises(ValueError):
            encode_frame([])


class TCPIntegrationTests(unittest.TestCase):
    def test_chat_between_room_players_over_tcp(self):
        rooms = RoomManager()
        lock = threading.RLock()
        def on_message(conn, message):
            with lock:
                server.send_many(rooms.handle_message(conn, message))
        def on_disconnect(conn):
            with lock:
                server.send_many(rooms.on_disconnect(conn))
        server = TCPServer('127.0.0.1', 0, on_message, on_disconnect)
        server.start()
        self.addCleanup(server.close)
        white = TCPClient('127.0.0.1', server.port)
        black = TCPClient('127.0.0.1', server.port)
        self.addCleanup(white.close)
        self.addCleanup(black.close)
        def receive(client, kind):
            deadline = time.monotonic() + 3
            while time.monotonic() < deadline:
                for message in client.poll_messages():
                    if message['type'] == kind:
                        return message
                time.sleep(0.01)
            self.fail('Missing ' + kind)
        white.send({'type': 'CREATE_ROOM'})
        room = receive(white, 'WELCOME')['room_code']
        black.send({'type': 'JOIN_ROOM', 'room_code': room})
        receive(white, 'GAME_START')
        white.send({'type': 'CHAT_SEND', 'text': 'Xin chào ♞'})
        received = receive(black, 'CHAT_MESSAGE')
        self.assertEqual(received['text'], 'Xin chào ♞')
        self.assertEqual(received['color'], 'white')

    def test_list_rooms_then_join_over_tcp(self):
        rooms = RoomManager()
        lock = threading.RLock()
        def on_message(conn, message):
            with lock:
                server.send_many(rooms.handle_message(conn, message))
        def on_disconnect(conn):
            with lock:
                server.send_many(rooms.on_disconnect(conn))
        server = TCPServer('127.0.0.1', 0, on_message, on_disconnect)
        server.start()
        self.addCleanup(server.close)
        host = TCPClient('127.0.0.1', server.port)
        viewer = TCPClient('127.0.0.1', server.port)
        self.addCleanup(host.close)
        self.addCleanup(viewer.close)
        def receive(client, kind):
            deadline = time.monotonic() + 3
            while time.monotonic() < deadline:
                for message in client.poll_messages():
                    if message['type'] == kind:
                        return message
                time.sleep(0.01)
            self.fail('Missing ' + kind)
        host.send({'type': 'AUTH_GUEST', 'username': 'Alice'})
        receive(host, 'AUTH_OK')
        self.addCleanup(rooms.auth_service.store.close)
        host.send({'type': 'CREATE_ROOM', 'minutes': 10})
        code = receive(host, 'WELCOME')['room_code']
        viewer.send({'type': 'LIST_ROOMS'})
        self.assertEqual(receive(viewer, 'ROOM_LIST')['rooms'], [{'room_code': code, 'host': 'Alice', 'minutes': 10}])
        viewer.send({'type': 'JOIN_ROOM', 'room_code': code})
        self.assertEqual(receive(host, 'GAME_START')['room_code'], code)

    def test_client_closes_unresponsive_connection_after_six_seconds(self):
        listener = socket.socket()
        listener.bind(('127.0.0.1', 0))
        listener.listen()
        self.addCleanup(listener.close)
        client = TCPClient('127.0.0.1', listener.getsockname()[1])
        self.addCleanup(client.close)
        conn, _ = listener.accept()
        self.addCleanup(conn.close)
        conn.settimeout(9)
        start = time.monotonic()
        self.assertEqual(recv_frame(conn)['type'], 'PING')
        with self.assertRaises(EOFError):
            recv_frame(conn)
        elapsed = time.monotonic() - start
        self.assertGreaterEqual(elapsed, 5.5)
        self.assertLess(elapsed, 8)

    def test_full_timed_game(self):
        rooms = RoomManager()
        lock = threading.RLock()
        def on_message(conn_id, message):
            with lock:
                server.send_many(rooms.handle_message(conn_id, message))
        def on_disconnect(conn_id):
            with lock:
                server.send_many(rooms.on_disconnect(conn_id))
        server = TCPServer('127.0.0.1', 0, on_message, on_disconnect)
        server.start()
        self.addCleanup(server.close)
        white = TCPClient('127.0.0.1', server.port)
        black = TCPClient('127.0.0.1', server.port)
        self.addCleanup(white.close)
        self.addCleanup(black.close)
        def receive(client, count):
            messages = []
            deadline = time.monotonic() + 3
            while len(messages) < count and time.monotonic() < deadline:
                messages.extend(client.poll_messages())
                if len(messages) < count:
                    time.sleep(0.01)
            self.assertEqual(len(messages), count)
            return messages
        white.send({'type': 'CREATE_ROOM', 'minutes': 5})
        welcome = receive(white, 1)[0]
        self.assertEqual(welcome['color'], 'white')
        black.send({'type': 'JOIN_ROOM', 'room_code': welcome['room_code']})
        white_start = receive(white, 1)[0]
        black_welcome, black_start = receive(black, 2)
        self.assertEqual(black_welcome['color'], 'black')
        self.assertEqual(white_start, black_start)
        self.assertEqual(white_start['white_time'], 300)
        self.assertEqual(white_start['black_time'], 300)
        expected = {'fen', 'turn', 'revision', 'white_time', 'black_time', 'game_over', 'result', 'reason'}
        self.assertTrue(expected <= white_start.keys())
        for revision, (client, move) in enumerate(((white, 'f2f3'), (black, 'e7e5'), (white, 'g2g4'), (black, 'd8h4'))):
            client.send({'type': 'MOVE_REQUEST', 'uci': move, 'expected_revision': revision})
            white_move, black_move = receive(white, 1)[0], receive(black, 1)[0]
            self.assertEqual(white_move, black_move)
            self.assertTrue(expected <= white_move.keys())
            self.assertEqual(white_move['revision'], revision + 1)
        self.assertTrue(white_move['game_over'])
        self.assertEqual(white_move['result'], '0-1')
        self.assertEqual(white_move['reason'], 'Checkmate')

    def test_two_clients_and_disconnect(self):
        received, disconnected = queue.Queue(), queue.Queue()
        server = TCPServer('127.0.0.1', 0, lambda conn, msg: received.put((conn, msg)), disconnected.put)
        server.start()
        self.addCleanup(server.close)
        a = TCPClient('127.0.0.1', server.port)
        b = TCPClient('127.0.0.1', server.port)
        self.addCleanup(a.close)
        self.addCleanup(b.close)
        a.send({'who': 'a'})
        b.send({'who': 'b'})
        pairs = dict((msg['who'], conn) for conn, msg in (received.get(timeout=3), received.get(timeout=3)))
        self.assertNotEqual(pairs['a'], pairs['b'])
        server.send_many([(pairs['a'], {'reply': 'A'}), (pairs['b'], {'reply': 'B'})])
        def wait_message(client):
            deadline = time.monotonic() + 3
            while time.monotonic() < deadline:
                messages = client.poll_messages()
                if messages:
                    return messages
                time.sleep(0.01)
            self.fail('No message received')
        self.assertEqual(wait_message(a), [{'reply': 'A'}])
        self.assertEqual(wait_message(b), [{'reply': 'B'}])
        a.close()
        self.assertEqual(disconnected.get(timeout=3), pairs['a'])
        server.send(pairs['b'], {'reply': 'still connected'})
        self.assertEqual(wait_message(b), [{'reply': 'still connected'}])


if __name__ == '__main__':
    unittest.main()
