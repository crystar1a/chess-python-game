# Kế hoạch danh sách phòng TCP

1. Bổ sung `LIST_ROOMS`/`ROOM_LIST`, chỉ liệt kê phòng đang chờ và chia khối để giữ giới hạn frame; kiểm thử phòng đầy, phòng đóng và danh sách nhiều trang.
2. Thêm cấu hình địa chỉ server với cổng mặc định 8765; kiểm thử dữ liệu sai và lưu/đọc lại.
3. Bổ sung màn hình kết nối, danh sách phòng, làm mới, phân trang và chọn tham gia; giữ chức năng nhập mã phòng và reconnect.
4. Kiểm thử TCP hai client, hiển thị giao diện, các tình huống phòng thay đổi và toàn bộ bộ kiểm thử.
