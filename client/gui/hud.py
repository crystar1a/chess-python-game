import math

import chess
import pygame

from client.gui.board_view import BOARD, BOARD_TOP, PLAYER_BAR_HEIGHT


def draw_players(screen, game, pieces, font, small, clock_font, difficulty, stopped=False):
    for name, side, top in (('Opponent', not game.player, 0),
                            ('You', game.player, BOARD_TOP + BOARD)):
        active = not stopped and game.board.turn == side
        bar = pygame.Rect(0, top, BOARD, PLAYER_BAR_HEIGHT)
        pygame.draw.rect(screen, (42, 46, 49), bar)

        avatar = pygame.Rect(9, top + 8, 40, 40)
        pygame.draw.rect(screen, (95, 118, 91), avatar, border_radius=5)
        icon = pieces[('w' if side == chess.WHITE else 'b') + 'k']
        screen.blit(pygame.transform.scale(icon, avatar.size), avatar)

        title = font.render(name, True, (241, 242, 235))
        screen.blit(title, (avatar.right + 10, top + 5))
        detail = 'White' if side == chess.WHITE else 'Black'
        if side != game.player:
            detail += ' · ' + difficulty
        screen.blit(small.render(detail, True, (181, 188, 179)), (avatar.right + 10, top + 29))

        clock = pygame.Rect(BOARD - 124, top + 8, 116, 40)
        pygame.draw.rect(screen, (218, 232, 207) if active else (56, 62, 65), clock, border_radius=5)
        time_text = '--:--'
        if game.remaining is not None:
            seconds = math.ceil(game.remaining[side])
            time_text = f'{seconds // 60:02}:{seconds % 60:02}'
        text = clock_font.render(time_text, True, (38, 49, 38) if active else (192, 199, 193))
        screen.blit(text, text.get_rect(center=clock.center))
        if active:
            status = small.render('YOUR TURN' if side == game.player else 'THINKING', True, (179, 211, 158))
            screen.blit(status, status.get_rect(midright=(clock.left - 12, bar.centery)))
