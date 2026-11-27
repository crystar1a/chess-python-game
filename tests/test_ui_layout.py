import unittest
from unittest.mock import patch

import pygame
import chess
from types import SimpleNamespace

from client.gui import theme
from client.gui.screens import draw_online_menu_screen, draw_resign_confirmation, draw_game_sidebar, draw_room_list_screen, draw_server_screen
from client.gui.board_view import draw_board, square_pos
from client.game.local_board import Game
from client.gui.layout import (
    MIN_HEIGHT,
    MIN_WIDTH,
    clamp_window_size,
    compute_game_layout,
    compute_lobby_layout,
)


class LayoutTests(unittest.TestCase):
    def test_chat_panel_swaps_move_list_and_locks_send_while_offline(self):
        pygame.font.init()
        surface = pygame.Surface((960, 680))
        lay = compute_game_layout(960, 680)
        fonts = theme.get_fonts(lay['scale'])
        controller = SimpleNamespace(game=Game(chess.WHITE, None), mode='online', error=None)
        args = (surface, lay['sidebar'], fonts, controller, 'ABC123', 'Normal', None, 0, (0, 0), False)
        moves = draw_game_sidebar(*args)
        chat = draw_game_sidebar(*args, chat_open=True, chat_text='Xin chào')
        offline = draw_game_sidebar(*args, chat_open=True, chat_text='Xin chào', disconnected=True)
        self.assertIn('chat_toggle', moves)
        self.assertNotIn('chat_input', moves)
        self.assertIn('chat_input', chat)
        self.assertIn('chat_send', chat)
        self.assertNotIn('resign', offline)
    def test_room_list_and_server_address_controls_fit(self):
        pygame.font.init()
        surface = pygame.Surface((720, 560))
        lay = compute_lobby_layout(720, 560)
        fonts = theme.get_fonts(lay['scale'])
        server = draw_server_screen(surface, lay, fonts, '127.0.0.1:8765', None, 0, (0, 0), False)
        rooms = [{'room_code': 'ABC123', 'host': 'Alice', 'minutes': 5}]
        listing = draw_room_list_screen(surface, lay, fonts, rooms, 0, None, (0, 0), False)
        self.assertTrue(surface.get_rect().contains(server['box']))
        self.assertEqual(listing['rooms'][0][0], 'ABC123')
        self.assertTrue(surface.get_rect().contains(listing['rooms'][0][1]))

    def test_waiting_status_displays_copy_notice_then_default(self):
        pygame.font.init()
        surface = pygame.Surface((960, 680))
        lay = compute_game_layout(960, 680)
        fonts = theme.get_fonts(lay['scale'])
        controller = SimpleNamespace(game=Game(chess.WHITE, None), mode='online', error=None)
        for notice, expected in (('Đã sao chép mã phòng', 'Đã sao chép mã phòng'), (None, 'Đang chờ đối thủ tham gia')):
            with self.subTest(notice=notice), patch('client.gui.screens._draw_centered', wraps=__import__('client.gui.screens', fromlist=['_draw_centered'])._draw_centered) as draw:
                draw_game_sidebar(surface, lay['sidebar'], fonts, controller, 'ABC123', 'Normal', notice, 0, (0, 0), False, waiting=True)
                status_call = next(call for call in draw.call_args_list if call.args[1] == expected)
                self.assertEqual(status_call.kwargs['color'], theme.TEXT_PRIMARY)

    def test_waiting_board_hides_opponent_and_offers_only_leave(self):
        pygame.font.init()
        surface = pygame.Surface((960, 680))
        game = Game(chess.WHITE, None)
        pieces = {}
        for color in 'wb':
            for piece in 'pnbrqk':
                image = pygame.Surface((40, 40))
                image.fill((250, 10, 10) if color == 'w' else (10, 10, 250))
                pieces[color + piece] = image
        draw_board(surface, game, None, pieces, only_color=chess.WHITE, board_origin=(0, 0), square_size=40)
        wx, wy = square_pos(chess.A1, chess.WHITE, (0, 0), 40)
        bx, by = square_pos(chess.A8, chess.WHITE, (0, 0), 40)
        self.assertEqual(surface.get_at((wx + 20, wy + 20))[:3], (250, 10, 10))
        self.assertNotEqual(surface.get_at((bx + 20, by + 20))[:3], (10, 10, 250))
        lay = compute_game_layout(960, 680)
        fonts = theme.get_fonts(lay['scale'])
        controller = SimpleNamespace(game=game, mode='online', error=None)
        hits = draw_game_sidebar(surface, lay['sidebar'], fonts, controller, 'ABC123', 'Normal', None, 0, (0, 0), False, waiting=True)
        self.assertIn('cancel', hits)
        self.assertNotIn('resign', hits)
        self.assertNotIn('online_rematch', hits)

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
