# Kế hoạch phát triển Pixel Chess

## Mục tiêu

Xây dựng trò chơi cờ vua Pixel Chess bằng Python và Pygame; dùng `python-chess` xử lý luật, Stockfish làm đối thủ và `pygame.mixer` phát âm thanh. Tổ chức theo kiến trúc client–server, phân lớp trong từng phía. Hoàn thiện bản chơi với bot trên một máy trước để làm cơ sở cập nhật TCD và UCD, sau đó triển khai chế độ chơi qua mạng bằng `socket` và `threading` thuần của Python.

Người chơi chọn chơi với bot, sau đó chọn độ khó Easy, Normal hoặc Hard, rồi chọn thời gian và màu quân trước ván; bot cầm quân còn lại và quân trắng đi trước. Chọn quân và ô đích bằng chuột, dùng luật cờ vua tiêu chuẩn.

## Tiêu chí thiết kế: "Avoid Code Bloated"

Giữ code dễ đọc, dễ bảo trì và tránh phình to khi xây dựng thêm chức năng. Áp dụng kiến trúc phân lớp đã chọn, phân chia trách nhiệm rõ ràng và tận dụng thư viện chuẩn (`socket`, `threading`, `struct`, `json`, `queue`) cùng Pygame, `python-chess` và Stockfish. Chỉ thêm abstraction, cấu hình hoặc tính năng khi có nhu cầu cụ thể; tránh trùng lặp và độ phức tạp không cần thiết.

## Công nghệ và tài nguyên

- Khai báo `pygame-ce` và `python-chess` trong `requirements.txt`; dùng `pygame-ce` tương thích Python 3.14 (import qua `pygame`).
- Stockfish là chương trình UCI riêng, được nạp từ thư mục `client/ai/stockfish/`; ưu tiên adapter UCI hiện có của `python-chess` để tránh phụ thuộc trùng lặp.
- Nguồn ảnh `assets/` có 12 ảnh quân `wp, wn, wb, wr, wq, wk, bp, bn, bb, br, bq, bk` và `original.png`.
- Thư mục `assets/sounds/` có các tệp MP3: `capture`, `castle`, `game-end`, `game-start`, `move-check`, `move-opponent`, `move-self`, `notify`, `promote` và `tenseconds`. Trò chơi vẫn chạy bình thường khi thiếu âm thanh hoặc thiếu engine local.

## Kiến trúc client–server

Cấu trúc mục tiêu giữ ở mức tối giản (chỉ bổ sung đúng 5 tệp mạng khi triển khai online). Giai đoạn hiện tại lưu trữ phòng, phiên và `token` trực tiếp trên bộ nhớ RAM (`dict` bảo vệ bởi `threading.RLock`); cơ sở dữ liệu SQLite và đóng gói Docker sẽ tích hợp ở giai đoạn sau.

```text
chess_online/
├── client/
│   ├── main.py
│   ├── gui/
│   │   ├── board_view.py
│   │   ├── hud.py
│   │   └── resources.py
│   ├── input/
│   │   └── mouse_controller.py
│   ├── game/
│   │   ├── local_board.py
│   │   └── game_controller.py
│   ├── ai/
│   │   └── stockfish.py
│   └── net/
│       ├── tcp_client.py
│       └── udp_client.py
├── server/
│   ├── main.py
│   ├── app.py
│   ├── rooms.py
│   ├── game/
│   │   ├── chess_match.py
│   │   └── rules.py
│   └── net/
│       ├── tcp_server.py
│       └── udp_server.py
├── shared/
│   └── protocol.py
├── tests/
├── assets/
│   ├── pieces/
│   ├── sounds/
│   └── fonts/
├── requirements.txt
└── README.md
```

- **Client**: `main.py` khởi tạo ứng dụng; `gui/` vẽ, quản lý tài nguyên và âm thanh; `input/` xử lý chuột; `game/` điều phối thông qua `GameController`; `ai/` tích hợp Stockfish cho chế độ bot; `net/` quản lý kết nối `tcp_client.py` và `udp_client.py` đẩy sự kiện qua `queue.Queue` để không chặn vòng lặp Pygame.
- **Server**: `app.py` điều phối dịch vụ; `rooms.py` quản lý phòng và phiên người chơi trên RAM; `server/game/` dùng `python-chess` làm nguồn sự thật duy nhất (Server-Authoritative) để kiểm tra lượt, nước đi, đồng hồ và kết quả; `server/net/` xử lý socket TCP và UDP đa luồng.
- **Shared**: `shared/protocol.py` định nghĩa framing 4-byte big-endian (`!I`) + JSON UTF-8 và toàn bộ cấu trúc gói tin dùng chung.

## Thiết kế bản chơi với bot

1. Khởi tạo `pygame-ce`; khi chọn chơi với bot, cho chọn độ khó **Easy (3 ply)**, **Normal (8 ply)** hoặc **Hard (15 ply)**, sau đó chọn thời gian 5, 10, 15 phút hoặc không tính thời gian và màu trắng hoặc đen, rồi bắt đầu ván. Cả engine local và REST API dùng chung bộ độ sâu này. Vẽ bàn cờ 8×8, scale ảnh quân theo ô và đặt quân của người chơi ở phía dưới.
2. Chọn quân của người chơi bằng chuột và đánh dấu các ô đích hợp lệ. Quân trắng đi trước; nếu người chơi chọn đen, bot đi nước đầu. Chỉ thực hiện nước đi được `python-chess` xác nhận; bỏ qua thao tác ngoài bàn cờ và nước sai.
3. Khi phong cấp, cho chọn hậu, xe, tượng hoặc mã trước khi gửi nước đi. Hiển thị lượt và kết quả ván.
4. Gửi bản sao vị trí cho Stockfish với giới hạn độ sâu đã chọn. Chạy tác vụ engine ngoài vòng lặp giao diện; khóa nước đi của người chơi khi chờ. Kiểm tra kết quả engine hợp lệ và còn thuộc ván hiện tại.
5. Tích hợp các tệp trong `assets/sounds/` cho sự kiện tương ứng. Nếu mixer hoặc tệp âm thanh lỗi, thông báo hợp lý và tiếp tục không âm thanh.
6. Khi thiếu engine local, gọi `stockfish.online` qua HTTPS GET với API key tùy chọn trong `client/ai/stockfish/api.txt` (tự động lùi về chế độ khách nếu gặp HTTP 401/403).
7. Hiển thị chiếu hết, hết nước đi và hòa. Bản nháp có thể tự nhận hòa khi `python-chess` xác định có quyền yêu cầu hòa.
8. Với ván có tính giờ, mỗi bên có thời gian riêng bằng mức đã chọn, không cộng thêm thời gian sau nước đi. Hết giờ thì bên hết giờ thua, trừ khi đối thủ không thể chiếu hết bằng bất kỳ chuỗi nước đi hợp lệ nào thì ván hòa.

## Các bước thực hiện

- [x] Khảo sát dự án nguồn, các tệp âm thanh hiện có, Stockfish và môi trường Python.
- [x] Chuyển mã từ `src/` sang cấu trúc `client/` theo trách nhiệm trên; cập nhật điểm vào, import và kiểm thử.
- [x] Tạo cấu trúc tối thiểu, dependencies và hướng dẫn chạy; đưa asset vào dự án.
- [x] Xây lớp quản lý ván dựa trên `python-chess`; đã có kiểm thử cơ bản cho nước hợp lệ và không hợp lệ.
- [x] Thống nhất độ sâu tìm kiếm Easy 3, Normal 8, Hard 15 cho cả local và REST API (14/14 unit test đạt).
- [ ] Hoàn thiện và kiểm thử menu, bàn cờ và phong cấp: kiểm thử đầy đủ luồng chọn chế độ, màu quân, thời gian và 4 lựa chọn phong cấp.
- [ ] Hoàn thiện đồng hồ: bao phủ đầy đủ các thế cờ không thể chiếu hết khi một bên hết giờ.
- [ ] Kiểm thử đầy đủ tích hợp Stockfish bất đồng bộ, `pygame.mixer` và dọn tiến trình khi đóng hoặc bắt đầu lại ván.
- [ ] Cập nhật TCD và UCD sau khi bản bot đạt tiêu chí. Triển khai và kiểm thử chế độ chơi mạng theo 4 bước bên dưới.

## Định hướng TCP và UDP (4 Bước triển khai)

Sử dụng thư viện chuẩn `socket` + `threading` (`ThreadPoolExecutor` cho các kết nối TCP client, `threading.RLock` bảo vệ trạng thái phòng trên RAM, `queue.Queue` giao tiếp giữa luồng mạng và luồng Pygame).

1. [ ] **Bước 1 — Tách lớp Controller & Khóa chuẩn Framing (Nền tảng):**
   - Đưa toàn bộ thao tác đi quân và phong cấp qua `GameController` (chế độ local áp dụng cục bộ; chế độ online phát `MOVE_REQUEST` dạng UCI và chỉ cập nhật bàn cờ khi nhận xác nhận từ server).
   - Xây dựng `shared/protocol.py` dùng **Length-Prefix Framing 4-byte big-endian (`!I`) + JSON UTF-8** (`MAX_FRAME = 65536`) và bộ kiểm thử `tests/test_network.py` cho trường hợp cắt nhỏ gói tin (fragmentation) và dính nhiều gói (coalescing).
2. [ ] **Bước 2 — Lõi TCP 1v1 trên Localhost (Cổng 8765):**
   - Cài đặt `tcp_server.py` và `tcp_client.py` bằng `socket` + `threading`.
   - Server giữ `python-chess.Board` duy nhất trong `ChessMatch`, kiểm tra lượt, nước đi hợp lệ, tăng `revision` sau mỗi nước đi (`MOVE_REQUEST` gửi kèm `expected_revision`).
   - Đồng hồ tính trên server bằng `time.monotonic()`, gửi kèm thời gian còn lại qua TCP trong `GAME_START` và `MOVE_ACCEPTED`; client tự đếm ngược hiển thị giữa hai nước đi. Chơi trọn một ván PvP qua localhost với phòng tạo bằng mã.
3. [ ] **Bước 3 — Khôi phục phiên qua TCP (Reconnect 60 giây):**
   - Bổ sung heartbeat TCP (`PING`/`PONG` mỗi 3s), tự động đóng socket chết nếu quá 12s không phản hồi.
   - Giữ trạng thái phòng và `token` trên RAM trong 60 giây khi người chơi mất kết nối (đồng hồ vẫn chạy; quá 60s xử thua). Khi nối lại bằng `RESUME` + `token`, server trả về toàn bộ trạng thái hiện tại (màu quân, FEN, nước cuối, đồng hồ, `revision`).
4. [ ] **Bước 4 — Dò phòng LAN & Đo độ trễ qua UDP (Cổng 9999) + Giao diện Online:**
   - Cài đặt `udp_server.py` và `udp_client.py`: hỗ trợ gửi broadcast `DISCOVER` (`255.255.255.255:9999`) để tìm phòng đang mở trong mạng LAN (vẫn giữ tùy chọn nhập `IP:port` thủ công) và gói UDP `PING`/`PONG` đo độ trễ (RTT) hiển thị trên HUD.
   - Bổ sung menu Online tối giản trong Pygame (Tạo phòng, Danh sách phòng LAN, Nhập IP/Mã phòng).

*(Ghi chú giai đoạn sau: Lưu lịch sử ván PGN vào SQLite, xác thực tài khoản và đóng gói Docker sẽ thực hiện sau khi hoàn tất 4 bước mạng cốt lõi trên.)*