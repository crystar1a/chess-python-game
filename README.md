# Pixel Chess

Cờ vua với bot Stockfish hoặc người chơi khác qua TCP. Python, pygame-ce và python-chess.

## Tính năng

- Chọn màu quân và độ khó Easy, Normal hoặc Hard
- Chọn thời gian 5/10/15 phút hoặc không giới hạn
- Chọn quân và ô đích bằng chuột; phong cấp hậu/xe/tượng/mã
- Chiếu hết, hết nước đi, hòa
- Âm thanh, đồng hồ, nút New game bắt đầu ván mới
- Chat với đối thủ trong ván online; bấm nút Chat để chuyển giữa tin nhắn và lịch sử nước đi.

## Cài đặt

```powershell
# uv
uv venv .venv
.\.venv\Scripts\Activate.ps1
uv pip install -r requirements.txt
python main.py

# pip
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
python main.py
```

## Chơi online

Máy chủ chạy `python -m server.main`. Khi chọn **Chơi Online**, nhập địa chỉ IP hoặc tên máy server (có thể kèm cổng, mặc định `8765`); game ghi nhớ địa chỉ cho lần sau. Chọn **Danh sách phòng** để xem và tham gia phòng đang chờ trên server đó, hoặc **Vào phòng** để nhập mã. Nếu chơi qua Tailscale, dùng địa chỉ Tailscale của máy chạy server và bảo đảm hai máy được cấp quyền kết nối. Kết nối TCP chưa có TLS; không mở server trực tiếp ra Internet công cộng.

## Stockfish local và REST API

Khuyến nghị [tải Stockfish](https://stockfishchess.org/download/) để chơi ngoại tuyến và tránh độ trễ mạng. Giải nén, đổi tên tệp thực thi theo hệ điều hành rồi đặt tại `client/ai/stockfish/`:
- Windows: `stockfish-windows-x86-64-universal.exe`
- Linux x86-64: `stockfish-linux-x86-64-universal`, cấp `chmod +x`
- macOS: đặt bản tương thích tại `client/ai/stockfish/stockfish`, cấp `chmod +x`

Khi thiếu engine local, game tự gửi thế cờ đến StockfishOnline qua HTTPS. Easy, Normal và Hard dùng độ sâu tìm kiếm lần lượt là 5, 10 và 15 cho cả engine local và REST API. Độ sâu tính theo lượt đi của một bên (ply).

Bạn có thể chơi ngay với quyền khách. Nếu thường dùng REST, hãy [đăng ký tài khoản StockfishOnline](https://stockfish.online/account/signup.php) để lấy API key cho hàng đợi ưu tiên. Dán riêng key trên một dòng vào `client/ai/stockfish/api.txt` rồi bắt đầu ván mới. Có thể tạo tệp sau khi clone hoặc để trống. Git bỏ qua tệp chứa key và các engine local.
