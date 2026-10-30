# DEPLOYMENT.md: SILADESA

## Environment Overview

| Environment | Tujuan | Infrastruktur | Database | Data |
|:---|:---|:---|:---|:---|
| **Local** | Pengembangan harian | Laptop developer | SQLite | Seed + data dummy |
| **Staging** | UAT sebelum go-live | VPS yang sama, port 8080, subdomain `staging.` | PostgreSQL (schema terpisah) | Salinan anonim dari produksi |
| **Production** | Operasional desa | VPS 2 vCPU / 2 GB / 40 GB SSD | PostgreSQL 16 | Data warga sebenarnya |

**Domain:**

| Subdomain | Fungsi |
|:---|:---|
| `layanan.desakampala.id` | Panel admin, web widget, halaman verifikasi `/v/{token}` |
| `staging.layanan.desakampala.id` | UAT (opsional, dapat dimatikan saat go-live) |

**Spesifikasi VPS minimum:**

| Komponen | Minimum | Rekomendasi |
|:---|:---|:---|
| vCPU | 2 | 2 |
| RAM | 2 GB | 4 GB |
| Disk | 40 GB SSD | 80 GB SSD |
| Bandwidth | 1 TB/bulan | 2 TB/bulan |
| OS | Ubuntu 24.04 LTS | Ubuntu 24.04 LTS |
| Lokasi | Jakarta/Singapura | Jakarta (latensi < 30 ms ke Jeneponto) |

Estimasi biaya bulanan: VPS Rp 100.000–180.000, domain Rp 15.000/bulan (amortisasi), Fonnte Rp 100.000, backup offsite Rp 20.000. **Total ± Rp 250.000–320.000/bulan.**

## Prerequisites

| Kebutuhan | Detail |
|:---|:---|
| Akses SSH | Kunci publik terdaftar; password login dinonaktifkan |
| DNS | Record `A` untuk `layanan.desakampala.id` → IP VPS |
| Port terbuka | 22 (dibatasi IP admin), 80, 443 |
| Akun Fonnte | Token device + nomor WhatsApp desa |
| Bot Telegram | Token dari `@BotFather` |
| Repositori | GitHub dengan Actions aktif |
| Pengelola kata sandi | Bitwarden/1Password desa untuk kredensial |

## Container Architecture

Tiga service, satu network internal, hanya Caddy yang terekspos ke host.

```yaml
# docker-compose.yml
name: siladesa

services:
  app:
    build:
      context: .
      dockerfile: Dockerfile
    image: ghcr.io/desakampala/siladesa:${APP_VERSION:-latest}
    restart: unless-stopped
    env_file:
      - .env
    environment:
      DATABASE_URL: postgresql+psycopg://siladesa:${POSTGRES_PASSWORD}@db:5432/siladesa
      TZ: Asia/Makassar
    volumes:
      - ./storage:/app/storage
      - ./models:/app/models
    depends_on:
      db:
        condition: service_healthy
    healthcheck:
      test: ["CMD", "python", "-c", "import urllib.request,sys; sys.exit(0 if urllib.request.urlopen('http://127.0.0.1:8000/healthz', timeout=3).status==200 else 1)"]
      interval: 30s
      timeout: 5s
      retries: 3
      start_period: 40s
    networks:
      - internal
    read_only: true
    tmpfs:
      - /tmp
    security_opt:
      - no-new-privileges:true

  db:
    image: postgres:16-alpine
    restart: unless-stopped
    environment:
      POSTGRES_DB: siladesa
      POSTGRES_USER: siladesa
      POSTGRES_PASSWORD: ${POSTGRES_PASSWORD}
      TZ: Asia/Makassar
    volumes:
      - ./pgdata:/var/lib/postgresql/data
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U siladesa -d siladesa"]
      interval: 10s
      timeout: 5s
      retries: 5
    networks:
      - internal

  caddy:
    image: caddy:2.8-alpine
    restart: unless-stopped
    ports:
      - "80:80"
      - "443:443"
    volumes:
      - ./Caddyfile:/etc/caddy/Caddyfile:ro
      - ./caddy_data:/data
      - ./caddy_config:/config
      - ./storage/documents:/srv/documents:ro
      - ./app/static:/srv/static:ro
    depends_on:
      - app
    networks:
      - internal

networks:
  internal:
    driver: bridge
```

**Catatan:** `db` tidak memiliki `ports:` sehingga tidak dapat diakses dari luar network Docker. `app` juga tidak mengekspos port ke host.

## Dockerfile

```dockerfile
# ---------- Stage 1: Tailwind build ----------
FROM alpine:3.20 AS css
WORKDIR /build
RUN wget -qO tailwindcss https://github.com/tailwindlabs/tailwindcss/releases/download/v3.4.14/tailwindcss-linux-x64 \
    && chmod +x tailwindcss
COPY app/templates ./app/templates
COPY app/static/css/input.css ./app/static/css/input.css
COPY tailwind.config.js ./
RUN ./tailwindcss -i app/static/css/input.css -o app/static/css/app.css --minify

# ---------- Stage 2: Runtime ----------
FROM python:3.12-slim AS runtime

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    TZ=Asia/Makassar

RUN apt-get update && apt-get install -y --no-install-recommends \
      libpq5 curl tzdata fonts-liberation \
    && rm -rf /var/lib/apt/lists/*

# Times New Roman tidak tersedia bebas lisensi; Liberation Serif dipakai sebagai metrik setara
RUN mkdir -p /usr/share/fonts/truetype/liberation

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .
COPY --from=css /build/app/static/css/app.css ./app/static/css/app.css

RUN useradd --create-home --uid 10001 siladesa \
    && mkdir -p storage/documents storage/attachments storage/officials models \
    && chown -R siladesa:siladesa /app
USER siladesa

EXPOSE 8000

CMD ["sh", "-c", "alembic upgrade head && uvicorn app.main:app --host 0.0.0.0 --port 8000 --workers 2 --proxy-headers --forwarded-allow-ips='*'"]
```

**Catatan font:** arsip surat desa memakai Times New Roman. Karena lisensi font tersebut tidak bebas untuk didistribusikan dalam image, sistem memakai **Liberation Serif** yang metriknya identik. Bila desa memiliki lisensi, font asli dapat ditempel ke `app/static/fonts/` dan didaftarkan di `renderer.py`.

## Reverse Proxy

```caddyfile
# Caddyfile
{
    email admin@desakampala.id
}

layanan.desakampala.id {
    encode zstd gzip

    header {
        Strict-Transport-Security "max-age=31536000; includeSubDomains"
        X-Content-Type-Options "nosniff"
        X-Frame-Options "DENY"
        Referrer-Policy "strict-origin-when-cross-origin"
        Permissions-Policy "geolocation=(), microphone=(), camera=()"
        -Server
    }

    # Aset statis langsung dari disk
    handle /static/* {
        root * /srv
        file_server
        header Cache-Control "public, max-age=604800, immutable"
    }

    # PDF arsip tidak pernah publik
    handle /storage/* {
        respond 404
    }

    handle {
        reverse_proxy app:8000 {
            header_up X-Real-IP {remote_host}
        }
    }

    log {
        output file /data/access.log {
            roll_size 20mb
            roll_keep 5
        }
        format json
    }
}
```

## Environment Variables

```bash
# .env — JANGAN commit. chmod 600 .env

# Aplikasi
APP_ENV=production
APP_VERSION=1.0.0
APP_URL=https://layanan.desakampala.id
SECRET_KEY=<openssl rand -hex 32>
SESSION_COOKIE_NAME=siladesa_session
SESSION_LIFETIME_MINUTES=30
TZ=Asia/Makassar

# Database
POSTGRES_PASSWORD=<openssl rand -base64 24>

# Admin awal (hanya dipakai saat seed pertama)
BOOTSTRAP_ADMIN_EMAIL=admin@desakampala.id
BOOTSTRAP_ADMIN_PASSWORD=<password kuat>

# Kanal
TELEGRAM_BOT_TOKEN=123456:ABC...
TELEGRAM_WEBHOOK_SECRET=<openssl rand -hex 24>
FONNTE_TOKEN=<token device>
FONNTE_WEBHOOK_TOKEN=<openssl rand -hex 24>

# NLP
MODEL_DIR=/app/models
CONFIDENCE_TINGGI=0.65
CONFIDENCE_RENDAH=0.40

# Berkas
STORAGE_DIR=/app/storage
MAX_UPLOAD_MB=5
DOWNLOAD_TOKEN_TTL_DAYS=7

# Observability (opsional)
SENTRY_DSN=
LOG_LEVEL=INFO

# Backup
RESTIC_REPOSITORY=
RESTIC_PASSWORD=
```

**Aturan:** `SECRET_KEY` dan `POSTGRES_PASSWORD` wajib dirotasi bila ada indikasi kebocoran; rotasi `SECRET_KEY` membatalkan semua sesi aktif (dapat diterima).

## Deployment Steps

### 1. Persiapan VPS

```bash
# Sebagai root
apt update && apt upgrade -y
adduser --disabled-password --gecos "" deploy
usermod -aG sudo deploy
rsync --archive --chown=deploy:deploy ~/.ssh /home/deploy

# Hardening
sed -i 's/^#*PermitRootLogin.*/PermitRootLogin no/' /etc/ssh/sshd_config
sed -i 's/^#*PasswordAuthentication.*/PasswordAuthentication no/' /etc/ssh/sshd_config
systemctl restart ssh

ufw default deny incoming
ufw default allow outgoing
ufw allow 22/tcp
ufw allow 80,443/tcp
ufw enable

apt install -y fail2ban unattended-upgrades
systemctl enable --now fail2ban

# Docker
curl -fsSL https://get.docker.com | sh
usermod -aG docker deploy
```

### 2. Deploy aplikasi

```bash
su - deploy
git clone https://github.com/desakampala/siladesa.git /home/deploy/siladesa
cd /home/deploy/siladesa

cp .env.example .env
nano .env                    # isi seluruh variabel
chmod 600 .env

mkdir -p storage/documents storage/attachments storage/officials models pgdata

docker compose pull
docker compose up -d
docker compose logs -f app
```

### 3. Seed dan verifikasi

```bash
docker compose exec app python -m app.seed
docker compose exec app alembic current
curl -s https://layanan.desakampala.id/healthz | jq
```

**Respons yang diharapkan:**

```json
{ "status": "ok", "database": "ok", "model": "2026.11.1", "version": "1.0.0" }
```

### 4. Daftarkan webhook

```bash
# Telegram
curl -F "url=https://layanan.desakampala.id/webhooks/telegram" \
     -F "secret_token=$TELEGRAM_WEBHOOK_SECRET" \
     "https://api.telegram.org/bot$TELEGRAM_BOT_TOKEN/setWebhook"

# Fonnte: atur URL webhook di dashboard Fonnte
# https://layanan.desakampala.id/webhooks/fonnte
```

### 5. Uji asap (smoke test)

| # | Uji | Ekspektasi |
|:--|:---|:---|
| 1 | Kirim "halo" ke WhatsApp desa | Balasan menu dalam ≤ 5 detik |
| 2 | Kirim "syarat sktm" | Jawaban persyaratan benar |
| 3 | Ajukan SKTM sampai submit | Tiket `MENUNGGU_VERIFIKASI` muncul di admin |
| 4 | Login admin, setujui pengajuan | PDF terkirim, nomor surat terbentuk |
| 5 | Pindai QR di PDF | Halaman `/v/{token}` menampilkan `SAH` |
| 6 | Pindai QR dokumen yang dicabut | Halaman menampilkan `DIBATALKAN` |
| 7 | Akses `http://` | Redirect ke `https://` |
| 8 | Akses `/docs` | 404 (dinonaktifkan di produksi) |

## CI/CD Pipeline

```yaml
# .github/workflows/ci.yml
name: CI

on:
  push:
    branches: [main]
    tags: ["v*"]
  pull_request:

jobs:
  test:
    runs-on: ubuntu-latest
    services:
      postgres:
        image: postgres:16
        env:
          POSTGRES_PASSWORD: test
          POSTGRES_DB: siladesa_test
        ports: ["5432:5432"]
        options: >-
          --health-cmd pg_isready --health-interval 10s
          --health-timeout 5s --health-retries 5
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: "3.12"
          cache: pip
      - run: pip install -r requirements-dev.txt
      - run: ruff check .
      - run: ruff format --check .
      - run: pytest -q --cov=app --cov-fail-under=70
        env:
          DATABASE_URL: postgresql+psycopg://postgres:test@localhost:5432/siladesa_test

  image:
    needs: test
    if: startsWith(github.ref, 'refs/tags/v')
    runs-on: ubuntu-latest
    permissions:
      contents: read
      packages: write
    steps:
      - uses: actions/checkout@v4
      - uses: docker/login-action@v3
        with:
          registry: ghcr.io
          username: ${{ github.actor }}
          password: ${{ secrets.GITHUB_TOKEN }}
      - uses: docker/build-push-action@v6
        with:
          push: true
          tags: ghcr.io/desakampala/siladesa:${{ github.ref_name }}
```

**Deploy tidak otomatis.** Setelah image terbit, operator menjalankan langkah rollback-safe berikut:

```bash
cd /home/deploy/siladesa
sed -i "s/^APP_VERSION=.*/APP_VERSION=v1.1.0/" .env
docker compose pull app
docker compose up -d app
docker compose logs -f app
```

Deploy otomatis lewat SSH sengaja tidak dipakai: satu orang harus tetap melihat log pertama setelah rilis.

## Backup & Restore

### Backup harian (otomatis)

```bash
#!/usr/bin/env bash
# /home/deploy/bin/backup.sh — cron 02.00 WITA
set -euo pipefail
cd /home/deploy/siladesa

STAMP=$(date +%Y%m%d-%H%M)
BACKUP_DIR=/home/deploy/backups

mkdir -p "$BACKUP_DIR"

# 1. Database
docker compose exec -T db pg_dump -U siladesa -Fc siladesa \
  > "$BACKUP_DIR/db-$STAMP.dump"

# 2. Berkas (dokumen, TTD, model)
tar -czf "$BACKUP_DIR/files-$STAMP.tar.gz" storage models

# 3. Simpan lokal 7 hari
find "$BACKUP_DIR" -type f -mtime +7 -delete

# 4. Offsite terenkripsi 30 hari
restic backup "$BACKUP_DIR" --tag siladesa
restic forget --keep-daily 7 --keep-weekly 4 --prune
```

```cron
# crontab -e (user deploy)
0 2 * * * /home/deploy/bin/backup.sh >> /home/deploy/logs/backup.log 2>&1
30 2 * * 0 /home/deploy/bin/backup.sh --verify >> /home/deploy/logs/backup.log 2>&1
```

### Restore

```bash
cd /home/deploy/siladesa
docker compose stop app

# Database
docker compose exec -T db dropdb -U siladesa siladesa
docker compose exec -T db createdb -U siladesa siladesa
cat /home/deploy/backups/db-20261104-0200.dump \
  | docker compose exec -T db pg_restore -U siladesa -d siladesa --clean --if-exists

# Berkas
tar -xzf /home/deploy/backups/files-20261104-0200.tar.gz -C /home/deploy/siladesa

docker compose start app
curl -s https://layanan.desakampala.id/healthz
```

**Uji restore wajib dilakukan minimal sekali sebelum go-live** dan setiap 6 bulan. Backup yang belum pernah diuji restore bukan backup.

**RPO:** ≤ 24 jam. **RTO:** ≤ 4 jam.

## Rollback Strategy

| Skenario | Tindakan | Waktu |
|:---|:---|:---|
| Rilis baru error, migrasi kompatibel | `APP_VERSION=v1.0.0` lalu `docker compose up -d app` | < 2 menit |
| Migrasi tidak kompatibel | Rollback image + `alembic downgrade -1` + restore DB dari dump pra-rilis | < 30 menit |
| Data rusak karena bug | Restore dump terakhir + replay berkas | < 1 jam |
| VPS hilang | Provision VPS baru, clone repo, restore dump + volume, arahkan DNS | < 4 jam |

**Aturan migrasi:** setiap migrasi wajib punya `downgrade()` yang benar-benar berfungsi dan diuji di CI. Migrasi yang menghapus kolom dilakukan dua tahap (deprecate → hapus) dengan jeda satu rilis.

## Monitoring & Alerting

| Apa | Alat | Ambang | Aksi |
|:---|:---|:---|:---|
| Uptime `/healthz` | Uptime Kuma | 2 gagal berturut | Notifikasi Telegram ke admin |
| Error 5xx | Sentry | > 5 dalam 5 menit | Notifikasi email |
| Disk | cron + `df` | > 80% | Hapus PDF sementara, notifikasi |
| RAM | `docker stats` | > 90% selama 10 menit | Restart app, investigasi |
| Backup gagal | skrip backup | exit ≠ 0 | Notifikasi Telegram |
| Model tidak aktif | `/healthz` | `model: "none"` | Notifikasi Admin Teknis |
| Antrean eskalasi | kueri harian | > 10 tiket > 24 jam | Ringkasan harian ke Sekdes |

**Log rotation:** Caddy menangani log akses; log aplikasi keluar ke stdout dan dirotasi oleh driver `json-file` Docker (`max-size=20m`, `max-file=5`).

## Security Hardening Checklist

- [ ] `PermitRootLogin no`, `PasswordAuthentication no`
- [ ] UFW aktif, hanya 22/80/443
- [ ] `fail2ban` aktif untuk SSH
- [ ] `unattended-upgrades` aktif
- [ ] Docker tidak mengekspos port `db` dan `app` ke host
- [ ] Container berjalan sebagai non-root, `read_only: true`
- [ ] `.env` bermode `600`, tidak ada di git
- [ ] `/docs` dan `/redoc` dinonaktifkan di produksi
- [ ] HTTPS memaksa redirect, HSTS aktif
- [ ] Rate limit login dan chat aktif
- [ ] Akun admin default wajib ganti password saat login pertama
- [ ] Backup terenkripsi dan diuji restore
- [ ] Audit log diperiksa mingguan oleh Sekdes
- [ ] Kredensial tersimpan di pengelola kata sandi desa, bukan di kertas

## Operational Runbook

### Chatbot tidak membalas

1. `curl -s https://layanan.desakampala.id/healthz` — periksa `status`, `database`, `model`.
2. `docker compose logs --tail=100 app | grep -i error`
3. Bila `model: "none"` → aktifkan model terakhir di panel admin (`/admin/model`).
4. Bila `database: "error"` → `docker compose ps db`, periksa disk dan log PostgreSQL.
5. Bila semuanya sehat → periksa status gateway Fonnte dan webhook Telegram.
6. Bila belum pulih dalam 15 menit, aktifkan pengumuman manual di WhatsApp desa.

### Dokumen gagal terbit

1. Buka detail pengajuan di panel admin; status tetap `DIPROSES`.
2. Periksa pesan error pada `application_event` terakhir.
3. Penyebab umum: placeholder template tidak cocok, pejabat tidak aktif, berkas TTD hilang.
4. Perbaiki penyebab, lalu jalankan ulang penerbitan dari detail pengajuan.
5. Nomor surat yang di-rollback akan dialokasikan ulang; pastikan tidak ada nomor yang sudah tercetak manual.

### QR menampilkan "tidak ditemukan"

1. Periksa `qr_token` pada PDF vs kolom `document.qr_token`.
2. Pastikan dokumen berstatus `TERBIT`, bukan `DRAFT`.
3. Bila token benar tetapi tidak ditemukan, periksa apakah database di-restore dari backup lama.
4. Bila PDF berasal dari versi lama, terbitkan ulang dengan nomor baru dan cabut yang lama.

### Lupa password admin terakhir

```bash
docker compose exec app python -m app.cli reset-admin \
  --email admin@desakampala.id
# Password sementara dicetak ke stdout, wajib diganti saat login
```

### Rotasi kredensial

```bash
# 1. Buat nilai baru
openssl rand -hex 32

# 2. Perbarui .env
nano .env

# 3. Restart hanya app
docker compose up -d --force-recreate app
```

## Go-Live Checklist

**Teknis**

- [ ] Seluruh test lulus, coverage ≥ 70%
- [ ] Akurasi model ≥ 85% (cross-validation) dan didokumentasikan
- [ ] Migrasi berjalan bersih dari database kosong
- [ ] Backup harian aktif dan restore sudah diuji
- [ ] Monitoring uptime aktif dan notifikasi teruji
- [ ] Uji beban 50 concurrent pengguna berhasil
- [ ] Uji 5 perangkat untuk pemindaian QR berhasil
- [ ] Seluruh halaman admin lolos pemeriksaan WCAG dasar (kontras, fokus, label)

**Konten & legal**

- [ ] Empat template surat divalidasi dan ditandatangani Sekdes
- [ ] Format nomor surat disetujui Kepala Desa
- [ ] Pejabat aktif dan scan TTD terunggah
- [ ] Kebijakan privasi dan teks persetujuan disetujui desa
- [ ] Surat izin/persetujuan penggunaan sistem dari Kepala Desa ada
- [ ] Kontak darurat untuk gangguan tercantum di pesan bot

**Operasional**

- [ ] Dua operator dilatih (sesi 2 jam + buku panduan satu halaman)
- [ ] Admin Teknis dapat melakukan reset password dan restore backup
- [ ] Jadwal piket verifikasi pengajuan disepakati
- [ ] Pengumuman peluncuran disiapkan untuk warga (WhatsApp, papan dusun)
- [ ] Rencana pemeliharaan bulanan (30 menit, di luar jam layanan) disepakati

## Maintenance Schedule

| Frekuensi | Tugas | Penanggung jawab |
|:---|:---|:---|
| Harian | Periksa antrean pengajuan dan eskalasi | Operator |
| Harian (otomatis) | Backup 02.00 WITA | Sistem |
| Mingguan | Tinjau pertanyaan gagal, labeli minimal 20 | Admin Teknis |
| Mingguan | Periksa audit log anomali | Sekdes |
| Bulanan | Retrain model, evaluasi metrik, aktivasi bila membaik | Admin Teknis |
| Bulanan | Rekap laporan layanan | Sekdes |
| Bulanan | `apt upgrade` + rebuild image (jendela 30 menit) | Admin Teknis |
| 6 bulan | Uji restore backup penuh | Admin Teknis |
| 6 bulan | Rotasi kredensial dan tinjau akses admin | Kepala Desa |
| Tahunan | Tinjau retensi data dan hapus arsip kedaluwarsa | Sekdes + Admin Teknis |
