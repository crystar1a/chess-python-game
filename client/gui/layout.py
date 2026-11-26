import pygame

MIN_WIDTH = 720
MIN_HEIGHT = 560
DEFAULT_WIDTH = 960
DEFAULT_HEIGHT = 680


def clamp_window_size(w: int, h: int) -> tuple[int, int]:
    """Clamp window dimensions to the minimum supported UI size."""
    return max(MIN_WIDTH, int(w)), max(MIN_HEIGHT, int(h))


def compute_lobby_layout(w: int, h: int) -> dict:
    """Compute centered, equal-edge layout for lobby/setup screens and bottom Auth bar."""
    w, h = clamp_window_size(w, h)
    pad = 24
    content_w = min(760, w - pad * 2)
    left = (w - content_w) // 2
    gap = 16
    auth_h = max(116, min(136, int(h * 0.20)))
    hero_h = max(320, h - pad * 2 - auth_h - gap)
    total_h = hero_h + gap + auth_h
    top = max(pad, (h - total_h) // 2)

    hero_card = pygame.Rect(left, top, content_w, hero_h)
    auth_card = pygame.Rect(left, hero_card.bottom + gap, content_w, auth_h)
    single_card = pygame.Rect(left, top, content_w, h - pad * 2)

    return {
        'win_w': w,
        'win_h': h,
        'content_w': content_w,
        'hero_card': hero_card,
        'auth_card': auth_card,
        'single_card': single_card,
        'scale': min(1.25, max(0.9, min(w / DEFAULT_WIDTH, h / DEFAULT_HEIGHT))),
    }


def compute_game_layout(w: int, h: int) -> dict:
    """Compute square board, aligned player bars, and proportional sidebar."""
    w, h = clamp_window_size(w, h)
    pad = 16
    gap = 16
    sidebar_w = max(230, min(340, int(w * 0.28)))
    bar_h = max(46, min(62, int(h * 0.085)))

    avail_w = w - pad * 2 - gap - sidebar_w
    avail_h = h - pad * 2 - bar_h * 2 - 12
    square_size = max(44, min(avail_w, avail_h) // 8)
    board_size = square_size * 8

    total_w = board_size + gap + sidebar_w
    total_h = bar_h * 2 + 12 + board_size
    start_x = max(pad, (w - total_w) // 2)
    start_y = max(pad, (h - total_h) // 2)

    top_bar = pygame.Rect(start_x, start_y, board_size, bar_h)
    board_rect = pygame.Rect(start_x, top_bar.bottom + 6, board_size, board_size)
    bottom_bar = pygame.Rect(start_x, board_rect.bottom + 6, board_size, bar_h)
    sidebar = pygame.Rect(board_rect.right + gap, top_bar.top, sidebar_w, bottom_bar.bottom - top_bar.top)

    return {
        'win_w': w,
        'win_h': h,
        'square_size': square_size,
        'bar_height': bar_h,
        'top_bar': top_bar,
        'board_rect': board_rect,
        'bottom_bar': bottom_bar,
        'sidebar': sidebar,
        'scale': min(1.25, max(0.88, square_size / 72.0)),
    }
