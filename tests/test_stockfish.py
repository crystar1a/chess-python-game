import os
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

import chess

from client.ai.stockfish import Engine, SKILL_LEVELS, engine_path
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

    def test_each_difficulty_configures_engine(self):
        for difficulty, skill in SKILL_LEVELS.items():
            with self.subTest(difficulty=difficulty), patch('client.ai.stockfish.chess.engine.SimpleEngine.popen_uci') as open_engine:
                engine = Engine(difficulty)
                engine.start(chess.Board())
                engine.thread.join(5)
                self.assertFalse(engine.thread.is_alive())
                open_engine.return_value.configure.assert_called_once_with({'Skill Level': skill})
                open_engine.return_value.quit.assert_called_once()

    def test_missing_engine_reports_error(self):
        with patch('client.ai.stockfish.chess.engine.SimpleEngine.popen_uci', side_effect=OSError('missing')):
            engine = Engine()
            engine.start(chess.Board())
            engine.thread.join(5)
            self.assertEqual(engine.results.get_nowait()[2], 'missing')

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
