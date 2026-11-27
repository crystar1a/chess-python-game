# TCP reconnect implementation plan

**Goal:** Tự động khôi phục ván trong 60 giây và xác nhận đầu hàng khi rời phòng.

**Architecture:** Server quản lý token riêng, hạn reconnect và snapshot có thẩm quyền; client xử lý heartbeat, reconnect và đồng bộ ngoài luồng giao diện.

**Tech stack:** Python socket, threading, queue, pygame, python-chess.

**Spec:** `docs/superpowers/specs/2026-11-27-reconnect-design.md`.

## Công việc

1. `server/rooms.py`, `server/game/chess_match.py`, `tests/test_server_match.py`: kiểm thử và triển khai token riêng, RESUME, hạn 60 giây, đồng hồ, kết quả khi hai bên ngắt và lịch sử nước đi; xử lý RESIGN và dọn phòng sau khi gửi kết quả.
2. `server/net/tcp_server.py`, `client/net/tcp_client.py`, `tests/test_network.py`: kiểm thử và triển khai heartbeat 3/12 giây, đóng socket hết hạn không làm hỏng frame, sự kiện ngắt và tự động reconnect.
3. `client/main.py`, `client/game/game_controller.py`, `client/gui/`, `tests/test_online_controller.py`: tích hợp snapshot đầy đủ, khóa nước khi reconnect và hiển thị trạng thái, xác nhận rời phòng và kết quả.
4. Chạy toàn bộ unittest và kiểm thử TCP hai client với ngắt mạng, reconnect, nước đi chưa nhận xác nhận, hết hạn và đầu hàng; cập nhật plan theo bằng chứng.
5. Bổ sung **Kết nối lại** trong Chơi Online → Vào phòng cho trường hợp mở lại ứng dụng: lưu và lấy token phiên riêng cùng thông tin phòng/server bằng cơ chế cục bộ được bảo vệ; xử lý thiếu phiên, sai token và hết hạn. Kiểm thử hai client trên cùng máy, đóng một client rồi mở lại và khôi phục đúng người chơi. Mã phòng hoặc tên khách không đủ để xác thực phiên.

Không commit hoặc push. Giữ thay đổi hiện có. Không lưu token vào log.
