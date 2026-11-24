import chess
import pygame

SIZE = 72
BOARD = SIZE * 8
PLAYER_BAR_HEIGHT = 56
BOARD_TOP = PLAYER_BAR_HEIGHT


def square_pos(square, player):
    file, rank = chess.square_file(square), chess.square_rank(square)
    return ((file if player == chess.WHITE else 7 - file) * SIZE,
            BOARD_TOP + (7 - rank if player == chess.WHITE else rank) * SIZE)


def draw_board(screen, game, selected, pieces):
    for row in range(8):
        for col in range(8):
            shade = 180 if (row + col) % 2 == 0 else 124
            pygame.draw.rect(screen, (shade, shade, shade), (col * SIZE, BOARD_TOP + row * SIZE, SIZE, SIZE))
    if selected is not None:
        pygame.draw.rect(screen, (225, 190, 65), (*square_pos(selected, game.player), SIZE, SIZE), 5)
        for move in game.board.legal_moves:
            if move.from_square == selected:
                x, y = square_pos(move.to_square, game.player)
                pygame.draw.circle(screen, (85, 105, 80), (x + SIZE // 2, y + SIZE // 2), 8)
    for square, piece in game.board.piece_map().items():
        screen.blit(pieces[('w' if piece.color else 'b') + piece.symbol().lower()], square_pos(square, game.player))
