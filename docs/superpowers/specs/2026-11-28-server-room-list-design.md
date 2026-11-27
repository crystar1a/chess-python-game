# Danh sách phòng trên server TCP

Người chơi nhập và lưu địa chỉ server LAN hoặc Tailscale trước khi kết nối, sau đó xem tất cả phòng đang chờ trên server đó và chọn phòng để tham gia. Server giữ quyền quyết định phòng còn chỗ; danh sách không bao gồm phòng đang chơi. Địa chỉ và mã phòng vẫn có thể nhập thủ công.

Các phương án đã thảo luận gồm dò LAN/Tailscale hoặc dùng server danh bạ; người dùng chọn cho client hỏi trực tiếp server game bằng TCP. Phương án này không tự tìm địa chỉ server và không cần WebSocket, UDP hay dịch vụ trung tâm. Kết nối Internet công khai cần TLS và xác thực phù hợp; tính năng này không thay đổi bảo mật TCP hiện có.

Server trả danh sách theo các khối để không vượt giới hạn frame, chỉ có mã phòng, tên chủ và thời gian. Client cho phép làm mới, chuyển trang và chọn phòng; server vẫn từ chối nếu phòng đã đầy hoặc bị đóng. Lưu địa chỉ cục bộ và không lưu mật khẩu hoặc token trong tệp cấu hình.
