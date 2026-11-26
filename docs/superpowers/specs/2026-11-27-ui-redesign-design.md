# Pixel Chess Pygame UI Redesign

**Date:** 2026-11-27
**Project:** Pixel Chess (`E:\chess_game`)
**Status:** Ready for user approval (builder check completed)

## 1. Intent and Why

Pixel Chess currently renders all screens (`auth`, `menu`, `bot_setup`, `online_menu`, `join_input`, `waiting`, `game`) in a fixed `816×688` window with hardcoded coordinates inside [client/main.py](file:///E:/chess_game/client/main.py), a very dark olive working-tree palette, mixed English/Vietnamese copy, no move history, click-only piece input, and instant piece teleports without visual move feedback.

The goal is to rebuild the **Pygame (`pygame-ce`) desktop UI** so it feels crisp, brighter, intuitive, and responsive while preserving the lightweight character of Pixel Chess and all existing game/network/auth mechanics:
- **Brighter green aesthetic** inspired by classic Chess.com green boards and clean flat surfaces (applying the visual clarity principles of `design-taste-frontend`: unified color/type tokens, aligned edges, minimal text, clear hover/press states, zero visual clutter).
- **Combined Lobby + Bottom Auth:** Launch straight into the main menu (`Chơi với Bot` / `Chơi Online`) with the account/guest Auth bar anchored cleanly at the bottom.
- **Intuitive in-game board & sidebar:** Resizable window by dragging window edges, algebraic move list (`1. e4 e5`) with scrolling, drag-and-drop alongside click-to-move, board coordinates, last-move & check highlights, and subtle ~110ms Chess.com-style slide animation.

## 2. Goals, Non-Goals, and Anti-Goals

### Goals
- Replace the unfinished dark-olive UI pass with a brighter, high-contrast green & warm-ivory palette across all screens.
- Unify UI copy in **Vietnamese** (keeping standard algebraic chess notation `e4`, `Nf3`, `O-O`, etc.).
- Merge `auth` into the bottom of the `menu` screen so players can jump into **Chơi với Bot** immediately as `Guest` or sign in/register without an extra blocking gate.
- Support free window resizing (`pygame.RESIZABLE` + `pygame.VIDEORESIZE`) down to a safe minimum (`720×560`, default `960×680`), keeping the chessboard square, pixel art sharp (nearest-neighbor scaling), and sidebar/menus cleanly aligned.
- Add **drag-and-drop** piece movement (preserving existing click-to-move), **scrollable move history**, **board coordinates (`a–h`, `1–8`)**, **last-move / check / legal-target highlights**, and **subtle ~110ms slide animation** for clicked, bot, and opponent moves.
- Separate rendering, theme, layout computation, and reusable widgets into [client/gui/](file:///E:/chess_game/client/gui) while keeping logic and network layers separate.

### Non-Goals
- No HTML/Web frontend rewrite; keep the `pygame-ce` desktop client (`python main.py`).
- No external GUI toolkit dependencies (`pygame-gui`, `pygame-menu`, etc.).
- No Elo rating, in-game chat, right-click arrows/square markings, premoves, or move-history time-travel scrubbing.
- No audio overhaul (keep existing [Sounds](file:///E:/chess_game/client/gui/resources.py)).

### Anti-Goals
- **No heavy or distracting animations:** No particle bursts, camera shake, pulsing backgrounds, or slow screen transitions.
- **No breaking existing logic/network/input tests:** Keep [tests/test_input.py](file:///E:/chess_game/tests/test_input.py), [tests/test_online_controller.py](file:///E:/chess_game/tests/test_online_controller.py), [tests/test_server_match.py](file:///E:/chess_game/tests/test_server_match.py), [tests/test_auth.py](file:///E:/chess_game/tests/test_auth.py), and [tests/test_auth_client.py](file:///E:/chess_game/tests/test_auth_client.py) passing.
- **No clipped text or overlapping buttons** when resizing the window to `720×560` or maximizing to larger screens.

## 3. Constraints

- **Dependencies:** `pygame-ce`, `python-chess`, and Python standard library only.
- **Architecture boundary (`AGENTS.md`):** Logic provides state (`Controller`, `Game`, `ChessMatch`, `RoomManager`), GUI renders and translates input. Online mode continues to flow through `Controller.apply_server_snapshot(message)` and `on_online_move_intent(uci, expected_revision)`.
- **Pixel art fidelity:** Existing `16×16` sprites in [assets/pieces/pieces.png](file:///E:/chess_game/assets/pieces/pieces.png) must use integer/nearest-neighbor `pygame.transform.scale` (not `smoothscale`) so pixel pieces stay crisp at any board size.
- **Vietnamese text rendering:** Keep `Chess-Sans.ttf` for headings/clocks/algebraic notation and fallback to system sans font (`segoeui.ttf` on Windows, or Pygame default sans if missing) for strings containing non-ASCII Vietnamese characters.
- **Backwards-compatible board/input API:** `square_pos` and `SIZE` in [board_view.py](file:///E:/chess_game/client/gui/board_view.py) and `square_at` / `select_square` in [mouse_controller.py](file:///E:/chess_game/client/input/mouse_controller.py) must keep their existing default signatures so existing unit tests continue to work without modification.

## 4. Approaches Considered

1. **Approach 1 — Modular Theme, Dynamic Layout & Lightweight Widgets in `client/gui/` *(Chosen)***
   - Separate color/font tokens (`theme.py`), pure geometry calculation from `(win_w, win_h)` (`layout.py`), reusable controls (`widgets.py`), and screen/board rendering (`board_view.py`, `hud.py`, `screens.py`) from the event loop in [client/main.py](file:///E:/chess_game/client/main.py).
   - **Tradeoffs:** Cleanest separation of concerns, reliable hit-testing across arbitrary window sizes, and minimal coupling to `Controller`; requires extracting existing hardcoded drawing out of [client/main.py](file:///E:/chess_game/client/main.py).
2. **Approach 2 — Inline Responsive Math Inside `client/main.py` *(Rejected)***
   - Replace hardcoded rects directly inside `run()`.
   - **Tradeoffs:** Fewer new files, but [client/main.py](file:///E:/chess_game/client/main.py) is already ~680 lines mixing networking, auth, and rendering; adding drag-and-drop, animation state, scrollable move history, and resize math inline would become brittle and hard to maintain.
3. **Approach 3 — Third-Party Pygame Widget Toolkit (`pygame_gui`) *(Rejected)***
   - **Tradeoffs:** Built-in scrollbars and inputs, but adds a new dependency and clashes visually and architecturally with pixel chess styling and the existing 60 FPS loop.

## 5. Detailed Design

### 5.1. Visual System & Brighter Green Palette (`client/gui/theme.py`)
- **Surfaces & Borders:**
  - App background: `#2E3D30` (warm slate-green, noticeably brighter and cleaner than the old `#151B17`)
  - Card / Panel surface: `#394B3B`, elevated sub-panel / input surface: `#273429`
  - Subtle border: `#59725A`, focused border: `#A4D65E`
- **Typography & Accents:**
  - Primary text: `#F5F6EC` (warm ivory)
  - Secondary / muted text: `#BCCAB7`
  - Primary CTA button: `#81B64C`, hover `#93C75D`, pressed `#6D9E3D` (dark ink `#182217`)
  - Secondary button: `#465B48`, hover `#546D56`, pressed `#3B4D3D` (ivory ink `#F5F6EC`)
  - Danger / Check / Error: `#D9534F` (softened `#E06C65` for text/badges)
- **Board & Indicators (Chess.com-inspired green):**
  - Light square: `#EEEED2`
  - Dark square: `#769656`
  - Selected square & Last move (`from` / `to`): `#BACA44` on dark squares / `#F6F669` (or alpha-blended warm lime-yellow `#E6E85E` at ~45% alpha) so square polarity stays legible
  - King in check: subtle radial/inset red tint `#D94E4E` on the king's square
  - Legal moves: centered muted dot (`r ≈ square_size * 0.16`) on empty target squares; corner/ring border (`width ≈ max(3, square_size // 14)`) on capture target squares
  - Coordinates (`a–h`, `1–8`): rendered inside the bottom rank (`10px–12px`) and leftmost file corners using the opposite square's tone (`#769656` on light squares, `#EEEED2` on dark squares) for high legibility without wasting margin space.

### 5.2. Dynamic Resizable Layout (`client/gui/layout.py`)
- Window initializes at `(960, 680)` with `pygame.RESIZABLE` and clamps resizing in `VIDEORESIZE` / layout calculation to a minimum of `(720, 560)` (if the OS allows a smaller window drag, clamp layout metrics or enforce `pygame.display.set_mode((max(720, w), max(560, h)), pygame.RESIZABLE)` when resizing finishes / on clamp). *Design call: clamp the computed layout safely at `min_w=720, min_h=560` and also enforce minimum window size on `VIDEORESIZE`.*
- **Lobby & Setup Screens (`menu`, `bot_setup`, `online_menu`, `join_input`, `waiting`):**
  - Centered main column (`content_w = min(760, win_w - 64)`), equal left/right margins (`(win_w - content_w) // 2`).
  - **Main Menu (`menu`) vertical split:**
    - **Top/Middle Hero Card:** Title `PIXEL CHESS`, brief subtitle, two equal-width primary/secondary mode cards or buttons (**Chơi với Bot**, **Chơi Online**) alongside a clean static mini-board emblem.
    - **Bottom Auth Bar:** Anchored cleanly at the bottom edge of `content_w` (equal left/right edges with the hero card above):
      - When not signed in / guest editable: single compact card with `Tên người chơi` input, `Mật khẩu (trống = Khách)` input, `Lưu` button, and inline status/error line underneath.
      - When saved/authenticated: compact status bar showing `Tài khoản: <username>` (`Khách` / `Đã đăng nhập` / `Khách (Offline)`) + `Đổi tài khoản` button on the right.
      - Clicking **Đăng ký** still opens the centered modal overlay (`Bạn muốn đăng ký '<username>'?`, `Xác nhận mật khẩu`, `Đăng ký`, `Hủy`) sized relative to `(win_w, win_h)`.
- **Game Screen (`game`):**
  - Outer padding `pad = 16`, gap `gap = 16`.
  - Sidebar width `sidebar_w = clamp(int(win_w * 0.28), 230, 340)`.
  - Player bar height `bar_h = clamp(int(win_h * 0.085), 46, 62)`.
  - Available board space: `avail_w = win_w - pad * 2 - gap - sidebar_w`, `avail_h = win_h - pad * 2 - bar_h * 2 - 12`.
  - `square_size = max(44, min(avail_w, avail_h) // 8)`, `board_size = square_size * 8`.
  - Left column (`board_x`, `board_y`) holds Opponent Bar (top, width `board_size`), Square Board (`board_size × board_size`), Player Bar (bottom, width `board_size`), vertically centered in `win_h`.
  - Right column (`sidebar_x = board_x + board_size + gap`, width `sidebar_w`, aligned top/bottom with Opponent Bar top and Player Bar bottom — equal top/bottom edges!):
    - Top header: Match badge (`ĐẤU VỚI BOT - <Độ khó>` or `TRỰC TUYẾN - Phòng <CODE>`), turn/status pill (`LƯỢT BẠN` / `ĐỐI THỦ` / kết quả ván).
    - Middle (flex height): **Danh sách nước đi** panel showing numbered pairs (`1.  e4    e5`), newest move highlighted, auto-scrolled to bottom on new moves, scrollable with mouse wheel when overflowing.
    - Bottom: Mode-aware action buttons (Local: `Chơi lại / Cài đặt` & `Về sảnh chính`; Online active: `Đầu hàng`; Online ended: `Rời phòng`).

### 5.3. Auth + Menu Combined Behavior
- App launches directly in `state = 'menu'` with default `auth_session = {'username': 'Guest', 'is_guest': True, 'token': None, 'offline_guest': True}` and `auth_saved = False`.
- **Chơi với Bot:** Immediately starts `bot_setup` at any time without requiring a server or clicking `Lưu`. If the user typed a valid non-empty username in the bottom input without clicking `Lưu` (and password is empty), use that username as display name; otherwise use `auth_session['username']` (`Guest`).
- **Chơi Online:**
  - If `auth_saved` is `True` and `offline_guest` is `False` (already verified/authenticated with server): enters `online_menu` immediately.
  - Otherwise, if user clicks **Chơi Online**, trigger the same auth check automatically using the current `auth_username` (default `'Guest'` if input is blank) and `auth_password` (`purpose = 'enter_online'`):
    - On `AUTH_OK`: set `auth_saved = True`, store `auth_session`, and enter `online_menu`.
    - On `AUTH_NEEDS_REGISTER`: open the register confirmation modal; after confirmation, proceed to `online_menu`.
    - On error (e.g. `username_registered`, wrong password, server offline): stay on `menu` and show the error in the bottom Auth bar.
- Clicking `Lưu` in the bottom Auth bar behaves identically to current auth submission (`purpose = 'entry'`), updating `auth_saved = True` on `AUTH_OK` and staying on `menu` with the compact logged-in Auth footer.

### 5.4. Move History, Last Move, Drag & Drop, and Slide Animation

#### Move History & Last Move Tracking (`Controller` + Optional Server `uci`)
- Currently, [Controller.apply_server_snapshot](file:///E:/chess_game/client/game/game_controller.py#L48-L68) replaces `game.board = chess.Board(message['fen'])`, wiping `move_stack`, and [ChessMatch.apply_move](file:///E:/chess_game/server/game/chess_match.py#L94-L104) does not include the played `uci`.
- **Server enhancement (`server/game/chess_match.py`):** Add optional `'uci': uci_move` to the `MOVE_ACCEPTED` dictionary (backwards-compatible with all existing tests).
- **Client tracking (`client/game/local_board.py` & `client/game/game_controller.py`):**
  - Track `move_history: list[str]` (SAN strings, e.g. `['e4', 'e5', 'Nf3']`) and `last_move: chess.Move | None` on `Game` (updated automatically in `Game.move(move)` for local mode).
  - In `Controller.apply_server_snapshot(message, ...)`:
    - On `GAME_START` (or `revision == 0`, or when snapshot board equals `chess.STARTING_FEN`): reset `move_history = []`, `last_move = None`.
    - On `MOVE_ACCEPTED` (or legacy FEN transition from a non-terminal prior board): determine `move` using `message.get('uci')` if legal on the previous `game.board`, else infer by checking which legal move on the previous `game.board` produces the new board's piece placement (`board_fen()`). Record `prev_board.san(move)` in `game.move_history` and set `game.last_move = move`.
    - Expose `last_move_event` (e.g. `(move, is_local_drag)` or revision counter) so the GUI knows when a new move arrived to trigger the slide animation.

#### Drag-and-Drop & Click-to-Move (`client/input/mouse_controller.py` + `client/main.py`)
- Keep `square_at(pos, player, board_origin=(0, BOARD_TOP), square_size=SIZE)` and `select_square(pos, controller, selected, board_origin=(0, BOARD_TOP), square_size=SIZE)` backwards-compatible with default arguments.
- Add drag-state handling in `game`:
  - `MOUSEBUTTONDOWN` (left button) on a square containing the player's own piece (when it's the player's turn, not thinking, not awaiting server, and not game over):
    - Store `drag_state = {'from_sq': sq, 'piece': piece, 'start_pos': pos, 'pos': pos, 'active': False}`.
    - Do not activate visual dragging until pointer moves `> 5px` from `start_pos` (prevents accidental micro-drags on normal clicks).
  - `MOUSEMOTION`: if `drag_state`, update `pos`; once distance `> 5px`, set `drag_state['active'] = True` and set `selected = drag_state['from_sq']` so legal targets stay highlighted.
  - `MOUSEBUTTONUP` (left button):
    - If `drag_state` and `drag_state['active']`:
      - Compute `target = square_at(pos, game.player, board_origin, square_size)`.
      - If `target` is a legal move from `from_sq`: if promotion, set `promotion = (from_sq, target)`; otherwise submit `controller.apply_uci(...)` with `skip_next_slide = True` (piece was placed directly by hand) and clear `selected` & `drag_state`.
      - If dropped on invalid square or outside board: cancel drag and clear `selected` (piece snaps back cleanly).
    - If `drag_state` and NOT `drag_state['active']`: treat as a regular click via `select_square(...)`.
    - If no `drag_state` (e.g. clicking an empty destination square while `selected` is already set): handle via `select_square(...)` on `MOUSEBUTTONDOWN` (or `MOUSEBUTTONUP` consistently) — *Design call: handle non-own-piece clicks immediately on `MOUSEBUTTONDOWN` just like before, and only defer own-piece click-vs-drag resolution to `MOUSEBUTTONUP` when `drag_state` was initiated.*

#### Subtle Slide Animation (`~110ms`)
- Maintain a lightweight GUI-only `slide_anim` object (`{'from_sq', 'to_sq', 'piece_key', 'start_time', 'duration': 0.11}`):
  - Triggered whenever `game.last_move` changes (detected via move count / `(revision, fen)` change) UNLESS the move was just placed via manual drag-and-drop.
  - While `t = (now - start_time) / duration < 1.0`:
    - `board_view.draw_board` skips drawing the stationary piece on `to_sq` and draws `piece_key` interpolated between `square_pos(from_sq)` and `square_pos(to_sq)` using ease-out cubic `1 - (1 - t) ** 3`.
  - Piece sprite surfaces are cached by `square_size` so resizing does not re-scale on every frame.

### 5.5. Screen-by-Screen Vietnamese Copy & Navigation
- `menu` (default): `PIXEL CHESS`, `Chơi với Bot`, `Chơi Online`, bottom Auth bar (`Tên đăng nhập`, `Mật khẩu (trống = Khách)`, `Lưu` / `Đổi tài khoản`).
- `bot_setup` *(design call — unified single card)*: Replace the old 2-step wizard with one centered setup card showing all three rows together (`Chọn độ khó`: `Dễ` / `Trung bình` / `Khó`; `Chọn quân`: `Trắng` / `Đen`; `Thời gian mỗi bên`: `5 phút` / `10 phút` / `15 phút` / `Không giới hạn`) with defaults `Trung bình`, `Trắng`, `10 phút`, plus `Bắt đầu` and `Quay lại` (returns to `menu`).
- `online_menu`: `Chơi Online (localhost)`, `Thời gian mỗi bên`, `Tạo phòng`, `Vào phòng`, `Quay lại` (returns to `menu`).
- `join_input`: `Vào phòng`, `Mã phòng (6 ký tự)`, `Tham gia`, `Quay lại` (returns to `online_menu`).
- `waiting`: `Đang chờ đối thủ...`, `Mã phòng: <CODE>`, `Bạn cầm quân: Trắng/Đen`, `Hủy` (calls `stop_online()` and returns to `online_menu`).
- `game` *(design call — mode-aware sidebar navigation)*: Opponent bar, Square board with coordinates & highlights, Player bar, Sidebar (`Ván đấu`, Turn/Result banner, Scrollable Move List, and mode-aware action buttons):
  - **In `local` (Bot) mode:** Show `Chơi lại / Cài đặt` (closes controller and returns to `bot_setup`) and `Về sảnh chính` (closes controller and returns to `menu`).
  - **In `online` mode while match is active (`not game.result and not controller.error`):** Show `Đầu hàng` (sends `RESIGN`) and disable/hide `Về sảnh` until the match ends—or label `Rời phòng` only after `game.result` / `controller.error`—so players cannot accidentally drop the socket mid-match without resigning. *(Design call: while active online, show `Đầu hàng` as the active action and show `Rời phòng` only once `game.result` or `controller.error` is set, calling `stop_online()` and returning to `online_menu`.)*

## 6. Left to the Builder

- Exact pixel padding, border radii (`4px–8px`), and responsive font sizes within `theme.py` and `layout.py` ratios.
- Exact Vietnamese error messages mapped from server error codes (`room_not_found`, `invalid_credentials`, etc.).
- Writing unit tests for `compute_layout` across window sizes (minimum `720×560`, default `960×680`, wide/tall ratios), `Controller` SAN `move_history` & `last_move` inference (with and without `uci` in `MOVE_ACCEPTED`), and drag/click input handling, plus visually inspecting rendered Pygame screenshots across screens.
