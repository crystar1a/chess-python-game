import tempfile
import unittest
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from server.auth import AuthService, UserStore
from server.rooms import RoomManager
from shared.protocol import MessageType, make_message
from client.net.tcp_client import TCPClient
from unittest.mock import patch, MagicMock


class AuthTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.path = Path(self.tmp.name) / 'users.db'
        self.store = UserStore(self.path)
        self.addCleanup(self.store.close)
        self.auth = AuthService(self.store)

    def test_register_login_and_guest(self):
        self.assertEqual(self.auth.check_guest(' AlIce ')['status'], 'ok')
        self.assertEqual(self.auth.submit_login_or_probe('Alice', 'pass')['status'], 'needs_register')
        result = self.auth.register(' Alice ', 'pass')
        self.assertEqual(result['username'], 'Alice')
        self.assertEqual(self.auth.verify_token(result['token']), 'Alice')
        self.assertEqual(self.auth.check_guest('alice')['status'], 'username_registered')
        self.assertEqual(self.auth.submit_login_or_probe('ALICE', 'wrong')['status'], 'invalid_credentials')
        self.assertEqual(self.auth.submit_login_or_probe('alice', 'pass')['username'], 'Alice')
        self.assertNotEqual(self.store.db.execute('SELECT password_hash FROM users').fetchone()[0], 'pass')

    def test_invalid_and_concurrent_registration(self):
        self.assertEqual(self.auth.check_guest('a!')['status'], 'invalid_username')
        self.assertEqual(self.auth.register('Alice', 'abc')['status'], 'invalid_password')
        with ThreadPoolExecutor(max_workers=2) as pool:
            statuses = list(pool.map(lambda n: self.auth.register(n, 'pass')['status'], ['Alice', 'ALICE']))
        self.assertCountEqual(statuses, ['ok', 'username_registered'])
        self.assertIsNone(self.auth.verify_token('bad'))

    def test_room_auth_and_names(self):
        rooms = RoomManager(self.auth)
        def send(conn, kind, **fields):
            return rooms.handle_message(conn, make_message(kind, **fields))
        self.assertEqual(send('a', MessageType.AUTH_GUEST, username='Alice')[0][1]['type'], 'AUTH_OK')
        self.assertEqual(send('b', MessageType.AUTH_GUEST, username='Bob')[0][1]['type'], 'AUTH_OK')
        self.assertEqual(send('x', MessageType.AUTH_TOKEN, token=[])[0][1]['reason'], 'invalid_token')
        code = send('a', MessageType.CREATE_ROOM)[0][1]['room_code']
        start = send('b', MessageType.JOIN_ROOM, room_code=code)[0][1]
        self.assertEqual((start['white_name'], start['black_name']), ('Alice', 'Bob'))
        rooms.on_disconnect('a')
        self.assertNotIn('a', rooms._conn_to_user)

    def test_malformed_auth_does_not_keep_prior_identity(self):
        rooms = RoomManager(self.auth)
        rooms.handle_message('a', {'type': 'AUTH_GUEST', 'username': 'Alice'})
        reply = rooms.handle_message('a', {'type': 'AUTH_SUBMIT', 'username': [], 'password': None})[0][1]
        self.assertEqual(reply['reason'], 'invalid_username')
        self.assertNotIn('a', rooms._conn_to_user)

    def test_tcp_timeout_reset(self):
        sock = MagicMock()
        with patch('client.net.tcp_client.socket.create_connection', return_value=sock) as connect, patch('client.net.tcp_client.threading.Thread'):
            TCPClient('host', 123, timeout=1.5)
        connect.assert_called_once_with(('host', 123), timeout=1.5)
        sock.settimeout.assert_called_once_with(None)
