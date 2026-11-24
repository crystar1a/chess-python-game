# Pixel Chess

Cờ vua với bot Stockfish. Python, pygame-ce, python-chess. Chạy một máy. Chơi mạng (TCP/UDP) là giai đoạn sau.

## Tính năng

- Chọn màu quân và độ khó Easy, Normal hoặc Hard
- Chọn thời gian 5/10/15 phút hoặc không giới hạn
- Chọn quân và ô đích bằng chuột; phong cấp hậu/xe/tượng/mã
- Chiếu hết, hết nước đi, hòa
- Âm thanh, đồng hồ, nút New game bắt đầu ván mới

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

## Stockfish local và REST API

Khuyến nghị [tải Stockfish](https://stockfishchess.org/download/) để chơi ngoại tuyến và tránh độ trễ mạng. Giải nén, đổi tên tệp thực thi theo hệ điều hành rồi đặt tại `client/ai/stockfish/`:
- Windows: `stockfish-windows-x86-64-universal.exe`
- Linux x86-64: `stockfish-linux-x86-64-universal`, cấp `chmod +x`
- macOS: đặt bản tương thích tại `client/ai/stockfish/stockfish`, cấp `chmod +x`

Khi thiếu engine local, game tự gửi thế cờ đến StockfishOnline qua HTTPS. Easy, Normal và Hard dùng độ sâu tìm kiếm lần lượt là 3, 8 và 15 cho cả engine local và REST API. Độ sâu tính theo lượt đi của một bên (ply).

Bạn có thể chơi ngay với quyền khách. Nếu thường dùng REST, hãy [đăng ký tài khoản StockfishOnline](https://stockfish.online/account/signup.php) để lấy API key cho hàng đợi ưu tiên. Dán riêng key trên một dòng vào `client/ai/stockfish/api.txt` rồi bắt đầu ván mới. Có thể tạo tệp sau khi clone hoặc để trống. Git bỏ qua tệp chứa key và các engine local.
