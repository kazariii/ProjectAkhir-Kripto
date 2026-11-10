# Verifikasi tiket 01

Dokumen ini membedakan persiapan implementasi, pemeriksaan lokal, dan demonstrasi layanan sebenarnya. Tanggal persiapan: 10 November 2026. Tiket sumber tetap otoritas; `spec.md`, glosarium, dan ADR belum tersedia pada baseline `61536f0`.

## Batas antarmuka pengujian

Pengguna menyetujui dua jalur pengujian yang berasal dari acceptance criteria tiket: telemetry firmware, serta MQTT/TLS sampai dashboard/persistensi dan izin akses. Pengujian lokal pertama dijalankan melalui fungsi publik pembentuk pesan firmware. Pemeriksaan parser Telegraf menjadi bagian yang dapat dijalankan dari jalur kedua; bagian runtime tetap menunggu lingkungan tersedia.

| Batas | Perilaku yang diperiksa | Batas bukti |
| --- | --- | --- |
| Pembacaan sensor → pesan telemetry | Suhu valid menghasilkan JSON numerik dengan identitas tetap; suhu gagal dan konversi belum selesai tidak menghasilkan pesan | Uji host tidak membuktikan sensor, interval simulator, Wi-Fi, atau broker sebenarnya |
| MQTT/TLS → dashboard dan penyimpanan | Ingest angka/tag/waktu penerimaan, kueri terbaru/historis, persistensi setelah restart, CA/hostname dan pembatasan akun | Memerlukan Docker berjalan serta akses deployment/cloud dan simulasi |

## Pemetaan acceptance criteria

| Kriteria | Artefak yang disiapkan | Pemeriksaan yang diperlukan |
| --- | --- | --- |
| ESP32 + DS18B20, interval 2 detik | Firmware, diagram Wokwi, build PlatformIO | Build dan log interval simulasi |
| EMQX Serverless, Spend Limit 0 | Panduan pemilik akun | Bukti konsol deployment sebenarnya |
| Topik, identitas, JSON suhu | Kontrak firmware dan parser Telegraf | Uji pesan serta ingest nyata |
| TLS dan identitas server pada dua klien | CA lokal, hostname, NTP, konfigurasi TLS | Audit konfigurasi dan koneksi nyata |
| Username terpisah dan fallback deny | Tabel izin minimum di panduan | Bukti aturan konsol dan hasil akses |
| Docker versi tetap, rahasia diabaikan Git | Compose serta template lokal | Validasi Compose, start layanan, pemeriksaan Git |
| Float, tag perangkat, waktu penerimaan | Parser `json_v2` tanpa timestamp perangkat | Pemeriksaan titik hasil ingest |
| Nilai terbaru dan sejarah | Provisioning datasource dan dashboard | Perubahan slider sampai dashboard |
| Persistensi | Volume InfluxDB/Grafana serta provisioning | Restart dan kueri titik sebelum/sesudah |
| Pembacaan gagal tidak jadi suhu | Penolakan nilai dan diagnosis serial | Uji batas pesan dan kabel DQ terputus |
| Petunjuk dan bukti aktual | Panduan ini beserta catatan hasil | Pengulangan sesuai langkah tertulis |

## Kondisi awal yang diamati

- Worktree implementasi bersih pada branch `ticket/01-end-to-end-suhu`; baseline integrasi `61536f0` merupakan ancestor.
- Repository awal berisi instruksi agen dan tujuh tiket; belum ada kode aplikasi atau konfigurasi layanan.
- Kredensial EMQX Cloud dan akses simulasi Wokwi belum tersedia pada sesi implementasi.
- Mesin Docker belum tersedia. Aplikasi Docker Desktop gagal mulai pada pemeriksaan agen induk; konfigurasi global tidak diubah.

Kondisi ini belum membuktikan jalur end-to-end. Hasil build/tes lokal dan bukti pemilik akan dicatat sesudah benar-benar dijalankan.

## Hasil lokal aktual

| Pemeriksaan | Hasil | Batas kesimpulan |
| --- | --- | --- |
| C++ telemetry melalui GCC MinGW 5.1, C++11, `-Wall -Wextra -Werror` | Lulus; payload 27,5 Celsius cocok dengan JSON numerik dan identitas yang diharapkan | Tidak menjalankan sensor/Wi-Fi/TLS |
| Pembacaan tidak valid | Lulus; -127, -55,1, 125,1, NaN, infinity tidak menghasilkan pesan dan memberi diagnosis | Nilai disuntikkan pada batas publik, bukan dari kabel fisik |
| Konversi startup | Lulus; 85 Celsius sebelum konversi ditolak; 85 sesudah konversi dan batas numerik -55/125 diterima | Penyelesaian konversi hardware belum diamati di simulator |
| Build ESP32 `python -m platformio run` | SUCCESS, exit 0; RAM 26.356/327.680 byte (8,0%), flash 544.993/1.310.720 byte (41,6%); build awal 451,50 detik termasuk unduhan dependensi | Menggunakan template tanpa kredensial; firmware berhenti saat runtime sampai `secrets.h` diisi dan dibuild ulang |
| Telegraf native 1.40.3 dengan blok parser produksi | Lima kasus lulus: 27,5 dan perubahan 35 masuk sebagai float dengan tag perangkat dan waktu penerimaan; field suhu hilang, identitas hilang, serta teks nonnumerik ditolak | Input MQTT diganti `inputs.file` untuk tes; belum membuktikan broker/TLS/InfluxDB/Grafana |
| `docker compose config --quiet` dengan nilai dummy proses lokal | Exit 0 | Memvalidasi render Compose; tidak memulai container |
| Manifest image Docker pada registry resmi | Tiga image mengembalikan HTTP 200; digest dikunci di Compose | Belum mengunduh/menjalankan container |
| JSON diagram dan dashboard | Berhasil diparse | Tidak membuktikan rendering atau simulasi |

### Jejak red → green firmware

Tes ditulis satu perilaku setiap siklus, lalu implementasi minimal ditambahkan:

1. Payload suhu valid: kompilasi gagal terlebih dahulu karena `telemetry.h` belum ada (`fatal error: telemetry.h: No such file or directory`); setelah implementasi, executable exit 0.
2. Penolakan pembacaan gagal: assertion `!rejected.publish` gagal, executable exit 3; setelah validasi rentang/finite, executable exit 0.
3. Konversi startup: assertion `!makeTelemetry(85.0f, false).publish` gagal, executable exit 3; setelah gerbang konversi selesai, executable exit 0. Tes sekaligus mempertahankan 85 Celsius yang benar setelah konversi.

Parser Telegraf diperiksa setelah konfigurasi dibuat, melalui binary Telegraf sebenarnya. Pemeriksaan ini tidak diklaim sebagai siklus test-first atau demonstrasi end-to-end.

Build memakai espressif32 6.9.0, Arduino ESP32 package `3.20017.241212+sha.dcc1105b`, toolchain Xtensa `8.4.0+2021r2-patch5`, PubSubClient 2.8.0, OneWire 2.3.8, dan DallasTemperature 4.0.6. Ada dua warning dari kode dependensi OneWire pada baris 599/600 (`extra tokens at end of #undef directive`); build tetap berhasil. Tidak ada sertifikat deployment atau kredensial cloud yang digunakan selama build.

Contoh hasil parser aktual (10 November 2026, data uji tanpa rahasia):

```text
PASS: valid float, identity tag, reception timestamp | suhu,device_id=esp32-meja01 temperature_c=27.5 1794300549000000000
PASS: changed Celsius reaches metric | suhu,device_id=esp32-meja01 temperature_c=35 1794300549000000000
PASS: missing temperature rejected | parser error, no measurement
PASS: missing device identity rejected | parser error, no measurement
PASS: nonnumeric temperature rejected | parser error, no measurement
```

Payload pertama sengaja menyertakan `timestamp: 0`; hasil tetap memakai waktu penerimaan Telegraf, bukan epoch nol. Skrip juga memeriksa pesan error dan ketiadaan metric karena `telegraf --test` dapat exit 0 walaupun parser melaporkan error.

## Verifikasi pemilik yang masih diperlukan

Belum dijalankan: pembuatan/verifikasi akun EMQX, konfirmasi Spend Limit 0, audit aturan autentikasi/otorisasi aktual, handshake CA/hostname pada kedua klien, simulasi Wokwi, interval serial 2 detik, pemutusan DQ, perubahan suhu sampai Grafana, kueri riwayat InfluxDB, serta restart dan persistensi container. Kredensial/cloud tidak tersedia dan mesin Docker belum berjalan, sehingga acceptance criteria ini belum dinyatakan lulus.

| Percobaan pemilik | Tanggal/waktu | Bukti disamarkan | Hasil aktual |
| --- | --- | --- | --- |
| Serverless, batas nol, dua akun dan fallback deny | Belum dilakukan | — | Belum diverifikasi |
| Wi-Fi, NTP, TLS, interval 2 detik, payload sensor | Belum dilakukan | — | Belum diverifikasi |
| Suhu 25 → 35 terlihat di Grafana dan InfluxDB | Belum dilakukan | — | Belum diverifikasi |
| DQ terputus menghasilkan diagnosis tanpa suhu palsu | Belum dilakukan | — | Belum diverifikasi |
| Restart mempertahankan riwayat dan menerima titik baru | Belum dilakukan | — | Belum diverifikasi |

Simpan bukti mentah lokal di `evidence/local/` yang diabaikan Git. Sebelum memasukkan bukti ke laporan/repository, hilangkan password, token, dan konfigurasi lokal rahasia. Jangan menandai tiket selesai hanya berdasarkan pemeriksaan lokal di atas.
