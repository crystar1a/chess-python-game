import unittest

import chess

from client.game.local_board import Game
from client.gui.board_view import SIZE, square_pos
from client.input.mouse_controller import select_square, square_at


class MouseTests(unittest.TestCase):
    def test_corners_match_both_orientations(self):
        for player in (chess.WHITE, chess.BLACK):
            for square in (chess.A1, chess.A8, chess.H1, chess.H8):
                x, y = square_pos(square, player)
                self.assertEqual(square_at((x + SIZE // 2, y + SIZE // 2), player), square)
        self.assertIsNone(square_at((-1, 0), chess.WHITE))

    def test_click_selected_piece_to_deselect(self):
        game = Game(chess.WHITE, None)
        pos = square_pos(chess.E2, game.player)
        selected, _, _ = select_square(pos, game, None)
        self.assertEqual(selected, chess.E2)
        self.assertEqual(select_square(pos, game, selected), (None, None, None))
        self.assertFalse(game.board.move_stack)

    def test_select_and_move(self):
        game = Game(chess.WHITE, None)
        selected, promotion, sound = select_square(square_pos(chess.E2, game.player), game, None)
        self.assertEqual(selected, chess.E2)
        selected, promotion, sound = select_square(square_pos(chess.E4, game.player), game, selected)
        self.assertIsNone(selected)
        self.assertIsNone(promotion)
        self.assertEqual(sound, 'move-self')
        self.assertEqual(game.board.peek(), chess.Move.from_uci('e2e4'))
