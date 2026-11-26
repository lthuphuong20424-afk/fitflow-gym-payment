# Single-tab journeys — FitFlow v10

**MoMo:** FitFlow → MoMo-style Payment → Transaction Details (success) → Return to FitFlow → Digital Receipt. Ví mẫu đã liên kết sẵn, không có tiền thật.

**VietQR Classroom Demo:** FitFlow → VietQR QR mẫu + `PENDING` → Presenter / QA gửi sự kiện PSP giả lập → Backend `PAID` → FitFlow Digital Receipt. Tất cả trong một tab, không có Demo Bank bắt buộc.

**VietQR Live:** FitFlow hiển thị mã QR ngân hàng từ payOS; khách dùng ứng dụng ngân hàng riêng để chuyển tiền; webhook/truy vấn trạng thái đã xác minh cập nhật hóa đơn, sau đó FitFlow hiển thị biên nhận. Không coi quét QR là đã thanh toán.

Xem `VIETQR_V10_PAYMENT_FLOW_VI.md` để thao tác chi tiết.
