# FitFlow STRIDE 2.0 — Menu và liên kết ví mô phỏng

## Nội dung đã bổ sung

**Menu cố định 5 mục trong khung điện thoại**

- **Home:** tổng quan hội viên, trạng thái kỳ tập, tác vụ nhanh và nhắc thanh toán đang mở.
- **Plans:** chọn Monthly / Quarterly / Semiannual Pass. Nếu đã có hóa đơn chưa hoàn tất, nút chính quay lại hóa đơn cũ để tránh tạo thanh toán trùng.
- **Wallet:** tình trạng MoMo Auto-Renew, thao tác kết nối/hủy (mô phỏng), phương thức VietQR và giải thích vì sao không nhập thẻ trực tiếp vào app gym.
- **Activity:** lịch sử hóa đơn và trạng thái do backend lưu. Danh sách xem được là các hóa đơn gắn với trình duyệt hiện tại, không phải hệ thống tài khoản đăng nhập đa người dùng.
- **Profile:** nhập tên hội viên, email và số điện thoại mẫu. Thông tin bổ sung lưu cục bộ ở trình duyệt, không được backend xác thực hay gửi đến MoMo. Tên hội viên được dùng khi tạo hóa đơn.

## Hướng dẫn demo đầy đủ (không Docker)

1. Giải nén thư mục `Gym_Payment_Fullstack` và mở đúng thư mục trong VS Code.
2. Chạy `py --version` (Python 3.12+), rồi ` .\run_windows.bat` ở PowerShell.
3. Mở `http://localhost:8000`. Chọn tab **Profile**, điền **tên mẫu** (ví dụ Linh Tran), email và điện thoại (không bắt buộc), chọn **Save member profile**.
4. Chọn tab **Wallet** → **Connect MoMo Wallet**. FitFlow tạo yêu cầu thanh toán của **Monthly Pass**; tên hội viên được điền sẵn từ hồ sơ.
5. Chọn **Proceed to payment**. Đọc các điều khoản thu định kỳ **600,000 VND mỗi tháng**, tích ô đồng ý, chọn **Connect MoMo Wallet**.
6. Một tab **MoMo Authorization Simulator** mở ra. Xem `FitFlow Test Wallet •••• 8842`, nhập 4 số cuối ví **mẫu** là `8842`, tích ô xác nhận, nhấn **Approve monthly auto-renew** (hoặc **Decline** để thử nhánh từ chối). Không nhập mật khẩu, OTP, PIN, CVV hoặc thông tin thẻ thật.
7. Quay về FitFlow; trạng thái sẽ đổi sang **Wallet linked · DEMO** sau khi backend nhận kết quả. Hóa đơn vẫn chưa trả tiền.
8. Nhấn **Pay first month with MoMo** → trên màn mô phỏng thanh toán riêng chọn xác nhận thành công hoặc thất bại. Sau khi thành công, FitFlow tự hiển thị biên nhận, kỳ tập được kích hoạt một lần.
9. Thử tab **Wallet**, **Home**, **Activity** và **Profile** sau khi thanh toán. Trên biên nhận có thể trình diễn mô phỏng kỳ thu tiếp theo và hủy quyền thu.
10. Để thử VietQR: chọn gói tập khác sau khi hoàn tất hóa đơn cũ, chọn **Dynamic VietQR**. QR Demo chứa thông tin hóa đơn mẫu; mở **Presenter / QA → Simulate bank / payOS callback → Send success event**, rồi quan sát FitFlow tự chuyển sang `PAID`.

## Quy tắc an toàn và phạm vi thực tế

- **MoMo Subscription thật** không nhập tài khoản/mật khẩu ví tại website gym. Phải chuyển sang quá trình xác thực và cấp quyền do MoMo vận hành, sau đó backend xác minh kết quả PSP và lưu token thay vì thông tin bí mật của khách.
- Ô `8842` là **mã ví giả định được công khai ngay trên màn hình** chỉ để mô phỏng thao tác xác nhận; nó không chứng minh người nhập là chủ ví thật.
- **Thẻ ngân hàng** chỉ nên được nhập trên checkout do PSP có khả năng xử lý thẻ cung cấp (hosted fields/redirect), với token hóa thích hợp. Chưa có tích hợp thanh toán thẻ trong project này; phần Wallet ghi rõ giới hạn đó.
- Chế độ **Demo** không chuyển tiền thật; phần **payOS Live** chỉ dành cho VietQR sau khi cấu hình merchant và webhook. MoMo Live hiện chưa tích hợp.
- Bản public Vercel là bản trình diễn nghiệp vụ, **chưa có hệ thống đăng nhập và phân quyền hội viên**, không dùng để lưu dữ liệu nhạy cảm hoặc nhận thẻ thật.

## Chạy kiểm thử

```powershell
py -m pip install -r backend\requirements.txt
py -m pip install pytest httpx
py -m pytest -q tests\test_payments.py
```

Nếu gặp lỗi cổng 8000 đã được sử dụng, hãy dừng server cũ trong Terminal bằng `Ctrl+C` trước khi chạy lại.
