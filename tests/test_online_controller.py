import unittest
from unittest.mock import Mock, patch

import chess

from client.game.game_controller import Controller


class OnlineControllerTests(unittest.TestCase):
    def test_existing_ui_snapshot_and_callback(self):
        callback = Mock(spec=lambda uci: None)
        controller = Controller(chess.WHITE, 5, mode='online', on_online_move_intent=callback)
        controller.apply_server_snapshot(chess.STARTING_FEN, remaining=None, result=None)
        controller.apply_uci('e2e4')
        callback.assert_called_once_with('e2e4')
        self.assertIsNone(controller.game.remaining)
        controller.close()
    def test_snapshot_and_move_intent(self):
        callback = Mock()
        controller = Controller(chess.WHITE, None, mode='online', on_online_move_intent=callback)
        with patch('client.game.game_controller.time.monotonic', return_value=100):
            controller.apply_server_snapshot({'fen': chess.STARTING_FEN, 'revision': 4,
                'white_time': 280.0, 'black_time': 290.0, 'game_over': False,
                'result': None, 'reason': None})
        self.assertEqual(controller.revision, 4)
        self.assertEqual(controller.game.remaining, {chess.WHITE: 280.0, chess.BLACK: 290.0})
        controller.apply_uci('e2e4')
        callback.assert_called_once_with('e2e4', 4)
        self.assertEqual(controller.game.board.fen(), chess.STARTING_FEN)
        controller.close()

    def test_terminal_and_untimed_snapshot(self):
        controller = Controller(chess.WHITE, 5, mode='online')
        controller.apply_server_snapshot({'fen': chess.STARTING_FEN, 'revision': 8,
            'white_time': None, 'black_time': None, 'game_over': True,
            'result': '0-1', 'reason': 'Checkmate'})
        self.assertIsNone(controller.game.remaining)
        self.assertEqual(controller.game.result, '0-1 - Checkmate')
        controller.close()

    def test_online_clock_waits_for_authoritative_result(self):
        controller = Controller(chess.WHITE, None, mode='online')
        with patch('client.game.game_controller.time.monotonic', return_value=0):
            controller.apply_server_snapshot({'fen': chess.STARTING_FEN, 'revision': 0,
                'white_time': 1.0, 'black_time': 300.0, 'game_over': False,
                'result': None, 'reason': None})
        with patch('client.game.local_board.time.monotonic', return_value=2):
            controller.update()
        self.assertEqual(controller.game.remaining[chess.WHITE], 0)
        self.assertIsNone(controller.game.result)
        controller.close()
