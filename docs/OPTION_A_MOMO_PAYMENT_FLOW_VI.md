# FitFlow — Quy trình MoMo đã chốt (Option A)

**Phiên bản trình diễn:** mô phỏng tài khoản MoMo đã được liên kết và đã cấp quyền thu định kỳ trước đó. Không đăng nhập ví, không nhập số thẻ, PIN, CVV hay OTP. Không chuyển tiền thật.

## Luồng thanh toán tháng đầu (một tab Chrome)

1. Trên FitFlow, chọn **Monthly Pass → MoMo Auto-Renew → Proceed to payment**.
2. Màn FitFlow hiển thị ví demo đã liên kết sẵn (không xuất hiện bước cấp quyền). Chọn **Open MoMo payment**.
3. Ứng dụng điều hướng **trong cùng tab** sang **MoMo-style Payment**, hiển thị tên FITFLOW CLUB, mã đơn hàng, 600.000đ và nguồn tiền mô phỏng.
4. Nhấn **Xác nhận**. Backend đối chiếu đơn và ghi nhận thanh toán, sau đó trả về **trang MoMo Success riêng bằng GET**. Việc tải lại trang kết quả không gửi lại biểu mẫu POST.
5. MoMo Success hiển thị **Thanh toán thành công**, số tiền, mã hóa đơn, mã giao dịch mô phỏng, hội viên và thời điểm ghi nhận.
6. Nhấn **Return to FitFlow**. Trình duyệt trở về `/?receipt=<order-token>` **trong cùng tab**; FitFlow tải trạng thái `PAID` từ backend và hiển thị **Digital Receipt**.

## Kỳ gia hạn tự động

Có thể dùng **Simulate Next Billing Cycle** ở các điều khiển dành cho giảng viên. Backend tạo hóa đơn của kỳ mới. Đây là mô phỏng merchant-initiated collection, **không xuất hiện lại màn xác nhận khách hàng**, và không phải một scheduler hoặc giao dịch MoMo thật.

## Giới hạn quan trọng

Màn hồng–trắng là **MoMo-style classroom simulator**, không phải MoMo chính thức. Bản demo đặt sẵn một quyền thu trong cơ sở dữ liệu mô phỏng; **trong triển khai thực tế, quyền thu định kỳ phải được khách hàng cấp trước tại MoMo**. Không suy ra rằng việc lưu thông tin ví trong app gym đã cấp quyền thu.

VietQR v10 không còn bắt buộc điều hướng Demo Bank: hiển thị QR mẫu + chờ xác nhận, dùng Presenter / QA mô phỏng callback trong cùng tab. Với payOS Live, QR do payOS tạo và backend xác minh webhook thật.
