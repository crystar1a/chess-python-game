import chess
import pygame

from client.gui import theme
from client.gui.widgets import draw_button, draw_card, draw_move_list, draw_text_input


def _draw_centered(screen, text, cx, y, fonts, size='ui', color=theme.TEXT_PRIMARY):
    face = theme.pick_font(fonts, text, size)
    surf = face.render(text, True, color)
    rect = surf.get_rect(midtop=(cx, y))
    screen.blit(surf, rect)
    return rect


def _draw_mini_board(screen, rect, pieces):
    sq = min(rect.width, rect.height) // 4
    ox = rect.x + (rect.width - sq * 4) // 2
    oy = rect.y + (rect.height - sq * 4) // 2
    for r in range(4):
        for c in range(4):
            tone = theme.SQ_LIGHT if (r + c) % 2 == 0 else theme.SQ_DARK
            pygame.draw.rect(screen, tone, (ox + c * sq, oy + r * sq, sq, sq))
    king = pygame.transform.scale(pieces['wk'], (sq * 2, sq * 2))
    screen.blit(king, (ox + sq, oy + sq))


def draw_menu_screen(screen, lay, fonts, pieces, ui_state, now, mouse_pos, mouse_down):
    hero = lay['hero_card']
    auth = lay['auth_card']
    draw_card(screen, hero)
    draw_card(screen, auth)

    cx = hero.centerx
    _draw_centered(screen, 'PIXEL CHESS', cx, hero.y + 28, fonts, size='display')
    _draw_centered(screen, 'Cờ vua cổ điển · Nhẹ, rõ ràng, trực quan', cx, hero.y + 72, fonts, size='ui_small', color=theme.TEXT_MUTED)

    mini_rect = pygame.Rect(cx - 56, hero.y + 108, 112, 112)
    _draw_mini_board(screen, mini_rect, pieces)

    btn_w = min(220, (hero.width - 72) // 2)
    btn_h = 48
    btn_y = hero.bottom - btn_h - 32
    bot_rect = pygame.Rect(cx - btn_w - 10, btn_y, btn_w, btn_h)
    online_rect = pygame.Rect(cx + 10, btn_y, btn_w, btn_h)
    draw_button(screen, bot_rect, 'Chơi với Bot', fonts, primary=True, mouse_pos=mouse_pos, mouse_down=mouse_down)
    draw_button(screen, online_rect, 'Chơi Online', fonts, mouse_pos=mouse_pos, mouse_down=mouse_down)

    hits = {'bot': bot_rect, 'online': online_rect}

    # Bottom Auth Bar
    if ui_state['auth_saved']:
        sess = ui_state['auth_session']
        tag = 'Khách (Offline)' if sess['offline_guest'] else ('Khách' if sess['is_guest'] else 'Đã đăng nhập')
        label = f"Tài khoản: {sess['username']} ({tag})"
        face = theme.pick_font(fonts, label, 'ui')
        surf = face.render(label, True, theme.TEXT_PRIMARY)
        screen.blit(surf, surf.get_rect(midleft=(auth.x + 20, auth.centery)))
        switch_rect = pygame.Rect(auth.right - 168, auth.centery - 20, 148, 40)
        draw_button(screen, switch_rect, 'Đổi tài khoản', fonts, mouse_pos=mouse_pos, mouse_down=mouse_down)
        hits['switch_auth'] = switch_rect
    else:
        lbl = theme.pick_font(fonts, 'Tài khoản / Tên hiển thị', 'ui_small').render(
            'Tài khoản / Tên hiển thị (để trống mật khẩu để chơi Khách)', True, theme.TEXT_MUTED
        )
        screen.blit(lbl, (auth.x + 18, auth.y + 12))
        save_w = 104
        gap = 10
        field_w = (auth.width - 36 - save_w - gap * 2) // 2
        row_y = auth.y + 40
        user_rect = pygame.Rect(auth.x + 18, row_y, field_w, 40)
        pass_rect = pygame.Rect(user_rect.right + gap, row_y, field_w, 40)
        save_rect = pygame.Rect(pass_rect.right + gap, row_y, save_w, 40)
        draw_text_input(screen, user_rect, ui_state['auth_username'], 'Guest', ui_state['auth_field'] == 'username', fonts, now=now)
        draw_text_input(screen, pass_rect, ui_state['auth_password'], 'Mật khẩu', ui_state['auth_field'] == 'password', fonts, masked=True, now=now)
        draw_button(screen, save_rect, 'Lưu', fonts, primary=True, disabled=ui_state['auth_pending'], mouse_pos=mouse_pos, mouse_down=mouse_down)
        hits.update({'auth_user': user_rect, 'auth_pass': pass_rect, 'auth_save': save_rect})

        if ui_state['auth_pending']:
            _draw_centered(screen, 'Đang kiểm tra...', auth.centerx, auth.bottom - 24, fonts, size='ui_small', color=theme.TEXT_MUTED)
        elif ui_state['auth_error'] and not ui_state['auth_modal']:
            _draw_centered(screen, ui_state['auth_error'], auth.centerx, auth.bottom - 24, fonts, size='ui_small', color=theme.ERROR_TEXT)

    if ui_state['auth_modal']:
        overlay = pygame.Surface((lay['win_w'], lay['win_h']), pygame.SRCALPHA)
        overlay.fill((0, 0, 0, 175))
        screen.blit(overlay, (0, 0))
        modal = pygame.Rect(lay['win_w'] // 2 - 220, lay['win_h'] // 2 - 125, 440, 250)
        draw_card(screen, modal, bg=theme.BG_CARD, border=theme.BORDER_FOCUS, radius=8, width=2)
        _draw_centered(screen, f"Đăng ký tài khoản '{ui_state['auth_username'].strip()}'?", modal.centerx, modal.y + 22, fonts, size='ui_title')
        _draw_centered(screen, 'Nhập lại mật khẩu để xác nhận', modal.centerx, modal.y + 56, fonts, size='ui_small', color=theme.TEXT_MUTED)
        confirm_rect = pygame.Rect(modal.x + 50, modal.y + 92, modal.width - 100, 42)
        draw_text_input(screen, confirm_rect, ui_state['auth_confirm'], 'Xác nhận mật khẩu', True, fonts, masked=True, now=now)
        if ui_state['auth_error']:
            _draw_centered(screen, ui_state['auth_error'], modal.centerx, modal.y + 144, fonts, size='ui_small', color=theme.ERROR_TEXT)
        ok_rect = pygame.Rect(modal.centerx - 135, modal.bottom - 62, 125, 42)
        cancel_rect = pygame.Rect(modal.centerx + 10, modal.bottom - 62, 125, 42)
        draw_button(screen, ok_rect, 'Đăng ký', fonts, primary=True, mouse_pos=mouse_pos, mouse_down=mouse_down)
        draw_button(screen, cancel_rect, 'Hủy', fonts, mouse_pos=mouse_pos, mouse_down=mouse_down)
        hits.update({'modal_ok': ok_rect, 'modal_cancel': cancel_rect})

    return hits


def draw_bot_setup_screen(screen, lay, fonts, difficulty, color, minutes, minutes_options, mouse_pos, mouse_down):
    card = lay['single_card']
    draw_card(screen, card)
    cx = card.centerx
    _draw_centered(screen, 'CHƠI VỚI BOT', cx, card.y + 28, fonts, size='title')

    hits = {'diff': {}, 'color': {}, 'minutes': {}}

    # Độ khó
    _draw_centered(screen, 'Độ khó', cx, card.y + 78, fonts, size='ui_small', color=theme.TEXT_MUTED)
    diff_map = (('Easy', 'Dễ'), ('Normal', 'Trung bình'), ('Hard', 'Khó'))
    dw = min(140, (card.width - 96) // 3)
    dx0 = cx - (dw * 3 + 24) // 2
    for i, (val, label) in enumerate(diff_map):
        r = pygame.Rect(dx0 + i * (dw + 12), card.y + 106, dw, 42)
        draw_button(screen, r, label, fonts, selected=(difficulty == val), mouse_pos=mouse_pos, mouse_down=mouse_down)
        hits['diff'][val] = r

    # Chọn quân
    _draw_centered(screen, 'Chọn quân', cx, card.y + 172, fonts, size='ui_small', color=theme.TEXT_MUTED)
    cw = 136
    w_rect = pygame.Rect(cx - cw - 8, card.y + 200, cw, 42)
    b_rect = pygame.Rect(cx + 8, card.y + 200, cw, 42)
    draw_button(screen, w_rect, 'Trắng', fonts, selected=(color == chess.WHITE), mouse_pos=mouse_pos, mouse_down=mouse_down)
    draw_button(screen, b_rect, 'Đen', fonts, selected=(color == chess.BLACK), mouse_pos=mouse_pos, mouse_down=mouse_down)
    hits['color'][chess.WHITE] = w_rect
    hits['color'][chess.BLACK] = b_rect

    # Thời gian
    _draw_centered(screen, 'Thời gian mỗi bên', cx, card.y + 266, fonts, size='ui_small', color=theme.TEXT_MUTED)
    mw = min(132, (card.width - 100) // 4)
    mx0 = cx - (mw * 4 + 30) // 2
    for i, m in enumerate(minutes_options):
        r = pygame.Rect(mx0 + i * (mw + 10), card.y + 294, mw, 42)
        lbl = f'{m} phút' if m else 'Không giới hạn'
        draw_button(screen, r, lbl, fonts, selected=(minutes == m), mouse_pos=mouse_pos, mouse_down=mouse_down)
        hits['minutes'][m] = r

    start_rect = pygame.Rect(cx - 145, card.bottom - 76, 136, 46)
    back_rect = pygame.Rect(cx + 9, card.bottom - 76, 136, 46)
    draw_button(screen, start_rect, 'Bắt đầu', fonts, primary=True, mouse_pos=mouse_pos, mouse_down=mouse_down)
    draw_button(screen, back_rect, 'Quay lại', fonts, mouse_pos=mouse_pos, mouse_down=mouse_down)
    hits['start'] = start_rect
    hits['back'] = back_rect
    return hits


def draw_online_menu_screen(screen, lay, fonts, minutes, minutes_options, connect_error, mouse_pos, mouse_down, creating=False):
    card = lay['single_card']
    draw_card(screen, card)
    cx = card.centerx
    _draw_centered(screen, 'TẠO PHÒNG' if creating else 'CHƠI ONLINE', cx, card.y + 32, fonts, size='title')

    hits = {'minutes': {}}
    if creating:
        _draw_centered(screen, 'Thời gian mỗi bên', cx, card.y + 98, fonts, size='ui_small', color=theme.TEXT_MUTED)
        mw = min(132, (card.width - 100) // 4)
        mx0 = cx - (mw * 4 + 30) // 2
        for i, m in enumerate(minutes_options):
            r = pygame.Rect(mx0 + i * (mw + 10), card.y + 128, mw, 42)
            draw_button(screen, r, f'{m} phút' if m else 'Không giới hạn', fonts, selected=(minutes == m), mouse_pos=mouse_pos, mouse_down=mouse_down)
            hits['minutes'][m] = r

    create_rect = pygame.Rect(cx - 110, card.y + 210, 220, 46)
    join_rect = pygame.Rect(cx - 110, card.y + 270, 220, 46)
    back_rect = pygame.Rect(cx - 110, card.y + 330, 220, 46)
    draw_button(screen, create_rect, 'Tạo phòng', fonts, primary=True, mouse_pos=mouse_pos, mouse_down=mouse_down)
    if not creating:
        draw_button(screen, join_rect, 'Vào phòng', fonts, mouse_pos=mouse_pos, mouse_down=mouse_down)
    draw_button(screen, back_rect, 'Quay lại', fonts, mouse_pos=mouse_pos, mouse_down=mouse_down)
    hits.update({'create': create_rect, 'back': back_rect})
    if not creating:
        hits['join'] = join_rect

    if connect_error:
        _draw_centered(screen, connect_error, cx, card.bottom - 52, fonts, size='ui_small', color=theme.ERROR_TEXT)
    return hits


def draw_join_input_screen(screen, lay, fonts, room_input, active, connect_error, now, mouse_pos, mouse_down):
    card = lay['single_card']
    draw_card(screen, card)
    cx = card.centerx
    _draw_centered(screen, 'VÀO PHÒNG', cx, card.y + 36, fonts, size='title')
    _draw_centered(screen, 'Nhập mã phòng (6 ký tự)', cx, card.y + 116, fonts, size='ui_small', color=theme.TEXT_MUTED)

    box = pygame.Rect(cx - 110, card.y + 148, 220, 46)
    draw_text_input(screen, box, room_input, 'VD: A1B2C3', active, fonts, now=now)

    join_rect = pygame.Rect(cx - 110, card.y + 224, 220, 46)
    back_rect = pygame.Rect(cx - 110, card.y + 284, 220, 46)
    draw_button(screen, join_rect, 'Tham gia', fonts, primary=True, disabled=not room_input.strip(), mouse_pos=mouse_pos, mouse_down=mouse_down)
    draw_button(screen, back_rect, 'Quay lại', fonts, mouse_pos=mouse_pos, mouse_down=mouse_down)
    if connect_error:
        _draw_centered(screen, connect_error, cx, card.bottom - 52, fonts, size='ui_small', color=theme.ERROR_TEXT)
    return {'box': box, 'join': join_rect, 'back': back_rect}


def draw_waiting_screen(screen, lay, fonts, room_code, controller, is_creator, connect_error, mouse_pos, mouse_down):
    card = lay['single_card']
    draw_card(screen, card)
    cx = card.centerx
    _draw_centered(screen, 'ĐANG CHỜ ĐỐI THỦ', cx, card.y + 44, fonts, size='title')
    code_rect = None
    if room_code:
        code_rect = _draw_centered(screen, f'Mã phòng: {room_code}', cx, card.y + 120, fonts, size='ui_title', color=theme.BORDER_FOCUS)
    if controller is not None:
        side = 'Trắng' if controller.game.player == chess.WHITE else 'Đen'
        _draw_centered(screen, f'Bạn cầm quân: {side}', cx, card.y + 160, fonts, size='ui')
    msg = 'Đang chờ người chơi khác tham gia...' if is_creator else 'Đang kết nối vào ván...'
    _draw_centered(screen, msg, cx, card.y + 210, fonts, size='ui_small', color=theme.TEXT_MUTED)
    cancel_rect = pygame.Rect(cx - 100, card.bottom - 86, 200, 46)
    draw_button(screen, cancel_rect, 'Hủy', fonts, mouse_pos=mouse_pos, mouse_down=mouse_down)
    if connect_error:
        _draw_centered(screen, connect_error, cx, card.bottom - 36, fonts, size='ui_small', color=theme.ERROR_TEXT)
    return {'cancel': cancel_rect, 'room_code': code_rect}


def draw_resign_confirmation(screen, fonts, mouse_pos, mouse_down):
    width, height = screen.get_size()
    overlay = pygame.Surface((width, height), pygame.SRCALPHA)
    overlay.fill((0, 0, 0, 175))
    screen.blit(overlay, (0, 0))
    modal = pygame.Rect(0, 0, min(440, width - 40), 190)
    modal.center = (width // 2, height // 2)
    draw_card(screen, modal, bg=theme.BG_CARD, border=theme.BORDER_FOCUS, radius=8, width=2)
    _draw_centered(screen, 'Bạn muốn đầu hàng?', modal.centerx, modal.y + 24, fonts, size='ui_title')
    _draw_centered(screen, 'Ván đấu sẽ kết thúc.', modal.centerx, modal.y + 62, fonts, size='ui_small', color=theme.TEXT_MUTED)
    confirm = pygame.Rect(modal.centerx - 135, modal.bottom - 62, 125, 42)
    cancel = pygame.Rect(modal.centerx + 10, modal.bottom - 62, 125, 42)
    draw_button(screen, confirm, 'Đầu hàng', fonts, danger=True, mouse_pos=mouse_pos, mouse_down=mouse_down)
    draw_button(screen, cancel, 'Hủy', fonts, mouse_pos=mouse_pos, mouse_down=mouse_down)
    return {'resign_confirm': confirm, 'resign_cancel': cancel}


def draw_game_sidebar(
    screen,
    sidebar,
    fonts,
    controller,
    room_code,
    difficulty,
    rejected_reason,
    scroll_offset,
    mouse_pos,
    mouse_down,
    disconnected=False,
):
    draw_card(screen, sidebar)
    game = controller.game
    pad = 12
    inner_w = sidebar.width - pad * 2
    x = sidebar.x + pad

    header_txt = f'TRỰC TUYẾN · {room_code}' if controller.mode == 'online' else f'ĐẤU VỚI BOT · {difficulty}'
    header_rect = _draw_centered(screen, header_txt, sidebar.centerx, sidebar.y + 14, fonts, size='ui_small', color=theme.BORDER_FOCUS)

    status_txt = game.result or (controller.error if not disconnected else None) or rejected_reason
    if not status_txt:
        status_txt = 'Lượt quân Trắng' if game.board.turn == chess.WHITE else 'Lượt quân Đen'
    status_color = theme.ERROR_TEXT if ((controller.error and not disconnected) or rejected_reason) else theme.TEXT_PRIMARY
    _draw_centered(screen, status_txt, sidebar.centerx, sidebar.y + 40, fonts, size='ui', color=status_color)

    btn_h = 40
    if controller.mode == 'local':
        btn_area_h = btn_h * 2 + 8 + pad
    else:
        btn_area_h = btn_h + pad

    moves_rect = pygame.Rect(x, sidebar.y + 72, inner_w, max(100, sidebar.bottom - (sidebar.y + 72) - btn_area_h - 10))
    clamped_scroll = draw_move_list(screen, moves_rect, game.move_history, fonts, scroll_offset=scroll_offset)

    hits = {'moves_rect': moves_rect, 'scroll': clamped_scroll}
    if controller.mode == 'online' and room_code:
        hits['room_code'] = header_rect
    if controller.mode == 'local':
        r1 = pygame.Rect(x, sidebar.bottom - pad - btn_h * 2 - 8, inner_w, btn_h)
        r2 = pygame.Rect(x, sidebar.bottom - pad - btn_h, inner_w, btn_h)
        draw_button(screen, r1, 'Chơi lại / Cài đặt', fonts, primary=True, mouse_pos=mouse_pos, mouse_down=mouse_down)
        draw_button(screen, r2, 'Về sảnh chính', fonts, mouse_pos=mouse_pos, mouse_down=mouse_down)
        hits['rematch'] = r1
        hits['menu'] = r2
    else:
        r1 = pygame.Rect(x, sidebar.bottom - pad - btn_h, inner_w, btn_h)
        ended = bool(game.result or (controller.error and not disconnected))
        if ended:
            draw_button(screen, r1, 'Rời phòng', fonts, primary=True, mouse_pos=mouse_pos, mouse_down=mouse_down)
            hits['leave'] = r1
        else:
            draw_button(screen, r1, 'Đầu hàng', fonts, danger=True, disabled=disconnected, mouse_pos=mouse_pos, mouse_down=mouse_down)
            if not disconnected:
                hits['resign'] = r1
    return hits
