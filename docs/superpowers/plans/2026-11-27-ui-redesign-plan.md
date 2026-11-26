# Pixel Chess UI Redesign Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Rebuild the Pixel Chess `pygame-ce` UI with a brighter green palette, merged Menu + bottom Auth, freely resizable window (`720×560` min, `960×680` default), scrollable SAN move list, drag-and-drop, and ~110ms slide animation.

**Architecture:** Separate theme/font/sprite caching (`theme.py`), pure dynamic geometry (`layout.py`), reusable immediate-mode widgets (`widgets.py`), board & slide rendering (`board_view.py`), HUD (`hud.py`), and screen renderers (`screens.py`) from the event/network loop in `client/main.py`. Track `move_history` (SAN) and `last_move` on `Game` / `Controller` with optional `'uci'` in `MOVE_ACCEPTED` and a FEN-diff fallback.

**Tech Stack:** Python, `pygame-ce`, `python-chess`, `unittest`.

**Spec:** [2026-11-27-ui-redesign-design.md](file:///E:/chess_game/docs/superpowers/specs/2026-11-27-ui-redesign-design.md)

## Global Constraints

- Dependencies: `pygame-ce`, `python-chess`, and Python stdlib only.
- Architecture boundary (`AGENTS.md`): Logic provides state; GUI renders and translates input. Online mode flows through `Controller.apply_server_snapshot(message)` and `on_online_move_intent(uci, expected_revision)`.
- Pixel art: `16×16` sprites in `assets/pieces/pieces.png` must use nearest-neighbor `pygame.transform.scale` (never `smoothscale`).
- Backwards compatibility: `SIZE`, `square_pos` (`board_view.py`) and `square_at`, `select_square` (`mouse_controller.py`) must keep their existing default signatures so `tests/test_input.py` passes unmodified.
- Language: Unify all UI copy in Vietnamese (except standard algebraic notation `e4`, `Nf3`, `O-O`).

## Review Focus

- **Window resized below minimum (`< 720×560`) or extreme aspect ratios:** `compute_game_layout` / `compute_lobby_layout` must clamp safely (`square_size >= 44`) without negative rects or overlapping buttons.
- **Online `MOVE_ACCEPTED` without `'uci'` field (legacy/external server):** `Controller.apply_server_snapshot` must infer `last_move` and SAN via `board_fen()` diff without crashing.
- **Drag-and-drop onto invalid square or outside board:** `resolve_drop` must return `(None, None)` and leave board state unchanged.
- **Drag-and-drop onto promotion square:** Must open `promotion_bubble` rather than silently promoting or losing the move.
- **Clicking `Chơi với Bot` before clicking `Lưu` in bottom Auth bar:** Must enter `bot_setup` immediately using valid typed username or `'Guest'`.

---

### Task 1: Move History & Last-Move Tracking (`Game`, `Controller`, `ChessMatch`)

**Files:**
- Modify: `server/game/chess_match.py:94-104`
- Modify: `client/game/local_board.py:6-41`
- Modify: `client/game/game_controller.py:48-69`
- Test: `tests/test_game.py`, `tests/test_online_controller.py`

**Interfaces:**
- Produces on `Game`: `game.move_history: list[str]`, `game.last_move: chess.Move | None`
- Produces in `MOVE_ACCEPTED`: optional `'uci': str`

- [ ] **Step 1: Write failing tests for `move_history` & `last_move` in `tests/test_game.py` and `tests/test_online_controller.py`**

```python
# In tests/test_game.py
def test_move_history_and_last_move_recorded(self):
    game = Game(chess.WHITE, None)
    game.move(chess.Move.from_uci('e2e4'))
    game.move(chess.Move.from_uci('e7e5'))
    self.assertEqual(game.move_history, ['e4', 'e5'])
    self.assertEqual(game.last_move, chess.Move.from_uci('e7e5'))

# In tests/test_online_controller.py
def test_snapshot_tracks_san_history_with_uci_and_fen_fallback(self):
    c = Controller(chess.WHITE, 5, mode='online')
    c.apply_server_snapshot({'fen': chess.STARTING_FEN, 'revision': 0, 'white_time': 300.0, 'black_time': 300.0, 'game_over': False})
    b1 = chess.Board()
    b1.push_uci('e2e4')
    c.apply_server_snapshot({'fen': b1.fen(), 'revision': 1, 'uci': 'e2e4', 'white_time': 299.0, 'black_time': 300.0, 'game_over': False})
    b1.push_uci('e7e5')
    c.apply_server_snapshot({'fen': b1.fen(), 'revision': 2, 'white_time': 299.0, 'black_time': 298.0, 'game_over': False})
    self.assertEqual(c.game.move_history, ['e4', 'e5'])
    self.assertEqual(c.game.last_move, chess.Move.from_uci('e7e5'))
    c.close()
```

- [ ] **Step 2: Run tests to verify they fail**
Run: `uv run python -m unittest tests/test_game.py tests/test_online_controller.py -v`
Expected: FAIL (`AttributeError: 'Game' object has no attribute 'move_history'`).

- [ ] **Step 3: Implement tracking in `ChessMatch`, `Game`, and `Controller`**
  - In `server/game/chess_match.py`: add `uci=uci_move` to `make_message(MessageType.MOVE_ACCEPTED, ...)` in `apply_move`.
  - In `client/game/local_board.py`: initialize `self.move_history = []` and `self.last_move = None` in `Game.__init__`; in `Game.move`, record `san = board.san(move)` before `board.push(move)`, append `san` to `self.move_history`, and set `self.last_move = move`.
  - In `client/game/game_controller.py`: in `Controller.apply_server_snapshot`, if `revision == 0` or `fen == chess.STARTING_FEN`, reset `game.move_history = []` and `game.last_move = None`. Otherwise, find `move` from `message.get('uci')` (if legal on `prev_board`) or by matching `test_board.board_fen() == new_board.board_fen()` across `prev_board.legal_moves`; if found, append `prev_board.san(move)` to `game.move_history` and set `game.last_move = move`.

- [ ] **Step 4: Run tests to verify they pass**
Run: `uv run python -m unittest tests/test_game.py tests/test_online_controller.py tests/test_server_match.py -v`
Expected: PASS.

---

### Task 2: Bright Green Theme & Dynamic Resizable Layout (`theme.py`, `layout.py`)

**Files:**
- Create: `client/gui/theme.py`
- Create: `client/gui/layout.py`
- Test: `tests/test_ui_layout.py`

**Interfaces:**
- Produces (`theme.py`): color constants (`BG_APP`, `BG_CARD`, `BG_INPUT`, `BORDER`, `BORDER_FOCUS`, `TEXT_PRIMARY`, `TEXT_MUTED`, `BTN_PRIMARY`, `BTN_PRIMARY_HOVER`, `BTN_PRIMARY_PRESS`, `BTN_SECONDARY`, `BTN_SECONDARY_HOVER`, `DANGER`, `SQ_LIGHT`, `SQ_DARK`, `SQ_LAST_LIGHT`, `SQ_LAST_DARK`, `SQ_CHECK`), `get_fonts(scale: float = 1.0) -> dict[str, pygame.font.Font]`, `get_scaled_pieces(square_size: int) -> dict[str, pygame.Surface]`
- Produces (`layout.py`): `MIN_WIDTH = 720`, `MIN_HEIGHT = 560`, `DEFAULT_WIDTH = 960`, `DEFAULT_HEIGHT = 680`, `clamp_window_size(w: int, h: int) -> tuple[int, int]`, `compute_lobby_layout(w: int, h: int) -> dict`, `compute_game_layout(w: int, h: int) -> dict`

- [ ] **Step 1: Write failing tests for `layout.py` in `tests/test_ui_layout.py`**

```python
import unittest
from client.gui.layout import MIN_WIDTH, MIN_HEIGHT, clamp_window_size, compute_game_layout, compute_lobby_layout

class LayoutTests(unittest.TestCase):
    def test_clamp_enforces_minimum(self):
        self.assertEqual(clamp_window_size(400, 300), (MIN_WIDTH, MIN_HEIGHT))
        self.assertEqual(clamp_window_size(1200, 800), (1200, 800))

    def test_game_layout_keeps_board_square_and_equal_edges(self):
        for w, h in ((720, 560), (960, 680), (1440, 900)):
            lay = compute_game_layout(w, h)
            board = lay['board_rect']
            self.assertEqual(board.width, board.height)
            self.assertGreaterEqual(lay['square_size'], 44)
            self.assertEqual(lay['top_bar'].top, lay['sidebar'].top)
            self.assertEqual(lay['bottom_bar'].bottom, lay['sidebar'].bottom)

    def test_lobby_layout_centers_content_and_bottom_auth(self):
        lay = compute_lobby_layout(960, 680)
        self.assertEqual(lay['hero_card'].left, lay['auth_card'].left)
        self.assertEqual(lay['hero_card'].right, lay['auth_card'].right)
        self.assertLess(lay['hero_card'].bottom, lay['auth_card'].top)
```

- [ ] **Step 2: Run test to verify it fails**
Run: `uv run python -m unittest tests/test_ui_layout.py -v`
Expected: FAIL (`ModuleNotFoundError: No module named 'client.gui.layout'`).

- [ ] **Step 3: Implement `client/gui/theme.py` and `client/gui/layout.py`**
  - `theme.py`: Define the brighter green palette from Spec §5.1, cache fonts by rounded scale, and cache `load_pieces(square_size)` by `square_size` using `pygame.transform.scale`.
  - `layout.py`: Implement `clamp_window_size`, `compute_lobby_layout`, and `compute_game_layout` using the exact formulas in Spec §5.2 (`pad=16`, `gap=16`, `sidebar_w`, `bar_h`, `square_size >= 44`).

- [ ] **Step 4: Run test to verify it passes**
Run: `uv run python -m unittest tests/test_ui_layout.py -v`
Expected: PASS.

---

### Task 3: Reusable Widgets & Dynamic Board/HUD (`widgets.py`, `board_view.py`, `hud.py`)

**Files:**
- Create: `client/gui/widgets.py`
- Modify: `client/gui/board_view.py:1-73`
- Modify: `client/gui/hud.py:9-41`
- Test: `tests/test_input.py`

**Interfaces:**
- Produces (`widgets.py`): `draw_card(screen, rect, bg=..., border=..., radius=6)`, `draw_button(screen, rect, text, fonts, primary=False, selected=False, disabled=False, mouse_pos=None, mouse_down=False)`, `draw_text_input(screen, rect, text, placeholder, active, fonts, masked=False, now=0.0)`, `draw_move_list(screen, rect, moves: list[str], fonts, scroll_offset: int) -> int` (returns clamped `scroll_offset`)
- Produces (`board_view.py`): `square_pos(square, player, board_origin=(0, BOARD_TOP), square_size=SIZE)`, `draw_board(screen, game, selected, pieces, only_color=None, board_origin=(0, BOARD_TOP), square_size=SIZE, last_move=None, hidden_square=None, anim_piece=None, drag_piece=None, fonts=None)`

- [ ] **Step 1: Implement `client/gui/widgets.py`**
  - `draw_button`: crisp hover/press (`1px` y-offset when `mouse_down` and hovered), Vietnamese diacritic font selection, text clipping/fitting.
  - `draw_move_list`: 2-column numbered pairs (`1.  e4    e5`), latest move highlighted, `screen.set_clip(rect)` during rendering, returns clamped `scroll_offset`.

- [ ] **Step 2: Update `client/gui/board_view.py` and `client/gui/hud.py`**
  - Add optional `board_origin=(0, BOARD_TOP)` and `square_size=SIZE` to `square_pos`, `promotion_rects`, and `draw_board`.
  - Render `#EEEED2` / `#769656` squares, `last_move` highlight, check red tint on `game.board.king(game.board.turn)` when `game.board.is_check()`, legal move dots/capture rings, `a–h` / `1–8` coordinates, `anim_piece` (interpolated position), and `drag_piece` (`1.08×` scale centered on cursor).
  - Update `draw_players` in `hud.py` with optional `board_rect=None` and `bar_height=PLAYER_BAR_HEIGHT` so it aligns with `compute_game_layout`.

- [ ] **Step 3: Run existing input tests to verify backwards compatibility**
Run: `uv run python -m unittest tests/test_input.py -v`
Expected: PASS.

---

### Task 4: Drag-and-Drop & Click Input (`mouse_controller.py`)

**Files:**
- Modify: `client/input/mouse_controller.py:6-45`
- Test: `tests/test_input.py`

**Interfaces:**
- Produces: `square_at(pos, player, board_origin=(0, BOARD_TOP), square_size=SIZE) -> int | None`
- Produces: `select_square(pos, controller, selected, board_origin=(0, BOARD_TOP), square_size=SIZE)`
- Produces: `resolve_drop(from_sq, pos, controller, board_origin=(0, BOARD_TOP), square_size=SIZE) -> tuple[tuple[int, int] | None, str | None]`

- [ ] **Step 1: Write failing tests for dynamic `board_origin`/`square_size` and `resolve_drop` in `tests/test_input.py`**

```python
def test_resolve_drop_valid_invalid_and_promotion(self):
    controller = Controller(chess.WHITE, None, mode='local')
    origin, sq_size = (20, 60), 64
    e2_pos = (origin[0] + 4 * sq_size + 10, origin[1] + 6 * sq_size + 10)
    self.assertEqual(square_at(e2_pos, chess.WHITE, origin, sq_size), chess.E2)
    e4_pos = (origin[0] + 4 * sq_size + 10, origin[1] + 4 * sq_size + 10)
    promo, sound = resolve_drop(chess.E2, e4_pos, controller, origin, sq_size)
    self.assertIsNone(promo)
    self.assertEqual(sound, 'move-self')
    # Invalid drop outside board
    self.assertEqual(resolve_drop(chess.D2, (0, 0), controller, origin, sq_size), (None, None))
```

- [ ] **Step 2: Run test to verify it fails**
Run: `uv run python -m unittest tests/test_input.py -v`
Expected: FAIL (`ImportError: cannot import name 'resolve_drop'`).

- [ ] **Step 3: Implement dynamic parameters and `resolve_drop` in `client/input/mouse_controller.py`**

- [ ] **Step 4: Run test to verify it passes**
Run: `uv run python -m unittest tests/test_input.py -v`
Expected: PASS.

---

### Task 5: Screen Renderers & Main Loop Integration (`screens.py`, `client/main.py`)

**Files:**
- Create: `client/gui/screens.py`
- Modify: `client/main.py:43-683`

**Interfaces:**
- Consumes: `theme.py`, `layout.py`, `widgets.py`, `board_view.py`, `hud.py`, `mouse_controller.py`
- Produces: Complete resizable Pygame UI with merged `menu` + bottom Auth, unified Vietnamese `bot_setup`, `online_menu`, `join_input`, `waiting`, and `game` (drag-and-drop, ~110ms slide animation, scrollable move list, mode-aware sidebar buttons).

- [ ] **Step 1: Implement `client/gui/screens.py`**
  - Pure draw functions returning hit-rects for `menu` (with bottom Auth bar + Register modal), `bot_setup` (single card), `online_menu`, `join_input`, `waiting`, and `game` sidebar.

- [ ] **Step 2: Refactor `client/main.py`**
  - Initialize `pygame.display.set_mode((DEFAULT_WIDTH, DEFAULT_HEIGHT), pygame.RESIZABLE)`.
  - Handle `VIDEORESIZE` with `clamp_window_size`.
  - Launch directly in `state = 'menu'` with default `Guest` session; wire `Chơi với Bot` (immediate) and `Chơi Online` (auto-auth if needed).
  - Wire `drag_state` (`> 5px` threshold), `MOUSEWHEEL` on move list, ~110ms `slide_anim` (skipped on manual drop), and mode-aware `game` buttons (`Chơi lại / Cài đặt`, `Về sảnh chính`, `Đầu hàng` / `Rời phòng`).

- [ ] **Step 3: Run full test suite & smoke-test `python main.py`**
Run: `uv run python -m unittest discover -s tests -v`
Expected: All unit/integration tests PASS.
