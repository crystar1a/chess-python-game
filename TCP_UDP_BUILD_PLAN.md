# Giai đoạn xây dựng TCP + UDP cho game cờ vua online

## Mục tiêu

Xây dựng nền tảng multiplayer cho game cờ vua Python, ưu tiên độ tin cậy của nước đi và đồng bộ trạng thái giữa hai người chơi.

- TCP là kênh chính cho mọi sự kiện gameplay: nước đi, kết quả trận, chat, rematch, reconnect.
- UDP là kênh phụ cho ping, presence, đồng hồ hiển thị và các update không bắt buộc.
- Server là nguồn sự thật (authoritative server): chỉ server giữ bàn cờ thật và quyết định nước đi hợp lệ.
- Client chỉ gửi ý định (`MOVE_REQUEST`), không tự quyết định kết quả trận đấu.

## Nguyên tắc kiến trúc

| Thành phần | Trách nhiệm | Không được làm |
|---|---|---|
| Client GUI | Vẽ bàn cờ, quân cờ, hiệu ứng | Không quyết định nước đi hợp lệ |
| Client Input | Chuyển click/kéo thả thành intent | Không ghi trực tiếp vào trạng thái server |
| Client GameController | Quản lý UI state và gửi message | Không là nguồn sự thật của luật cờ |
| Network layer | Gửi/nhận message qua TCP/UDP | Không chứa luật cờ |
| Server Match | Giữ `python-chess.Board`, kiểm tra và áp dụng nước đi | Không phụ thuộc Pygame |
| Server Broadcaster | Phát event đến người chơi trong room | Không xử lý input trực tiếp từ GUI |

## Cấu trúc thư mục đề xuất

```text
chess_online/
├── client/
│   ├── main.py
│   ├── gui/
│   │   ├── renderer.py
│   │   ├── board_view.py
│   │   └── hud.py
│   ├── input/
│   │   └── mouse_controller.py
│   ├── game/
│   │   ├── local_board.py
│   │   └── game_controller.py
│   └── net/
│       ├── network_client.py
│       ├── tcp_client.py
│       ├── udp_client.py
│       └── protocol.py
├── server/
│   ├── main.py
│   ├── app.py
│   ├── matchmaking.py
│   ├── rooms.py
│   ├── game/
│   │   ├── chess_match.py
│   │   └── rules.py
│   ├── net/
│   │   ├── tcp_server.py
│   │   ├── udp_server.py
│   │   └── protocol.py
│   └── persistence/
│       └── game_repository.py
├── shared/
│   ├── messages.py
│   ├── serialization.py
│   └── constants.py
└── tests/
```

## Phân chia giao thức

### TCP: bắt buộc đáng tin

Dùng TCP cho:

- Đăng nhập, tạo phòng, tham gia phòng, matchmaking.
- `MOVE_REQUEST`, `MOVE_ACCEPTED`, `MOVE_REJECTED`.
- `GAME_START`, `GAME_OVER`, `REMATCH_REQUEST`.
- Chat, đầu hàng, yêu cầu hòa, undo request.
- Đồng bộ full state khi reconnect.

### UDP: optional, mất gói không nghiêm trọng

Dùng UDP cho:

- Ping và RTT.
- Presence: online, trong lobby, đang chơi.
- Đồng hồ hiển thị mượt hơn, kèm timestamp.
- Spectator updates hoặc hiệu ứng không ảnh hưởng kết quả.

Không dùng UDP cho nước đi, kết quả trận, chat hoặc dữ liệu cần đảm bảo không mất.

## Message protocol

Mọi message nên có các trường chung:

```json
{
  "v": 1,
  "type": "MOVE_REQUEST",
  "match_id": "m_123",
  "seq": 42,
  "player_id": "p_1",
  "sent_at_ms": 1710000000000,
  "payload": {}
}
```

### Client → Server

```json
{
  "v": 1,
  "type": "MOVE_REQUEST",
  "match_id": "m_123",
  "seq": 42,
  "player_id": "p_1",
  "payload": {
    "move": "e2e4",
    "client_time_ms": 1710000000000
  }
}
```

### Server → cả hai client

```json
{
  "v": 1,
  "type": "MOVE_ACCEPTED",
  "match_id": "m_123",
  "seq": 42,
  "payload": {
    "move": "e2e4",
    "turn": "black",
    "fen": "rnbqkbnr/pppppppp/8/8/4P3/8/PPPP1PPP/RNBQKBNR b KQkq - 0 1",
    "in_check": false,
    "game_over": false
  }
}
```

### Server từ chối nước đi

```json
{
  "v": 1,
  "type": "MOVE_REJECTED",
  "match_id": "m_123",
  "seq": 42,
  "payload": {
    "move": "e2e4",
    "reason": "illegal_move"
  }
}
```

## Luồng chơi online

```text
1. Client kết nối TCP tới server
2. Client gửi AUTH / JOIN_QUEUE
3. Server ghép 2 người chơi, tạo match_id
4. Server gửi GAME_START: màu quân, FEN, thời gian
5. Client A gửi MOVE_REQUEST qua TCP
6. Server kiểm tra bằng python-chess
7. Server gửi MOVE_ACCEPTED cho cả A và B
8. Client cập nhật bàn cờ từ message server
9. Nếu mất kết nối, server giữ match và gửi FULL_STATE khi reconnect
```

## Xử lý reconnect

- Mỗi client có `player_id` và `session_token`.
- Server lưu `match_id`, trạng thái bàn cờ, lịch sử nước đi và đồng hồ.
- Khi reconnect, client gửi `RECONNECT_REQUEST`.
- Server gửi `FULL_STATE` gồm FEN, PGN hoặc move history, lượt hiện tại, đồng hồ và trạng thái trận.
- Client chỉ tiếp tục chơi sau khi nhận `FULL_STATE`.

## Đồng bộ trạng thái

- Mỗi message có `seq` tăng dần.
- Client lưu `last_received_seq`.
- Nếu nhận `seq` cũ: bỏ qua.
- Nếu phát hiện thiếu `seq`: gửi `STATE_SYNC_REQUEST`.
- Server có thể gửi `FULL_STATE` định kỳ hoặc khi có yêu cầu.
- Với cờ vua, không cần client prediction phức tạp; chỉ cần optimistic UI nhẹ khi kéo quân.

## Kế hoạch triển khai theo sprint

### Sprint 1: Nền tảng local

- Hoàn thiện game cờ 2 người trên cùng máy bằng `python-chess` + Pygame.
- Tách GUI khỏi logic game.
- Thêm undo, hiển thị lượt, phát hiện chiếu hết/pat/hòa.
- Viết unit test cho luật cờ.

### Sprint 2: Giao thức và TCP local

- Tạo `shared/messages.py` và `shared/serialization.py`.
- Cài đặt TCP client/server bằng `asyncio` hoặc `socket` + thread.
- Chạy server và 2 client trên cùng máy.
- Gửi/nhận `MOVE_REQUEST`, `MOVE_ACCEPTED`, `MOVE_REJECTED`.
- Server là nơi duy nhất giữ `python-chess.Board`.

### Sprint 3: Room và matchmaking

- Thêm lobby, tạo phòng, tham gia phòng bằng mã phòng.
- Quản lý player session và room.
- Ghép 2 người vào một match.
- Gửi `GAME_START` và đồng bộ trạng thái ban đầu.

### Sprint 4: Reconnect và robustness

- Thêm heartbeat TCP.
- Xử lý disconnect: giữ match trong thời gian grace period.
- Thêm `RECONNECT_REQUEST` và `FULL_STATE`.
- Xử lý timeout, đầu hàng, rời phòng.

### Sprint 5: UDP telemetry

- Thêm UDP client/server.
- Gửi ping/RTT và presence.
- Đồng bộ đồng hồ hiển thị bằng timestamp.
- Không đưa nước đi qua UDP.

### Sprint 6: AI và deployment

- Thêm Stockfish qua UCI bằng `python-chess`.
- Đóng gói server, cấu hình port, logging và monitoring.
- Test trên LAN, sau đó test qua internet/NAT.
- Thêm bảo mật: xác thực, rate limit, chống spam message.

## Công nghệ đề xuất

| Hạng mục | Đề xuất | Ghi chú |
|---|---|---|
| Luật cờ | `python-chess` | Move generation, validation, game end detection |
| GUI | `pygame` | Vẽ bàn cờ và xử lý input |
| TCP | `asyncio` | Phù hợp cho nhiều kết nối concurrent |
| UDP | `asyncio` DatagramProtocol hoặc `socket` | Dùng cho telemetry |
| Serialization | JSON cho giai đoạn đầu | Dễ debug; sau có thể đổi MessagePack/protobuf |
| AI | Stockfish + UCI | `python-chess` hỗ trợ giao tiếp engine |
| Test | `pytest` | Test luật cờ và protocol không cần GUI |

## Checklist trước khi code mạng

- [ ] Game local chạy ổn định, không phụ thuộc mạng.
- [ ] GUI không import trực tiếp `python-chess` ngoài qua GameController.
- [ ] Server có `ChessMatch` riêng, không phụ thuộc Pygame.
- [ ] Message có version, type, match_id, seq, player_id.
- [ ] Có serialization chung trong `shared/`.
- [ ] TCP client/server có thể gửi và nhận message JSON.
- [ ] Server kiểm tra mọi nước đi trước khi phát kết quả.
- [ ] Client chỉ cập nhật bàn cờ sau khi nhận xác nhận từ server.
- [ ] Có reconnect và full state sync.
- [ ] UDP chỉ dùng cho telemetry, không dùng cho gameplay-critical events.
