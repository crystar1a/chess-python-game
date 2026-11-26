import pygame

from client.gui.resources import ROOT, load_pieces

BG_APP = (46, 61, 48)          # #2E3D30
BG_CARD = (57, 75, 59)         # #394B3B
BG_INPUT = (39, 52, 41)        # #273429
BG_SUBTLE = (50, 66, 52)       # #324234

BORDER = (89, 114, 90)         # #59725A
BORDER_FOCUS = (164, 214, 94)  # #A4D65E

TEXT_PRIMARY = (245, 246, 236) # #F5F6EC
TEXT_MUTED = (182, 202, 176)   # #B6CAB0
TEXT_DARK = (24, 34, 23)       # #182217

BTN_PRIMARY = (129, 182, 76)       # #81B64C
BTN_PRIMARY_HOVER = (147, 199, 93) # #93C75D
BTN_PRIMARY_PRESS = (109, 158, 61) # #6D9E3D

BTN_SECONDARY = (70, 91, 72)       # #465B48
BTN_SECONDARY_HOVER = (84, 109, 86)# #546D56
BTN_SECONDARY_PRESS = (59, 77, 61) # #3B4D3D

DANGER = (217, 83, 79)         # #D9534F
DANGER_HOVER = (230, 102, 98)
DANGER_PRESS = (188, 66, 62)
ERROR_TEXT = (242, 134, 128)

SQ_LIGHT = (238, 238, 210)     # #EEEED2
SQ_DARK = (118, 150, 86)       # #769656
SQ_LAST_LIGHT = (246, 246, 125)
SQ_LAST_DARK = (186, 202, 68)  # #BACA44
SQ_CHECK = (217, 78, 78)
SQ_LEGAL_DOT = (44, 62, 40, 115)
SQ_LEGAL_RING = (44, 62, 40, 140)

_FONT_CACHE = {}
_PIECE_CACHE = {}


def get_fonts(scale: float = 1.0) -> dict[str, pygame.font.Font]:
    """Return cached font dictionary scaled cleanly for the current window."""
    key = round(max(0.8, min(1.6, scale)), 2)
    if key in _FONT_CACHE:
        return _FONT_CACHE[key]

    chess_font_path = str(ROOT / 'assets' / 'fonts' / 'Chess-Sans.ttf')
    sys_font_path = 'C:/Windows/Fonts/segoeui.ttf'

    def _load(path, size):
        try:
            return pygame.font.Font(path, max(11, int(round(size * key))))
        except OSError:
            return pygame.font.SysFont('segoeui,arial,sans-serif', max(11, int(round(size * key))))

    fonts = {
        'display': _load(chess_font_path, 32),
        'title': _load(chess_font_path, 22),
        'body': _load(chess_font_path, 18),
        'small': _load(chess_font_path, 14),
        'micro': _load(chess_font_path, 12),
        'clock': _load(chess_font_path, 22),
        'ui_title': _load(sys_font_path, 20),
        'ui': _load(sys_font_path, 16),
        'ui_small': _load(sys_font_path, 14),
        'ui_micro': _load(sys_font_path, 12),
    }
    _FONT_CACHE[key] = fonts
    return fonts


def pick_font(fonts: dict[str, pygame.font.Font], text: str, size: str = 'ui') -> pygame.font.Font:
    """Use Chess-Sans for pure ASCII/notation and system sans for Vietnamese diacritics."""
    has_unicode = any(ord(ch) > 127 for ch in text)
    if has_unicode:
        return fonts.get(size if size.startswith('ui') else f'ui_{size}' if f'ui_{size}' in fonts else 'ui', fonts['ui'])
    return fonts.get(size, fonts['body'])


def get_scaled_pieces(square_size: int) -> dict[str, pygame.Surface]:
    """Cache nearest-neighbor scaled pixel pieces by square_size."""
    if square_size not in _PIECE_CACHE:
        _PIECE_CACHE[square_size] = load_pieces(square_size)
    return _PIECE_CACHE[square_size]
