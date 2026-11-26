import pygame

from client.gui import theme


def draw_card(screen, rect, bg=theme.BG_CARD, border=theme.BORDER, radius=6, width=1):
    pygame.draw.rect(screen, bg, rect, border_radius=radius)
    if width > 0:
        pygame.draw.rect(screen, border, rect, width=width, border_radius=radius)


def draw_button(
    screen,
    rect,
    text,
    fonts,
    primary=False,
    selected=False,
    danger=False,
    disabled=False,
    mouse_pos=None,
    mouse_down=False,
):
    if mouse_pos is None:
        mouse_pos = pygame.mouse.get_pos()
    hovered = (not disabled) and rect.collidepoint(mouse_pos)
    pressed = hovered and mouse_down

    if disabled:
        bg = theme.BG_SUBTLE
        border = theme.BORDER
        fg = theme.TEXT_MUTED
    elif danger:
        bg = theme.DANGER_PRESS if pressed else theme.DANGER_HOVER if hovered else theme.DANGER
        border = (240, 140, 136) if hovered else theme.DANGER
        fg = theme.TEXT_PRIMARY
    elif primary or selected:
        bg = theme.BTN_PRIMARY_PRESS if pressed else theme.BTN_PRIMARY_HOVER if hovered else theme.BTN_PRIMARY
        border = theme.BORDER_FOCUS if hovered else theme.BTN_PRIMARY
        fg = theme.TEXT_DARK
    else:
        bg = theme.BTN_SECONDARY_PRESS if pressed else theme.BTN_SECONDARY_HOVER if hovered else theme.BTN_SECONDARY
        border = theme.BORDER_FOCUS if hovered else theme.BORDER
        fg = theme.TEXT_PRIMARY

    draw_rect = rect.move(0, 1) if pressed else rect
    pygame.draw.rect(screen, bg, draw_rect, border_radius=5)
    pygame.draw.rect(screen, border, draw_rect, width=1, border_radius=5)

    face = theme.pick_font(fonts, text, 'ui')
    rendered = face.render(text, True, fg)
    if rendered.get_width() > draw_rect.width - 14:
        face = theme.pick_font(fonts, text, 'ui_small')
        rendered = face.render(text, True, fg)
    if rendered.get_width() > draw_rect.width - 10:
        rendered = pygame.transform.smoothscale(rendered, (draw_rect.width - 10, rendered.get_height()))
    screen.blit(rendered, rendered.get_rect(center=draw_rect.center))


def draw_text_input(screen, rect, text, placeholder, active, fonts, masked=False, now=0.0):
    draw_card(
        screen,
        rect,
        bg=theme.BG_INPUT,
        border=theme.BORDER_FOCUS if active else theme.BORDER,
        radius=5,
        width=2 if active else 1,
    )
    display = '*' * len(text) if masked else text
    is_placeholder = not display
    if is_placeholder:
        display = placeholder
    color = theme.TEXT_MUTED if is_placeholder else theme.TEXT_PRIMARY
    face = theme.pick_font(fonts, display, 'ui')
    while display and not is_placeholder and face.size(display)[0] > rect.width - 22:
        display = display[1:]
    rendered = face.render(display, True, color)
    pos = rendered.get_rect(midleft=(rect.x + 10, rect.centery))
    screen.blit(rendered, pos)
    if active and int(now * 2) % 2 == 0:
        cx = (rect.x + 10) if is_placeholder else min(rect.right - 8, pos.right + 2)
        pygame.draw.line(screen, theme.BORDER_FOCUS, (cx, rect.y + 9), (cx, rect.bottom - 9), 2)


def draw_move_list(screen, rect, moves, fonts, scroll_offset=0):
    """Render numbered 2-column SAN moves inside rect, returning clamped scroll_offset."""
    draw_card(screen, rect, bg=theme.BG_INPUT, border=theme.BORDER, radius=5, width=1)
    row_h = 24
    pad = 8
    inner = rect.inflate(-pad * 2, -pad * 2)
    total_rows = (len(moves) + 1) // 2
    max_scroll = max(0, total_rows * row_h - inner.height)
    scroll_offset = max(0, min(scroll_offset, max_scroll))

    if not moves:
        empty = theme.pick_font(fonts, 'Chưa có nước đi', 'ui_small').render(
            'Chưa có nước đi', True, theme.TEXT_MUTED
        )
        screen.blit(empty, empty.get_rect(center=inner.center))
        return 0

    prev_clip = screen.get_clip()
    screen.set_clip(inner)
    num_font = fonts['small']
    move_font = fonts['small']
    col1_x = inner.x + 34
    col2_x = inner.x + 34 + (inner.width - 34) // 2

    for row_idx in range(total_rows):
        y = inner.y + row_idx * row_h - scroll_offset
        if y + row_h < inner.y or y > inner.bottom:
            continue
        if row_idx % 2 == 1:
            pygame.draw.rect(screen, theme.BG_SUBTLE, (inner.x, y, inner.width, row_h), border_radius=3)

        num_surf = num_font.render(f'{row_idx + 1}.', True, theme.TEXT_MUTED)
        screen.blit(num_surf, (inner.x + 4, y + 4))

        w_idx = row_idx * 2
        b_idx = w_idx + 1
        for idx, x in ((w_idx, col1_x), (b_idx, col2_x)):
            if idx >= len(moves):
                continue
            is_last = idx == len(moves) - 1
            if is_last:
                pill = pygame.Rect(x - 4, y + 2, (inner.width - 38) // 2, row_h - 4)
                pygame.draw.rect(screen, theme.BTN_PRIMARY, pill, border_radius=3)
                fg = theme.TEXT_DARK
            else:
                fg = theme.TEXT_PRIMARY
            m_surf = move_font.render(moves[idx], True, fg)
            screen.blit(m_surf, (x, y + 4))

    screen.set_clip(prev_clip)
    return scroll_offset
