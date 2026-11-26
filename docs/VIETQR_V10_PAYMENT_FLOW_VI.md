# FitFlow v10 — VietQR đúng nghiệp vụ, gọn và chạy trong một tab

## 1. Hai chế độ, hai nguồn xác nhận khác nhau

| | Classroom Demo (mặc định) | payOS Live (cần tài khoản merchant) |
|---|---|---|
| QR hiển thị | Chuỗi **thông tin hóa đơn mẫu** (`FITFLOW CLASSROOM DEMO - NOT A BANK TRANSFER`) | Mã VietQR trả về từ yêu cầu thanh toán của payOS |
| Quét QR | Chỉ đọc dữ liệu mẫu; **không thể chuyển tiền** | Dùng app ngân hàng để xem và xác nhận chuyển khoản |
| Ai tạo kết quả | Người thuyết trình dùng Presenter/QA để **giả lập** sự kiện từ ngân hàng/PSP | payOS gửi webhook được backend xác thực, hoặc backend truy vấn trạng thái provider |
| Trạng thái khi chưa có kết quả | `PENDING`, chưa kích hoạt | `PENDING`, chưa kích hoạt |
| Khi có kết quả `PAID` hợp lệ | Backend lưu sự kiện mẫu, kích hoạt đúng một lần | Backend xác minh signature + orderCode + số tiền + ID, kích hoạt đúng một lần |
| Chuyển tab | Không | FitFlow vẫn ở tab hiện tại; khách dùng app ngân hàng riêng để chuyển tiền |

> **Lưu ý:** Chế độ Demo không cung cấp VietQR ngân hàng thật. Để khách có thể quét và chuyển khoản từ app ngân hàng, phải dùng payOS Live với thông tin nhận tiền thật và tích hợp merchant hợp lệ.

## 2. Hướng dẫn trình diễn Classroom Demo

1. Khởi động dự án: ` .\run_windows.bat ` và vào `http://localhost:8000`.
2. Chọn **Plans → Monthly Pass → Dynamic VietQR → Proceed to payment**.
3. Màn hình VietQR mới hiển thị: **600,000 VND**, QR mẫu, mã hóa đơn, mã tham chiếu, trạng thái **Awaiting payment confirmation**, và khối hướng dẫn.
4. Giải thích: “QR mẫu chỉ chứa thông tin hóa đơn, nên chưa chứng minh đã nhận tiền. Trong thực tế khách mở ứng dụng ngân hàng để quét VietQR được payOS tạo.”
5. Mở mục **Presenter / QA · Simulate bank / payOS callback** ngay dưới thẻ QR; nhấn **Send success event**.
6. FastAPI ghi nhận sự kiện demo và API `/api/orders/{token}` trả về `PAID`. FitFlow tự cập nhật màn **Digital Receipt** trong cùng tab.
7. Để thử thất bại, tạo hóa đơn mới rồi nhấn **Send failed event**. Hóa đơn chưa trả, hệ thống cho tạo yêu cầu QR mới; lịch sử lần thử cũ được giữ lại.

### Các trường hợp quan trọng khi phản biện

- **Pending:** chưa gia hạn, không tự báo thành công theo thời gian đếm.
- **Timeout/Unknown Live:** không phát lệnh thu khác khi chưa kiểm tra request cũ.
- **Sai số tiền:** backend từ chối ghi nhận thành công; ghi lại ngoại lệ phục vụ đối soát.
- **Webhook trùng:** không gia hạn lần hai.
- **Chuyển tiền hai lần thật:** phải ghi nhận ngoại lệ đối soát và hoàn tiền theo quy trình, không tự xóa dấu vết.

## 3. Chế độ Live

1. Được payOS chấp nhận merchant và cấu hình phương thức nhận tiền.
2. Tạo `.env` với `PAYMENT_MODE=live`, `DATABASE_URL`, bộ khóa payOS, `PUBLIC_BASE_URL` là HTTPS public.
3. Đăng ký webhook `/api/webhooks/payos` và xác minh chữ ký, mã đơn hàng, số tiền, tham chiếu giao dịch ở backend.
4. Tạo hóa đơn trong FitFlow; backend gọi API payOS để tạo **payment request riêng cho hóa đơn** và hiển thị QR ngân hàng thật.
5. Khách chuyển khoản từ ứng dụng ngân hàng; FitFlow tiếp tục chờ cho tới khi nhận kết quả được xác thực từ payOS.

Không đưa khóa API/secret lên JavaScript frontend. Chế độ Live chưa được thử bằng giao dịch tiền thật trong môi trường này. Mô hình hiện tại chưa đủ các kiểm soát bảo mật để vận hành production.
