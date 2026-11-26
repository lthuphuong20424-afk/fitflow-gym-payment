# FitFlow STRIDE v4 — MoMo-style provider simulator

## Vì sao bản trước nhìn khác ảnh mẫu?
Ở bản v3, màn **cấp quyền MoMo** tại `/demo/momo/{token}?auth=...` vẫn dùng giao diện tím cũ. Bản giao diện mới chỉ nằm ở màn **thanh toán tháng đầu** `/demo/momo/{token}/payment?attempt=...`. Vì vậy ảnh chụp ở màn AUTHORIZATION không hề giống màn PAYMENT đã chốt.

Bản v4 sửa triệt để: **cả hai màn dùng chung `frontend/momo_simulator.html`, `css/momo_simulator.css` và `js/momo_simulator.js`**, đều là khung điện thoại tông hồng/trắng kiểu ứng dụng MoMo, có thẻ thông tin FitFlow Club và thanh hành động dưới đáy. Không Docker.

## Chạy mới trên Windows (tránh mở nhầm bản v3)

1. Dừng server cũ trong VS Code bằng `Ctrl+C`.
2. **Giải nén ZIP v4 vào một thư mục mới**, không mở lại bản `Gym_Payment_Fullstack` cũ.
3. Mở thư mục `Gym_Payment_Fullstack` của v4 bằng VS Code.
4. Chạy `./run_windows.bat` trong PowerShell (hoặc ` .\run_windows.bat`).
5. Mở `http://localhost:8000` bằng Chrome và nhấn `Ctrl+Shift+R` nếu trình duyệt giữ giao diện cũ.

## Kịch bản gồm hai bước tách biệt

**A. Liên kết ví — chưa thu tiền**
1. Home hoặc Plans → Monthly Pass → chọn **MoMo Auto-Renew**.
2. Xác nhận điều khoản trên FitFlow → **Connect MoMo Wallet**.
3. Tab MoMo-style mở ra với tiêu đề **Thanh toán an toàn** và banner **Xác nhận liên kết Ví MoMo**.
4. Cuộn xuống thẻ **Xác nhận ví và ủy quyền**, kiểm tra hạn mức 600.000đ/tháng.
5. Nhập **8842** (chỉ là 4 số cuối của ví mẫu được hiển thị), tích đồng ý và bấm **Cho phép thu định kỳ**.
6. Trang hiển thị **Liên kết ví thành công**. Chọn **Quay lại FitFlow**. Hóa đơn vẫn chưa PAID.

**B. Thanh toán tháng đầu — xác nhận khoản tiền riêng**
1. Tại FitFlow, bấm **Pay first month with MoMo**.
2. Tab mới mở ra **Thanh toán an toàn** với thẻ **FitFlow Club** gồm số tiền, mã hóa đơn, nguồn tiền, ưu đãi và các ngân hàng mẫu.
3. Chọn Ví MoMo hoặc một nguồn tiền mẫu → **Xác nhận**.
4. Backend ghi nhận PAID và kích hoạt hội viên một lần. Trang MoMo-style hiển thị **Thanh toán thành công** → **Quay lại FitFlow**, nơi hiển thị biên nhận.
5. Thử **Từ chối thanh toán** bằng hóa đơn mới để minh họa FAILED và **VietQR fallback**.

**Lưu ý:** Không cần nhập mã ví cho bước thanh toán B, bởi bước A đã hoàn tất liên kết. Đây là logic mô phỏng Subscription; khách chỉ cần cấp quyền định kỳ một lần. Các kỳ sau backend có thể mô phỏng merchant-initiated collection bằng Presenter controls, không yêu cầu xác nhận lại từng kỳ.

## Phân biệt DEMO và LIVE
- MoMo-style là **classroom simulator**, không phải ứng dụng MoMo thật; các nguồn tiền và số dư hiển thị đều là **mẫu**. Không đăng nhập ví thật, không nhập OTP/PIN/mật khẩu/CVV.
- Các endpoint `/demo/momo/...` bị vô hiệu hóa ở `PAYMENT_MODE=live`. Chưa có API Subscription thật và không trừ tiền ngân hàng.
- Giao diện FitFlow chính vẫn bằng tiếng Anh; hai màn provider simulator dùng tiếng Việt theo ảnh tham khảo của nhóm. Nếu yêu cầu toàn dự án tiếng Anh, dịch riêng các chuỗi trong `frontend/momo_simulator.html` và `frontend/js/momo_simulator.js`.
- Phần backend SQLite cho local và PostgreSQL cho Vercel không thay đổi.

## Thành phần đã thay đổi
- `backend/app/main.py`: thay hai trang HTML riêng biệt bằng một helper render từ template, giữ logic authorization/payment idempotent; cho phép chọn **nguồn tiền mẫu** hợp lệ trong trang payment.
- `frontend/momo_simulator.html`: cấu trúc chung của hai màn MoMo-style.
- `frontend/css/momo_simulator.css`: tông hồng/trắng, khung điện thoại, responsive, sticky confirmation.
- `frontend/js/momo_simulator.js`: hiển thị dữ liệu hóa đơn thật từ backend, điều hướng trạng thái, lựa chọn nguồn tiền mẫu, promo demo.
- `tests/test_payments.py`: bổ sung kiểm thử cả hai màn thống nhất giao diện và kiểm tra nguồn tiền mẫu.

## Test

Mở terminal ở thư mục gốc rồi chạy `py -m pytest -q` nếu đã cài pytest, hoặc `python -m pytest -q`.

Trong bài thuyết trình, nhấn mạnh: khách **cấp quyền MoMo trước**, **trả tiền tháng đầu riêng**, sau đó các kỳ tương lai mới có thể **thu theo lịch bằng API Subscription** khi tích hợp chính thức và còn quyền hợp lệ.
