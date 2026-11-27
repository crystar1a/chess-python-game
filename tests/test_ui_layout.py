import unittest

import pygame

from client.gui import theme
from client.gui.screens import draw_online_menu_screen, draw_resign_confirmation
from client.gui.layout import (
    MIN_HEIGHT,
    MIN_WIDTH,
    clamp_window_size,
    compute_game_layout,
    compute_lobby_layout,
)


class LayoutTests(unittest.TestCase):
    def test_resign_confirmation_has_separate_buttons(self):
        pygame.font.init()
        surface = pygame.Surface((960, 680))
        fonts = theme.get_fonts(compute_lobby_layout(960, 680)['scale'])
        hits = draw_resign_confirmation(surface, fonts, (0, 0), False)
        self.assertFalse(hits['resign_confirm'].colliderect(hits['resign_cancel']))
        self.assertTrue(surface.get_rect().contains(hits['resign_confirm']))
        self.assertTrue(surface.get_rect().contains(hits['resign_cancel']))

    def test_online_time_options_only_during_room_creation(self):
        pygame.font.init()
        lay = compute_lobby_layout(960, 680)
        surface = pygame.Surface((960, 680))
        fonts = theme.get_fonts(lay['scale'])
        args = (surface, lay, fonts, 10, (5, 10, 15, None), None, (0, 0), False)
        menu = draw_online_menu_screen(*args)
        setup = draw_online_menu_screen(*args, creating=True)
        self.assertEqual(menu['minutes'], {})
        self.assertIn('join', menu)
        self.assertEqual(set(setup['minutes']), {5, 10, 15, None})
        self.assertNotIn('join', setup)

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
