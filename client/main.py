import math
import queue
import threading
import time

import chess
import pygame

from client.game.game_controller import Controller
from client.gui import theme
from client.gui.board_view import draw_board, draw_promotion_bubble, promotion_rects, square_pos
from client.gui.hud import draw_players
from client.gui.layout import DEFAULT_HEIGHT, DEFAULT_WIDTH, clamp_window_size, compute_game_layout, compute_lobby_layout
from client.gui.resources import Sounds
from client.gui.screens import (
    draw_bot_setup_screen,
    draw_game_sidebar,
    draw_join_input_screen,
    draw_menu_screen,
    draw_online_menu_screen,
    draw_server_screen,
    draw_room_list_screen,
    draw_resign_confirmation,
    draw_rematch_confirmation,
    draw_waiting_screen,
)
from client.input.mouse_controller import resolve_drop, select_square, square_at
from client.net.auth_client import ConnectionUnavailable, exchange
from client.net.session_store import save_session, room_request, delete_session
from client.net.server_config import load_address, save_address, parse_address
from server.auth import normalize_username
from shared.protocol import DEFAULT_TCP_PORT, MessageType, make_message

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
    'resume_expired': 'Phiên kết nối lại đã hết hạn',
    'invalid_resume_token': 'Phiên kết nối lại không hợp lệ',
}


def run():
    pygame.init()
    win_w, win_h = DEFAULT_WIDTH, DEFAULT_HEIGHT
    screen = pygame.display.set_mode((win_w, win_h), pygame.RESIZABLE)
    pygame.display.set_caption('Pixel Chess')
    clock = pygame.time.Clock()
    sounds = Sounds()

    state = 'menu'
    auth_session = {'username': 'Guest', 'is_guest': True, 'token': None, 'offline_guest': True}
    auth_saved = False
    auth_username = ''
    auth_password = ''
    auth_confirm = ''
    auth_field = 'username'
    auth_modal = False
    auth_error = None
    auth_pending = False
    auth_generation = 0
    auth_results = queue.Queue()
    pending_room = None
    server_address = load_address()
    server_host, server_port = parse_address(server_address)
    rooms = []
    rooms_offset = 0
    chat_open = False
    chat_focus = False
    chat_text = ''
    chat_messages = []
    chat_unread = 0
    chat_scroll = 0

    opponent_name = 'Đối thủ'
    color = chess.WHITE
    minutes = 10
    online_minutes = 10
    difficulty = 'Normal'
    room_code = None
    room_input = ''
    room_input_active = True
    is_creator = False
    connect_error = None
    controller = None
    client = None

    selected = None
    promotion = None
    drag_state = None
    slide_anim = None
    skip_next_slide = False
    last_seen_move_count = 0
    move_scroll = 0

    awaiting_accept = False
    resign_modal = False
    rematch_modal = False
    rematch_pending = False
    player_disconnected = False
    opponent_disconnected = False
    rejected_reason = None
    reject_until = 0.0
    previous_result = None
    hits = {}
    running = True

    def start_auth(message, purpose):
        nonlocal auth_pending, auth_generation, auth_error
        auth_pending = True
        auth_error = None
        auth_generation += 1
        generation = auth_generation

        def worker():
            try:
                response, connection = exchange(server_host, server_port, message)
                auth_results.put((generation, purpose, response, connection, None))
            except (OSError, TimeoutError) as exc:
                auth_results.put((generation, purpose, None, None, exc))

        threading.Thread(target=worker, daemon=True).start()

    def submit_auth(register=False, purpose='entry', default_guest=False):
        nonlocal auth_error
        if auth_pending:
            return
        uname = auth_username.strip()
        if not uname and default_guest and not auth_password:
            uname = 'Guest'
        if normalize_username(uname) is None:
            auth_error = 'Tên: 3-20 ký tự (chữ, số, _, ., -)'
        elif auth_password and len(auth_password) < 4:
            auth_error = 'Mật khẩu tối thiểu 4 ký tự'
        elif register and auth_confirm != auth_password:
            auth_error = 'Mật khẩu xác nhận không khớp'
        else:
            kind = MessageType.AUTH_REGISTER if register else MessageType.AUTH_SUBMIT if auth_password else MessageType.AUTH_GUEST
            fields = {'username': uname}
            if auth_password:
                fields['password'] = auth_password
            start_auth(make_message(kind, **fields), purpose)

    def begin_room(message):
        nonlocal pending_room, state
        if auth_pending:
            return
        pending_room = message
        identity = (
            make_message(MessageType.AUTH_TOKEN, token=auth_session['token'])
            if auth_session['token']
            else make_message(MessageType.AUTH_GUEST, username=auth_session['username'])
        )
        start_auth(identity, 'room')
        state = 'waiting'

    def reset_board_ui():
        nonlocal selected, promotion, drag_state, slide_anim, skip_next_slide, last_seen_move_count, move_scroll
        selected = None
        promotion = None
        drag_state = None
        slide_anim = None
        skip_next_slide = False
        last_seen_move_count = 0
        move_scroll = 0

    def copy_room_code():
        nonlocal connect_error, rejected_reason, reject_until
        try:
            if not pygame.scrap.get_init():
                pygame.scrap.init()
            pygame.scrap.put_text(room_code)
            if state == 'waiting' and not (controller is not None and is_creator):
                connect_error = 'Đã sao chép mã phòng'
            else:
                rejected_reason = 'Đã sao chép mã phòng'
                reject_until = time.monotonic() + 3
        except pygame.error:
            if state == 'waiting' and not (controller is not None and is_creator):
                connect_error = 'Không thể sao chép mã phòng'
            else:
                rejected_reason = 'Không thể sao chép mã phòng'
                reject_until = time.monotonic() + 3

    def stop_online():
        nonlocal controller, client, awaiting_accept, room_code, is_creator, player_disconnected, opponent_disconnected, rematch_modal, rematch_pending
        nonlocal chat_open, chat_focus, chat_text, chat_messages, chat_unread, chat_scroll
        if controller is not None:
            controller.close()
            controller = None
        if client is not None:
            client.close()
            client = None
        reset_board_ui()
        awaiting_accept = False
        room_code = None
        is_creator = False
        player_disconnected = opponent_disconnected = False
        rematch_modal = rematch_pending = False
        chat_open = chat_focus = False
        chat_text = ''
        chat_messages = []
        chat_unread = chat_scroll = 0
        pygame.key.stop_text_input()

    def safe_send(msg):
        nonlocal client, connect_error, state, controller, player_disconnected
        try:
            client.send(msg)
            return True
        except OSError:
            if controller is not None and controller.mode == 'online':
                controller.error = 'Mất kết nối. Đang kết nối lại...'
                player_disconnected = True
            else:
                connect_error = 'Mất kết nối tới server.'
                state = 'online_menu'
            return False

    def on_move_intent(uci, expected_revision):
        nonlocal awaiting_accept
        board = controller.game.board
        move = chess.Move.from_uci(uci)
        snd = ('promote' if move.promotion else 'castle' if board.is_castling(move)
               else 'capture' if board.is_capture(move) else None)
        if controller.revision is not None:
            safe_send(make_message(MessageType.MOVE_REQUEST, uci=uci, expected_revision=expected_revision))
        awaiting_accept = True
        if snd:
            sounds.play(snd)

    def send_chat():
        nonlocal chat_text
        if (controller is not None and controller.mode == 'online' and not controller.game.result
                and not player_disconnected and not opponent_disconnected and not controller.error
                and chat_text.strip() and client is not None):
            if safe_send(make_message(MessageType.CHAT_SEND, text=chat_text)):
                chat_text = ''

    while running:
        now = time.monotonic()
        if chat_open and (state != 'game' or controller is None or controller.game.result):
            chat_open = False
        if resign_modal and (state != 'game' or controller is None or controller.game.result or player_disconnected or opponent_disconnected):
            resign_modal = False
        if chat_focus and (state != 'game' or controller is None or controller.game.result or player_disconnected or opponent_disconnected or not chat_open):
            chat_focus = False
            pygame.key.stop_text_input()
        if rejected_reason and now > reject_until:
            rejected_reason = None

        mouse_pos = pygame.mouse.get_pos()
        mouse_down = pygame.mouse.get_pressed()[0]

        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                running = False

            elif event.type == pygame.VIDEORESIZE:
                win_w, win_h = clamp_window_size(event.w, event.h)
                if (event.w, event.h) != (win_w, win_h):
                    screen = pygame.display.set_mode((win_w, win_h), pygame.RESIZABLE)

            elif event.type == pygame.MOUSEWHEEL and state == 'game':
                if chat_open and hits.get('chat_list') and hits['chat_list'].collidepoint(mouse_pos):
                    chat_scroll = max(0, chat_scroll + event.y * 28)
                elif not chat_open and hits.get('moves_rect') and hits['moves_rect'].collidepoint(mouse_pos):
                    move_scroll = max(0, move_scroll - event.y * 28)

            elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                pos = event.pos

                if state == 'menu':
                    if auth_modal:
                        if hits.get('modal_ok') and hits['modal_ok'].collidepoint(pos):
                            submit_auth(register=True, purpose='entry')
                        elif hits.get('modal_cancel') and hits['modal_cancel'].collidepoint(pos):
                            auth_generation += 1
                            auth_pending = False
                            auth_modal = False
                            auth_confirm = ''
                            auth_error = None
                    elif hits.get('bot') and hits['bot'].collidepoint(pos):
                        if not auth_saved:
                            typed = auth_username.strip()
                            if typed and normalize_username(typed) and not auth_password:
                                auth_session['username'] = typed
                            else:
                                auth_session['username'] = 'Guest'
                        state = 'bot_setup'
                    elif hits.get('online') and hits['online'].collidepoint(pos):
                        connect_error = None
                        state = 'server_setup'
                    elif hits.get('switch_auth') and hits['switch_auth'].collidepoint(pos):
                        auth_saved = False
                        auth_session = {'username': 'Guest', 'is_guest': True, 'token': None, 'offline_guest': True}
                        auth_username = auth_password = auth_confirm = ''
                        auth_error = None
                    elif hits.get('auth_user') and hits['auth_user'].collidepoint(pos):
                        auth_field = 'username'
                    elif hits.get('auth_pass') and hits['auth_pass'].collidepoint(pos):
                        auth_field = 'password'
                    elif hits.get('auth_save') and hits['auth_save'].collidepoint(pos):
                        submit_auth(register=False, purpose='entry')

                elif state == 'bot_setup':
                    for val, rect in hits.get('diff', {}).items():
                        if rect.collidepoint(pos):
                            difficulty = val
                    for val, rect in hits.get('color', {}).items():
                        if rect.collidepoint(pos):
                            color = val
                    for val, rect in hits.get('minutes', {}).items():
                        if rect.collidepoint(pos):
                            minutes = val
                    if hits.get('start') and hits['start'].collidepoint(pos):
                        controller = Controller(color, minutes, difficulty, mode='local')
                        reset_board_ui()
                        previous_result = None
                        state = 'game'
                        sounds.play('game-start')
                    elif hits.get('back') and hits['back'].collidepoint(pos):
                        state = 'menu'

                elif state == 'server_setup':
                    if hits.get('connect') and hits['connect'].collidepoint(pos):
                        try:
                            new_host, new_port = save_address(server_address)
                            if (new_host, new_port) != (server_host, server_port):
                                auth_saved = False
                                auth_session = {'username': 'Guest', 'is_guest': True, 'token': None, 'offline_guest': True}
                            server_host, server_port = new_host, new_port
                            connect_error = None
                            if auth_saved and not auth_session['offline_guest']:
                                state = 'online_menu'
                            else:
                                state = 'menu'
                                submit_auth(register=False, purpose='enter_online', default_guest=True)
                        except (OSError, ValueError) as exc:
                            connect_error = str(exc)
                    elif hits.get('back') and hits['back'].collidepoint(pos):
                        state = 'menu'

                elif state == 'online_menu':
                    if hits.get('create') and hits['create'].collidepoint(pos):
                        state = 'create_room'
                    elif hits.get('join') and hits['join'].collidepoint(pos):
                        state = 'join_input'
                        room_input = ''
                        room_input_active = True
                    elif hits.get('rooms') and hits['rooms'].collidepoint(pos):
                        rooms = []
                        rooms_offset = 0
                        begin_room(make_message(MessageType.LIST_ROOMS))
                    elif hits.get('back') and hits['back'].collidepoint(pos):
                        state = 'menu'

                elif state == 'create_room':
                    for val, rect in hits.get('minutes', {}).items():
                        if rect.collidepoint(pos):
                            online_minutes = val
                    if hits.get('create') and hits['create'].collidepoint(pos):
                        if client is None:
                            is_creator = True
                            begin_room(make_message(MessageType.CREATE_ROOM, minutes=online_minutes))
                    elif hits.get('back') and hits['back'].collidepoint(pos):
                        state = 'online_menu'

                elif state == 'room_list':
                    if hits.get('back') and hits['back'].collidepoint(pos):
                        stop_online()
                        state = 'online_menu'
                    elif hits.get('refresh') and hits['refresh'].collidepoint(pos):
                        safe_send(make_message(MessageType.LIST_ROOMS))
                    elif hits.get('prev') and hits['prev'].collidepoint(pos):
                        rooms_offset = max(0, rooms_offset - 5)
                    elif hits.get('next') and hits['next'].collidepoint(pos):
                        if rooms_offset + 5 < len(rooms):
                            rooms_offset += 5
                    else:
                        for code, rect in hits.get('rooms', []):
                            if rect.collidepoint(pos):
                                is_creator = False
                                if safe_send(room_request(auth_session['username'], code)):
                                    state = 'waiting'
                                break

                elif state == 'join_input':
                    if hits.get('join') and hits['join'].collidepoint(pos):
                        if client is None and room_input.strip():
                            is_creator = False
                            connect_error = None
                            begin_room(room_request(auth_session['username'], room_input))
                    elif hits.get('back') and hits['back'].collidepoint(pos):
                        state = 'online_menu'
                        stop_online()
                    elif hits.get('box') and hits['box'].collidepoint(pos):
                        room_input_active = True
                    else:
                        room_input_active = False

                elif state == 'waiting':
                    if room_code and hits.get('room_code') and hits['room_code'].collidepoint(pos):
                        copy_room_code()
                    elif hits.get('cancel') and hits['cancel'].collidepoint(pos):
                        stop_online()
                        auth_generation += 1
                        auth_pending = False
                        connect_error = None
                        state = 'online_menu'

                elif state == 'game':
                    game = controller.game
                    if rematch_modal:
                        if hits.get('rematch_accept') and hits['rematch_accept'].collidepoint(pos):
                            rematch_modal = False
                            safe_send(make_message(MessageType.REMATCH_ACCEPT))
                        elif hits.get('rematch_decline') and hits['rematch_decline'].collidepoint(pos):
                            rematch_modal = False
                            safe_send(make_message(MessageType.REMATCH_DECLINE))
                        continue
                    if resign_modal:
                        if hits.get('resign_cancel') and hits['resign_cancel'].collidepoint(pos):
                            resign_modal = False
                        elif hits.get('resign_confirm') and hits['resign_confirm'].collidepoint(pos):
                            resign_modal = False
                            if client is not None and not player_disconnected and not opponent_disconnected and not game.result and not controller.error:
                                safe_send(make_message(MessageType.RESIGN))
                        continue
                    if hits.get('chat_toggle') and hits['chat_toggle'].collidepoint(pos):
                        chat_open = not chat_open
                        chat_focus = False
                        pygame.key.stop_text_input()
                        if chat_open:
                            chat_unread = 0
                            chat_scroll = 0
                        continue
                    if chat_open and hits.get('chat_input') and hits['chat_input'].collidepoint(pos):
                        chat_focus = not player_disconnected and not opponent_disconnected
                        if chat_focus:
                            pygame.key.start_text_input()
                        continue
                    if chat_open and hits.get('chat_send') and hits['chat_send'].collidepoint(pos):
                        send_chat()
                        continue
                    if chat_focus:
                        chat_focus = False
                        pygame.key.stop_text_input()
                    if controller.mode == 'online' and room_code and hits.get('room_code') and hits['room_code'].collidepoint(pos):
                        copy_room_code()
                        continue
                    if controller.mode == 'local':
                        if hits.get('rematch') and hits['rematch'].collidepoint(pos):
                            stop_online()
                            state = 'bot_setup'
                            continue
                        if hits.get('menu') and hits['menu'].collidepoint(pos):
                            stop_online()
                            state = 'menu'
                            continue
                    else:
                        if hits.get('online_rematch') and hits['online_rematch'].collidepoint(pos) and not rematch_pending:
                            if safe_send(make_message(MessageType.REMATCH_REQUEST)):
                                rematch_pending = True
                                rejected_reason = 'Đang chờ đối thủ xác nhận'
                                reject_until = time.monotonic() + 5
                            continue
                        if hits.get('leave') and hits['leave'].collidepoint(pos):
                            stop_online()
                            state = 'online_menu'
                            continue
                        if hits.get('resign') and hits['resign'].collidepoint(pos) and not player_disconnected and not opponent_disconnected:
                            resign_modal = True
                            continue

                    if game.result or controller.error or game.board.turn != game.player or controller.thinking or awaiting_accept:
                        continue

                    lay = compute_game_layout(win_w, win_h)
                    b_orig = lay['board_rect'].topleft
                    sq_sz = lay['square_size']

                    if promotion:
                        _, rects_p, _ = promotion_rects(promotion[1], game.player, win_w, win_h, b_orig, sq_sz)
                        for i, rect in enumerate(rects_p):
                            if rect.collidepoint(pos):
                                piece = (chess.ROOK, chess.KNIGHT, chess.BISHOP, chess.QUEEN)[i]
                                uci = chess.Move(promotion[0], promotion[1], promotion=piece).uci()
                                controller.apply_uci(uci)
                                promotion = selected = None
                                break
                        continue

                    sq = square_at(pos, game.player, b_orig, sq_sz)
                    piece = game.board.piece_at(sq) if sq is not None else None
                    if piece and piece.color == game.player:
                        drag_state = {'from_sq': sq, 'piece': piece, 'start_pos': pos, 'pos': pos, 'active': False}
                    else:
                        selected, promotion, _ = select_square(pos, controller, selected, b_orig, sq_sz)

            elif event.type == pygame.MOUSEMOTION and state == 'game' and drag_state is not None:
                drag_state['pos'] = event.pos
                if not drag_state['active']:
                    if math.hypot(event.pos[0] - drag_state['start_pos'][0], event.pos[1] - drag_state['start_pos'][1]) > 5:
                        drag_state['active'] = True
                        selected = drag_state['from_sq']

            elif event.type == pygame.MOUSEBUTTONUP and event.button == 1 and state == 'game' and drag_state is not None:
                lay = compute_game_layout(win_w, win_h)
                b_orig = lay['board_rect'].topleft
                sq_sz = lay['square_size']
                if drag_state['active']:
                    promo, snd = resolve_drop(drag_state['from_sq'], event.pos, controller, b_orig, sq_sz)
                    if promo:
                        promotion = promo
                        selected = drag_state['from_sq']
                    else:
                        if snd or controller.mode == 'online':
                            skip_next_slide = True
                        selected = None
                    if snd:
                        sounds.play(snd)
                else:
                    selected, promotion, _ = select_square(event.pos, controller, selected, b_orig, sq_sz)
                drag_state = None

            elif event.type == pygame.TEXTINPUT and state == 'game' and chat_focus and not resign_modal and not rematch_modal:
                chat_text = (chat_text + ''.join(ch for ch in event.text if ord(ch) >= 32))[:500]

            elif event.type == pygame.KEYDOWN and state == 'game' and chat_focus and not resign_modal and not rematch_modal:
                if event.key in (pygame.K_RETURN, pygame.K_KP_ENTER):
                    send_chat()
                elif event.key == pygame.K_BACKSPACE:
                    chat_text = chat_text[:-1]
                elif event.key == pygame.K_ESCAPE:
                    chat_focus = False
                    pygame.key.stop_text_input()

            elif event.type == pygame.KEYDOWN and state == 'game' and resign_modal and event.key == pygame.K_ESCAPE:
                resign_modal = False

            elif event.type == pygame.KEYDOWN and state == 'menu' and not auth_saved:
                key = event.key
                if key == pygame.K_ESCAPE and auth_modal:
                    auth_generation += 1
                    auth_pending = False
                    auth_modal = False
                    auth_confirm = ''
                    auth_error = None
                elif key in (pygame.K_RETURN, pygame.K_KP_ENTER):
                    submit_auth(register=auth_modal, purpose='entry')
                elif key == pygame.K_TAB and not auth_modal:
                    auth_field = 'password' if auth_field == 'username' else 'username'
                elif not auth_pending:
                    value = auth_confirm if auth_modal else auth_username if auth_field == 'username' else auth_password
                    if key == pygame.K_BACKSPACE:
                        value = value[:-1]
                    elif event.unicode.isprintable() and len(value) < 128:
                        value += event.unicode
                    if auth_modal:
                        auth_confirm = value
                    elif auth_field == 'username':
                        auth_username = value
                    else:
                        auth_password = value

            elif event.type == pygame.KEYDOWN and state == 'server_setup':
                if event.key == pygame.K_BACKSPACE:
                    server_address = server_address[:-1]
                elif event.key == pygame.K_ESCAPE:
                    state = 'menu'
                elif event.key == pygame.K_v and event.mod & pygame.KMOD_CTRL:
                    try:
                        if not pygame.scrap.get_init():
                            pygame.scrap.init()
                        server_address = (pygame.scrap.get_text() or '').strip()[:255]
                    except pygame.error:
                        connect_error = 'Không thể đọc clipboard'
                elif event.unicode.isprintable() and len(server_address) < 255:
                    server_address += event.unicode

            elif event.type == pygame.KEYDOWN and state == 'join_input':
                key = event.key
                if key == pygame.K_v and event.mod & pygame.KMOD_CTRL and room_input_active:
                    try:
                        if not pygame.scrap.get_init():
                            pygame.scrap.init()
                        pasted = pygame.scrap.get_text() or ''
                        room_input = ''.join(ch for ch in pasted.upper() if ch.isascii() and ch.isalnum())[:6]
                    except pygame.error:
                        connect_error = 'Không thể đọc clipboard'
                elif key in (pygame.K_RETURN, pygame.K_KP_ENTER):
                    if client is None and room_input.strip():
                        is_creator = False
                        connect_error = None
                        begin_room(room_request(auth_session['username'], room_input))
                elif key == pygame.K_BACKSPACE:
                    room_input = room_input[:-1]
                elif key == pygame.K_ESCAPE:
                    state = 'online_menu'
                    stop_online()
                else:
                    ch = event.unicode
                    if room_input_active and len(room_input) < 6 and ch.isalnum():
                        room_input += ch.upper()

        while True:
            try:
                generation, purpose, response, connection, error = auth_results.get_nowait()
            except queue.Empty:
                break
            if generation != auth_generation:
                if connection:
                    connection.close()
                continue
            auth_pending = False
            if error:
                if purpose == 'entry' and not auth_password and isinstance(error, ConnectionUnavailable):
                    auth_session = {'username': auth_username.strip() or 'Guest', 'is_guest': True, 'token': None, 'offline_guest': True}
                    auth_saved = True
                    auth_error = None
                elif purpose == 'room':
                    connect_error = 'Không thể kết nối tới server'
                    state = 'online_menu'
                else:
                    auth_error = 'Không thể kết nối tới server'
                continue
            kind = response.get('type')
            if kind == MessageType.AUTH_OK:
                if purpose in ('entry', 'enter_online'):
                    auth_session = {'username': response['username'], 'is_guest': response['is_guest'], 'token': response.get('token'), 'offline_guest': False}
                    auth_saved = True
                    auth_password = auth_confirm = ''
                    auth_modal = False
                    connection.close()
                    if purpose == 'enter_online':
                        connect_error = None
                        state = 'online_menu'
                else:
                    client = connection
                    auth_session['offline_guest'] = False
                    safe_send(pending_room)
                    if pending_room.get('type') == MessageType.RESUME:
                        client.enable_reconnect(pending_room['token'])
            elif kind == MessageType.AUTH_NEEDS_REGISTER and purpose in ('entry', 'enter_online'):
                connection.close()
                auth_modal = True
                auth_confirm = ''
            else:
                connection.close()
                reason = response.get('reason', 'unknown')
                labels = {
                    'username_registered': 'Tài khoản đã được đăng ký trước',
                    'invalid_credentials': 'Sai mật khẩu',
                    'invalid_token': 'Phiên đăng nhập đã hết hạn',
                    'invalid_username': 'Tên không hợp lệ',
                    'invalid_password': 'Mật khẩu không hợp lệ',
                }
                auth_error = labels.get(reason, 'Lỗi xác thực')
                if purpose == 'room':
                    auth_saved = False
                    auth_session = {'username': 'Guest', 'is_guest': True, 'token': None, 'offline_guest': True}
                    auth_password = auth_confirm = ''
                    state = 'menu'

        if client is not None:
            for msg in client.poll_messages():
                mtype = msg.get('type')
                if mtype == MessageType.WELCOME:
                    room_code = msg.get('room_code')
                    name = msg.get('color')
                    client.enable_reconnect(msg['token'])
                    try:
                        save_session(auth_session['username'], room_code, msg['token'], name)
                    except (OSError, ValueError):
                        connect_error = 'Không thể lưu phiên kết nối lại'
                    color = chess.WHITE if name == 'white' else chess.BLACK
                    is_creator = name == 'white'
                    if controller is not None:
                        controller.game.player = color
                    if controller is None:
                        controller = Controller(
                            color, online_minutes, 'Normal', mode='online',
                            on_online_move_intent=on_move_intent,
                        )
                    sounds.play('notify')
                elif mtype == MessageType.GAME_START:
                    new_chat = controller is None or state != 'game' or bool(controller.game.result)
                    if controller is None:
                        color = chess.WHITE if msg.get('color') == 'white' else chess.BLACK
                        room_code = msg.get('room_code')
                        controller = Controller(color, online_minutes, 'Normal', mode='online', on_online_move_intent=on_move_intent)
                    opponent_name = msg.get('black_name' if color == chess.WHITE else 'white_name', 'Đối thủ')
                    controller.apply_server_snapshot(msg)
                    if new_chat:
                        chat_open = chat_focus = False
                        chat_text = ''
                        chat_messages = []
                        chat_unread = chat_scroll = 0
                        pygame.key.stop_text_input()
                    reset_board_ui()
                    controller.error = None
                    rematch_pending = rematch_modal = False
                    if getattr(client, '_token', None) and room_code:
                        try:
                            save_session(auth_session['username'], room_code, client._token, 'white' if color == chess.WHITE else 'black')
                        except (OSError, ValueError):
                            pass
                    player_disconnected = False
                    opponent_disconnected = msg.get('opponent_disconnected', False)
                    state = 'game'
                    awaiting_accept = False
                    if msg.get('game_over'):
                        delete_session(auth_session['username'], room_code)
                        sounds.play('game-end')
                    else:
                        sounds.play('game-start')
                elif mtype == 'RECONNECTING':
                    if controller is not None and state == 'game':
                        resign_modal = False
                        player_disconnected = True
                        controller.error = 'Mất kết nối. Đang kết nối lại...'
                        awaiting_accept = True
                elif mtype == MessageType.ROOM_STATE:
                    if msg.get('reason') == 'opponent_disconnected':
                        resign_modal = False
                        opponent_disconnected = True
                    elif msg.get('reason') == 'opponent_reconnected':
                        opponent_disconnected = False
                    elif msg.get('reason') == 'waiting_for_opponent':
                        rematch_pending = False
                        if controller is not None:
                            controller.close()
                        controller = Controller(color, online_minutes, 'Normal', mode='online', on_online_move_intent=on_move_intent)
                        reset_board_ui()
                        state = 'waiting'
                elif mtype == MessageType.ROOM_LIST:
                    if msg.get('first'):
                        rooms = []
                    rooms.extend(msg.get('rooms', []))
                    if msg.get('complete', True):
                        rooms_offset = min(rooms_offset, max(0, (len(rooms) - 1) // 5 * 5))
                        connect_error = None
                        state = 'room_list'
                elif mtype == MessageType.REMATCH_REQUEST:
                    if state == 'game' and controller and controller.game.result:
                        rematch_modal = True
                elif mtype == MessageType.REMATCH_DECLINE:
                    stop_online()
                    state = 'online_menu'
                elif mtype == MessageType.CHAT_MESSAGE:
                    if controller is not None and state == 'game' and not controller.game.result:
                        chat_messages.append(msg)
                        chat_messages = chat_messages[-100:]
                        chat_scroll = 0
                        if not chat_open and msg.get('color') != ('white' if controller.game.player == chess.WHITE else 'black'):
                            chat_unread += 1
                elif mtype == MessageType.CHAT_REJECTED:
                    rejected_reason = 'Không thể gửi tin nhắn lúc này'
                    reject_until = now + 3
                elif mtype == MessageType.MOVE_ACCEPTED:
                    controller.apply_server_snapshot(msg)
                    controller.error = None
                    is_own = awaiting_accept
                    awaiting_accept = False
                    if msg.get('game_over'):
                        delete_session(auth_session['username'], room_code)
                        sounds.play('game-end')
                    elif not is_own:
                        board = controller.game.board
                        sounds.play('move-check' if board.is_check() else 'move-opponent')
                elif mtype == MessageType.MOVE_REJECTED:
                    awaiting_accept = False
                    rejected_reason = msg.get('reason', 'Nước đi bị từ chối.')
                    reject_until = now + 3
                elif mtype == MessageType.ERROR:
                    reason = msg.get('reason')
                    if state == 'game' and reason in ('resigned', 'draw_accepted', 'opponent_disconnected'):
                        delete_session(auth_session['username'], room_code)
                        result = msg.get('result') or reason
                        controller.apply_server_snapshot(
                            controller.game.board.fen(),
                            remaining=controller.game.remaining,
                            result=result,
                        )
                        controller.error = None
                        sounds.play('game-end')
                    else:
                        connect_error = ERROR_LABELS.get(reason, str(reason) if reason else 'Lỗi kết nối')
                        if client is not None:
                            client.close()
                            client = None
                        controller = None
                        state = 'online_menu'

        # Render
        screen.fill(theme.BG_APP)
        if state == 'game' or (state == 'waiting' and controller is not None and is_creator):
            waiting_for_opponent = state == 'waiting'
            lay = compute_game_layout(win_w, win_h)
            fonts = theme.get_fonts(lay['scale'])
            pieces = theme.get_scaled_pieces(lay['square_size'])
            game = controller.game
            previous_result = game.result
            sound = None if waiting_for_opponent else controller.update()
            if game.result and not previous_result:
                sounds.play('game-end')
            elif sound:
                sounds.play(sound)

            # Detect new move for subtle slide animation & auto-scroll
            if len(game.move_history) != last_seen_move_count:
                last_seen_move_count = len(game.move_history)
                move_scroll = 10**9
                if game.last_move and not skip_next_slide:
                    moved_piece = game.board.piece_at(game.last_move.to_square)
                    if moved_piece:
                        key = ('w' if moved_piece.color else 'b') + moved_piece.symbol().lower()
                        slide_anim = {
                            'from_sq': game.last_move.from_square,
                            'to_sq': game.last_move.to_square,
                            'key': key,
                            'start': now,
                            'dur': 0.11,
                        }
                skip_next_slide = False

            anim_piece = None
            hidden_sq = drag_state['from_sq'] if (drag_state and drag_state['active']) else None
            if slide_anim is not None:
                t = (now - slide_anim['start']) / slide_anim['dur']
                if t >= 1.0:
                    slide_anim = None
                else:
                    ease = 1.0 - (1.0 - t) ** 3
                    fx, fy = square_pos(slide_anim['from_sq'], game.player, lay['board_rect'].topleft, lay['square_size'])
                    tx, ty = square_pos(slide_anim['to_sq'], game.player, lay['board_rect'].topleft, lay['square_size'])
                    anim_piece = (slide_anim['key'], fx + (tx - fx) * ease, fy + (ty - fy) * ease)
                    hidden_sq = slide_anim['to_sq']

            drag_piece = None
            if drag_state and drag_state['active']:
                p = drag_state['piece']
                drag_piece = (('w' if p.color else 'b') + p.symbol().lower(), *drag_state['pos'])

            draw_board(
                screen,
                game,
                selected,
                pieces,
                only_color=game.player if waiting_for_opponent else None,
                board_origin=lay['board_rect'].topleft,
                square_size=lay['square_size'],
                last_move=game.last_move,
                hidden_square=hidden_sq,
                anim_piece=anim_piece,
                drag_piece=drag_piece,
                fonts=fonts,
            )
            draw_players(
                screen,
                game,
                pieces,
                fonts['ui'],
                fonts['ui_small'],
                fonts['clock'],
                difficulty if controller.mode == 'local' else 'Online',
                stopped=bool(game.result or controller.error),
                player_name=auth_session['username'],
                opponent_name=opponent_name if controller.mode == 'online' else 'Bot',
                board_rect=lay['board_rect'],
                bar_height=lay['bar_height'],
                player_disconnected=player_disconnected,
                opponent_disconnected=opponent_disconnected,
                waiting=waiting_for_opponent,
            )
            hits = draw_game_sidebar(
                screen,
                lay['sidebar'],
                fonts,
                controller,
                room_code,
                difficulty,
                rejected_reason,
                move_scroll,
                mouse_pos,
                mouse_down,
                disconnected=player_disconnected or opponent_disconnected,
                waiting=waiting_for_opponent,
                chat_open=chat_open,
                chat_messages=chat_messages,
                chat_text=chat_text,
                chat_unread=chat_unread,
                chat_focus=chat_focus,
                chat_scroll=chat_scroll,
                now=now,
            )
            if chat_open and 'chat_list' in hits:
                chat_scroll = hits['scroll']
            else:
                move_scroll = hits['scroll']

            if promotion:
                bubble, rects_p, arrow_x = promotion_rects(
                    promotion[1], game.player, win_w, win_h, lay['board_rect'].topleft, lay['square_size']
                )
                draw_promotion_bubble(screen, bubble, rects_p, pieces, game.player, arrow_x, mouse_pos)
            if resign_modal and not game.result:
                hits = draw_resign_confirmation(screen, fonts, mouse_pos, mouse_down)
            elif rematch_modal and game.result:
                hits = draw_rematch_confirmation(screen, fonts, mouse_pos, mouse_down)
        else:
            lay = compute_lobby_layout(win_w, win_h)
            fonts = theme.get_fonts(lay['scale'])
            pieces = theme.get_scaled_pieces(72)
            if state == 'menu':
                hits = draw_menu_screen(
                    screen,
                    lay,
                    fonts,
                    pieces,
                    {
                        'auth_saved': auth_saved,
                        'auth_session': auth_session,
                        'auth_username': auth_username,
                        'auth_password': auth_password,
                        'auth_confirm': auth_confirm,
                        'auth_field': auth_field,
                        'auth_pending': auth_pending,
                        'auth_error': auth_error,
                        'auth_modal': auth_modal,
                    },
                    now,
                    mouse_pos,
                    mouse_down,
                )
            elif state == 'bot_setup':
                hits = draw_bot_setup_screen(screen, lay, fonts, difficulty, color, minutes, MINUTES_OPTIONS, mouse_pos, mouse_down)
            elif state in ('online_menu', 'create_room'):
                hits = draw_online_menu_screen(screen, lay, fonts, online_minutes, MINUTES_OPTIONS, connect_error, mouse_pos, mouse_down, creating=state == 'create_room')
            elif state == 'server_setup':
                hits = draw_server_screen(screen, lay, fonts, server_address, connect_error, now, mouse_pos, mouse_down)
            elif state == 'room_list':
                hits = draw_room_list_screen(screen, lay, fonts, rooms, rooms_offset, connect_error, mouse_pos, mouse_down)
            elif state == 'join_input':
                hits = draw_join_input_screen(screen, lay, fonts, room_input, room_input_active, connect_error, now, mouse_pos, mouse_down)
            elif state == 'waiting':
                hits = draw_waiting_screen(screen, lay, fonts, room_code, controller, is_creator, connect_error, mouse_pos, mouse_down)

        pygame.display.flip()
        clock.tick(60)

    if controller is not None:
        controller.close()
    if client is not None:
        client.close()
    pygame.quit()


if __name__ == '__main__':
    run()
