# Tự động nối lại ván online

## Mục tiêu và phạm vi

Giữ ván TCP đang diễn ra khi kết nối mất ngoài ý muốn; client tự thử nối lại trong tối đa 60 giây. Sau khi mở lại ứng dụng, người chơi cũng có thể chọn **Kết nối lại** từ luồng Chơi Online → Vào phòng. Đồng hồ ván tiếp tục chạy. Người chơi chủ động rời phòng phải xác nhận đầu hàng; xác nhận kết thúc ván và đóng phòng, hủy giữ nguyên ván. Không triển khai UDP hoặc lưu phiên sau khi server khởi động lại.

## Các phương án

- **Tự động nối lại:** client thử lại và hiển thị trạng thái; cần xử lý vòng đời kết nối và đồng bộ, nhưng ít gây gián đoạn. Người dùng chọn phương án này.
- **Nối lại thủ công:** dễ triển khai hơn nhưng cần người chơi thao tác trong thời gian chờ.

Hai cách bổ sung cho nhau: tự động khi ứng dụng vẫn chạy; lựa chọn thủ công khi người chơi mở lại ứng dụng.

## Thiết kế

- Server giữ phòng và trạng thái ván trên RAM khi một kết nối mất; thông báo cho đối thủ và cho mỗi bên một token phiên riêng, không dùng chung token phòng. Token được tạo bằng nguồn ngẫu nhiên an toàn và chỉ gắn với một vị trí trong một ván.
- Trong Chơi Online → Vào phòng, bổ sung lựa chọn **Kết nối lại**. Sau khi ứng dụng mở lại, lựa chọn này dùng thông tin phiên đã lưu của người chơi để gửi `RESUME`, không gửi `JOIN_ROOM` như một người mới. Nếu không có phiên phù hợp, sai token, server không truy cập được hoặc hết hạn, hiển thị lý do và cho phép quay lại; không tự tạo ván mới.
- Lưu token phiên và thông tin server/phòng bằng cơ chế lưu trữ cục bộ được bảo vệ, tách phiên của từng người chơi ngay cả khi chạy hai client trên một máy; không dùng mã phòng hay tên khách làm bằng chứng sở hữu phiên. Xóa thông tin phiên khi ván kết thúc hoặc đầu hàng, và không đưa token vào log hoặc mã nguồn. Cần xác định và kiểm thử cơ chế bảo vệ phù hợp trên các hệ điều hành được hỗ trợ trước khi triển khai.
- Client phát hiện kết nối đóng hoặc heartbeat thất bại, thông báo đang kết nối lại và tự thử kết nối đến cùng server. Vì thời điểm phát hiện ở client và server có thể khác nhau, client tiếp tục thử cho đến khi server báo hết hạn/kết thúc hoặc người chơi hủy; server quyết định hạn 60 giây. Việc thử lại chạy ngoài vòng lặp giao diện; không cho gửi nước đi khi mất kết nối hoặc đang chờ đồng bộ.
- Heartbeat TCP dùng PING/PONG mỗi 3 giây, coi kết nối chết sau 6 giây không có phản hồi; kiểm tra theo chu kỳ 1 giây. Cơ chế theo dõi phải giữ nguyên dữ liệu frame đang nhận dở; khi quá hạn, đóng socket để luồng đọc thoát. Thời hạn nối lại 60 giây bắt đầu khi server xác định kết nối bị mất, dựa trên đồng hồ monotonic của server.
- Client gửi RESUME với token phiên riêng. Server xác minh phiên, thời hạn và trạng thái ván; thay kết nối cũ bằng kết nối mới một cách nguyên tử, gửi snapshot có màu quân, FEN, lượt, thời gian, kết quả, revision, nước cuối và thông tin cần thiết để khôi phục hiển thị; thông báo đối thủ khi kết nối lại. Một token không thể chiếm vị trí của bên còn lại.
- Server là nguồn sự thật: nếu mất kết nối ngay sau khi gửi nước đi, client không tự gửi lại nước cũ; sau RESUME dùng snapshot và revision của server. Snapshot bao gồm lịch sử nước đi để khôi phục danh sách nước đi. Từ chối token sai hoặc hết hạn với lý do rõ ràng; nếu ván kết thúc khi người chơi mất kết nối, giữ kết quả đến hết thời hạn nối lại và cho phép nhận snapshot kết thúc, không tiếp tục ván.
- Đồng hồ ván tiếp tục chạy trong thời gian mất kết nối. Nếu hết giờ trước thời hạn nối lại, kết quả theo luật đồng hồ được xử lý; nếu thời hạn nối lại hết trước và chỉ một bên đang mất kết nối, bên đó thua. Nếu cả hai cùng mất kết nối khi hạn đầu tiên đến, xử hòa do cả hai mất kết nối. Xử lý thứ tự sự kiện dưới cùng khóa server để chỉ công bố một kết quả; không kết thúc ván hai lần.
- Nút rời phòng trong ván online mở xác nhận đầu hàng. Hủy giữ ván; xác nhận gửi RESIGN, server thông báo kết quả và đóng phòng. Nếu kết nối đã mất, client hiển thị không thể xác nhận đầu hàng và tiếp tục thử nối lại; không tự tuyên bố kết quả server.

## Kiểm thử và giới hạn

Kiểm thử tự động heartbeat, ngắt và nối lại đúng/sai token, hai bên có token khác nhau, hết hạn, đồng hồ hết trước hạn nối lại, ngắt sau nước đi đã được chấp nhận, cả hai mất kết nối, từ chối kết nối cũ và xác nhận/hủy đầu hàng. Kiểm thử hai client trên cùng máy, đóng ứng dụng một bên, mở lại và chọn Kết nối lại; xác nhận đúng màu, lịch sử và đồng hồ, không thể chiếm phiên của người khác. Kiểm thử tích hợp TCP và kiểm thử thủ công mất mạng, nối lại và rời phòng. Không ghi token hoặc mật khẩu vào log. Kiểm thử trên LAN thực tế được thực hiện riêng sau kiểm thử localhost.
