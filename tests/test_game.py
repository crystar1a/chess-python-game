import unittest
from unittest.mock import patch

import chess

from client.game.local_board import Game


class GameTests(unittest.TestCase):
    def test_legal_and_illegal_moves(self):
        game = Game(chess.WHITE, None)
        self.assertIsNone(game.move(chess.Move.from_uci('e2e5')))
        self.assertEqual(game.move(chess.Move.from_uci('e2e4')), 'move-self')
        self.assertEqual(game.board.turn, chess.BLACK)

    def test_clocks_switch_and_expire(self):
        with patch('client.game.local_board.time.monotonic', return_value=0) as clock:
            game = Game(chess.WHITE, 5)
            clock.return_value = 10
            game.move(chess.Move.from_uci('e2e4'))
            clock.return_value = 20
            game.tick()
            self.assertEqual(game.remaining[chess.WHITE], 290)
            self.assertEqual(game.remaining[chess.BLACK], 290)
            clock.return_value = 311
            game.tick()
            self.assertEqual(game.result, 'White wins on time')

    def test_insufficient_material_on_timeout(self):
        with patch('client.game.local_board.time.monotonic', return_value=0) as clock:
            game = Game(chess.WHITE, 5)
            game.board = chess.Board('8/8/8/8/8/8/4k3/4K3 w - - 0 1')
            clock.return_value = 301
            game.tick()
            self.assertIn('Draw', game.result)

    def test_timeout_draw_king_plus_knight_vs_king(self):
        with patch('client.game.local_board.time.monotonic', return_value=0) as clock:
            game = Game(chess.WHITE, 5)
            game.board = chess.Board('8/8/8/8/8/8/4n3/4K3 w - - 0 1')
            clock.return_value = 301
            game.tick()
            self.assertIn('Draw', game.result)

    def test_timeout_draw_king_plus_bishop_vs_king(self):
        with patch('client.game.local_board.time.monotonic', return_value=0) as clock:
            game = Game(chess.WHITE, 5)
            game.board = chess.Board('8/8/8/8/8/8/4b3/4K3 w - - 0 1')
            clock.return_value = 301
            game.tick()
            self.assertIn('Draw', game.result)

    def test_timeout_win_when_opponent_can_mate(self):
        with patch('client.game.local_board.time.monotonic', return_value=0) as clock:
            game = Game(chess.BLACK, 5)
            game.board = chess.Board('8/8/8/8/8/8/4Q3/4k3 b - - 0 1')
            clock.return_value = 301
            game.tick()
            self.assertEqual(game.result, 'White wins on time')


if __name__ == '__main__':
    unittest.main()
