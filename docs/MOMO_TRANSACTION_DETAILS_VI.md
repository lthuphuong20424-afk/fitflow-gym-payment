# FitFlow v9 — MoMo Transaction Details / Liên hệ CSKH

## Những gì thay đổi

Sau khi xác nhận thanh toán thành công trên MoMo-style Simulator, trình duyệt hiển thị màn **Chi Tiết Giao Dịch** ngay trong cùng khung điện thoại, thay cho màn success đơn giản của v8.

Màn chi tiết sử dụng thông tin thật từ **backend của hệ thống mô phỏng**: mã hóa đơn, mã tham chiếu giao dịch, số tiền, hội viên, thời gian ghi nhận và thời hạn gói tập. Các mục không có dữ liệu thực tế (phí MoMo, điểm thưởng) không được tạo số liệu giả.

Nút **Liên hệ CSKH** thay hoàn toàn nút **Yêu cầu hoàn/hủy**. Khi bấm, một bảng hỗ trợ mở ngay trên màn hình MoMo với thông tin giao dịch và nút **Sao chép thông tin hỗ trợ**. Đây là chức năng minh họa cho buổi thuyết trình; **không có CSKH thật**, không gửi tin nhắn, không thực hiện hoàn tiền hoặc hủy đăng ký. Để gửi yêu cầu CSKH thật, cần kết nối kênh hỗ trợ chính thức do phòng gym cung cấp.

## Luồng kiểm tra

1. Mở FitFlow và chọn **Monthly Pass**.
2. Chọn **MoMo Auto-Renew**. Ví mẫu đã được liên kết sẵn trong Demo Mode.
3. Mở **MoMo Payment**, xác nhận thanh toán.
4. Trình duyệt hiển thị **Chi Tiết Giao Dịch** với trạng thái **Thành công**.
5. Trong khối **Thông tin đơn hàng**, chọn **Liên hệ CSKH**, sau đó sao chép thông tin hoặc đóng bảng hỗ trợ.
6. Bấm **Return to FitFlow**. Ứng dụng trở lại **Digital Receipt** với trạng thái hóa đơn PAID.

Toàn bộ luồng diễn ra trên **một tab**. Sau khi backend áp dụng kết quả giao dịch, trang thành công sử dụng POST/Redirect/GET; tải lại trang không tạo giao dịch mới.

## Chạy local trên Windows (không Docker)

Mở thư mục `Gym_Payment_Fullstack` trong VS Code. Trong Terminal tại thư mục chứa `run_windows.bat` chạy:

```powershell
.\run_windows.bat
```

Mở `http://localhost:8000`. Nếu đã có bản cũ đang chạy, nhấn `Ctrl+C` trước khi khởi động lại và dùng `Ctrl+Shift+R` để cập nhật CSS/JS mới. Nếu trình duyệt còn nhớ hóa đơn cũ, chọn tạo một giao dịch mới để xem đầy đủ luồng.

## Hạn chế

- Không liên kết ví MoMo thật, không chuyển tiền thật.
- Không gửi hỗ trợ khách hàng thật.
- Không xác nhận giá trị phí giao dịch hay thưởng điểm do nhà cung cấp cấp.
- Bản public trên Vercel cần cấu hình PostgreSQL cloud như hướng dẫn `DEPLOY_VERCEL_VI.md`.
