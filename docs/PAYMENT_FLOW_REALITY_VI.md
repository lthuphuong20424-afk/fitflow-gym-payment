# FitFlow — Payment Flow Reality (v10)

## Vai trò

- **FitFlow:** tạo invoice, tạo payment attempt, hiển thị QR và quyền hội viên.
- **Bank app:** khách chủ động xác nhận chuyển khoản qua VietQR thật (Live).
- **payOS:** tạo yêu cầu VietQR và thông báo/truy vấn giao dịch.
- **Backend:** kiểm tra kết quả, số tiền, invoice, chữ ký và chỉ kích hoạt một lần.

## Classroom Demo

**QR chỉ mang dữ liệu hóa đơn mẫu, không phải mã chuyển tiền.** Đối với buổi thuyết trình, sử dụng khu vực Presenter / QA để gửi sự kiện thành công/thất bại giả lập. Backend và frontend thể hiện cùng chuỗi trạng thái như tích hợp thật nhưng không có tiền hay ngân hàng tham gia. Màn Demo Bank của các bản v7–v9 đã bỏ khỏi luồng chính. Không yêu cầu mở tab mới.

## Live

Merchant cần hợp đồng/kết nối payOS, khóa API, webhook public HTTPS và tài khoản ngân hàng nhận tiền. Frontend hiển thị QR do payOS trả về; khách mở app ngân hàng, xác minh và chuyển khoản. Backend đối chiếu kết quả đã xác thực trước khi cập nhật `PAID` và kỳ hội viên. `PENDING`, `UNKNOWN`, `FAILED` khác nhau; không tự tạo yêu cầu thu mới khi chưa có kết quả cuối cùng. Nhận lặp webhook phải idempotent.

MoMo Subscription là luồng độc lập, được mô phỏng bằng ví giả định đã liên kết trước đó. Không gọi MoMo simulator là kết nối MoMo thật.

Chi tiết: `VIETQR_V10_PAYMENT_FLOW_VI.md`.
