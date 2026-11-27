import unittest
import tempfile
import threading
import time
from pathlib import Path
from unittest.mock import patch

from server.rooms import RoomManager
from client.net.session_store import save_session, load_session, delete_session, room_request
from client.net.tcp_client import TCPClient
from server.net.tcp_server import TCPServer


class ReconnectTests(unittest.TestCase):
    def test_room_request_uses_resume_only_when_session_exists(self):
        with patch('client.net.session_store.load_session', return_value={'token': 'secret'}):
            self.assertEqual(room_request('Alice', ' abc123 '), {'type': 'RESUME', 'token': 'secret'})
        with patch('client.net.session_store.load_session', return_value=None):
            self.assertEqual(room_request('Alice', ' abc123 '), {'type': 'JOIN_ROOM', 'room_code': 'ABC123'})

    def setUp(self):
        self.rooms = RoomManager()
        self.white = self.rooms.handle_message('white', {'type': 'CREATE_ROOM'})[0][1]
        joined = self.rooms.handle_message('black', {'type': 'JOIN_ROOM', 'room_code': self.white['room_code']})
        self.black = next(msg for conn, msg in joined if conn == 'black' and msg['type'] == 'WELCOME')

    def test_tokens_are_per_player_and_resume_restores_snapshot(self):
        self.assertNotEqual(self.white['token'], self.black['token'])
        self.rooms.handle_message('white', {'type': 'MOVE_REQUEST', 'uci': 'e2e4', 'expected_revision': 0})
        self.rooms.on_disconnect('black')
        response = self.rooms.handle_message('new_black', {'type': 'RESUME', 'token': self.black['token']})
        snapshot = next(msg for conn, msg in response if conn == 'new_black' and msg['type'] == 'GAME_START')
        self.assertEqual(snapshot['revision'], 1)
        self.assertEqual(snapshot['moves'], ['e2e4'])
        self.assertEqual(snapshot['color'], 'black')

    def test_expired_session_receives_finished_game(self):
        with patch('server.rooms.time.monotonic', return_value=100) as clock:
            self.rooms.on_disconnect('black')
            clock.return_value = 161
            self.rooms.check_timeouts()
            result = self.rooms.handle_message('new_black', {'type': 'RESUME', 'token': self.black['token']})
            snapshot = next(msg for conn, msg in result if conn == 'new_black' and msg['type'] == 'GAME_START')
            self.assertTrue(snapshot['game_over'])
            self.assertEqual(snapshot['result'], '1-0')
            self.assertEqual(snapshot['reason'], 'Disconnected')

    def test_late_resume_finishes_game_even_before_timeout_poll(self):
        with patch('server.rooms.time.monotonic', return_value=100) as clock:
            self.rooms.on_disconnect('black')
            clock.return_value = 161
            deliveries = self.rooms.handle_message('new_black', {'type': 'RESUME', 'token': self.black['token']})
            snapshot = next(msg for conn, msg in deliveries if conn == 'new_black' and msg['type'] == 'GAME_START')
            self.assertEqual(snapshot['result'], '1-0')
            self.assertTrue(any(conn == 'white' and msg.get('game_over') for conn, msg in deliveries))

    def test_room_cannot_be_joined_as_new_player_after_disconnect(self):
        self.rooms.on_disconnect('black')
        result = self.rooms.handle_message('intruder', {'type': 'JOIN_ROOM', 'room_code': self.white['room_code']})
        self.assertEqual(result[0][1]['reason'], 'room_full')

    def test_resign_rejected_while_opponent_disconnected(self):
        self.rooms.on_disconnect('black')
        result = self.rooms.handle_message('white', {'type': 'RESIGN'})
        self.assertEqual(result[0][1]['type'], 'MOVE_REJECTED')
        self.assertEqual(result[0][1]['reason'], 'opponent_disconnected')
        self.assertIsNone(self.rooms._rooms[self.white['room_code']]['match'].result)

    @unittest.skipUnless(__import__('os').name == 'nt', 'Windows DPAPI')
    def test_session_storage_is_protected_and_can_be_reloaded(self):
        with tempfile.TemporaryDirectory(dir='.') as tmp, patch('client.net.session_store.SESSION_DIR', Path(tmp)):
            save_session('Alice', 'ABC123', 'secret-token', 'white')
            self.assertNotIn(b'secret-token', next(Path(tmp).glob('*.bin')).read_bytes())
            self.assertEqual(load_session('Alice', 'ABC123')['token'], 'secret-token')
            self.assertIsNone(load_session('Bob', 'ABC123'))
            delete_session('Alice', 'ABC123')
            self.assertIsNone(load_session('Alice', 'ABC123'))

    def test_tcp_disconnect_and_resume_game(self):
        rooms = RoomManager()
        lock = threading.RLock()
        def on_message(conn, msg):
            with lock:
                server.send_many(rooms.handle_message(conn, msg))
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
            end = time.monotonic() + 3
            while time.monotonic() < end:
                for message in client.poll_messages():
                    if message['type'] == kind:
                        return message
                time.sleep(0.01)
            self.fail('Missing ' + kind)
        white.send({'type': 'CREATE_ROOM'})
        welcome = receive(white, 'WELCOME')
        black.send({'type': 'JOIN_ROOM', 'room_code': welcome['room_code']})
        receive(black, 'WELCOME')
        receive(white, 'GAME_START')
        white.send({'type': 'MOVE_REQUEST', 'uci': 'e2e4', 'expected_revision': 0})
        receive(white, 'MOVE_ACCEPTED')
        white.close()
        receive(black, 'ROOM_STATE')
        restored = TCPClient('127.0.0.1', server.port)
        self.addCleanup(restored.close)
        restored.send({'type': 'RESUME', 'token': welcome['token']})
        snapshot = receive(restored, 'GAME_START')
        self.assertEqual(snapshot['color'], 'white')
        self.assertEqual(snapshot['moves'], ['e2e4'])
        self.assertEqual(snapshot['revision'], 1)

    def test_tcp_automatically_reconnects_and_restores_opponent_move(self):
        rooms = RoomManager()
        lock = threading.RLock()
        def on_message(conn, msg):
            with lock:
                server.send_many(rooms.handle_message(conn, msg))
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
        def receive(client, kind, timeout=6):
            end = time.monotonic() + timeout
            while time.monotonic() < end:
                for message in client.poll_messages():
                    if message['type'] == kind:
                        return message
                time.sleep(0.01)
            self.fail('Missing ' + kind)
        white.send({'type': 'CREATE_ROOM'})
        welcome = receive(white, 'WELCOME')
        white.enable_reconnect(welcome['token'])
        black.send({'type': 'JOIN_ROOM', 'room_code': welcome['room_code']})
        receive(white, 'GAME_START')
        white.send({'type': 'MOVE_REQUEST', 'uci': 'e2e4', 'expected_revision': 0})
        receive(white, 'MOVE_ACCEPTED')
        with lock:
            conn_id = rooms._rooms[welcome['room_code']]['white_conn']
            server.connections[conn_id].shutdown(__import__('socket').SHUT_RDWR)
        receive(white, 'RECONNECTING')
        receive(black, 'ROOM_STATE')
        black.send({'type': 'MOVE_REQUEST', 'uci': 'e7e5', 'expected_revision': 1})
        receive(black, 'MOVE_ACCEPTED')
        snapshot = receive(white, 'GAME_START')
        self.assertEqual(snapshot['color'], 'white')
        self.assertEqual(snapshot['revision'], 2)
        self.assertEqual(snapshot['moves'], ['e2e4', 'e7e5'])
