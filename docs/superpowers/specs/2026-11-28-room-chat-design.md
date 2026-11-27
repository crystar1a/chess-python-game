# Chat trong ván online

## Mục tiêu

Hai người chơi trong cùng phòng gửi tin nhắn khi ván online đang diễn ra. Bấm nút **Chat** để thay panel lịch sử nước đi bằng cửa sổ chat; bấm lại chính nút đó để trở về lịch sử. Tin nhắn đến khi chat đang ẩn vẫn được nhận.

## Các phương án

- **Qua server TCP hiện tại — lựa chọn của người dùng:** client gửi tin tới server, server chuyển cho hai người trong phòng. Tận dụng kết nối và ranh giới phòng hiện có.
- **Client kết nối trực tiếp:** cần thêm kết nối riêng và xử lý NAT; không chọn.

## Thiết kế

- Chỉ cho gửi chat khi ván online đã bắt đầu và chưa kết thúc. Không cho gửi trong phòng chờ, khi ván đã kết thúc hoặc khi client mất kết nối. Không thêm chat với bot hay chat giữa các phòng.
- Nút Chat luôn ở cùng vị trí trong ván và đóng vai trò bật/tắt panel. Khi đang hiển thị chat có danh sách tin nhắn, ô nhập và nút gửi; Enter gửi tin khi ô nhập được chọn. Khi chat ẩn, tin nhắn vẫn được thêm vào danh sách và nút Chat báo có tin mới.
- Client gửi thông điệp chat qua TCP. Server xác minh kết nối thuộc phòng có ván đang diễn ra, kiểm tra nội dung rồi chuyển cho những người chơi đang kết nối trong phòng đó; tên hiển thị lấy từ trạng thái server, không tin vào tên do client gửi. Không chuyển tin sang phòng khác.
- Quyết định triển khai đề xuất: giới hạn 500 ký tự mỗi tin; bỏ qua tin rỗng hoặc chỉ gồm khoảng trắng; server từ chối tin không hợp lệ. Hiển thị tối đa 100 tin gần nhất trong bộ nhớ client; không lưu database, không khôi phục tin bị bỏ lỡ khi mất kết nối. Khi bắt đầu ván mới hoặc rời phòng, xóa lịch sử chat của ván trước.
- Khi đối thủ mất kết nối, vẫn có thể mở và đọc lịch sử, nhưng không gửi tin mới; giao diện thông báo phù hợp. Không tự gửi lại tin sau khi kết nối lại.

## Kiểm thử

Kiểm thử tin hợp lệ, rỗng, quá dài, gửi ngoài ván và cách ly giữa phòng; kiểm thử bật/tắt panel, nhận khi đang ẩn, giới hạn lịch sử, mất kết nối và bắt đầu ván mới. Kiểm thử thủ công hai client qua TCP/Tailscale; không ảnh hưởng lượt đi, đồng hồ, phong cấp hoặc reconnect.

## Phạm vi mạng

Bỏ UDP, tự dò server và đo độ trễ khỏi kế hoạch hiện tại. Chat và nước đi dùng TCP hiện có; vẫn nhập địa chỉ server và liệt kê phòng từ server đó.
