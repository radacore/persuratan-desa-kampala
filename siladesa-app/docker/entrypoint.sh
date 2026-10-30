#!/bin/sh
# Entrypoint produksi: pastikan skema mutakhir, isi data awal, lalu jalankan app.
set -eu

echo "[entrypoint] migrasi basis data ..."
python -m alembic upgrade head

# Idempoten: hanya mengisi yang belum ada dan melatih model bila belum aktif.
echo "[entrypoint] seed data awal ..."
python -m app.seed

echo "[entrypoint] menyalakan SILADESA ..."
exec "$@"
