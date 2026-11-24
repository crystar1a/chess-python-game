# Kế hoạch phát triển Pixel Chess

## Mục tiêu

Xây dựng trò chơi cờ vua Pixel Chess bằng Python và Pygame; dùng python-chess xử lý luật, Stockfish làm đối thủ và pygame.mixer phát âm thanh. Tổ chức theo kiến trúc client–server, phân lớp trong từng phía. Ưu tiên bản nháp chơi với bot trên một máy; triển khai TCP và UDP ở giai đoạn sau.

Đây là bước tiền đề: xây dựng trò chơi cờ vua trước để làm cơ sở cập nhật TCD và UCD, từ đó thiết kế và xây dựng chương trình chơi cờ qua mạng ở giai đoạn tiếp theo.

Người chơi chọn chơi với bot, sau đó chọn độ khó Easy, Normal hoặc Hard, rồi chọn thời gian và màu quân trước ván; bot cầm quân còn lại và quân trắng đi trước. Chọn quân và ô đích bằng chuột, dùng luật cờ vua tiêu chuẩn.

## Tiêu chí thiết kế: "Avoid Code Bloated" 

Giữ code dễ đọc, dễ bảo trì và tránh phình to khi xây dựng thêm chức năng. Áp dụng kiến trúc phân lớp đã chọn, phân chia trách nhiệm rõ ràng và tận dụng Pygame, python-chess và Stockfish. Chỉ thêm abstraction, cấu hình hoặc tính năng khi có nhu cầu cụ thể; tránh trùng lặp và độ phức tạp không cần thiết, đồng thời tái cấu trúc khi cần để duy trì sự rõ ràng.

## Công nghệ và tài nguyên

- Khai báo pygame-ce và python-chess trong requirements.txt; dùng pygame-ce tương thích Python 3.14 (import qua `pygame`).
- Stockfish là chương trình UCI riêng, được nạp từ thư mục `client/ai/stockfish/`; python-chess không tự cài engine. Gói `stockfish` trên pip cũng chỉ là wrapper và vẫn cần engine riêng; ưu tiên adapter UCI hiện có của python-chess để tránh phụ thuộc trùng lặp.
- Nguồn ảnh `E:\Chess_Nhom_2\assets` có 12 ảnh quân wp, wn, wb, wr, wq, wk, bp, bn, bb, br, bq, bk và original.png. Kiểm tra nội dung, kích thước sau đó sao chép vào thư mục dự án.
- Thư mục `assets/sounds/` đã có các tệp MP3: `capture`, `castle`, `game-end`, `game-start`, `move-check`, `move-opponent`, `move-self`, `notify`, `promote` và `tenseconds`. Theo thông tin được cung cấp, ảnh và âm thanh có thể tải và sử dụng; kiểm tra khả năng phát và dùng đường dẫn tương đối trong project. Kiểm tra và hướng dẫn cung cấp Stockfish nếu chưa có. Trò chơi vẫn chạy khi thiếu âm thanh; không phụ thuộc đường dẫn E: khi phân phối.

## Kiến trúc client–server

Cấu trúc mục tiêu dưới đây kết hợp client–server với phân chia trách nhiệm trong từng phía. Tên `chess_online/` là thư mục gốc dự án; các tệp và thư mục mạng chỉ tạo khi triển khai tính năng tương ứng.

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
│       ├── network_client.py
│       ├── tcp_client.py
│       └── udp_client.py
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
│   │   └── udp_server.py
│   └── persistence/
│       └── game_repository.py
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

- **Client**: `main.py` khởi tạo ứng dụng; `gui/` vẽ, quản lý tài nguyên và âm thanh; `input/` xử lý chuột; `game/` điều phối và giữ bàn cờ cục bộ; `ai/` tích hợp Stockfish cho chế độ bot; `net/` kết nối mạng khi có chế độ online. Giao diện không tự quyết định kết quả ván.
- **Server**: quản lý kết nối, ghép trận, phòng và ván; `server/game/` dùng python-chess để kiểm tra lượt, nước đi và kết quả. Server là nguồn trạng thái có thẩm quyền trong ván online; persistence chỉ cần khi có yêu cầu lưu ván.
- **Shared** đặt định dạng thông điệp JSON và mã đóng/đọc frame dùng chung tại `shared/protocol.py`.
- **Chế độ bot cục bộ** dùng python-chess và Stockfish để quản lý ván trên client. Chế độ online dùng bản sao bàn cờ để vẽ và gợi ý ô đích. Bản sao chỉ thay đổi khi nhận trạng thái xác nhận từ server.
- **Tests**: kiểm thử chế độ bot trước, sau đó bổ sung kiểm thử giao thức, đồng bộ và hành vi server khi triển khai online.

Mã bản bot được tổ chức trong `client/game/`, `client/ai/`, `client/gui/` và `client/input/`. Điểm vào `client/main.py` điều phối vòng lặp; `main.py` ở gốc giữ lệnh chạy hiện tại. Chỉ tách thêm tệp khi cần và chưa tạo server hay giao thức giả cho bản bot.

## Thiết kế bản chơi với bot

1. Khởi tạo pygame-ce; khi chọn chơi với bot, cho chọn độ khó Easy, Normal hoặc Hard, sau đó chọn thời gian 5, 10, 15 phút hoặc không tính thời gian và màu trắng hoặc đen, rồi bắt đầu ván. Cấu hình sức mạnh Stockfish khác nhau cho từng mức. Vẽ bàn cờ 8×8, scale ảnh quân theo ô và đặt quân của người chơi ở phía dưới. Xác định phép chuyển giữa tọa độ màn hình và ô python-chess cho cả hai hướng.
2. Chọn quân của người chơi bằng chuột và đánh dấu các ô đích hợp lệ. Quân trắng đi trước; nếu người chơi chọn đen, bot đi nước đầu. Chỉ thực hiện nước đi được python-chess xác nhận; bỏ qua thao tác ngoài bàn cờ và nước sai.
3. Khi phong cấp, cho chọn hậu, xe, tượng hoặc mã trước khi gửi nước đi. Hiển thị lượt và kết quả ván.
4. Gửi bản sao vị trí cho Stockfish với giới hạn thời gian suy nghĩ. Chạy tác vụ engine ngoài vòng lặp giao diện; khóa nước đi của người chơi khi chờ. Kiểm tra kết quả engine hợp lệ và còn thuộc ván hiện tại.
5. Tích hợp các tệp trong `assets/sounds/` cho sự kiện tương ứng: bắt đầu và kết thúc ván, nước đi của người chơi và bot, bắt quân, nhập thành, chiếu và phong cấp. Các âm thanh khác dùng khi có sự kiện phù hợp. Nếu mixer hoặc tệp âm thanh lỗi, thông báo hợp lý và tiếp tục không âm thanh.
6. Hiển thị lỗi rõ ràng nếu engine không có hoặc không khởi động được; cho phép thoát hoặc bắt đầu lại sau khi khắc phục. Khi thoát hoặc bắt đầu lại, bỏ qua kết quả cũ và đóng tiến trình an toàn.
7. Hiển thị chiếu hết, hết nước đi và hòa. Bản nháp có thể tự nhận hòa khi python-chess xác định có quyền yêu cầu hòa; thông báo rõ quyết định này.
8. Với ván có tính giờ, mỗi bên có thời gian riêng bằng mức đã chọn, không cộng thêm thời gian sau nước đi. Đồng hồ của bên đến lượt chạy, kể cả khi bot suy nghĩ hoặc người chơi chọn phong cấp; đổi đồng hồ sau nước đi hợp lệ và dừng khi ván kết thúc. Hết giờ thì bên hết giờ thua, trừ khi đối thủ không thể chiếu hết bằng bất kỳ chuỗi nước đi hợp lệ nào thì ván hòa. Với lựa chọn không tính thời gian, không chạy đồng hồ. Bắt đầu lại đặt lại đồng hồ theo lựa chọn của ván.

## Các bước thực hiện

- [x] Khảo sát dự án nguồn, các tệp âm thanh hiện có, Stockfish và môi trường Python.
- [x] Chuyển mã từ `src/` sang cấu trúc `client/` theo trách nhiệm trên; cập nhật điểm vào, import và kiểm thử.
- [x] Tạo cấu trúc tối thiểu, dependencies và hướng dẫn chạy; đưa asset vào dự án.
- [x] Xây lớp quản lý ván dựa trên python-chess; đã có kiểm thử cơ bản cho nước hợp lệ và không hợp lệ.
- [ ] Hoàn thiện và kiểm thử menu, bàn cờ và phong cấp: đã có ba mức độ khó, chọn thời gian và màu, hướng bàn cờ, chuột và phong cấp; chưa có bước chọn chế độ chơi với bot riêng và chưa kiểm thử đầy đủ các luồng.
- [ ] Hoàn thiện đồng hồ: đã có thời gian riêng, tùy chọn không giới hạn, đổi lượt và xử lý hết giờ; kiểm tra hòa khi hết giờ hiện dựa trên thiếu quân, chưa bao phủ mọi thế cờ không thể chiếu hết.
- [ ] Kiểm thử đầy đủ tích hợp Stockfish bất đồng bộ, xử lý lỗi và dọn tiến trình: đã triển khai, kiểm thử cấu hình, lỗi khởi động và nước đi cũ; còn kiểm tra đóng hoặc bắt đầu lại khi engine đang chạy.
- [ ] Kiểm thử đầy đủ pygame.mixer và chế độ không âm thanh: đã tải các tệp và xử lý lỗi mixer/tệp; còn xác minh các sự kiện âm thanh và trường hợp thiếu tài nguyên.
- [ ] Hoàn thiện bắt đầu lại, kết quả ván, README và kiểm thử đầu cuối: đã có chức năng và hướng dẫn cơ bản; chưa xác nhận một ván hoàn chỉnh và các tình huống thủ công.
- [x] Đối chiếu kế hoạch TCP/UDP với thiết kế của dự án cũ và mã Pygame hiện tại. Đã xác định thứ tự triển khai ở mục **Định hướng TCP và UDP**.
- [ ] Cập nhật TCD và UCD sau khi bản bot đạt tiêu chí. Triển khai và kiểm thử chế độ chơi mạng theo các mốc bên dưới.

### Kiểm tra tiến độ hiện tại

- Ngày 24/11/2026, chạy `python -m unittest discover -s tests -v` bằng môi trường ảo Windows. **13/13 kiểm thử đạt**, gồm nước hợp lệ và sai, đồng hồ và các ca hết giờ, ánh xạ ô theo hai hướng bàn cờ, chọn và bỏ chọn quân, ba cấu hình Stockfish, đường dẫn engine, lỗi khởi động và kết quả engine đã cũ.
- Đã kiểm tra Stockfish thực tế trả nước hợp lệ trước khi chuyển thư mục engine; đường dẫn mới đã được kiểm thử tồn tại. Chưa ghi nhận kiểm thử một ván hoàn chỉnh sau các thay đổi giao diện và cấu trúc.
- Đã có panel người chơi và đối thủ, đồng hồ, font Chess Sans và hiệu ứng hover. Phần chơi mạng đang ở giai đoạn thiết kế. Hai nhánh đi quân và phong cấp hiện vẫn gọi `game.move()` trực tiếp.
- Còn thiếu kiểm thử các luật đặc biệt, bốn lựa chọn phong cấp, kết thúc ván, các mức thời gian, tương tác menu, âm thanh, reset và thoát khi bot đang chạy. Cần kiểm thử thủ công cả hai màu và ghi kết quả trước khi xác nhận bản bot hoàn tất.

## Kiểm thử và tiêu chí hoàn thành

- Người chơi chọn được trắng hoặc đen và hoàn thành ván với bot; trắng đi trước, bot đi đầu khi người chơi chọn đen. Cửa sổ phản hồi khi bot suy nghĩ; bắt đầu lại và thoát sạch.
- Kiểm thử nước hợp lệ và sai, nhập thành, bắt tốt qua đường, bốn lựa chọn phong cấp, chiếu hết, hết nước đi và hòa.
- Kiểm thử ánh xạ bốn góc bàn cờ ở cả hai hướng, chọn lại quân, bấm ngoài bàn và khóa đầu vào lúc bot đang đi.
- Kiểm thử các lựa chọn 5, 10, 15 phút và không tính thời gian; đồng hồ đổi đúng lượt, tiếp tục chạy khi bot suy nghĩ hoặc chọn phong cấp, dừng khi kết thúc và đặt lại khi bắt đầu lại. Kiểm thử kết quả hết giờ, bao gồm trường hợp hòa khi đối thủ không thể chiếu hết.
- Kiểm thử thứ tự menu, cả ba mức độ khó và cấu hình Stockfish tương ứng trước khi chọn thời gian.
- Kiểm thử thiếu hoặc lỗi engine, kết quả bot cũ sau khi tạo ván mới, thiếu âm thanh và đóng cửa sổ khi engine đang chạy.
- README mô tả cài đặt, chạy, cấu hình Stockfish, nguồn asset, giới hạn và lệnh kiểm thử; ghi nhận kết quả kiểm thử tự động và thủ công.

## Định hướng TCP và UDP

**Mốc đầu tiên** là chơi trọn một ván PvP qua TCP giữa hai cửa sổ Pygame trên cùng máy. Server giữ bàn cờ, kiểm tra lượt và nước đi, tính giờ và quyết định kết quả. UDP được bổ sung ở mốc tìm server trong LAN.

1. [ ] **Đưa nước đi qua controller.** Thao tác chọn ô và chọn quân phong cấp tạo nước đi để controller xử lý. Chế độ bot áp dụng nước đi cục bộ. Chế độ online gửi `MOVE_REQUEST` với mã UCI (ví dụ `e7e8q`) và cập nhật bàn cờ từ snapshot của server. Chạy lại bộ kiểm thử bot sau thay đổi.
2. [ ] **Chạy một ván qua TCP trên cùng máy.** Dùng `asyncio` cho server và worker mạng chuyển sự kiện vào queue để vòng lặp Pygame đọc. Dùng JSON UTF-8 với tiền tố độ dài 4 byte big-endian, giới hạn payload 64 KiB. Kiểm thử một frame bị chia qua nhiều lần đọc và nhiều frame được đọc cùng lúc. Dùng `request_id` để ghép phản hồi với yêu cầu và nhận diện yêu cầu gửi lại. Server tăng `revision` khi trạng thái ván đổi. `MOVE_REQUEST` mang `expected_revision` của bàn cờ hiện tại. Kiểm thử sai lượt, nước sai, phong cấp và kết thúc ván. Sau mỗi nước hợp lệ, hai client phải có cùng FEN và `revision`.
3. [ ] **Tạo phòng bằng mã và kiểm thử trên LAN.** Thêm mục chơi online, phòng hai người lưu trong bộ nhớ và một chế độ giờ ban đầu `5+0`. Server tính giờ bằng `time.monotonic()` và gửi thời gian còn lại qua TCP khi bắt đầu ván và sau nước đi. Client tự đếm xuống để hiển thị. Kiểm thử hai máy cùng LAN và chốt chính sách yêu cầu hòa của chế độ online.
4. [ ] **Khôi phục phiên qua TCP.** Giữ ván và cho phép nối lại bằng token trong 60 giây nếu ván còn diễn ra. Đồng hồ tiếp tục chạy khi mất kết nối. Khi nối lại, server gửi màu quân, FEN, nước cuối, thời gian còn lại, kết quả và `revision`. Kiểm thử trường hợp server đã chấp nhận nước đi ngay trước khi kết nối bị ngắt và client chưa nhận được phản hồi.
5. [ ] **Tìm server trong LAN bằng UDP.** Client dò server qua UDP và dùng TCP để vào phòng và chơi. Giữ lựa chọn nhập `IP:port` thủ công. Đánh giá nhu cầu thêm cập nhật đồng hồ qua UDP sau khi thử chơi thực tế trên LAN.

Ghép trận tự động, chat và lưu lịch sử ván bằng SQLite thuộc giai đoạn sau. Khi triển khai qua Internet, dùng TLS cho kết nối TCP trước khi đưa token phiên hoặc thông tin đăng nhập qua mạng công cộng.

Tham khảo [TCP_UDP_BUILD_PLAN.md](TCP_UDP_BUILD_PLAN.md) và [NETWORK_ANALYSIS.md](NETWORK_ANALYSIS.md).
