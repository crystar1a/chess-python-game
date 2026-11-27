import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from client.net.server_config import load_address, save_address, parse_address


class ServerConfigTests(unittest.TestCase):
    def test_parse_address_and_invalid_port(self):
        self.assertEqual(parse_address(' 100.98.142.73 '), ('100.98.142.73', 8765))
        self.assertEqual(parse_address('server.local:9000'), ('server.local', 9000))
        for value in ('', ':123', 'host:', 'host:0', 'host:65536', 'bad host'):
            with self.subTest(value=value), self.assertRaises(ValueError):
                parse_address(value)

    def test_address_persists(self):
        with tempfile.TemporaryDirectory(dir='.') as tmp, patch('client.net.server_config.CONFIG_PATH', Path(tmp) / 'address'):
            self.assertEqual(load_address(), '127.0.0.1:8765')
            save_address('server.local:9000')
            self.assertEqual(load_address(), 'server.local:9000')
