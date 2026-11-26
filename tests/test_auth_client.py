import unittest
from unittest.mock import patch

from client.net.auth_client import exchange
from server.auth import AuthService, UserStore
from server.rooms import RoomManager
from server.net.tcp_server import TCPServer


class AuthClientTests(unittest.TestCase):
    def test_authenticate_again_on_a_new_connection(self):
        store = UserStore(':memory:')
        rooms = RoomManager(AuthService(store))
        server = TCPServer('127.0.0.1', 0, lambda cid, msg: server.send_many(rooms.handle_message(cid, msg)), rooms.on_disconnect)
        server.start()
        try:
            response, client = exchange('127.0.0.1', server.port, {'type': 'AUTH_REGISTER', 'username': 'Alice', 'password': 'secret'})
            self.assertEqual(response['type'], 'AUTH_OK')
            client.close()
            response, client = exchange('127.0.0.1', server.port, {'type': 'AUTH_TOKEN', 'token': response['token']})
            self.assertEqual(response['username'], 'Alice')
            self.assertFalse(response['is_guest'])
            client.close()
        finally:
            server.close()
            store.close()

    def test_exchange_sends_request_and_returns_response(self):
        class Client:
            def __init__(self, *args, **kwargs): self.sent = []
            def send(self, message): self.sent.append(message)
            def poll_messages(self): return [{'type': 'AUTH_OK', 'username': 'Alice'}]
            def close(self): pass
        with patch('client.net.auth_client.TCPClient', Client):
            reply, client = exchange('host', 123, {'type': 'AUTH_GUEST'})
        self.assertEqual(reply['username'], 'Alice')
        self.assertEqual(client.sent, [{'type': 'AUTH_GUEST'}])

    def test_exchange_times_out_and_closes(self):
        class Client:
            closed = False
            def __init__(self, *args, **kwargs): pass
            def send(self, message): pass
            def poll_messages(self): return []
            def close(self): Client.closed = True
        with patch('client.net.auth_client.TCPClient', Client):
            with self.assertRaises(TimeoutError): exchange('host', 123, {}, deadline=0)
        self.assertTrue(Client.closed)
