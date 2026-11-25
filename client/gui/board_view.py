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


def promotion_rects(to_square, player, screen_width, screen_height):
    x, y = square_pos(to_square, player)
    arrow_x = x + SIZE // 2  # tâm ô tốt = nơi mũi tên trỏ
    bubble_w, bubble_h = 180, 62
    bx = arrow_x - bubble_w // 2
    if bx < 0:
        bx = 0
    if bx + bubble_w > screen_width:
        bx = screen_width - bubble_w
    by = y + SIZE  # bubble directly below the pawn square
    if by + bubble_h > screen_height:
        by = screen_height - bubble_h - 6
    bubble = pygame.Rect(bx, by, bubble_w, bubble_h)

    icon_w = min(bubble_w // 5, bubble_h - 16)
    icon_h = icon_w
    gap = max(4, bubble_w // 40)
    total_w = 4 * icon_w + 3 * gap
    start_x = bx + (bubble_w - total_w) // 2
    start_y = by + (bubble_h - icon_h) // 2
    rects = [pygame.Rect(start_x + i * (icon_w + gap), start_y, icon_w, icon_h) for i in range(4)]
    return bubble, rects, arrow_x


def draw_promotion_bubble(screen, bubble, rects, pieces, player, arrow_x, hovered):
    pygame.draw.rect(screen, (42, 46, 49), bubble, border_radius=8)
    pygame.draw.rect(screen, (190, 211, 183), bubble, width=2, border_radius=8)
    pygame.draw.polygon(screen, (42, 46, 49), [(arrow_x - 6, bubble.top), (arrow_x + 6, bubble.top), (arrow_x, bubble.top - 10)])
    icons = [chess.ROOK, chess.KNIGHT, chess.BISHOP, chess.QUEEN]
    for i, rect in enumerate(rects):
        piece = chess.Piece(icons[i], player)
        key = ('w' if piece.color else 'b') + piece.symbol().lower()
        if rect.collidepoint(hovered):
            size = min(rect.w + 4, bubble.w // 4)
            icon = pygame.transform.scale(pieces[key], (size, size))
            icon_rect = icon.get_rect(center=rect.center)
            screen.blit(icon, icon_rect)
            pygame.draw.rect(screen, (190, 211, 183), rect, width=2, border_radius=4)
        else:
            icon = pygame.transform.scale(pieces[key], rect.size)
            screen.blit(icon, rect)


def draw_board(screen, game, selected, pieces, only_color=None):
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
        if only_color is not None and piece.color != only_color:
            continue
        screen.blit(pieces[('w' if piece.color else 'b') + piece.symbol().lower()], square_pos(square, game.player))
