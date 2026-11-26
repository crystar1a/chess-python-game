import unittest

from client.gui.layout import (
    MIN_HEIGHT,
    MIN_WIDTH,
    clamp_window_size,
    compute_game_layout,
    compute_lobby_layout,
)


class LayoutTests(unittest.TestCase):
    def test_clamp_enforces_minimum(self):
        self.assertEqual(clamp_window_size(400, 300), (MIN_WIDTH, MIN_HEIGHT))
        self.assertEqual(clamp_window_size(1200, 800), (1200, 800))

    def test_game_layout_keeps_board_square_and_equal_edges(self):
        for w, h in ((720, 560), (960, 680), (1440, 900)):
            lay = compute_game_layout(w, h)
            board = lay['board_rect']
            self.assertEqual(board.width, board.height)
            self.assertGreaterEqual(lay['square_size'], 44)
            self.assertEqual(lay['top_bar'].top, lay['sidebar'].top)
            self.assertEqual(lay['bottom_bar'].bottom, lay['sidebar'].bottom)

    def test_lobby_layout_centers_content_and_bottom_auth(self):
        lay = compute_lobby_layout(960, 680)
        self.assertEqual(lay['hero_card'].left, lay['auth_card'].left)
        self.assertEqual(lay['hero_card'].right, lay['auth_card'].right)
        self.assertLess(lay['hero_card'].bottom, lay['auth_card'].top)
