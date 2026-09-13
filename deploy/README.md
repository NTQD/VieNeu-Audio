# Triển khai VoxDirector AI (Step 15, Section 12 của spec)

## Local (đã xác nhận `docker compose build` thành công trên máy dev, 2026-09-10)

```bash
cp .env.example .env   # điền GEMINI_API_KEY thật
docker compose up --build
```

Mở `http://localhost` — nginx route `/` → frontend, `/api/*` và `/api/ws/*` → backend.

## VPS thật (chưa tự động hoá — cần bạn tự làm các bước sau)

Những phần này đòi hỏi quyền truy cập hạ tầng thật (VPS, domain, DNS) mà
phiên làm việc này không có — không thể tự động hoá thay bạn:

1. Trỏ domain (A record) về IP của VPS.
2. Trên VPS: clone repo, tạo `.env` với `GEMINI_API_KEY` thật và
   `NEXT_PUBLIC_API_URL=https://<domain-của-bạn>`.
3. `docker compose up -d --build` (chạy HTTP trước, chưa có cert).
4. Lấy chứng chỉ TLS lần đầu:
   ```bash
   docker compose run --rm certbot certonly --webroot \
     -w /var/www/certbot -d <domain-của-bạn> --email <email> --agree-tos
   ```
5. Cập nhật `deploy/nginx/nginx.conf` thêm server block `listen 443 ssl` trỏ
   tới cert vừa lấy (`/etc/letsencrypt/live/<domain>/`), rồi
   `docker compose restart nginx`.
6. Renew định kỳ: `docker compose run --rm certbot renew` (cron/systemd
   timer trên VPS, ngoài phạm vi compose).

## Chưa nối trong Docker image này

- **Video rendering** (`pipeline/video_renderer.py`) — nút "Xuất Video" ở
  frontend vẫn chủ đích `disabled`, chưa nối vào backend thật. Audio +
  phụ đề là trọng tâm đã kiểm chứng của Step 14.
- **BYOK** (người dùng tự nhập API key riêng) — Section 13 của spec liệt kê
  "BYOK key storage confirmation" là quyết định còn mở, chưa chốt cách lưu
  trữ an toàn. `GEMINI_API_KEY` hiện tại là key chung của server (biến môi
  trường), không phải key riêng từng người dùng.
