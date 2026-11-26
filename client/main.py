import chess
import pygame

from client.game.game_controller import Controller
from client.gui.board_view import BOARD, PLAYER_BAR_HEIGHT, SIZE, draw_board, promotion_rects, draw_promotion_bubble, square_pos
from client.gui.hud import draw_players
from client.gui.resources import ROOT, Sounds, load_pieces
from client.input.mouse_controller import select_square


WIDTH, HEIGHT = BOARD + 240, BOARD + 2 * PLAYER_BAR_HEIGHT


def run():
    pygame.init()
    screen = pygame.display.set_mode((WIDTH, HEIGHT))
    pygame.display.set_caption('Pixel Chess')
    font_path = str(ROOT / 'assets' / 'fonts' / 'Chess-Sans.ttf')
    font = pygame.font.Font(font_path, 20)
    small = pygame.font.Font(font_path, 16)
    button_font = pygame.font.Font(font_path, 18)
    clock_font = pygame.font.Font(font_path, 22)
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

    color = chess.WHITE
    minutes = 10
    difficulty = None
    controller = None
    selected = None
    promotion = None
    running = True
    while running:
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                running = False
            elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                if controller is None:
                    if difficulty is None:
                        for i, level in enumerate(('Easy', 'Normal', 'Hard')):
                            if pygame.Rect(200 + i * 140, 260, 125, 42).collidepoint(event.pos):
                                difficulty = level
                        continue
                    if pygame.Rect(270, 160, 120, 42).collidepoint(event.pos):
                        color = chess.WHITE
                    elif pygame.Rect(410, 160, 120, 42).collidepoint(event.pos):
                        color = chess.BLACK
                    for i, value in enumerate((5, 10, 15, None)):
                        if pygame.Rect(170 + i * 125, 260, 115, 42).collidepoint(event.pos):
                            minutes = value
                    if pygame.Rect(315, 360, 170, 45).collidepoint(event.pos):
                        controller = Controller(color, minutes, difficulty, mode='local')
                        selected = promotion = None
                        sounds.play('game-start')
                else:
                    game = controller.game
                    if pygame.Rect(BOARD + 25, 490, 185, 42).collidepoint(event.pos):
                        controller.close()
                        controller = None
                        difficulty = None
                        continue
                    if game.result or controller.error or game.board.turn != game.player or controller.thinking:
                        continue
                    if promotion:
                        bubble, rects, arrow_x = promotion_rects(promotion[1], game.player, screen.get_width(), screen.get_height())
                        for i, rect in enumerate(rects):
                            if rect.collidepoint(event.pos):
                                piece = (chess.ROOK, chess.KNIGHT, chess.BISHOP, chess.QUEEN)[i]
                                uci = chess.Move(promotion[0], promotion[1], promotion=piece).uci()
                                sound = controller.apply_uci(uci)
                                if sound:
                                    sounds.play('game-end' if game.result else sound)
                                promotion = selected = None
                        continue
                    selected, promotion, sound = select_square(event.pos, controller, selected)
                    if sound:
                        sounds.play('game-end' if game.result else sound)

        screen.fill((32, 35, 40))
        if controller is None:
            centered_label('Pixel Chess', 400, 70)
            if difficulty is None:
                centered_label('Choose bot difficulty', 400, 200)
                for i, level in enumerate(('Easy', 'Normal', 'Hard')):
                    button(pygame.Rect(200 + i * 140, 260, 125, 42), level)
                pygame.display.flip()
                clock.tick(60)
                continue
            centered_label('Bot: ' + difficulty, 400, 100, use_font=small)
            centered_label('Choose your color', 400, 125)
            button(pygame.Rect(270, 160, 120, 42), 'White', color == chess.WHITE)
            button(pygame.Rect(410, 160, 120, 42), 'Black', color == chess.BLACK)
            centered_label('Time per player', 400, 225)
            for i, value in enumerate((5, 10, 15, None)):
                button(pygame.Rect(170 + i * 125, 260, 115, 42), f'{value} min' if value else 'No limit', minutes == value)
            button(pygame.Rect(315, 360, 170, 45), 'Start game')
        else:
            game = controller.game
            previous_result = game.result
            sound = controller.update()
            if game.result and not previous_result:
                sounds.play('game-end')
            elif sound:
                sounds.play(sound)
            draw_board(screen, game, selected, pieces)
            centered_label('Pixel Chess', BOARD + 120, 20)
            if controller.engine.online and not controller.engine.api_key:
                centered_label('Online bot (guest)', BOARD + 120, 60, use_font=small)
                centered_label('Add a key to api.txt', BOARD + 120, 84, use_font=small)
                centered_label('for priority access.', BOARD + 120, 108, use_font=small)
            draw_players(screen, game, pieces, font, small, clock_font, difficulty,
                         stopped=bool(game.result or controller.error))
            if game.result or controller.error:
                text = game.result or controller.error
                words, line, y = text.split(), '', 260
                for word in words:
                    if small.size(line + ' ' + word)[0] > 205:
                        centered_label(line, BOARD + 120, y, use_font=small)
                        line, y = '', y + 23
                    line = (line + ' ' + word).strip()
                centered_label(line, BOARD + 120, y, use_font=small)
            elif promotion:
                bubble, rects, arrow_x = promotion_rects(promotion[1], game.player, screen.get_width(), screen.get_height())
                draw_promotion_bubble(screen, bubble, rects, pieces, game.player, arrow_x, pygame.mouse.get_pos())
            button(pygame.Rect(BOARD + 25, 490, 185, 42), 'New game / menu')
        pygame.display.flip()
        clock.tick(60)
    if controller:
        controller.close()
    pygame.quit()


if __name__ == '__main__':
    run()
