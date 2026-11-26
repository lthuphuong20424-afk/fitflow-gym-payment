> **Cập nhật v4:** Hai màn AUTHORIZATION và PAYMENT hiện đã được thiết kế cùng một phong cách MoMo hồng–trắng. Xem `MOMO_V4_STYLE_FLOW_VI.md` để có tên nút chính xác trong giao diện mới.

# FitFlow STRIDE — Luồng liên kết ví và thu phí định kỳ MoMo (mô phỏng)

> **Phạm vi:** Đây là mô phỏng nghiệp vụ cho bài giữa kỳ INS3068. Trang xác thực mang màu sắc MoMo để minh họa nhưng có nhãn rõ **CLASSROOM SIMULATOR — NOT THE MOMO APP**. Không có API MoMo thật, tài khoản ví thật, token của MoMo thật, giao dịch thật, OTP hay mật khẩu được thu thập. Chỉ VietQR khi cấu hình `PAYMENT_MODE=live` và payOS có khả năng xử lý tiền thật.

## 1. Chạy dự án không dùng Docker

1. Giải nén ZIP và mở **thư mục `Gym_Payment_Fullstack`** trong VS Code.
2. Mở **Terminal → New Terminal**.
3. Kiểm tra Python: `py --version` (khuyến nghị Python 3.12 trở lên).
4. Chạy: `./run_windows.bat` hoặc ` .\run_windows.bat` trong PowerShell. Nếu file chạy không được, kiểm tra Python PATH.
5. Mở **http://localhost:8000** trên máy tính. SQLite được tạo tự động trong `data/`.

## 2. Luồng MoMo khách hàng — kịch bản đầy đủ

1. **Choose Plan** → chọn **Monthly Pass — 600,000 VND**. Gói 3/6 tháng chỉ thanh toán một lần, không tự mở Subscription.
2. **Continue** → điền tên hội viên mẫu, chọn **MoMo Auto-Renew**, bấm **Proceed to payment**. Backend lập hóa đơn `UNPAID`; chưa cấp quyền, chưa thu phí.
3. Trên thẻ **MoMo Monthly Auto-Renew**, kiểm tra: số tiền tối đa 600,000 VND/tháng, chu kỳ monthly, điều kiện hủy. Tích **I understand the monthly amount...** rồi chọn **Connect MoMo Wallet**.
4. FitFlow tạo phiên ủy quyền ở backend (trạng thái `PENDING_DEMO`, có link 10 phút), mở một tab **MoMo Authorization Simulator**. Không yêu cầu mật khẩu, PIN hoặc OTP.
5. Trên tab simulator, khách chọn **Approve monthly auto-renew** hoặc **Decline authorization**:
   - Approve → backend lưu dấu vết đồng ý (`consent_at`, mã tham chiếu demo), trạng thái `ACTIVE_DEMO`.
   - Decline → `DECLINED_DEMO`, không cấp quyền, không được thu.
   - Hết 10 phút hoặc link không hợp lệ → không thể hoàn tất; có thể khởi tạo lại trên FitFlow.
6. Quay lại FitFlow, chờ 2–3 giây: màn **Wallet linked · DEMO** xuất hiện. **Chú ý:** hóa đơn vẫn `UNPAID`, chưa kích hoạt gói.
7. Nhấn **Pay first month with MoMo** → một tab mô phỏng thu phí tháng đầu mở ra; chọn **Confirm demo first payment** (hoặc **Simulate failed payment**). Backend ghi nhận `PAID`/`FAILED` và đồng bộ giao diện tự động.
8. Nếu thanh toán thành công → **Payment Successful** và biên nhận, ngày hết hạn hội viên. Nếu thất bại → hóa đơn chưa trả, có thể chọn **Switch to VietQR** cho *cùng hóa đơn*; hai lần thử được lưu, hội viên chỉ được kích hoạt một lần.
9. Trên biên nhận, nếu quyền thu còn hiệu lực, mở **Presenter · Next monthly billing cycle** → **Run next billing cycle (demo)**. Backend tạo hóa đơn phí tháng kế tiếp và thử thu `MOMO_DEMO` ở trạng thái `PENDING` **không bắt khách xác nhận lại quyền thu**. Mở **QA / Presenter** và thử `Simulate paid` hoặc `Simulate failed` để minh họa kết quả PSP.
10. **Cancel future auto-renew (demo)** → tắt quyền thu tương lai; khoản đã thu không tự hoàn tiền; nút chạy kỳ tiếp theo bị chặn.

## 3. Những điểm nghiệp vụ cần giải thích khi thuyết trình

| Đối tượng | Trạng thái / Nguyên tắc |
|---|---|
| Subscription consent | `PENDING_DEMO` → `ACTIVE_DEMO` hoặc `DECLINED_DEMO`; có thể `CANCELLED_DEMO` |
| Invoice | `UNPAID` / `PENDING` / `PAID`: không được tự coi là trả tiền vì cấp quyền thành công |
| Payment attempt | Một hóa đơn có thể có nhiều lần thử: MoMo failed → VietQR paid |
| Sự kiện xác minh | Backend mới đánh dấu Paid, frontend không tự ghi Paid từ nút chọn phương thức |
| Thu kỳ sau | Trong demo, Presenter chủ động kích hoạt kịch bản kỳ đến hạn. Chưa có scheduler tự động, không gọi API MoMo thật |
| Ngăn thu trùng | Một hóa đơn Paid một lần; phát sinh lần thu thực tế bổ sung phải lưu và đối soát |
| Hủy quyền | Chỉ chặn các khoản thu tương lai; khác với Refund |

**Phân biệt quan trọng:** MoMo **Subscription** là cơ chế cho phép trước khoản thu định kỳ trên ví MoMo, không phải biểu mẫu nhập số thẻ Visa/Mastercard. Người dùng thực tế phải chuyển sang luồng do MoMo cung cấp để cấp quyền. Ngày ủy quyền, token và trạng thái phải được kiểm tra bằng kết quả chính thức của MoMo trong một tích hợp thực, thay vì tin vào frontend. Bản demo sử dụng mã `MOMO-SIM-...` hoàn toàn giả định, **không phải subsToken**.

## 4. API phục vụ mô phỏng

| API | Mục đích |
|---|---|
| `POST /api/demo/orders/{token}/momo/start` | Khởi tạo quyền thu đang chờ, trả URL simulator |
| `GET /demo/momo/{token}?auth=...` | Trang giải thích và phê duyệt mô phỏng |
| `POST /demo/momo/{token}/decision` | Approve/Decline trong simulator |
| `POST /api/demo/orders/{token}/momo/charge` | Bắt đầu thanh toán tháng đầu riêng biệt |
| `GET /demo/momo/{token}/payment?attempt=...` | Trang thanh toán giả lập tháng đầu |
| `POST /demo/momo/{token}/payment/decision` | Xác nhận Paid/Failed ở demo wallet |
| `POST /api/demo/orders/{token}/momo/next-cycle` | Tạo hóa đơn và yêu cầu thu cho *kỳ kế tiếp giả lập* |
| `POST /api/demo/orders/{token}/momo/collect` | Nhà cung cấp giả lập thông báo kết quả thu kỳ tiếp theo (QA) |
| `POST /api/demo/orders/{token}/momo/cancel` | Hủy quyền thu tương lai |
| `GET /api/orders/{token}` | Frontend theo dõi trạng thái đã lưu ở backend |

Những endpoint `/api/demo/...` và `/demo/momo/...` **không hoạt động khi `PAYMENT_MODE=live`**. Không dùng chúng để tạo thanh toán thật. Thông tin đăng nhập và OTP của MoMo không xuất hiện trong dự án.

## 5. Khi muốn tích hợp MoMo thật

Cần được MoMo cấp tài khoản đối tác và quyền sử dụng Subscription API; backend phải khởi tạo request có chữ ký, nhận redirect/notification, xác minh kết quả cấp quyền, đổi callbackToken theo quy trình chính thức để lấy token, quản lý trạng thái quyền thu, xử lý token bị tạm dừng/hủy, thực hiện merchant-initiated charge đúng hạn và đối soát. Việc này **chưa được triển khai trong ZIP**. Không được thay chỉ bằng một ô nhập thông tin MoMo của khách hoặc giữ token giả từ bản demo.

Nguồn kỹ thuật chính thức:
- https://developers.momo.vn/v3/docs/payment/api/wallet/subscription/
- https://developers.momo.vn/v3/docs/payment/guides/aio-tokenization-payment/

## 6. Kết quả kiểm thử

Chạy tại thư mục gốc: `py -m pytest -q tests/test_payments.py` sau khi cài dependencies. Bộ test kiểm tra cấp quyền/thanh toán tách biệt, từ chối, làm lại phiên, token phiên sai, trạng thái Pending, fallback VietQR, thu kỳ tiếp theo idempotent, hủy quyền và vô hiệu hóa mô phỏng khi Live.

**Vercel:** vẫn không cần Docker. Khi public, cần PostgreSQL (`DATABASE_URL`) ngoài Vercel để lưu hóa đơn và quyền thu; chi tiết tại `docs/DEPLOY_VERCEL_VI.md`. Các kết quả thanh toán ở demo chỉ là mô phỏng, kể cả khi có URL công khai.
