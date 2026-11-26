# FITFLOW STRIDE — BẢN CẬP NHẬT MOMO AUTO-RENEW

Phiên bản này kế thừa **FitFlow_STRIDE_Realistic_Payment_Flow_No_Docker**, không thay thế luồng VietQR và không cần Docker.

## Điểm mới

- Bước đọc điều kiện và đồng ý liên kết/ủy quyền MoMo trước khi thu định kỳ.
- Màn hình **MoMo Authorization Simulator** riêng, có Approve/Decline, trạng thái `PENDING_DEMO` và link hết hạn sau 10 phút; không nhập thông tin ví thật.
- Backend ghi nhật ký consent, trạng thái và mã tham chiếu demo; giao diện tự cập nhật thông qua polling.
- Thanh toán tháng đầu là bước riêng trong **MoMo Payment Simulator**. Cấp quyền thành công không tự kích hoạt gói.
- Mô phỏng một kỳ đến hạn: tạo hóa đơn mới, dùng lại quyền đã cấp, yêu cầu thu từ phía gym và xử lý `PAID`/`FAILED` ở Presenter controls mà không yêu cầu khách phê duyệt lại.
- Hủy quyền thu tương lai, không hoàn tiền cũ; fallback VietQR tiếp tục hoạt động.
- Database SQLite/PostgreSQL tự nâng cấp các cột cần thiết; không phải reset dữ liệu cũ.
- Kiểm thử API: 17 bài, đã đạt trong môi trường local.

## Cách chạy

`py --version` → `.\run_windows.bat` → `http://localhost:8000` → chọn Monthly Pass và MoMo Auto-Renew.

Xem hướng dẫn từng nút: `docs/MOMO_SUBSCRIPTION_DEMO_VI.md`.

## Giới hạn rất quan trọng

**MoMo Subscription live chưa tích hợp.** Mọi thao tác liên kết, xác nhận và thu định kỳ MoMo trong dự án đều giả lập. Không có scheduler chạy tự động theo thời gian thực; Presenter phải chủ động mô phỏng khi đến hạn. Để thu tiền thật cần ký hợp đồng/được MoMo cấp quyền, bảo mật và triển khai/kiểm chứng webhook thực tế. Live payOS VietQR là luồng riêng, chỉ hoạt động sau khi cấu hình merchant.
