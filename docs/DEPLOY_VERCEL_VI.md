# Hướng dẫn public FitFlow lên Vercel — không sử dụng Docker

## 0. Những gì đã sẵn sàng và những gì chưa

File ZIP đã có **frontend STRIDE + FastAPI + SQLite khi chạy local + PostgreSQL khi triển khai Vercel**, cùng cấu hình `pyproject.toml`. Chưa có link public vì phải đăng nhập **GitHub/Vercel** và tạo **database cloud** bằng tài khoản của em. Không cần Docker Desktop, Dockerfile, compose hoặc XAMPP.

**Mục tiêu của bước đầu:** public chế độ `DEMO`, thử luồng giao diện và mô phỏng callback. **Chưa phải** giao dịch tiền thật.

## 1. Chạy trên Windows bằng VS Code

1. Giải nén ZIP; mở đúng thư mục có `pyproject.toml` và `run_windows.bat`.
2. Mở VS Code → **Terminal → New Terminal**.
3. Kiểm tra `py --version`, nên dùng Python **3.12**.
4. Nhập ` .\run_windows.bat `.
5. Truy cập `http://localhost:8000` và `http://localhost:8000/api/health`.
6. Local mặc định dùng SQLite; không cần tạo database hoặc thêm `.env`.

## 2. Tạo PostgreSQL cloud (ví dụ: Neon)

1. Vào [Neon Console](https://console.neon.tech/), tạo một project PostgreSQL.
2. Trong **Connection Details**, chọn **Pooled connection**, copy *PostgreSQL connection string* (định dạng `postgresql://user:password@host/db?sslmode=require`).
3. Lưu chuỗi này ở nơi an toàn; **không đăng vào chat, không chèn vào file frontend và không commit lên GitHub**.
4. Database có thể trống; backend sẽ tạo 5 bảng vào lần khởi tạo đầu tiên.

Có thể sử dụng PostgreSQL của Supabase thay Neon; cần dùng connection URI phù hợp cho serverless.

## 3. Đẩy code lên GitHub

1. Tạo một GitHub repo, ví dụ `fitflow-gym-payment`.
2. Mở Terminal tại đúng thư mục dự án (có `pyproject.toml`):

```powershell
git init
git add .
git commit -m "FitFlow: Docker-free FastAPI + Vercel + PostgreSQL"
git branch -M main
git remote add origin https://github.com/<username>/fitflow-gym-payment.git
git push -u origin main
```

Nếu repo đã có remote, dùng `git remote -v` để xem trước và không chạy lại `git remote add origin`. File `.env`, `.venv` và file SQLite được `.gitignore` loại trừ.

## 4. Import repository trên Vercel

1. Truy cập [Vercel Dashboard](https://vercel.com/dashboard).
2. Chọn **Add New → Project → Import Git Repository** (cấp quyền GitHub nếu Vercel yêu cầu).
3. Chọn repo FitFlow vừa push.
4. **Root Directory:** thư mục đang chứa `pyproject.toml` (nếu push nội dung thư mục `Gym_Payment_Fullstack` làm root của repo thì chọn `./`).
5. Để Vercel **auto-detect Python/FastAPI**, không đặt custom build command hay output directory; cấu hình `pyproject.toml` trỏ tới `backend.app.main:app`.
6. Mở phần **Environment Variables**, thêm:

| Key | Value |
|---|---|
| `DATABASE_URL` | Chuỗi PostgreSQL Pooled đã copy từ Neon |
| `PAYMENT_MODE` | `demo` |

7. Nhấn **Deploy**. Nếu biến môi trường được thêm sau khi build, chọn **Redeploy** để áp dụng.
8. Truy cập `https://<project>.vercel.app` và `https://<project>.vercel.app/api/health`.
9. JSON health phải cho thấy `"mode":"demo"` và `"database":"postgresql"`.
10. Thử: **Monthly Pass → VietQR → Presenter / QA → Send success event → Receipt**, rồi reload để kiểm tra trạng thái vẫn được lưu.

### QR trong chế độ DEMO

QR Demo v10 chỉ chứa **dữ liệu hóa đơn mẫu, không phải URL hay VietQR chuyển tiền**. Không yêu cầu `PUBLIC_BASE_URL` để quét QR mẫu. Muốn QR thật dùng được bằng app ngân hàng, cần `PAYMENT_MODE=live`, merchant payOS và địa chỉ HTTPS cho webhook.

## 5. Khi muốn thanh toán VietQR thật bằng payOS

Chỉ thực hiện sau khi có merchant account payOS và tài khoản ngân hàng nhận tiền. Trong **Vercel → Settings → Environment Variables** thiết lập:

```text
PAYMENT_MODE=live
DATABASE_URL=<postgresql_connection_url>
PUBLIC_BASE_URL=https://<your-stable-production-domain>
PAYOS_CLIENT_ID=<server_side_secret>
PAYOS_API_KEY=<server_side_secret>
PAYOS_CHECKSUM_KEY=<server_side_secret>
```

Tại phía payOS, cấu hình webhook HTTPS: `https://<your-stable-production-domain>/api/webhooks/payos`. PayOS webhook và lần hỏi trạng thái được backend kiểm tra để chuyển hóa đơn sang `PAID`. Đừng dùng địa chỉ preview thay đổi liên tục cho webhook production.

Lưu ý quan trọng:
- Các nút giả lập sẽ **bị tắt** trong `live`.
- MoMo Subscription **vẫn chỉ là phần mô phỏng nghiệp vụ**, chưa có API định kỳ của MoMo.
- Không nên public chế độ `live` khi chưa hoàn thiện xác thực, quản lý người dùng, chống lạm dụng, đối soát & kiểm thử với tài khoản merchant.
- Backend không gắn hóa đơn Paid chỉ vì khách bấm Continue hoặc frontend nhận URL redirect.

## 6. Xử lý lỗi hay gặp

| Lỗi | Cách kiểm tra |
|---|---|
| Deployment lỗi import FastAPI | Kiểm tra Vercel Root Directory có `pyproject.toml`, `requirements.txt`, và entrypoint `backend.app.main:app` |
| `Set DATABASE_URL ...` | Thêm `DATABASE_URL` vào Vercel Environment Variables và Redeploy |
| `connection refused` / `password authentication failed` | Kiểm tra URI Neon, password, pooled host, SSL và URL encoding |
| Frontend hiển thị nhưng không load gói | Mở `/api/health`, xem Vercel Function Logs; thường là backend/database |
| QR demo mở `localhost` | Set `PUBLIC_BASE_URL` sang URL public hoặc bật Vercel system env `VERCEL_URL` |
| Sau khi redeploy mất dữ liệu | Có thể em vẫn dùng SQLite; kiểm tra health `database: postgresql` |
| Live tạo QR báo lỗi | Kiểm tra merchant credentials và `PUBLIC_BASE_URL` HTTPS; không nhập key vào JS |

## 7. Tham khảo tài liệu chính thức

- Vercel FastAPI: https://vercel.com/docs/frameworks/backend/fastapi
- Vercel environment variables: https://vercel.com/docs/environment-variables
- Vercel Python runtime: https://vercel.com/docs/functions/runtimes/python
- Neon PostgreSQL: https://neon.com/docs

**Các hướng dẫn ở đây cấu hình code để triển khai; chưa tự tạo deployment hay tài khoản cho em.**
