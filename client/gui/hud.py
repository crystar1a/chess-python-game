import math

import chess
import pygame

from client.gui import theme
from client.gui.board_view import BOARD, BOARD_TOP, PLAYER_BAR_HEIGHT


def draw_players(
    screen,
    game,
    pieces,
    font,
    small,
    clock_font,
    difficulty,
    stopped=False,
    player_name='You',
    opponent_name='Opponent',
    board_rect=None,
    bar_height=PLAYER_BAR_HEIGHT,
):
    if board_rect is None:
        bx, bw = 0, BOARD
        top_y, bot_y = 0, BOARD_TOP + BOARD
    else:
        bx, bw = board_rect.x, board_rect.width
        top_y = board_rect.top - bar_height - 6
        bot_y = board_rect.bottom + 6

    for name, side, top in ((opponent_name, not game.player, top_y),
                            (player_name, game.player, bot_y)):
        active = not stopped and game.board.turn == side
        bar = pygame.Rect(bx, top, bw, bar_height)
        pygame.draw.rect(screen, theme.BG_CARD, bar, border_radius=5)
        pygame.draw.rect(screen, theme.BORDER_FOCUS if active else theme.BORDER, bar, width=1, border_radius=5)

        av_size = max(30, bar_height - 14)
        avatar = pygame.Rect(bx + 8, top + (bar_height - av_size) // 2, av_size, av_size)
        pygame.draw.rect(screen, theme.BG_SUBTLE, avatar, border_radius=4)
        icon = pieces[('w' if side == chess.WHITE else 'b') + 'k']
        screen.blit(pygame.transform.scale(icon, avatar.size), avatar)

        max_name_w = max(80, bw - 210)
        display_name = name
        while len(display_name) > 1 and font.size(display_name)[0] > max_name_w:
            display_name = display_name[:-1]
        title = font.render(display_name, True, theme.TEXT_PRIMARY)
        screen.blit(title, (avatar.right + 10, top + 5))

        detail = 'Trắng' if side == chess.WHITE else 'Đen'
        if side != game.player:
            detail += ' · ' + difficulty
        screen.blit(small.render(detail, True, theme.TEXT_MUTED), (avatar.right + 10, top + bar_height - 22))

        clock_w = min(116, max(84, bw // 5))
        clock = pygame.Rect(bar.right - clock_w - 8, top + 7, clock_w, bar_height - 14)
        pygame.draw.rect(screen, theme.BTN_PRIMARY if active else theme.BG_INPUT, clock, border_radius=4)
        time_text = '--:--'
        if game.remaining is not None:
            seconds = math.ceil(game.remaining[side])
            time_text = f'{seconds // 60:02}:{seconds % 60:02}'
        text = clock_font.render(time_text, True, theme.TEXT_DARK if active else theme.TEXT_MUTED)
        screen.blit(text, text.get_rect(center=clock.center))
        if active:
            status_txt = 'LƯỢT BẠN' if side == game.player else 'ĐỐI THỦ'
            status = small.render(status_txt, True, theme.BORDER_FOCUS)
            screen.blit(status, status.get_rect(midright=(clock.left - 10, bar.centery)))
