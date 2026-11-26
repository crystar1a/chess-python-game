# Login / Register & Guest Identity Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development or superpowers:executing-plans. Steps use checkboxes for tracking.

**Goal:** Cho phép người chơi dùng Guest hoặc tài khoản, giữ danh tính trong phiên và hiển thị tên trong trận.

**Architecture:** SQLite và AuthService quản lý tài khoản, token và xác thực theo kết nối TCP hiện có. Client thực hiện kết nối trong worker, xử lý kết quả trên vòng lặp pygame và xác thực lại trước khi gửi yêu cầu phòng.

**Tech Stack:** Python, sqlite3, hashlib, hmac, secrets, threading, pygame-ce, python-chess.

**Spec:** `docs/superpowers/specs/2026-11-27-login-register-design.md` (draft; cần được duyệt trước khi triển khai).

## Global Constraints

- Không thêm dependency; giữ framing JSON `!I`, `MAX_FRAME = 65536`.
- Username strip, 3–20 ký tự ASCII `[A-Za-z0-9_.-]`, duy nhất không phân biệt hoa thường; giữ nguyên casing hiển thị. Password tối thiểu 4 ký tự, không strip.
- Không lưu mật khẩu rõ hoặc credential client trên đĩa; token chỉ tồn tại trong RAM server/client.
- Guest offline chơi bot được; password submit khi offline phải báo lỗi, không chuyển thành Guest.
- Không chặn vòng lặp 60 FPS bằng connect, nhận dữ liệu hay chờ worker; timeout kết nối 1.5 giây và cần deadline phản hồi hữu hạn.
- Một agent thực hiện cả giao diện và backend; giữ ranh giới kiến trúc và tương thích interface.
- Thực hiện trong `E:\chess_game` trên `main`; không tự commit/push nếu chưa được yêu cầu.

## Review Focus

- Hai đăng ký cùng username khác casing: chỉ một thành công (Task 1).
- Sai kiểu hoặc thiếu trường trong thông điệp: trả lỗi, server không crash (Task 2).
- Server chấp nhận kết nối nhưng không trả lời: UI vẫn phản hồi và báo timeout (Task 3–4).
- Token bị mất sau server restart hoặc tên Guest bị đăng ký sau đó: quay lại auth, không gửi yêu cầu phòng (Task 4).
- Phản hồi cũ đến sau Cancel/Switch Account: không thay đổi phiên mới hoặc gửi yêu cầu phòng (Task 4).

## Cấu trúc file

- `server/auth.py`: lưu trữ SQLite, xác thực và token; `server/main.py`: vòng đời service dùng chung.
- `shared/protocol.py`, `server/rooms.py`: loại thông điệp, định tuyến xác thực và tên hai bên.
- `client/net/tcp_client.py`: timeout kết nối; `client/main.py`: điều phối trạng thái và worker; `client/gui/hud.py`: tên người chơi do Claude thực hiện.
- `tests/test_auth.py`, `tests/test_network.py`, `tests/test_server_match.py`, các kiểm thử client phù hợp: kiểm chứng từng lớp; `.gitignore`: bỏ qua database runtime.

### Task 1: Lưu tài khoản và phiên server

**Files:** Create `server/auth.py`, `tests/test_auth.py`; modify `.gitignore`, `server/main.py`.

**Interfaces:** `UserStore(db_path='server/data/chess.db')`; `AuthService(store)` với `check_guest(username)`, `submit_login_or_probe(username, password)`, `register(username, password)`, `verify_token(token)`; ba thao tác đầu trả dict có `status` và các trường `username`, `token` khi cần, verify trả `str | None`.

- [ ] Viết test dùng database tạm: giới hạn username/password, trim và casing, Guest trùng tên, mật khẩu sai, token hợp lệ/không hợp lệ; hai thread đăng ký cùng tên khác casing chỉ có một thành công; kiểm tra database không chứa password rõ và salt khác nhau.
- [ ] Chạy `uv run pytest tests/test_auth.py -v`, xác nhận fail vì module chưa tồn tại.
- [ ] Tạo schema như spec, khóa SQLite/thread phù hợp, PBKDF2-HMAC-SHA256 200.000 vòng với salt 16 byte và `hmac.compare_digest`; xử lý unique constraint nguyên tử. Tạo service duy nhất cho server, đóng tài nguyên khi dừng; ignore `server/data/*.db`.
- [ ] Chạy lại test trên, xác nhận pass; kiểm tra `:memory:` hoạt động qua nhiều lần gọi và thread.

### Task 2: Protocol và danh tính phòng

**Files:** Modify `shared/protocol.py`, `server/rooms.py`, `server/main.py`; test `tests/test_network.py`, `tests/test_server_match.py`.

**Interfaces:** `RoomManager(auth_service=None)`; các message `AUTH_GUEST`, `AUTH_SUBMIT`, `AUTH_REGISTER`, `AUTH_TOKEN`, `AUTH_OK`, `AUTH_NEEDS_REGISTER`, `AUTH_ERROR` có payload chính xác theo spec. `GAME_START` bổ sung `white_name`, `black_name`.

- [ ] Viết test framing round-trip cho các message; routing từng kết quả auth, payload thiếu/sai kiểu, token không hợp lệ, cleanup khi disconnect; test hai tên theo đúng màu và fallback `White`/`Black` cho kết nối legacy.
- [ ] Chạy `uv run pytest tests/test_network.py tests/test_server_match.py -v`, xác nhận test mới fail.
- [ ] Thêm enum và routing; ánh xạ status sang reason theo spec, lưu identity theo conn_id chỉ khi AUTH_OK. Dùng cùng service cho tất cả kết nối; giữ luồng phòng legacy tương thích, không tạo database mới cho mỗi message.
- [ ] Chạy lại hai file test; xác nhận pass và các test phòng hiện hữu không hồi quy.

### Task 3: Kết nối có timeout và không chặn UI

**Files:** Modify `client/net/tcp_client.py`; test `tests/test_network.py`.

**Interfaces:** `TCPClient(host, port=DEFAULT_TCP_PORT, timeout=None)` giữ hành vi mặc định; `send`, `poll_messages`, `close` giữ interface hiện tại.

- [ ] Viết test mock socket xác nhận timeout được áp dụng lúc connect, được reset về `None` trước receiver, và lỗi connect được chuyển cho caller; test đóng socket khi lỗi.
- [ ] Chạy `uv run pytest tests/test_network.py -v`, xác nhận test mới fail.
- [ ] Thêm timeout và cleanup; mọi lời gọi connect từ UI mới phải chạy trong worker, không chạy trực tiếp trong pygame loop. Thiết lập deadline phản hồi ở bộ điều phối Task 4.
- [ ] Chạy lại test, xác nhận pass.

### Task 4: Luồng auth và xác thực lại trước phòng

**Files:** Modify `client/main.py`; thêm test điều phối phù hợp trong `tests/`.

**Interfaces:** Session gồm `username`, `is_guest`, `token`, `offline_guest`; các request dùng message của Task 2. Mỗi thao tác bất đồng bộ mang generation ID để bỏ kết quả cũ; chỉ pygame thread cập nhật state.

- [ ] Viết test với fake transport/clock: Guest online/offline, password offline báo lỗi, login đúng/sai, probe cần đăng ký, modal cancel/mismatch/register, timeout phản hồi, switch account khi request đang chạy, token hết hiệu lực và tên Guest bị chiếm. Khẳng định không gửi CREATE_ROOM/JOIN_ROOM trước AUTH_OK.
- [ ] Chạy test mới, xác nhận fail; tách điều phối thành helper có thể test nếu cần, không chuyển logic vẽ sang backend.
- [ ] Khởi tạo state `auth`; worker connect timeout 1.5 giây, poll kết quả và deadline trong loop; đóng socket auth tạm sau thành công. Với Guest offline kiểm tra username local trước khi vào menu; password offline giữ nguyên auth và hiển thị lỗi.
- [ ] Thực hiện form, modal, keyboard Tab/Enter/Esc, masked password, trạng thái đang kiểm tra, lỗi theo spec; xóa password khi hoàn tất/hủy phiên. Menu hiển thị identity và Switch Account.
- [ ] Khi vào online, tạo socket mới và gửi AUTH_TOKEN hoặc AUTH_GUEST; chờ AUTH_OK trước thao tác phòng, xử lý invalid token/tên đã đăng ký bằng cách trở về auth; hủy và đóng socket khi điều hướng hoặc đổi tài khoản.
- [ ] Chạy test mới và `uv run pytest tests/test_network.py -v`, xác nhận pass. Kiểm tra thủ công UI vẫn đáp ứng khi server treo và khi server offline.

### Task 5: Tên người chơi trên HUD và nghiệm thu

**Files:** `client/gui/hud.py`, `client/main.py`, test HUD/client liên quan.

**Interfaces:** `draw_players(screen, game, pieces, font, small, clock_font, difficulty, stopped=False, player_name='You', opponent_name='Opponent')`; mặc định giữ tương thích.

- [ ] Viết test gọi HUD bằng signature cũ và mới, kiểm tra tên dài được cắt gọn; test map tên GAME_START theo màu local, bot hiển thị `Bot`.
- [ ] Chạy test mới và xác nhận fail; triển khai hiển thị và truyền tên, không đổi hành vi vẽ còn lại.
- [ ] Chạy `uv run pytest -q`; xác nhận toàn bộ pass. Chạy game và server, kiểm tra Guest offline → bot, register/login, hai client online thấy đúng tên, restart server làm token cũ hết hiệu lực, logout và đăng nhập lại.
- [ ] Ghi lại kết quả và giới hạn; chỉ commit hoặc tạo PR khi được yêu cầu.
