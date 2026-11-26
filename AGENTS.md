# AGENTS.md — Quy ước làm việc

Dự án Pixel Chess dùng Python, pygame-ce và python-chess.

- Làm việc trong `E:\chess_game` trên nhánh `main`, dựa trên `origin/main`. Không cần worktree hoặc phân chia quyền sở hữu theo agent.
- Một agent có thể sửa cả giao diện, logic, mạng và server theo phạm vi nhiệm vụ. Giữ ranh giới kiến trúc: logic cung cấp trạng thái, giao diện chịu trách nhiệm render.
- Giữ quy trình viết kế hoạch cho công việc cần kế hoạch; lưu spec và plan trong `docs/superpowers/`.
- Tuân theo `CLAUDE.md`; bảo toàn thay đổi chưa commit và không tự ý commit hoặc push.
- Online: UI truyền `GAME_START` hoặc `MOVE_ACCEPTED` vào `Controller.apply_server_snapshot(message)`; callback `on_online_move_intent(uci, expected_revision)` gửi `MOVE_REQUEST` với revision tương ứng.

## Chạy dự án

```powershell
uv sync
python main.py
```
