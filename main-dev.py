import chess
import pygame

from client.game.local_board import Game
from client.gui.board_view import BOARD, PLAYER_BAR_HEIGHT, SIZE, draw_board, promotion_rects, draw_promotion_bubble, square_pos
from client.gui.resources import ROOT, Sounds, load_pieces
from client.input.mouse_controller import square_at

WIDTH, HEIGHT = BOARD + 240, BOARD + 2 * PLAYER_BAR_HEIGHT


def run():
    pygame.init()
    screen = pygame.display.set_mode((WIDTH, HEIGHT))
    pygame.display.set_caption('Pixel Chess - Dev')
    font_path = str(ROOT / 'assets' / 'fonts' / 'Chess-Sans.ttf')
    font = pygame.font.Font(font_path, 20)
    small = pygame.font.Font(font_path, 16)
    button_font = pygame.font.Font(font_path, 18)
    clock = pygame.time.Clock()
    sounds = Sounds()
    pieces = load_pieces(SIZE)

    def centered_label(text, center_x, y, color=(235, 235, 235), use_font=font):
        rendered = use_font.render(text, True, color)
        screen.blit(rendered, rendered.get_rect(midtop=(center_x, y)))

    def button(rect, text, selected=False):
        hovered = rect.collidepoint(pygame.mouse.get_pos())
        color = (111, 153, 111) if selected and hovered else (91, 127, 91) if selected else (95, 101, 108) if hovered else (70, 73, 78)
        pygame.draw.rect(screen, color, rect, border_radius=5)
        if hovered:
            pygame.draw.rect(screen, (190, 211, 183), rect, width=2, border_radius=5)
        rendered = button_font.render(text, True, (235, 235, 235))
        screen.blit(rendered, rendered.get_rect(center=rect.center))

    color = None
    game = None
    selected = None
    promotion = None
    running = True
    while running:
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                running = False
            elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                if game is None:
                    if pygame.Rect(270, 260, 120, 42).collidepoint(event.pos):
                        color = chess.WHITE
                        game = Game(color, None)
                    elif pygame.Rect(410, 260, 120, 42).collidepoint(event.pos):
                        color = chess.BLACK
                        game = Game(color, None)
                    continue
                if game.result:
                    if pygame.Rect(BOARD + 25, 490, 185, 45).collidepoint(event.pos):
                        game = None
                        selected = promotion = None
                    continue
                if promotion:
                    bubble, rects, arrow_x = promotion_rects(promotion[1], color, screen.get_width(), screen.get_height())
                    for i, rect in enumerate(rects):
                        if rect.collidepoint(event.pos):
                            piece = (chess.ROOK, chess.KNIGHT, chess.BISHOP, chess.QUEEN)[i]
                            sound = game.move(chess.Move(promotion[0], promotion[1], promotion=piece))
                            if sound:
                                sounds.play('game-end' if game.result else sound)
                            promotion = selected = None
                    continue
                target = square_at(event.pos, color)
                if target is None:
                    continue
                piece = game.board.piece_at(target)
                if selected is None:
                    if piece is not None and piece.color == color:
                        selected = target
                elif target == selected:
                    selected = None
                else:
                    game.board.turn = color
                    move = chess.Move(selected, target)
                    if move in game.board.legal_moves:
                        sound = game.move(move)
                        if sound:
                            sounds.play('game-end' if game.result else sound)
                        game.board.turn = color
                        selected = None
                    else:
                        promoted = False
                        for promo in (chess.QUEEN, chess.ROOK, chess.BISHOP, chess.KNIGHT):
                            promo_move = chess.Move(selected, target, promotion=promo)
                            if promo_move in game.board.legal_moves:
                                promotion = (selected, target)
                                selected = None
                                promoted = True
                                break
                        if not promoted:
                            selected = None

        screen.fill((32, 35, 40))
        if game is None:
            centered_label('Pixel Chess - Dev', 400, 70)
            centered_label('Choose your color', 400, 200)
            button(pygame.Rect(270, 260, 120, 42), 'White', color == chess.WHITE)
            button(pygame.Rect(410, 260, 120, 42), 'Black', color == chess.BLACK)
        else:
            draw_board(screen, game, selected, pieces, only_color=color)
            centered_label('Pixel Chess - Dev', BOARD + 120, 20)
            centered_label('No opponent · No timer · Free play', BOARD + 120, 60, use_font=small)
            if game.result:
                text = game.result
                words, line, y = text.split(), '', 260
                for word in words:
                    if small.size(line + ' ' + word)[0] > 205:
                        centered_label(line, BOARD + 120, y, use_font=small)
                        line, y = '', y + 23
                    line = (line + ' ' + word).strip()
                centered_label(line, BOARD + 120, y, use_font=small)
            elif promotion:
                bubble, rects, arrow_x = promotion_rects(promotion[1], color, screen.get_width(), screen.get_height())
                draw_promotion_bubble(screen, bubble, rects, pieces, color, arrow_x, pygame.mouse.get_pos())
            button(pygame.Rect(BOARD + 25, 490, 185, 45), 'Back to menu')
        pygame.display.flip()
        clock.tick(60)
    pygame.quit()


if __name__ == '__main__':
    run()
