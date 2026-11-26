import chess
import pygame
import time

from client.game.game_controller import Controller
from client.gui.board_view import (
    BOARD,
    PLAYER_BAR_HEIGHT,
    SIZE,
    draw_board,
    promotion_rects,
    draw_promotion_bubble,
    square_pos,
)
from client.gui.hud import draw_players
from client.gui.resources import ROOT, Sounds, load_pieces
from client.input.mouse_controller import select_square
from client.net.tcp_client import TCPClient
from shared.protocol import DEFAULT_TCP_PORT, MessageType, make_message

WIDTH, HEIGHT = BOARD + 240, BOARD + 2 * PLAYER_BAR_HEIGHT

HOST = '127.0.0.1'
PORT = DEFAULT_TCP_PORT
MINUTES_OPTIONS = (5, 10, 15, None)

ERROR_LABELS = {
    'room_not_found': 'Phòng không tồn tại',
    'room_full': 'Phòng đã đầy',
    'invalid_minutes': 'Thời gian không hợp lệ',
    'no_active_match': 'Không có ván cờ đang diễn ra',
    'opponent_disconnected': 'Đối thủ đã ngắt kết nối',
    'resigned': 'Đối thủ đã đầu hàng',
    'draw_accepted': 'Hòa theo thỏa thuận',
    'unknown_message_type': 'Lỗi giao thức',
}


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

    def minutes_rects(y):
        return [pygame.Rect(170 + i * 125, y, 115, 42) for i in range(len(MINUTES_OPTIONS))]

    def draw_minutes(y, value):
        centered_label('Time per player', 400, y - 32, use_font=small)
        rects = minutes_rects(y)
        for i, value_option in enumerate(MINUTES_OPTIONS):
            button(rects[i], f'{value_option} min' if value_option else 'No limit', value == value_option)
        return rects

    # Trạng thái màn hình: menu | bot_setup | online_menu | join_input | waiting | game
    state = 'menu'
    color = chess.WHITE
    minutes = 10
    online_minutes = 10
    difficulty = None
    room_code = None
    room_input = ''
    room_input_active = True
    is_creator = False
    connect_error = None
    controller = None
    client = None
    selected = None
    promotion = None
    awaiting_accept = False
    revision = None
    rejected_reason = None
    reject_until = 0.0
    previous_result = None
    running = True

    def stop_online():
        nonlocal controller, client, selected, promotion, awaiting_accept, revision
        nonlocal room_code, is_creator
        if controller is not None:
            controller.close()
            controller = None
        if client is not None:
            client.close()
            client = None
        selected = None
        promotion = None
        awaiting_accept = False
        revision = None
        room_code = None
        is_creator = False

    def safe_send(msg):
        nonlocal client, connect_error, state
        try:
            client.send(msg)
            return True
        except OSError:
            connect_error = 'Mất kết nối tới server.'
            state = 'online_menu'
            if client is not None:
                client.close()
                client = None
            controller = None
            return False

    def on_move_intent(uci):
        """Gửi MOVE_REQUEST khi người chơi dự định đi nước (chế độ online)."""
        nonlocal awaiting_accept
        board = controller.game.board
        move = chess.Move.from_uci(uci)
        snd = ('promote' if move.promotion else 'castle' if board.is_castling(move)
               else 'capture' if board.is_capture(move) else None)
        if revision is not None:
            safe_send(make_message(MessageType.MOVE_REQUEST, uci=uci, expected_revision=revision))
        awaiting_accept = True
        if snd:
            sounds.play(snd)

    while running:
        now = time.monotonic()
        if rejected_reason and now > reject_until:
            rejected_reason = None

        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                running = False

            elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                pos = event.pos

                if state == 'menu':
                    if pygame.Rect(315, 160, 170, 45).collidepoint(pos):
                        state = 'bot_setup'
                        difficulty = None
                    elif pygame.Rect(315, 220, 170, 45).collidepoint(pos):
                        state = 'online_menu'

                elif state == 'bot_setup':
                    if difficulty is None:
                        for i, level in enumerate(('Easy', 'Normal', 'Hard')):
                            if pygame.Rect(200 + i * 140, 260, 125, 42).collidepoint(pos):
                                difficulty = level
                        continue
                    if pygame.Rect(270, 160, 120, 42).collidepoint(pos):
                        color = chess.WHITE
                    elif pygame.Rect(410, 160, 120, 42).collidepoint(pos):
                        color = chess.BLACK
                    rects = minutes_rects(260)
                    for i, value in enumerate(MINUTES_OPTIONS):
                        if rects[i].collidepoint(pos):
                            minutes = value
                    if pygame.Rect(315, 360, 170, 45).collidepoint(pos):
                        controller = Controller(color, minutes, difficulty, mode='local')
                        selected = promotion = None
                        previous_result = None
                        state = 'game'
                        sounds.play('game-start')

                elif state == 'online_menu':
                    rects = minutes_rects(260)
                    for i, value in enumerate(MINUTES_OPTIONS):
                        if rects[i].collidepoint(pos):
                            online_minutes = value
                    if pygame.Rect(315, 330, 170, 45).collidepoint(pos):
                        # Tạo phòng
                        if client is None:
                            try:
                                client = TCPClient(HOST, PORT)
                            except OSError:
                                connect_error = 'Không kết nối được server tại 127.0.0.1:8765'
                                client = None
                            else:
                                if safe_send(make_message(MessageType.CREATE_ROOM, minutes=online_minutes)):
                                    state = 'waiting'
                                    is_creator = True
                        # Nếu đang kết nối thì bấm lại không làm gì
                    elif pygame.Rect(315, 390, 170, 45).collidepoint(pos):
                        # Gia nhập phòng
                        state = 'join_input'
                        room_input = ''
                        room_input_active = True
                    elif pygame.Rect(315, 450, 170, 45).collidepoint(pos):
                        # Quay lại
                        state = 'menu'

                elif state == 'join_input':
                    if pygame.Rect(315, 330, 170, 45).collidepoint(pos):
                        # Gia nhập
                        if client is None and room_input.strip():
                            try:
                                client = TCPClient(HOST, PORT)
                            except OSError:
                                connect_error = 'Không kết nối được server tại 127.0.0.1:8765'
                                client = None
                            else:
                                if safe_send(make_message(
                                        MessageType.JOIN_ROOM,
                                        room_code=room_input.strip().upper())):
                                    state = 'waiting'
                                    is_creator = False
                    elif pygame.Rect(315, 390, 170, 45).collidepoint(pos):
                        # Quay lại
                        state = 'online_menu'
                        if client is not None:
                            client.close()
                            client = None
                            controller = None
                    elif pygame.Rect(315, 205, 170, 42).collidepoint(pos):
                        room_input_active = True
                    else:
                        room_input_active = False

                elif state == 'waiting':
                    if pygame.Rect(315, 360, 170, 45).collidepoint(pos):
                        # Hủy
                        stop_online()
                        connect_error = None
                        state = 'online_menu'

                elif state == 'game':
                    game = controller.game
                    if pygame.Rect(BOARD + 25, 490, 185, 42).collidepoint(pos):
                        stop_online()
                        state = 'online_menu'
                        continue
                    if controller.mode == 'online' and pygame.Rect(BOARD + 25, 540, 185, 42).collidepoint(pos):
                        # Từ bỏ
                        if client is not None:
                            safe_send(make_message(MessageType.RESIGN))
                        continue
                    if game.result or controller.error or game.board.turn != game.player \
                            or controller.thinking or awaiting_accept:
                        continue
                    if promotion:
                        bubble, rects_p, arrow_x = promotion_rects(
                            promotion[1], game.player, screen.get_width(), screen.get_height())
                        for i, rect in enumerate(rects_p):
                            if rect.collidepoint(pos):
                                piece = (chess.ROOK, chess.KNIGHT, chess.BISHOP, chess.QUEEN)[i]
                                uci = chess.Move(promotion[0], promotion[1], promotion=piece).uci()
                                controller.apply_uci(uci)
                                promotion = selected = None
                        continue
                    selected, promotion, _sound = select_square(pos, controller, selected)

            elif event.type == pygame.KEYDOWN and state == 'join_input':
                key = event.key
                if key in (pygame.K_RETURN, pygame.K_KP_ENTER):
                    if client is None and room_input.strip():
                        try:
                            client = TCPClient(HOST, PORT)
                        except OSError:
                            connect_error = 'Không kết nối được server tại 127.0.0.1:8765'
                            client = None
                        else:
                            if safe_send(make_message(
                                    MessageType.JOIN_ROOM,
                                    room_code=room_input.strip().upper())):
                                state = 'waiting'
                                is_creator = False
                elif key == pygame.K_BACKSPACE:
                    room_input = room_input[:-1]
                elif key == pygame.K_ESCAPE:
                    state = 'online_menu'
                    if client is not None:
                        client.close()
                        client = None
                        controller = None
                else:
                    ch = event.unicode
                    if room_input_active and len(room_input) < 6 and ch.isalnum():
                        room_input += ch.upper()

        # Xử lý tin nhắn từ server (không block)
        if client is not None:
            for msg in client.poll_messages():
                mtype = msg.get('type')

                if mtype == MessageType.WELCOME:
                    room_code = msg.get('room_code')
                    name = msg.get('color')
                    color = chess.WHITE if name == 'white' else chess.BLACK
                    is_creator = name == 'white'
                    if controller is None:
                        controller = Controller(
                            color, online_minutes, 'Normal', mode='online',
                            on_online_move_intent=on_move_intent,
                        )
                    revision = None
                    sounds.play('notify')

                elif mtype == MessageType.GAME_START:
                    remaining = None
                    if msg.get('white_time') is not None:
                        remaining = {
                            chess.WHITE: float(msg['white_time']),
                            chess.BLACK: float(msg['black_time']),
                        }
                    controller.apply_server_snapshot(
                        msg['fen'], remaining=remaining, result=msg.get('result'))
                    revision = msg.get('revision', 0)
                    controller.error = None
                    state = 'game'
                    awaiting_accept = False
                    sounds.play('game-start')

                elif mtype == MessageType.MOVE_ACCEPTED:
                    remaining = None
                    if msg.get('white_time') is not None:
                        remaining = {
                            chess.WHITE: float(msg['white_time']),
                            chess.BLACK: float(msg['black_time']),
                        }
                    controller.apply_server_snapshot(
                        msg['fen'], remaining=remaining, result=msg.get('result'))
                    revision = msg.get('revision', revision)
                    controller.error = None
                    is_own = awaiting_accept
                    awaiting_accept = False
                    if not is_own:
                        board = controller.game.board
                        sounds.play('move-check' if board.is_check() else 'move-opponent')

                elif mtype == MessageType.MOVE_REJECTED:
                    awaiting_accept = False
                    rejected_reason = msg.get('reason', 'Nước đi bị từ chối.')
                    reject_until = now + 3

                elif mtype == MessageType.ERROR:
                    reason = msg.get('reason')
                    if state == 'game' and reason in ('resigned', 'draw_accepted', 'opponent_disconnected'):
                        controller.apply_server_snapshot(
                            controller.game.board.fen(),
                            remaining=controller.game.remaining,
                            result=msg.get('result') or reason,
                        )
                        controller.error = None
                    else:
                        connect_error = ERROR_LABELS.get(reason, str(reason) if reason else 'Lỗi kết nối')
                        if client is not None:
                            client.close()
                            client = None
                        controller = None
                        state = 'online_menu'

        # Vẽ màn hình
        screen.fill((32, 35, 40))
        if state == 'menu':
            centered_label('Pixel Chess', 400, 70)
            button(pygame.Rect(315, 160, 170, 45), 'Play vs Bot')
            button(pygame.Rect(315, 220, 170, 45), 'Play Online (localhost)')

        elif state == 'bot_setup':
            if difficulty is None:
                centered_label('Choose bot difficulty', 400, 200)
                for i, level in enumerate(('Easy', 'Normal', 'Hard')):
                    button(pygame.Rect(200 + i * 140, 260, 125, 42), level)
            else:
                centered_label('Bot: ' + difficulty, 400, 100, use_font=small)
                centered_label('Choose your color', 400, 125)
                button(pygame.Rect(270, 160, 120, 42), 'White', color == chess.WHITE)
                button(pygame.Rect(410, 160, 120, 42), 'Black', color == chess.BLACK)
                draw_minutes(260, minutes)
                button(pygame.Rect(315, 360, 170, 45), 'Start game')

        elif state == 'online_menu':
            centered_label('Pixel Chess', 400, 70)
            centered_label('Play Online (localhost)', 400, 115, use_font=small)
            draw_minutes(260, online_minutes)
            button(pygame.Rect(315, 330, 170, 45), 'Create Room')
            button(pygame.Rect(315, 390, 170, 45), 'Join Room')
            button(pygame.Rect(315, 450, 170, 45), 'Back')
            if connect_error:
                centered_label(connect_error, 400, 520, use_font=small, color=(255, 100, 100))

        elif state == 'join_input':
            centered_label('Pixel Chess', 400, 70)
            centered_label('Join Room', 400, 115, use_font=small)
            centered_label('Room code', 400, 175, use_font=small)
            box = pygame.Rect(315, 205, 170, 42)
            pygame.draw.rect(screen, (95, 101, 108), box, border_radius=5)
            text = room_input + ('|' if int(now * 2) % 2 == 0 and room_input_active else '')
            rendered = font.render(text, True, (235, 235, 235))
            screen.blit(rendered, rendered.get_rect(center=box.center))
            draw_minutes(260, online_minutes)
            button(pygame.Rect(315, 330, 170, 45), 'Join', bool(room_input.strip()))
            button(pygame.Rect(315, 390, 170, 45), 'Back')
            if connect_error:
                centered_label(connect_error, 400, 520, use_font=small, color=(255, 100, 100))

        elif state == 'waiting':
            centered_label('Pixel Chess', 400, 70)
            if room_code:
                centered_label('Room: ' + room_code, 400, 145, use_font=small)
            if controller is not None:
                centered_label('You play ' + ('White' if controller.game.player == chess.WHITE else 'Black'),
                               400, 175, use_font=small)
            centered_label('Waiting for opponent...' if is_creator else 'Starting game...', 400, 230, use_font=small)
            button(pygame.Rect(315, 360, 170, 45), 'Cancel')
            if connect_error:
                centered_label(connect_error, 400, 520, use_font=small, color=(255, 100, 100))

        else:  # state == 'game'
            game = controller.game
            previous_result = game.result
            sound = controller.update()
            if game.result and not previous_result:
                sounds.play('game-end')
            elif sound:
                sounds.play(sound)
            draw_board(screen, game, selected, pieces)
            centered_label('Pixel Chess', BOARD + 120, 20)
            if controller.mode == 'online':
                centered_label('Room: ' + str(room_code), BOARD + 120, 60, use_font=small)
                centered_label('You play ' + ('White' if game.player == chess.WHITE else 'Black'),
                               BOARD + 120, 84, use_font=small)
            elif controller.engine.online and not controller.engine.api_key:
                centered_label('Online bot (guest)', BOARD + 120, 60, use_font=small)
                centered_label('Add a key to api.txt', BOARD + 120, 84, use_font=small)
                centered_label('for priority access.', BOARD + 120, 108, use_font=small)
            draw_players(screen, game, pieces, font, small, clock_font,
                         difficulty if controller.mode == 'local' else 'Online',
                         stopped=bool(game.result or controller.error))
            text = game.result or controller.error or rejected_reason
            if text:
                words, line, y = text.split(), '', 260
                for word in words:
                    if small.size(line + ' ' + word)[0] > 205:
                        centered_label(line, BOARD + 120, y, use_font=small)
                        line, y = '', y + 23
                    line = (line + ' ' + word).strip()
                centered_label(line, BOARD + 120, y, use_font=small)
            elif promotion:
                bubble, rects_p, arrow_x = promotion_rects(
                    promotion[1], game.player, screen.get_width(), screen.get_height())
                draw_promotion_bubble(screen, bubble, rects_p, pieces, game.player, arrow_x, pygame.mouse.get_pos())
            button(pygame.Rect(BOARD + 25, 490, 185, 42), 'New game / menu')
            if controller.mode == 'online':
                button(pygame.Rect(BOARD + 25, 540, 185, 42), 'Resign')
        pygame.display.flip()
        clock.tick(60)

    if controller is not None:
        controller.close()
    if client is not None:
        client.close()
    pygame.quit()


if __name__ == '__main__':
    run()
