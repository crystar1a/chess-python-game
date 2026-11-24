# Pixel Chess

Cờ vua với bot Stockfish. Python, pygame-ce, python-chess. Chạy một máy. Chơi mạng (TCP/UDP) là giai đoạn sau.

## Tính năng

- Chọn màu, độ khó Easy/Normal/Hard (Stockfish Skill Level 0/10/20)
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

Stockfish nằm tại `client/ai/stockfish/`:
- Windows: `stockfish-windows-x86-64-universal.exe`
- Linux x86-64: `stockfish-linux-x86-64-universal`, cấp `chmod +x`
- macOS: đặt bản tương thích tại `client/ai/stockfish/stockfish`, cấp `chmod +x`
