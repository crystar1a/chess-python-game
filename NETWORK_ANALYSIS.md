# Phân tích cấu trúc Network Programming (TCP + UDP) — Pixel Chess

**Dự án:** Pixel Chess — Cờ vua trực tuyến đa luồng  
**Ngôn ngữ:** Python 3.10+ + Tkinter  
**Thư viện cờ:** `python-chess` 1.11.2 (vendor/)  
**Cơ sở dữ liệu:** SQLite (`data/chess.db`)  
**Mã nguồn mạng:** `chessnet/` (`server.py`, `client.py`, `protocol.py`, `storage.py`, `gui.py`)  
**Điểm vào:** `app.py` (`--server` để chạy máy chủ, mặc định chạy client GUI)  
**Tài liệu tham khảo:** `README.md`, `tests/test_network.py` (14/14 test đạt)

---

## 1. Tổng quan kiến trúc mạng

Ứng dụng chia rõ ràng hai lớp vận chuyển song song trên một GameServer:

| Tính năng | Giao thức | Cổng mặc định | Đặc điểm |
|-----------|-----------|---------------|----------|
| Đăng nhập / Đăng ký | TCP | 8765 | Độ tin cậy, toàn vẹn dữ liệu, mã hóa PBKDF2 |
| Nước cờ & đồng bộ FEN | TCP | 8765 | Server-Authoritative, kiểm tra luật FIDE |
| Chat văn bản trong phòng | TCP | 8765 | Thứ tự tin nhắn, không thất lạc |
| Lịch sử ván đấu / PGN | TCP | 8765 | Truy vấn SQLite |
| Khôi phục phiên (reconnect 60s) | TCP | 8765 | Tái kết nối sau mất kết nối |
| Dò tìm server LAN | UDP | 9999 | Broadcast `255.255.255.255:9999` |
| Đồng hồ đếm ngược | UDP + TCP | UDP 9999 + TCP 8765 | UDP phát 5Hz (0.2s), TCP chốt chặn 2s |
| Thả biểu cảm Emoji | UDP | 9999 | Tốc độ cao, có rate-limit |

### Luồng xử lý (Concurrency model)

`GameServer.start()` khởi tạo **hai socket** (TCP `SOCK_STREAM`, UDP `SOCK_DGRAM`) rồi chạy 3 vòng lặp nền trong các daemon thread:

1. `accept_loop` — lắng nghe TCP, chấp nhận kết nối mới, phân công mỗi client vào `ThreadPoolExecutor` (tối đa 128 worker, tên thread `chess-client`).
2. `udp_loop` — lắng nghe UDP, xử lý DISCOVER/REGISTER/EMOJI.
3. `clock_loop` — chạy mỗi 0.2s: cập nhật đồng hồ, broadcast CLOCK qua UDP (mượt) và TCP (dự phòng mỗi 2s), xử lý timeout kết nối (>12s shutdown socket), xử lý hết hạn reconnect (>60s), dọn phòng đã xong (>300s).

Mỗi client được giữ trong `Session` (token, socket, ip, địa chỉ UDP, phòng, trạng thái disconnect, lock gửi). Tất cả truy cập trạng thái chung được bảo vệ bởi `threading.RLock()` (`self.lock`).

---

## 2. TCP — Đường truyền chính (cổng 8765)

### 2.1 Framing protocol (`chessnet/protocol.py`)

Mọi tin nhắn TCP dùng **Length-Prefix Framing** (4-byte big-endian unsigned int + payload JSON UTF-8):

```python
# encode
payload = json.dumps(message, ensure_ascii=False, separators=(',', ':')).encode('utf-8')
return struct.pack('!I', len(payload)) + payload

# receive
size = struct.unpack('!I', exact(sock, 4))[0]   # đọc đúng 4 byte độ dài
result = json.loads(exact(sock, size).decode('utf-8'))
```

- `MAX_FRAME = 65536` bytes — gói quá lớn hoặc khung rỗng / không hợp lệ ném `ValueError`.
- `exact()` đọc précis số byte yêu cầu, ném `EOFError` nếu kết nối bị đóng giữa chéo.
- Đáng chú ý: test `test_fragmentation_and_coalescing` chứng minh khung chịu được chia mảnh (byte-by-byte) và ghép nhiều khung liên tiếp.

### 2.2 Khởi động server (`chessnet/server.py:64-100`)

```python
class GameServer:
    def __init__(self, host='0.0.0.0', port=8765, udp_port=9999,
                 db_path='data/chess.db', reconnect_seconds=60):
```

- TCP socket: `AF_INET` + `SOCK_STREAM`, bind, `listen(128)`, `settimeout(0.5)`.
- UDP socket: `AF_INET` + `SOCK_DGRAM`, bind, `settimeout(0.5)`.
- Nếu bind thất bại (`OSError`): đóng cả hai socket, đóng store, shutdown pool, ném lại ngoại lệ.
- Cổng được truyền qua tham số dòng lệnh (`--port`, `--udp-port`), Docker exposes `8765/tcp` và `9999/udp`.

### 2.3 Vòng lặp chấp nhận kết nối (`accept_loop`, server.py:102-116)

- `tcp.accept()` chờ kết nối mới, mỗi socket client đặt `settimeout(15)`.
- `BoundedSemaphore(128)` giới hạn số kết nối đồng thời; nếu hết槽, socket bị đóng ngay.
- Mỗi kết nối được gửi đến `ThreadPoolExecutor` chạy `client_loop(sock, addr)`.

### 2.4 Xử lý từng client (`client_loop`, server.py:118-183)

1. Đọc tin nhandle chào đầu bằng `receive(sock)`.
2. Xác thực dựa trên `hello['type']`:
   - **LOGIN**: gọi `store.authenticate(name, password, register)` → băm PBKDF2-HMAC-SHA256 (120.000 vòng, salt 16 byte). Kiểm tra trùng tên đăng nhập ở nơi khác; nếu session cũ đang ngắt kết nối còn trong vòng 60s → cho phép khôi phục; nếu quá 60s → xóa session cũ và tạo mới.
   - **RESUME**: tìm session theo token; nếu không tồn tại hoặc đã disconnect quá `reconnect_seconds` (60s) → lỗi `"Phiên đã hết hạn"`; nếu session vẫn đang có socket ở nơi khác → lỗi `"Phiên đang kết nối ở nơi khác"`.
3. Lưu `session.sock`, `session.ip`, xóa cờ disconnect, gửi `WELCOME` kèm token và `udp_port`.
4. Gửi `lobby()` (danh sách phòng công khai + số người online) và, nếu session đã từng ở trong một phòng, broadcast lại trạng thái phòng đó.
5. Vòng lặp đọc tin nhắn TCP liên tục, gọi `handle(session, message)`; các lỗi `ValueError/KeyError/TypeError/JSONDecodeError` phản hồi `ERROR` ngược client.
6. `finally`: xóa socket khỏi `connections`, nếu socket là của session thì gán `session.sock = None`, đánh dấu `session.disconnected = time.monotonic()`, xóa session khỏi hàng đợi ghép trận, broadcast phòng/lobby, đóng socket, giải phóng semaphore.

**Quan trọng:** Khi mất kết nối TCP, session **không bị xóa ngay** — chỉ đánh dấu `disconnected` và giữ trong 60 giây để cho phép reconnect.

### 2.5 Các loại tin nhắn TCP (message types)

| Loại | Hướng | Ý nghĩa |
|------|-------|---------|
| `LOGIN` | C→S | Đăng nhập / đăng ký tài khoản |
| `RESUME` | C→S | Khôi phục phiên sau mất kết nối (dùng token) |
| `WELCOME` | S→C | Trả lời đăng nhập: token, tên, udp_port |
| `PING` / `PONG` | C↔S | Kiểm tra kết nối sống, đo độ trễ (latency) |
| `LOBBY` | C→S / S→C | Yêu cầu / nhận danh sách phòng và số người online |
| `HISTORY` | C→S / S→C | Lịch sử 30 ván gần nhất của người chơi |
| `PGN` | C→S / S→C | Xuất biên bản ván cờ chuẩn PGN |
| `CREATE` | C→S | Tạo phòng mới (kèm control, title, private) |
| `JOIN` / `SPECTATE` | C→S | Vào phòng chơi hoặc vào xem |
| `MATCH` / `CANCEL_MATCH` | C→S | Ghép trận ngẫu nhiên / hủy tìm đối thủ |
| `QUEUED` / `QUEUE_CANCELLED` | S→C | Thông báo trạng thái hàng đợi |
| `LEAVE` / `LEFT` | C→S / S→C | Rời phòng / xác nhận rời |
| `MOVE` | C→S | Đi quân (from, to, promotion) |
| `STATE` | S→C | Trạng thái phòng/bàn cờ đầy đủ (FEN, nước đi, đồng hồ, v.v.) |
| `RESIGN` / `DRAW` / `CLAIM_DRAW` | C→S | Đầu hàng, đề nghị hòa, yêu cầu hòa theo luật |
| `CHAT` | C→S / S→C (trong STATE) | Tin nhắn văn bản phòng (rate-limit 0.5s) |
| `ERROR` | S→C | Thông báo lỗi từ server |
| `CLOCK` | S→C | Đồng hồ đếm ngược (qua UDP thường, qua TCP dự phòng) |

---

## 3. UDP — Đường truyền bổ sung (cổng 9999)

### 3.1 Server-side UDP loop (`udp_loop`, server.py:376-405)

- Nhận `recvfrom(4096)`, parse JSON. Các gói không phải dict hoặc parse lỗi bị bỏ qua (`continue`).
- **DISCOVER**: nếu `type == 'DISCOVER'` và `app == 'PIXEL_CHESS_V1'` → phản hồi ngay `{'type':'SERVER','app':'PIXEL_CHESS_V1','name':hostname,'port':tcp_port,'udp_port':udp_port}` về địa chỉ nguồn. Dùng để quét LAN.
- **REGISTER**: lưu địa chỉ UDP của session (`s.udp = addr`) — chỉ cho phép nếu token hợp lệ, session đang có socket TCP và IP khớp với nguồn gói tin (chống giả mạo IP).
- **EMOJI**: chỉ xử lý nếu `s.udp == addr`, emoji trong `{👍, 🔥, 👏, 🤔}`, và cách tin nhắn trước >0.5s (rate-limit chống spam). Sau đó broadcast EMOJI đến tất cả địa chỉ UDP của người chơi và người xem trong cùng phòng.
- Gói malformed (ví dụ `send([])`, `REGISTER` với token là list) bị bắt bởi `ValueError/TypeError/KeyError` và **không làm chết luồng UDP**.

### 3.2 Client-side UDP (`chessnet/client.py:102-153`)

- `setup_udp()`: tạo socket UDP, bind `('0.0.0.0', 0)` (cổng ngẫu nhiên), `settimeout(0.5)`, chạy `udp_loop` trong daemon thread, sau đó gửi `REGISTER`.
- `udp_loop()`: nhận dữ liệu, chỉ chấp nhận gói từ `(peer_ip, server_udp_port)`, parse JSON, nếu type là `CLOCK` hoặc `EMOJI` thì đưa vào callback của GUI.
- `send_udp(kind, **kwargs)`: gửi JSON kèm `token` đến `(peer_ip, udp_port)`.
- `heartbeat()` (chạy mỗi 3s): gửi `PING` qua TCP và `REGISTER` qua UDP — giữ địa chỉ UDP được đăng ký ở server tươi mới.

### 3.3 Dùng UDP ở đâu trong game (`server.py`)

**Clock loop** (`server.py:407-447`) mỗi 0.2s:
- Cập nhật đồng hồ cờ (`settle`).
- Nếu phòng đang chơi, đóng gói `{'type':'CLOCK','id':...,'clocks':...,'turn':...,'revision':...}`:
  - Gửi qua **UDP** đến mọi người chơi/người xem có `s.udp` (nhịp 5Hz, hiển thị mượt).
  - Gửi qua **TCP** mỗi 2 giây (`now - last_tcp >= 2`) để chống lệch đồng hồ và dự phòng khi mất gói UDP.
- Phát hiện client chết: nếu `now - s.seen > 12` giây → `shutdown(socket.SHUT_RDWR)` socket TCP của client đó.
- Xử lý hết hạn reconnect: nếu `disconnected` quá `reconnect_seconds` (60s) → xử thua người chơi đó (hoặc xóa phòng nếu chưa bắt đầu), xóa người xem, dọn session nếu không còn tham gia phòng nào.
- Dọn phòng đã kết thúc超过 300 giây nếu không còn ai đang kết nối.

---

## 4. Cơ chế khôi phục phiên (Reconnect 60 giây)

Đây là tính năng nổi bật, được mô tả chi tiết trong `README.md` và kiểm thử bởi hai test:

- `test_reconnect_preserves_fen_clock_and_role` (test_network.py:164-178): đóng socket của người trắng, đợi session bị đánh dấu `sock is None`, sau đó đăng nhập lại bằng cùng token (`RESUME`) → nhận lại `STATE` với cùng FEN, cùng role (0 = trắng), đồng hồ vẫn còn (>295s), và ván đấu tiếp tục bình thường.
- `test_expired_reconnect_loses_and_cannot_resume` (test_network.py:180-189): đánh dấu `disconnected` là 61 giây trước → sau đó server tự động kết thúc ván, kết quả `0-1`, lý do `"Mất kết nối quá 60 giây"`.

**Luồng hoạt động:**
1. Client mất kết nối TCP (socket lỗi, đóng ứng dụng, hoặc bấm "Rời ván & Đăng xuất" gọi `disconnect_transport()` → `shutdown(SHUT_RDWR)`).
2. Server đánh dấu `session.disconnected = time.monotonic()`, `session.sock = None`, `session.udp = None`.
3. GUI client hiển thị màn hình đăng nhập lại với thông báo: *"Đã ngắt kết nối. Bạn có 60 giây để đăng nhập lại ván cờ."*
4. Người chơi nhập lại tên/mật khẩu (hoặc bấm Đăng nhập nếu token đã được lưu) → gửi `RESUME` với token.
5. Server tìm session theo token, kiểm tra `time.monotonic() - disconnected <= 60`, nếu hợp lệ → gán socket mới, gửi `WELCOME` + `STATE` phòng hiện tại, ván đấu được khôi phục nguyên vẹn (FEN, đồng hồ, lượt đi,role).
6. Nếu quá 60 giây → server xử thua người chơi ngắt kết nối và xóa phòng nếu chưa có ai.

---

## 5. Mô hình phòng và trò chơi (Server-Authoritative)

- `Room` (server.py:43-61): id (mã 6 ký tự hex in hoa), title, control (`3+0`/`5+0`/`10+5`), private, danh sách người chơi (`players`), người xem (`watchers`), đối tượng `chess.Board`, danh sách nước đi (`moves`), đồng hồ (`clocks`), status (`waiting`/`playing`/`finished`), revision, offer (đề nghị hòa), finished_at.
- Server là đơn vị kiểm tra duy nhất luật cờ: `board.legal_moves`, `board.push(move)`, `board.outcome()`, chiếu hết, hết nước đi, không đủ quân, lặp thế 5 lần, luật 75 nước.
- Mỗi nước đi hợp lệ tăng `revision`, broadcast `STATE` đến tất cả người chơi và người xem trong phòng.
- Đồng hồ: mỗi bên có thời gian ban đầu theo `CONTROLS`; sau mỗi nước đi cộng thêm `increment` (thời gian phụ); đồng hồ đếm ngược liên tục trong `clock_loop`; hết thời gian → thua (hoặc hòa nếu bên còn lại không đủ quân chiếu hết).
- Kết thúc ván → lưu vào SQLite (`games` table): tên hai bên, kết quả, lý do, PGN, thời gian.

---

## 6. Bản đồ file liên quan đến mạng

| File | Vai trò trong mạng |
|------|-------------------|
| `chessnet/protocol.py` | Framing 4-byte length prefix + JSON, `encode()`/`receive()`/`exact()` |
| `chessnet/server.py` | `GameServer`: TCP accept loop, TCP client loop, UDP loop, clock loop, xử lý tất cả message types, phòng, reconnect, đồng hồ |
| `chessnet/client.py` | `NetworkClient`: kết nối TCP, heartbeat, UDP setup/loop, `send()`/`send_udp()`, `discover()` (LAN broadcast), `PracticeBot` (đối thủ máy Minimax 2 ply) |
| `chessnet/gui.py` | `ChessApp` Tkinter: pumping sự kiện mạng (`pump()` mỗi 40ms), hiển thị STATE/CLOCK/EMOJI/PONG, gửi MOVE/CHAT/EMOJI, dialog đăng nhập + LAN discovery |
| `chessnet/storage.py` | `Store`: SQLite, `authenticate()` PBKDF2, `finish()` lưu ván, `history()`/`pgn()` |
| `app.py` | Điểm vào: `--server` chạy `GameServer.main()`, mặc định chạy GUI, `--test` chạy unittest |
| `tests/test_network.py` | 14 test tự động: framing, authentication, nước đi, spectator, chiếu hết, đặc biệt (nhập thành, bắt qua đường, phong cấp), reconnect 60s, hết hạn reconnect, clock timeout, UDP discovery/clock/emoji, matchmaking, phòng riêng, chat/hòa/rời phòng, heartbeat |
| `docker/Dockerfile` | Python 3.12-slim, expose `8765/tcp` `9999/udp`, volume `/app/data` |
| `docker/compose.yaml` | Map cổng `8765:8765/tcp`, `9999:9999/udp`, volume `chess-data` |
| `Run.cmd` / `Server.cmd` | Khởi động client / khởi động server chuyên dụng trên Windows |

---

## 7. Cổng mạng và tường lửa

```
TCP 8765  →  Điều khiển chính: đăng nhập, nước cờ, chat, lobby, lịch sử, reconnect
UDP 9999  →  Dò tìm LAN (broadcast), đồng hồ đồng bộ (5Hz), biểu cảm (emoji)
```

- Docker compose映射 cả hai cổng ra máy chủ.
- Trên Windows, cần cho phép Tường lửa Windows nếu chơi qua LAN/Wi-Fi giữa hai máy (ghi chú trong README).
- Nếu UDP broadcast bị chặn bởi router, người dùng có thể nhập thủ công `IP:8765`.

---

## 8. Đánh giá thiết kế

### Ưu điểm
1. **Ping-pong architecture rõ ràng:** TCP cho dữ liệu cần tin cậy (nước cờ, chat, xác thực), UDP cho dữ liệu nhạy cảm thời gian (đồng hồ, emoji) và dò tìm LAN.
2. **Server-Authoritative:** Server duy quyền kiểm tra luật cờ, đồng hồ, và kết quả — ngăn gian lận từ client.
3. **Reconnect gracefully:** Giữ session trong 60s sau mất kết nối, cho phép khôi phục ván đấu không làm mất tiến độ.
4. **Chống chập:** Rate-limit chat (0.5s), rate-limit emoji (0.5s), giới hạn 128 kết nối đồng thời, frame size tối đa 64KB, bắt ngoại lệ UDP không làm chết luồng.
5. **Mật khẩu không lưu dạng văn bản:** PBKDF2-HMAC-SHA256 với salt 16 byte, 120.000 vòng.
6. **Docker-ready:** Cổng được expose rõ ràng, volume dữ liệu tách ra.

### Ghi chú hạn chế
- UDP không có mã hóa hay xác thực gói riêng ngoài kiểm tra token/IP — rely vào TCP đã xác thực trước khi đăng ký địa chỉ UDP.
- `STATE` được broadcast đầy đủ cho mọi người xem (có thể tối giản nếu cần).
- Không có TLS — dữ liệu TCP đi dưới dạng văn bản JSON (trừ mật khẩu được băm trước khi gửi... nhưng login gửi mật khẩu dạng plaintext qua TCP, nên nên dùng trong mạng tin cậy hoặc thêm TLS).

---

## 9. Cách chạy thử mạng

```powershell
# Chạy server
python app.py --server
# hoặc
Server.cmd

# Chạy client GUI
python app.py
# hoặc
Run.cmd

# Chạy kiểm thử mạng tự động (14 test)
python app.py --test
```

Kết quả mong đợi: server in ra `Pixel Chess TCP 0.0.0.0:8765 | UDP 9999`.

---

*Tài liệu này được phân tích từ mã nguồn thực tế của dự án Pixel Chess (E:\Chess_Nhom_2), ngày 2026-11-24.*