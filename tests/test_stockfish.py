import os
import sys
import unittest
from pathlib import Path
from urllib.parse import parse_qs, urlsplit
from unittest.mock import patch

import chess

from client.ai.stockfish import Engine, engine_path
from client.game.game_controller import Controller


class StockfishTests(unittest.TestCase):
    def test_bundled_engine_path(self):
        executable = {
            'win32': 'stockfish-windows-x86-64-universal.exe',
            'linux': 'stockfish-linux-x86-64-universal',
        }.get(sys.platform, 'stockfish')
        expected = Path(__file__).resolve().parents[1] / 'client' / 'ai' / 'stockfish' / executable
        with patch.dict(os.environ, {'STOCKFISH_PATH': 'custom-engine'}):
            self.assertEqual(engine_path(), str(expected))

    @patch('client.ai.stockfish.engine_path', return_value=__file__)
    def test_each_difficulty_configures_engine(self, _path):
        for difficulty, depth in [('Easy', 3), ('Normal', 8), ('Hard', 15)]:
            with self.subTest(difficulty=difficulty), patch('client.ai.stockfish.chess.engine.SimpleEngine.popen_uci') as open_engine:
                engine = Engine(difficulty)
                engine.start(chess.Board())
                engine.thread.join(5)
                self.assertFalse(engine.thread.is_alive())
                open_engine.return_value.play.assert_called_once_with(chess.Board(), chess.engine.Limit(depth=depth))
                open_engine.return_value.quit.assert_called_once()

    @patch('client.ai.stockfish.engine_path', return_value=__file__)
    def test_local_launch_error(self, _path):
        with patch('client.ai.stockfish.chess.engine.SimpleEngine.popen_uci', side_effect=OSError('missing')):
            engine = Engine()
            engine.start(chess.Board())
            engine.thread.join(5)
            self.assertEqual(engine.results.get_nowait()[2], 'missing')

    @patch('client.ai.stockfish.engine_path', return_value='missing-engine')
    @patch('client.ai.stockfish.urlopen')
    def test_rest_fallback(self, http, _path):
        from io import BytesIO

        with patch('client.ai.stockfish.API_KEY_FILE') as key_file:
            for difficulty, depth, key in [('Easy', 3, ''), ('Normal', 8, 'test-key'), ('Hard', 15, '')]:
                key_file.read_text.return_value = key
                http.return_value = BytesIO(b'{"success":true,"bestmove":"bestmove e2e4 ponder e7e5"}')
                engine = Engine(difficulty)
                board = chess.Board()
                engine.start(board)
                engine.thread.join(5)
                self.assertEqual(engine.results.get_nowait(), (board.fen(), chess.Move.from_uci('e2e4'), None))
                request = http.call_args.args[0]
                self.assertEqual(parse_qs(urlsplit(request.full_url).query)['depth'], [str(depth)])
                self.assertEqual(parse_qs(urlsplit(request.full_url).query).get('key'), [key] if key else None)

    def test_stale_engine_move_is_rejected(self):
        controller = Controller(chess.BLACK, None)
        controller.thinking = True
        controller.engine.results.put(('old position', chess.Move.from_uci('e2e4'), None))
        controller.update()
        self.assertEqual(len(controller.game.board.move_stack), 0)
        self.assertIsNotNone(controller.error)
        controller.close()


if __name__ == '__main__':
    unittest.main()
