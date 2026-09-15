# Kế Hoạch Triển Khai VoxDirector AI Lên VPS

**Tài liệu này dành cho ai:** Người không rành DevOps, cần làm theo từng bước để đưa VoxDirector AI từ máy dev (Docker Compose local) lên một VPS thật, có domain thật, chạy ổn định cho một nhóm nhỏ (~3-10 người dùng beta).

**Ngân sách mục tiêu:** Thuê VPS 1 tháng để test + domain 1 năm, càng rẻ càng tốt nhưng vẫn chạy được thật (không chọn cấu hình rẻ đến mức treo máy).

---

## 1. VoxDirector AI thực sự cần bao nhiêu tài nguyên?

Trước khi chọn VPS, cần hiểu app này "nặng" ở đâu — chọn bừa theo giá rẻ nhất có thể khiến app không chạy nổi:

| Thành phần | Tốn gì | Ghi chú |
| --- | --- | --- |
| **VieNeu-TTS** (tạo giọng đọc) | CPU, một ít RAM | Chạy chế độ "Standard" (ONNX, không cần GPU), nhà phát triển SDK công bố là chạy thời gian thực được trên CPU thường. |
| **faster-whisper "medium"** (Agent Gamma — kiểm tra chất lượng bằng ASR) | **RAM nhiều nhất** (~2-3GB khi model được nạp), CPU khi chạy | Đây là thành phần nặng nhất. Có thể đổi sang model nhỏ hơn ("small" hoặc "base") qua biến môi trường mà **không cần sửa code** để giảm RAM nếu VPS yếu. |
| **ChromaDB + sentence-transformers** (tra cứu thuật ngữ Glossary) | RAM vừa phải | Model nhúng (embedding) nhỏ (~80MB), nhưng kéo theo thư viện torch (CPU) khi cài đặt. |
| **ffmpeg** (ghép audio, làm video, trộn nhạc nền) | CPU khi xử lý, không tốn RAM nhiều | Chạy dạng tiến trình ngắn, xong thì nhả tài nguyên. |
| **Backend FastAPI + Frontend Next.js + Nginx** | Nhẹ | Vài trăm MB RAM tổng cộng. |
| **Google Gemini** (các Agent Alpha/Beta) | **Không tốn tài nguyên VPS** | Đây là API gọi ra ngoài (cloud của Google), VPS chỉ cần có Internet để gọi, không cần chạy AI nặng ở local cho phần này. |

**Kết luận quan trọng:** VoxDirector AI **không cần GPU**. Cái cần nhất là **đủ RAM** (do faster-whisper + torch cộng dồn) và ổ đĩa **SSD** (để nạp model nhanh). Dự án hiện chỉ nhắm phục vụ một nhóm nhỏ vài người dùng thử nghiệm (beta), không phải hàng trăm người dùng cùng lúc — nên không cần cấu hình "doanh nghiệp".

---

## 2. Đề xuất thuê VPS

### Phương án 1 — Rẻ nhất có thể chấp nhận được (khuyên dùng để test 1 tháng)

| Mục | Đề xuất |
| --- | --- |
| **Nhà cung cấp** | **Hetzner Cloud** (`hetzner.com`) — nổi tiếng rẻ, tính tiền theo giờ nên huỷ bất cứ lúc nào không mất phí phạt, rất hợp để thuê thử 1 tháng. |
| **Gói** | **CX22** — 2 vCPU, 4GB RAM, 40GB SSD |
| **Giá tham khảo** | Khoảng **4-5 USD/tháng** (~110.000-130.000đ) |
| **Điều kiện bắt buộc đi kèm** | Phải đổi `WHISPER_MODEL_SIZE` từ `medium` xuống `small` (sửa 1 dòng trong file `.env`, không cần sửa code — xem Bước 5) để tránh hết RAM. Chỉ nên chạy **1 job cùng lúc**. |

### Phương án 2 — An toàn hơn, không phải chỉnh gì thêm (khuyên dùng nếu định dùng lâu dài)

| Mục | Đề xuất |
| --- | --- |
| **Nhà cung cấp** | **Hetzner Cloud** hoặc **Contabo** (`contabo.com`) |
| **Gói** | 4 vCPU, **8GB RAM**, ~80-160GB SSD (Hetzner: gói **CX32**; Contabo: gói **VPS S**) |
| **Giá tham khảo** | Khoảng **7-9 USD/tháng** (Hetzner) hoặc rẻ hơn nữa với Contabo (~6-7 USD/tháng, đổi lại là hiệu năng CPU chia sẻ nên có lúc không đều bằng Hetzner) |
| **Điều kiện đi kèm** | Không cần chỉnh gì, dùng đúng cấu hình mặc định (`WHISPER_MODEL_SIZE=medium`) vẫn thoải mái, chạy được vài job gần như cùng lúc. |

**Chọn hệ điều hành:** Ubuntu 22.04 LTS (bản mặc định của mọi nhà cung cấp VPS, ổn định, nhiều hướng dẫn).

> Nếu ngân sách cho phép, **khuyên chọn Phương án 2** — chênh nhau chỉ khoảng 2-4 USD/tháng nhưng đỡ lo bị treo máy giữa lúc đang xử lý cho người dùng thật.

---

## 3. Đề xuất tên miền (domain)

Vì đây là dự án có thể còn dùng cho nhiều sản phẩm phụ khác trong tương lai (không riêng VoxDirector), nên chọn 1 tên miền **chung, không gắn cứng với "VoxDirector"** — sau này chạy thêm dự án nào chỉ cần thêm subdomain (`voxdirector.tenmien.com`, `duan2.tenmien.com`...).

| Mục | Đề xuất |
| --- | --- |
| **Gợi ý tên miền** | Một cái tên ngắn, chung chung, dễ nhớ — ví dụ: `devforge.dev`, `sidelab.dev`, hoặc `buildnest.io` (kiểm tra còn trống lúc mua, đây chỉ là gợi ý mẫu). Ưu tiên đuôi `.dev` hoặc `.io` vì rẻ, không dính tên thương hiệu ai, và nghe "kỹ thuật/dự án cá nhân" — phù hợp làm mái nhà chung cho nhiều app nhỏ. |
| **Nhà đăng ký (registrar)** | **Porkbun** (`porkbun.com`) hoặc **Cloudflare Registrar** (`cloudflare.com/products/registrar`) — cả hai đều nổi tiếng bán đúng giá gốc, **không có kiểu "năm đầu rẻ, năm sau tăng giá gấp đôi"** như GoDaddy/Namecheap hay gặp. |
| **Giá tham khảo 1 năm** | `.dev`: khoảng 9-12 USD/năm. `.io`: khoảng 30-35 USD/năm (đắt hơn vì đuôi `.io` vốn có giá thuê cao). Nếu muốn rẻ nhất, chọn `.dev` hoặc thậm chí `.com` thường (~9-10 USD/năm ở Porkbun). |

> **Lưu ý:** Cloudflare Registrar chỉ bán đúng giá gốc, không cộng thêm lợi nhuận — rẻ nhất về lâu dài nhưng danh sách đuôi domain hỗ trợ ít hơn Porkbun một chút. Porkbun hỗ trợ nhiều đuôi hơn và giao diện dễ dùng cho người mới. Chọn 1 trong 2 đều ổn.

---

## 4. Các bước triển khai (làm theo thứ tự)

### Bước 0 — Chuẩn bị trước khi bắt đầu

- [ ] Đã thuê VPS (Bước 2), có địa chỉ IP, đã có quyền truy cập SSH (nhà cung cấp sẽ gửi email hoặc cho tải file khoá SSH).
- [ ] Đã mua domain (Bước 3).
- [ ] Đã có **API key Gemini thật** (`AIzaSy...`, lấy tại `aistudio.google.com/apikey`) — nếu chưa có key thật, KHÔNG deploy production được vì các Agent Alpha/Beta sẽ lỗi ngay khi xử lý.

### Bước 1 — Trỏ domain về VPS

1. Đăng nhập trang quản lý domain (Porkbun/Cloudflare).
2. Vào phần quản lý DNS, thêm 1 bản ghi:
   - Loại: **A**
   - Tên: `@` (hoặc để trống, tuỳ giao diện — nghĩa là domain gốc) — hoặc `voxdirector` nếu muốn dùng dạng `voxdirector.tenmien.dev`.
   - Giá trị: **địa chỉ IP của VPS** (lấy từ trang quản lý VPS).
3. Đợi khoảng 5-30 phút để DNS cập nhật (có thể kiểm tra bằng cách gõ `ping tenmien-cua-ban.dev` từ máy tính).

### Bước 2 — Cài đặt cơ bản trên VPS (SSH vào VPS)

```bash
# SSH vào VPS (thay IP thật vào)
ssh root@<IP-VPS-cua-ban>

# Cập nhật hệ thống
apt update && apt upgrade -y

# Cài Docker + Docker Compose (script cài đặt chính thức của Docker)
curl -fsSL https://get.docker.com | sh

# Kiểm tra đã cài thành công
docker --version
docker compose version
```

### Bước 3 — Tải mã nguồn về VPS

```bash
git clone https://github.com/NTQD/VieNeu-Audio.git
cd VieNeu-Audio
git checkout VoxDirector
```

### Bước 4 — Tạo file cấu hình `.env`

```bash
cp .env.example .env
nano .env
```

Điền các giá trị sau (thay bằng giá trị thật của bạn):

```
GEMINI_API_KEY=AIzaSy...(key thật của bạn)...
NEXT_PUBLIC_API_URL=https://tenmien-cua-ban.dev
```

Lưu file (trong `nano`: bấm `Ctrl+O` rồi `Enter` để lưu, `Ctrl+X` để thoát).

### Bước 5 — (Chỉ áp dụng nếu chọn VPS 4GB RAM ở Phương án 1) Giảm tải cho VPS yếu

Nếu VPS chỉ có 4GB RAM, thêm dòng sau vào cuối file `.env`:

```
VOXDIRECTOR_WHISPER_MODEL=small
```

(Bỏ qua bước này nếu dùng VPS 8GB RAM — mặc định `medium` vẫn chạy tốt.)

### Bước 6 — Khởi chạy lần đầu (chưa có HTTPS, chạy HTTP trước)

```bash
docker compose up -d --build
```

Đợi vài phút để build xong (lần đầu build lâu vì phải tải các gói AI). Kiểm tra bằng cách mở trình duyệt vào `http://<IP-VPS-cua-ban>` — nếu thấy giao diện VoxDirector AI hiện ra là thành công bước này.

### Bước 7 — Lấy chứng chỉ HTTPS (SSL) miễn phí

```bash
docker compose run --rm certbot certonly --webroot \
  -w /var/www/certbot -d tenmien-cua-ban.dev --email email-cua-ban@gmail.com --agree-tos
```

### Bước 8 — Bật HTTPS

1. Mở file cấu hình nginx: `nano deploy/nginx/nginx.conf`
2. Thêm đoạn cấu hình `server { listen 443 ssl; ... }` trỏ tới chứng chỉ vừa lấy ở Bước 7 (đường dẫn dạng `/etc/letsencrypt/live/tenmien-cua-ban.dev/`). *(Nếu không tự tin sửa file này, có thể nhờ AI coding assistant — như Claude Code đang dùng cho dự án — viết giúp đoạn cấu hình chính xác dựa trên domain thật của bạn.)*
3. Khởi động lại nginx:
   ```bash
   docker compose restart nginx
   ```
4. Mở `https://tenmien-cua-ban.dev` — thấy ổ khoá HTTPS trên trình duyệt là xong.

### Bước 9 — Tự động gia hạn chứng chỉ HTTPS

Chứng chỉ Let's Encrypt hết hạn sau 90 ngày, cần gia hạn định kỳ. Thêm 1 tác vụ tự động (cron job):

```bash
crontab -e
```

Thêm dòng này vào cuối file (chạy kiểm tra gia hạn mỗi ngày lúc 3h sáng):

```
0 3 * * * cd /root/VieNeu-Audio && docker compose run --rm certbot renew && docker compose restart nginx
```

### Bước 10 — Kiểm tra lần cuối

- [ ] Mở `https://tenmien-cua-ban.dev`, thử dán 1 đoạn văn bản và bấm "Bắt đầu xử lý" — chờ ra audio thật.
- [ ] Kiểm tra RAM còn dư trong lúc xử lý: `docker stats` (bấm `Ctrl+C` để thoát) — nếu RAM gần đầy hoàn toàn, cân nhắc nâng cấp VPS hoặc giảm `WHISPER_MODEL_SIZE`.
- [ ] Thử tắt/mở lại VPS (reboot) xem app có tự khởi động lại không — Docker Compose trong dự án đã đặt `restart: unless-stopped` nên sẽ tự chạy lại.

---

## 5. Những điều cần biết thêm (đọc để tránh bất ngờ)

- **Gemini API key là loại "dùng chung" hay "mỗi người 1 key"?** Dự án hỗ trợ cả 2: có ô nhập "API key riêng (BYOK)" trên giao diện web để mỗi người dùng tự nhập key của họ (chỉ lưu trên trình duyệt người đó); nếu để trống, hệ thống dùng key chung đã điền ở Bước 4.
- **Xuất Video** chỉ hoạt động khi người dùng có tải ảnh nền lên trước khi xử lý — nút "Xuất Video" sẽ tự mờ đi (disabled) nếu không có ảnh nền, đây là hành vi có chủ đích, không phải lỗi.
- **Sao lưu dữ liệu:** Thư mục `voxdirector/.chroma/` (danh sách thuật ngữ Glossary) và `voxdirector/.data/` (log job) nằm trực tiếp trên VPS, không tự sao lưu lên đâu cả. Nếu dữ liệu Glossary quan trọng, nên định kỳ tải về máy (`docker compose exec backend tar czf - voxdirector/.chroma` rồi tải file `.tar.gz` xuống) hoặc gắn thêm dịch vụ backup của nhà cung cấp VPS.
- **Chi phí Gemini API:** VPS không tính phí AI, nhưng gọi Gemini API sẽ tính phí riêng theo số token qua tài khoản Google Cloud/AI Studio của bạn — nên theo dõi mục "Ước tính chi phí" đã có sẵn trong app (mỗi job xử lý xong sẽ hiện chi phí ước tính).
