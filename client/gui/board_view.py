import chess
import pygame

from client.gui import theme

SIZE = 72
BOARD = SIZE * 8
PLAYER_BAR_HEIGHT = 56
BOARD_TOP = PLAYER_BAR_HEIGHT


def square_pos(square, player, board_origin=(0, BOARD_TOP), square_size=SIZE):
    file, rank = chess.square_file(square), chess.square_rank(square)
    ox, oy = board_origin
    return (
        ox + (file if player == chess.WHITE else 7 - file) * square_size,
        oy + (7 - rank if player == chess.WHITE else rank) * square_size,
    )


def promotion_rects(
    to_square,
    player,
    screen_width,
    screen_height,
    board_origin=(0, BOARD_TOP),
    square_size=SIZE,
):
    x, y = square_pos(to_square, player, board_origin, square_size)
    arrow_x = x + square_size // 2
    bubble_w, bubble_h = max(172, square_size * 3), max(58, int(square_size * 0.85))
    bx = max(8, min(arrow_x - bubble_w // 2, screen_width - bubble_w - 8))
    by = y + square_size
    if by + bubble_h > screen_height - 8:
        by = max(8, y - bubble_h - 6)
    bubble = pygame.Rect(bx, by, bubble_w, bubble_h)

    icon_w = min(bubble_w // 5, bubble_h - 14)
    gap = max(4, bubble_w // 40)
    total_w = 4 * icon_w + 3 * gap
    start_x = bx + (bubble_w - total_w) // 2
    start_y = by + (bubble_h - icon_w) // 2
    rects = [pygame.Rect(start_x + i * (icon_w + gap), start_y, icon_w, icon_w) for i in range(4)]
    return bubble, rects, arrow_x


def draw_promotion_bubble(screen, bubble, rects, pieces, player, arrow_x, hovered):
    pygame.draw.rect(screen, theme.BG_CARD, bubble, border_radius=6)
    pygame.draw.rect(screen, theme.BORDER_FOCUS, bubble, width=2, border_radius=6)
    icons = [chess.ROOK, chess.KNIGHT, chess.BISHOP, chess.QUEEN]
    for i, rect in enumerate(rects):
        piece = chess.Piece(icons[i], player)
        key = ('w' if piece.color else 'b') + piece.symbol().lower()
        if rect.collidepoint(hovered):
            pygame.draw.rect(screen, theme.BTN_SECONDARY_HOVER, rect.inflate(4, 4), border_radius=4)
            pygame.draw.rect(screen, theme.BORDER_FOCUS, rect.inflate(4, 4), width=1, border_radius=4)
        icon = pygame.transform.scale(pieces[key], rect.size)
        screen.blit(icon, rect)


def draw_board(
    screen,
    game,
    selected,
    pieces,
    only_color=None,
    board_origin=(0, BOARD_TOP),
    square_size=SIZE,
    last_move=None,
    hidden_square=None,
    anim_piece=None,
    drag_piece=None,
    fonts=None,
):
    ox, oy = board_origin
    last_squares = {last_move.from_square, last_move.to_square} if last_move else set()
    check_sq = game.board.king(game.board.turn) if game.board.is_check() else None

    for row in range(8):
        for col in range(8):
            is_light = (row + col) % 2 == 0
            file_idx = col if game.player == chess.WHITE else 7 - col
            rank_idx = (7 - row) if game.player == chess.WHITE else row
            sq = chess.square(file_idx, rank_idx)

            if sq in last_squares or sq == selected:
                color = theme.SQ_LAST_LIGHT if is_light else theme.SQ_LAST_DARK
            else:
                color = theme.SQ_LIGHT if is_light else theme.SQ_DARK

            rect = pygame.Rect(ox + col * square_size, oy + row * square_size, square_size, square_size)
            pygame.draw.rect(screen, color, rect)

            if sq == check_sq:
                overlay = pygame.Surface((square_size, square_size), pygame.SRCALPHA)
                overlay.fill((*theme.SQ_CHECK, 165))
                screen.blit(overlay, rect.topleft)

            if fonts:
                coord_color = theme.SQ_DARK if is_light else theme.SQ_LIGHT
                coord_font = fonts.get('micro')
                if coord_font:
                    if col == 0:
                        r_lbl = coord_font.render(str(rank_idx + 1), True, coord_color)
                        screen.blit(r_lbl, (rect.x + 3, rect.y + 2))
                    if row == 7:
                        f_lbl = coord_font.render(chess.FILE_NAMES[file_idx], True, coord_color)
                        screen.blit(f_lbl, (rect.right - f_lbl.get_width() - 3, rect.bottom - f_lbl.get_height() - 1))

    if selected is not None:
        sx, sy = square_pos(selected, game.player, board_origin, square_size)
        pygame.draw.rect(screen, theme.BORDER_FOCUS, (sx, sy, square_size, square_size), max(2, square_size // 20))
        dot_surf = pygame.Surface((square_size, square_size), pygame.SRCALPHA)
        center = (square_size // 2, square_size // 2)
        for move in game.board.legal_moves:
            if move.from_square != selected:
                continue
            tx, ty = square_pos(move.to_square, game.player, board_origin, square_size)
            dot_surf.fill((0, 0, 0, 0))
            if game.board.is_capture(move):
                pygame.draw.circle(dot_surf, theme.SQ_LEGAL_RING, center, int(square_size * 0.44), max(3, square_size // 14))
            else:
                pygame.draw.circle(dot_surf, theme.SQ_LEGAL_DOT, center, max(5, int(square_size * 0.16)))
            screen.blit(dot_surf, (tx, ty))

    for square, piece in game.board.piece_map().items():
        if only_color is not None and piece.color != only_color:
            continue
        if square == hidden_square:
            continue
        key = ('w' if piece.color else 'b') + piece.symbol().lower()
        screen.blit(pieces[key], square_pos(square, game.player, board_origin, square_size))

    if anim_piece is not None:
        key, ax, ay = anim_piece
        screen.blit(pieces[key], (ax, ay))

    if drag_piece is not None:
        key, mx, my = drag_piece
        big = int(square_size * 1.08)
        scaled = pygame.transform.scale(pieces[key], (big, big))
        screen.blit(scaled, scaled.get_rect(center=(mx, my)))
