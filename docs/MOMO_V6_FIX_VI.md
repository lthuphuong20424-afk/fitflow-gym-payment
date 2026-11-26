# FitFlow v6 — Sửa nút Xác nhận thanh toán MoMo

## Vấn đề của v5

Hai trường `wallet-suffix` và `auth-consent` thuộc bước liên kết ví vẫn nằm trong biểu mẫu thanh toán và còn thuộc tính `required`, dù màn hình liên kết đã được ẩn. HTML validation của trình duyệt chặn việc bấm nút **Xác nhận**.

## Đã sửa

- Tự động `disabled` và bỏ `required` ở hai trường khi đang ở màn *payment*; chỉ yêu cầu chúng trên màn *authorization* cũ nếu mở thủ công.
- Bấm **Xác nhận** gửi POST thanh toán mô phỏng tới backend.
- Khi backend chuyển hóa đơn sang `PAID`, màn **Thanh toán thành công** hiển thị số tiền, mã hóa đơn và nút **Quay lại FitFlow**.
- Đã bổ sung hàm xử lý ví mẫu liên kết sẵn cho PostgreSQL (để Vercel có thể chạy cùng logic với SQLite local).
- Vẫn giữ cơ chế giả lập, không trừ tiền từ ví MoMo thật.

## Chạy trên Windows (không Docker)

1. Dừng server v5 bằng `Ctrl+C` trong terminal.
2. Giải nén ZIP v6 vào thư mục mới và mở thư mục `Gym_Payment_Fullstack` bằng VS Code.
3. Chạy `.\run_windows.bat` trong PowerShell.
4. Vào `http://localhost:8000` và bấm `Ctrl+Shift+R`.
5. Tạo **hóa đơn mới**: `Monthly Pass` → `MoMo Auto-Renew` → `Proceed to payment` → `Open MoMo payment` → `Xác nhận`.
6. Quan sát màn thành công trong trang MoMo simulator, sau đó bấm `Quay lại FitFlow` để xem biên lai.

**Lưu ý:** Quyền sử dụng ví mẫu đã được giả định cho mục đích demo. Trong thực tế, thanh toán tự động vẫn yêu cầu khách hàng đã cấp quyền hợp lệ cho MoMo Subscription.
