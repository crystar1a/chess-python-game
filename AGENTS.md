# AGENTS.md — Quy ước hợp tác giữa Claude Code và Codex CLI

Dự án: Pixel Chess bot (Python, pygame-ce + python-chess)

Hai agent làm việc trên cùng repository `E:\chess_game`, mỗi agent phụ trách một miền code riêng. File này là bảng điều phối chung — cả hai đều đọc trước khi bắt đầu tác vụ mới.

---

## 1. Phân công trách nhiệm

### Claude Code — UI / Giao diện (frontend)

Miền sở hữu:
- `client/gui/` — `board_view.py`, `hud.py`, `resources.py` (vẽ bàn cờ, pieces, HUD, tải âm thanh/hình ảnh/font)
- `client/input/` — `mouse_controller.py` (xử lý input chuột, click ô cờ, kéo quân)
- `assets/` — hình ảnh quân cờ, font, âm thanh
- `main.py` — điểm khởi chạy ứng dụng (gọi `client.main.run()`)

Nhiệm vụ của Claude:
- Xây dựng và duy trì giao diện pygame: bảng cờ, hiển thị quân, hiệu ứng di chuyển, thông báo thua/thắng, âm thanh.
- Xử lý sự kiện chuột và chuyển thành "ý định đi cờ" (từ ô A đến ô B) rồi đẩy vào lớp logic qua interface đã định sẵn.
- Không sửa code trong `client/game/` hoặc `client/ai/` trừ khi Codex yêu cầu thay đổi interface.

### Codex CLI — Logic / Motor cờ (backend)

Miền sở hữu:
- `client/game/` — `local_board.py`, `game_controller.py` (quản lý trạng thái bàn cờ, luật cờ, validate nước đi, kết thúc ván)
- `client/ai/` — `stockfish.py` (kết nối Stockfish engine, gọi bestmove)
- Tích hợp thư viện `python-chess`, `stockfish` (binary)

Nhiệm vụ của Codex:
- Triển khai luồng chơi cờ: khởi tạo bàn, kiểm tra nước đi hợp lệ, áp dụng nước đi, phát hiện chiếu/chan/bất, kết thúc ván.
- Giao tiếp Stockfish để lấy nước đi máy, trả về nước đi cho UI hiển thị.
- Không sửa code trong `client/gui/` hoặc `client/input/` trừ khi Claude yêu cầu thay đổi interface.

---

## 2. Giao tiếp giữa hai miền (interface)

Điểm giao nhau là `client/main.py` (hàm `run()`) và các lớp trung gian:
- UI gọi `game_controller.apply_move(from_square, to_square)` → nhận về kết quả thành công/thất bại + trạng thái ván.
- UI gọi `ai.stockfish.get_best_move(board)` → nhận về nước đi gợi ý của máy.
- Logic không gọi trực tiếp hàm vẽ pygame; nó chỉ cung cấp dữ liệu trạng thái, UI tự quyết định cách render.

Khi cần thay đổi interface, agent yêu cầu thay đổi phải cập nhật `AGENTS.md` và thông báo agent kia trước khi viết code.

---

## 3. Quy ước làm việc chung

1. **Chọn nhánh theo phạm vi thay đổi**
   - Thay đổi nhỏ, ít rủi ro (như sửa lỗi chính tả hoặc tài liệu đơn giản) có thể commit và push trực tiếp lên `main` khi được yêu cầu.
   - Thay đổi logic hoặc giao diện lớn, có rủi ro hoặc cần phối hợp dùng nhánh riêng: `claude-ui-<tinh-nang>` cho Claude Code, `codex-logic-<tinh-nang>` cho Codex CLI. Mở Pull Request để review trước khi merge.
   - Tuân thủ bảo vệ nhánh và yêu cầu cụ thể của người dùng; khi không rõ mức rủi ro, dùng nhánh riêng và Pull Request.

2. **Không cùng sửa một file**
   - Mỗi file trong `AGENTS.md` chỉ có một chủ sở hữu. Nếu agent kia cần sửa, hãy gửi yêu cầu qua PR/comment.

3. **Đừng sửa code của người khác**
   - Claude không đụng code của `client/game/` và `client/ai/` trừ khi được phép.
   - Codex không đụng code của `client/gui/` và `client/input/` trừ khi được phép.

4. **Cập nhật AGENTS.md khi phân công thay đổi**
   - Nếu quyền sở hữu thay đổi, chỉnh sửa file này và commit kèm code.

5. **Tuân theo CLAUDE.md**
   - Cách viết code, commit message, tính đơn giản, goal-driven execution đều áp dụng cho cả hai agent.

---

## 4. Cách chạy dự án

```powershell
# Tạo virtual environment (nếu chưa có)
uv sync

# Chạy game
python main.py
```

Hoặc kích hoạt `.venv` trước rồi chạy `python main.py`.

---

## 5. Trạng thái hiện tại (cập nhật thường xuyên)

| Miền | Agent | File sở hữu | Trạng thái |
|------|-------|-------------|------------|
| UI / Giao diện | Claude Code | `client/gui/*`, `client/input/*`, `assets/*`, `main.py` | Sẵn sàng |
| Logic / Motor cờ | Codex CLI | `client/game/*`, `client/ai/*` | Sẵn sàng |

---

## 6. Quy tắc sử dụng git worktree

- Mỗi agent chỉ làm việc trong worktree của mình, không đổi branch của thư mục khác.
- Thư mục gốc `E:\chess_game` được giữ tại `main`, không làm việc trực tiếp ở đây.
- Claude Code: `E:\chess_game-claude`, branch `claude-ui-*`.
- Codex CLI: `E:\chess_game-codex`, branch `codex-logic-*`.
- Một branch chỉ có thể checkout tại một worktree một lúc.
- Trước khi chuyển branch hoặc tạo worktree mới, phải commit hoặc stash tất cả thay đổi chưa commit.

---

## 7. Quy ước bàn giao chéo (Handoff Message)

Sau khi hoàn thành một phiên làm việc, mỗi agent phải ghi/cập nhật file bàn giao trực tiếp vào thư mục worktree của agent còn lại (các file `message_to_*.md` đã được `.gitignore` bỏ qua, không commit vào git):

- **Claude Code** (tại `E:\chess_game-claude`) → ghi vào `E:\chess_game-codex\message_to_codex.md`
- **Codex CLI** (tại `E:\chess_game-codex`) → ghi vào `E:\chess_game-claude\message_to_claude.md`

### Quy trình bắt buộc ở đầu và cuối mỗi phiên

1. **Đầu phiên (Kiểm tra & chống outdated):**
   - Đọc file `message_to_<tên_mình>.md` trong worktree hiện tại (nếu có).
   - Đối chiếu nội dung trong file (thời gian, branch, commit hash, tên hàm/interface, payload) với `git status`, `git log -n 5 --oneline`, `origin/main` và mã nguồn thực tế. Nếu thấy lệch hoặc cũ hơn code hiện tại, ưu tiên sự thật trong code/git và ghi chú lại.
2. **Cuối phiên (Ghi bàn giao):**
   - Ghi đè/cập nhật file `message_to_<agent_kia>.md` trong worktree của agent kia với đầy đủ: thời gian, worktree, branch, commit hash, danh sách file đã sửa, thay đổi interface/payload (nếu có), kết quả kiểm thử, và việc tiếp theo đề xuất.

---

_Người viết: Claude Code (dành cho cả Claude Code và Codex CLI). Sửa khi cần thiết._
