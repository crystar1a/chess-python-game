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

    def test_move_history_and_last_move_recorded(self):
        game = Game(chess.WHITE, None)
        game.move(chess.Move.from_uci('e2e4'))
        game.move(chess.Move.from_uci('e7e5'))
        self.assertEqual(game.move_history, ['e4', 'e5'])
        self.assertEqual(game.last_move, chess.Move.from_uci('e7e5'))

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

    def test_promotion_queen(self):
        game = Game(chess.WHITE, None)
        game.board = chess.Board('8/4P3/8/8/8/8/8/8 w - - 0 1')
        move = chess.Move(chess.E7, chess.E8, promotion=chess.QUEEN)
        self.assertIn(move, game.board.legal_moves)
        sound = game.move(move)
        self.assertEqual(sound, 'promote')
        self.assertEqual(game.board.piece_at(chess.E8).piece_type, chess.QUEEN)
        self.assertEqual(game.board.piece_at(chess.E8).color, chess.WHITE)
        self.assertIsNone(game.board.piece_at(chess.E7))

    def test_promotion_all_four_choices(self):
        for promo in (chess.QUEEN, chess.ROOK, chess.BISHOP, chess.KNIGHT):
            with self.subTest(promotion=promo):
                game = Game(chess.WHITE, None)
                game.board = chess.Board('8/4P3/8/8/8/8/8/8 w - - 0 1')
                move = chess.Move(chess.E7, chess.E8, promotion=promo)
                sound = game.move(move)
                self.assertEqual(sound, 'promote')
                self.assertEqual(game.board.piece_at(chess.E8).piece_type, promo)


if __name__ == '__main__':
    unittest.main()
