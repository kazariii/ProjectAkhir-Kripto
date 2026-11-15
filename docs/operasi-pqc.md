# Operasi MQTT/PQC di LXC

Jalur utama sejak tiket 06 adalah Wokwi → Mosquitto TCP/1883 → receiver PQC → InfluxDB → Grafana. Monitoring tetap di LXC; laptop menjalankan simulator dan browser. MQTT/TLS/Telegraf lama telah dihentikan. Ini deployment lab privat dengan prospective FN-DSA, bukan sertifikasi keamanan produksi.

Untuk presentasi berurutan beserta expected output, gunakan [panduan demo lengkap](demo-proyek.md). Dokumen operasi ini tetap menjadi rujukan lokasi state, provisioning dan rollback.

## Lokasi dan state

| Komponen | Lokasi/akses |
|---|---|
| Source receiver, broker dan alat uji | `/opt/lab-kimia-mqtt` |
| Compose Influx/Grafana dan `.env` initialized | `/opt/lab-kimia-suhu` |
| Grafana | `http://10.34.211.141:3000/d/suhu-meja01`, UID `suhu-meja01` |
| Datasource | `influx-suhu`, org `lab-kimia`, bucket `telemetry` |
| InfluxDB | `http://127.0.0.1:8086`, hanya loopback LXC |
| Broker | `10.34.211.141:1883`, bind privat, login/ACL, tanpa TLS |
| Receiver | `lab-kimia-pqc-session.service`, enabled, restart on failure |
| Private MQTT | `evidence/local/mqtt-private` pada source receiver |
| Private identity dan token writer | `evidence/local/session-private` pada source receiver |

Dua direktori mempunyai peran berbeda: source ingress baru dan state monitoring yang sudah diinisialisasi. Jangan memindahkan direktori data atau membuat ulang bucket untuk menyamakan namanya. Volume tetap `lab-kimia-suhu_influx-data`, `lab-kimia-suhu_influx-config`, dan `lab-kimia-suhu_grafana-data`. Pertahankan `.env`, bind Grafana `10.34.211.141`, identity/pin dan token yang ada.

Nama akun/header `diag-*` dan `mqtt_diag_secrets.h` berasal dari provisioning awal dan kini juga dipakai transport sensor. Receiver diagnostic tidak wajib aktif dan service-nya dinonaktifkan pada jalur utama. Tidak ada rotasi kredensial atau perluasan izin aplikasi selama migrasi.

## Operasi rutin pada server

```sh
ssh root@10.34.211.141
cd /opt/lab-kimia-suhu
docker compose config --quiet
docker compose up -d --wait --wait-timeout 120
cd /opt/lab-kimia-mqtt/infra/mqtt
docker compose config --quiet
docker compose up -d --wait --wait-timeout 60
systemctl enable --now lab-kimia-pqc-session.service
journalctl -u lab-kimia-pqc-session.service -n 20 --no-pager -o cat
```

Compose utama hanya menjalankan InfluxDB/Grafana; broker memakai Compose miliknya. Receiver menerima secret melalui systemd `LoadCredential` dan memakai token **write-only** bucket telemetry. `.env` monitoring dipakai administrasi/Grafana dan tidak diberikan kepada receiver. Private directory 0700 dan secret files 0600. Jangan mencetak `.env`, header, identity, token, atau hasil `docker compose config` lengkap.

Restart layanan tanpa reboot LXC/menghapus volume:

```sh
cd /opt/lab-kimia-suhu
docker compose restart
docker compose up -d --wait --wait-timeout 120
cd /opt/lab-kimia-mqtt/infra/mqtt
docker compose restart
systemctl restart lab-kimia-pqc-session.service
```

Docker dan receiver enabled; container memakai `unless-stopped`. Ini konfigurasi autostart yang diperiksa, bukan bukti reboot seluruh LXC. Container yang sengaja dihentikan perlu dinyalakan lagi. Jangan menjalankan `down -v`, reset bucket, atau menghapus volume. Pantau `df -h /`: retensi Influx tetap tanpa batas dan backup eksternal belum disiapkan.

## Firmware utama dan Wokwi

Gunakan folder **`firmware`**, `platformio.ini` default `pqc-telemetry`, dan `wokwi.toml` yang menunjuk `.pio/build/pqc-telemetry/firmware.bin`/`.elf`. Ini application image PlatformIO yang didukung [konfigurasi resmi Wokwi](https://docs.wokwi.com/vscode/project-config#esp32-application-image-vs-full-image); build memakai partition/flash standar. Image dan ELF memuat key/kredensial demo sehingga tetap ignored/private.

Build pada LXC yang sudah mempunyai toolchain:

```sh
cd /opt/lab-kimia-mqtt
PLATFORMIO_CORE_DIR=/opt/lab-kimia-suhu/pqc-proof/evidence/local/platformio \
  /opt/lab-kimia-suhu/pqc-proof/.venv/bin/pio run -d firmware -j2
```

Salin `.bin` dan `.elf` melalui SCP ke `firmware/.pio/build/pqc-telemetry/` di laptop. F1 → Wokwi: Start Simulator, dengan Private Gateway/lisensi yang sudah aktif. Jalankan hanya satu perangkat/simulator. Awali 25°C/gas rendah, tunggu `TELEMETRY_STORED`; ubah sensor dan periksa flag serta dashboard. Bila UI mengingat gas 400 walaupun diagram berisi 0.1, turunkan slider sampai **DOUT HIGH**. Gas adalah stimulus simulator; ADC tidak dianggap ppm terkalibrasi.

Selama handshake/signature, sensor/alarm tetap berjalan, sampel lama dibuang dan telemetri dapat berhenti sekitar 12 detik virtual. Renewal terenkripsi dimulai pada umur endpoint 180 detik, expiry 300 detik. `TELEMETRY_STORED` berarti ACK AEAD terverifikasi setelah write dikonfirmasi; tidak adanya ACK tidak memastikan apakah database menulis atau tidak. Dashboard menandai data terlambat setelah >10 detik tanpa titik baru.

Untuk capture, aktifkan sementara `rfc2217ServerPort = 4000` pada `firmware/wokwi.toml`, lalu jalankan reader dari root repo sebelum Start:

```sh
node tools/telemetry/capture_serial.mjs evidence/local/wokwi-run-baru.txt
```

Jangan Pause. Setelah Stop, hentikan reader, nonaktifkan baris RFC2217, lalu tutup preview/reload VS Code bila listener masih terbuka. [Bukti tiket 06](verifikasi-pqc-tiket-06.md) memakai folder utama ini; `tools/*/simulator` tetap fixture pengujian sebelumnya.

## Migrasi pada state existing

Setelah menyalin source yang ditinjau ke `/opt/lab-kimia-mqtt`:

```sh
cd /opt/lab-kimia-mqtt
.venv/bin/python -m tools.deploy.migrate
# Hentikan Wokwi sebelum kontrol native/restart berikut.
.venv/bin/python -m tools.deploy.check_migration
```

Skrip pertama memvalidasi state, menyimpan compose lama/baseline di `evidence/local/migration06` (private), menerapkan Compose tanpa Telegraf, menghapus **container ingress stateless saja**, memastikan receiver/broker aktif dan menonaktifkan diagnostic proof. Kredensial/pin tidak dirotasi. Pengulangan memeriksa baseline yang sama; state berbeda ditolak. Kegagalan tidak otomatis menghidupkan ingress TLS lama. Skrip kedua menulis dua sampel sintetis berlabel native, merestart layanan, lalu memeriksa history, token dan Grafana; itu tidak menggantikan bukti Wokwi.

Provisioning fresh tetap mengikuti [MQTT](../tools/mqtt/README.md), [pin/session](../tools/session/README.md), dan [token writer](../tools/telemetry/README.md). Jangan mengatasi error dengan merotasi secret tanpa mengetahui penyebabnya.

## Rollback manual

Rollback ke transport lama mengaktifkan kembali MQTT/TLS dan tidak sesuai jalur utama revisi tugas. Hentikan Wokwi PQC dahulu; jangan menjalankan kedua ingress bersamaan.

```sh
systemctl disable --now lab-kimia-pqc-session.service
cd /opt/lab-kimia-suhu
docker compose -f compose.yaml -f compose.legacy.yaml config --quiet
docker compose -f compose.yaml -f compose.legacy.yaml up -d --wait --wait-timeout 120 telegraf
```

Gunakan konfigurasi cloud/CA lama yang masih tersimpan dan build firmware **eksplisit** `pio run -e esp32dev`; arahkan simulator secara sadar ke image legacy. Tidak ada pergantian transport saat runtime. Volume Influx/Grafana tetap sama. Compose sebelum migrasi juga tersedia private di `/opt/lab-kimia-mqtt/evidence/local/migration06/compose.before.yaml`.

Untuk kembali ke PQC, hentikan firmware legacy lalu jalankan `tools.deploy.migrate` lagi. Diagnostic tidak perlu diaktifkan. Override rollback divalidasi; mengaktifkan kembali cloud ingress lama bukan bagian uji jalur baru tiket 06.
