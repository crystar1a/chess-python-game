import socket
import struct
import threading
import unittest

from shared.protocol import MAX_FRAME, MessageType, encode_frame, make_message, recv_exact, recv_frame


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


if __name__ == '__main__':
    unittest.main()
