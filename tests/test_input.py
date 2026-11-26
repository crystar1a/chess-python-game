import unittest

import chess

from client.game.game_controller import Controller
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
        controller = Controller(chess.WHITE, None, mode='local')
        pos = square_pos(chess.E2, controller.game.player)
        selected, _, _ = select_square(pos, controller, None)
        self.assertEqual(selected, chess.E2)
        self.assertEqual(select_square(pos, controller, selected), (None, None, None))
        self.assertFalse(controller.game.board.move_stack)

    def test_select_and_move(self):
        controller = Controller(chess.WHITE, None, mode='local')
        selected, promotion, sound = select_square(square_pos(chess.E2, controller.game.player), controller, None)
        self.assertEqual(selected, chess.E2)
        selected, promotion, sound = select_square(square_pos(chess.E4, controller.game.player), controller, selected)
        self.assertIsNone(selected)
        self.assertIsNone(promotion)
        self.assertEqual(sound, 'move-self')
        self.assertEqual(controller.game.board.peek(), chess.Move.from_uci('e2e4'))

    def test_select_square_detects_promotion(self):
        controller = Controller(chess.WHITE, None, mode='local')
        controller.game.board = chess.Board('8/4P3/8/8/8/8/8/8 w - - 0 1')
        # Select pawn on E7
        selected, promotion, sound = select_square(square_pos(chess.E7, controller.game.player), controller, None)
        self.assertEqual(selected, chess.E7)
        self.assertIsNone(promotion)
        self.assertIsNone(sound)
        # Click E8 (promotion square)
        selected, promotion, sound = select_square(square_pos(chess.E8, controller.game.player), controller, selected)
        self.assertEqual(selected, chess.E7)
        self.assertEqual(promotion, (chess.E7, chess.E8))
        self.assertIsNone(sound)
