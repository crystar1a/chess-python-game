from pathlib import Path

import pygame


ROOT = Path(__file__).resolve().parents[2]


def load_pieces(square_size):
    sheet = pygame.image.load(ROOT / 'assets' / 'pieces' / 'pieces.png').convert_alpha()
    pieces = {}
    for row, color in enumerate('bw'):
        for col, piece in enumerate('kqbnrp'):
            tile = pygame.Surface((18, 18), pygame.SRCALPHA)
            tile.blit(sheet, (1, 1), (col * 16, row * 16, 16, 16))
            pieces[color + piece] = pygame.transform.scale(tile, (square_size, square_size))
    return pieces


class Sounds:
    def __init__(self):
        self.sounds = {}
        try:
            pygame.mixer.init()
            for path in (ROOT / 'assets' / 'sounds').glob('*.mp3'):
                try:
                    self.sounds[path.stem] = pygame.mixer.Sound(str(path))
                except pygame.error:
                    print(f'Cannot load sound: {path.name}')
        except pygame.error as exc:
            print(f'Sound unavailable: {exc}')

    def play(self, name):
        if name in self.sounds:
            self.sounds[name].play()
