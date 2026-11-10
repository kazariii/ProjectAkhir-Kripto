# Verifikasi tiket 01

Dokumen ini membedakan persiapan implementasi, pemeriksaan lokal, dan demonstrasi layanan sebenarnya. Tanggal persiapan: 10 November 2026. Tiket sumber tetap otoritas; `spec.md`, glosarium, dan ADR belum tersedia pada baseline `61536f0`.

## Batas antarmuka pengujian

Pengguna menyetujui dua jalur pengujian yang berasal dari acceptance criteria tiket: telemetry firmware, serta MQTT/TLS sampai dashboard/persistensi dan izin akses. Pengujian lokal pertama dijalankan melalui fungsi publik pembentuk pesan firmware. Hasil demo cloud setelah konfigurasi pemilik tersedia dicatat pada bagian pembaruan di bawah; hasil lokal awal tetap dipertahankan sebagai riwayat pemeriksaan.

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

## Pembaruan demo aktual — 10 November 2026

| Pemeriksaan | Bukti dan hasil aktual | Batas kesimpulan |
| --- | --- | --- |
| Deployment dan izin | Screenshot pemilik menunjukkan Serverless Running, Spend Limit $0.00, akun `esp32-meja01` dan `telegraf-meja01`, Allow Publish/Subscribe masing-masing pada topik utama, serta All Users deny Publish & Subscribe `#` | Screenshot konfigurasi tidak menggantikan uji operasi; hasil uji dicatat di bawah |
| Sensor Wokwi | Log pemilik setelah perbaikan timer menunjukkan suhu 25.00 Celsius dan gas 2177 ADC terkirim pada ms 33951, 35951, dan 37951 | Menunjukkan interval 2.000 ms saat terhubung; bukan bukti pembacaan sensor fisik |
| TLS dan autentikasi ESP32 | Probe PC menggunakan CA tertanam serta hostname/akun firmware berhasil melalui TLS 1.2 dan MQTT 3.1.1; source firmware tetap memverifikasi CA/hostname; Wokwi kemudian melaporkan pengiriman berhasil | Probe PC dan log Wokwi dibedakan; password tidak dicatat |
| Layanan produksi | InfluxDB healthy; Grafana dan Telegraf running. Telegraf tersambung ke EMQX melalui TLS dengan verifikasi aktif. `.env`, `secrets.h`, dan CA lokal diabaikan serta tidak dilacak Git | Belum merupakan uji restart layanan demo |
| Penyimpanan cloud → lokal | Kueri InfluxDB menemukan 34 titik `esp32-meja01` dalam jendela satu jam. Nilai suhu bervariasi, antara lain 22, 25, 34.69, 57, dan 104.81 Celsius. Sampel terakhir saat pemeriksaan: `2026-11-10T11:51:06.778561474Z`, suhu 25.12, gas 2177 | Jumlah/nilai merupakan snapshot pemeriksaan; tidak memasukkan titik uji sensor buatan oleh agen |
| Grafana | API panel stat suhu menghasilkan 25.12; panel historis menghasilkan 33 nilai numerik, tanpa error. Pemilik menyatakan perubahan suhu berhasil setelah mengikuti langkah slider | API membuktikan kueri/provisioning; tampilan browser dilaporkan pemilik |

### Pemeriksaan akses MQTT aktual

Semua koneksi pemeriksaan memakai TLS dengan verifikasi CA/hostname, MQTT 5, clean start, serta client ID sementara yang berbeda dari ESP32 dan Telegraf produksi. Tidak ada perubahan akun/aturan broker. Payload uji Publish terlarang tidak memuat field sensor, tidak retained, dan tidak dapat menjadi pengukuran suhu normal melalui parser produksi.

| Percobaan | Respons aktual | Hasil |
| --- | --- | --- |
| Akun ESP32 sah sebelum uji negatif | CONNACK 0 | Lulus |
| Tanpa username/password | CONNACK 134 | Ditolak |
| Username ESP32 dengan password salah | CONNACK 134 | Ditolak |
| Telegraf Subscribe topik utama | SUBACK 0 | Diizinkan |
| ESP32 Subscribe topik utama | SUBACK 135 | Ditolak |
| Telegraf Publish topik utama | PUBACK 135 | Ditolak |
| ESP32 Publish topik probe di luar izin | PUBACK 135 | Ditolak |
| Telegraf Subscribe topik probe di luar izin | SUBACK 135 | Ditolak |
| Akun ESP32 sah setelah uji negatif | CONNACK 0 | Lulus |

MQTT 5 memakai reason code 134 untuk kredensial tidak diterima dan 135 untuk operasi tidak diizinkan; lihat [spesifikasi OASIS](https://docs.oasis-open.org/mqtt/mqtt/v5.0/os/mqtt-v5.0-os.html). Hasil di atas membuktikan kasus yang diuji, bukan seluruh demonstrasi keamanan tiket 05/06.

## Verifikasi akhir pemilik — selesai

| Percobaan | Status | Cara membuktikan |
| --- | --- | --- |
| Restart stack demo | Lulus berdasarkan konfirmasi pemilik, 10 November 2026 | Pemilik mengonfirmasi percobaan restart/persistensi yang diarahkan sebelumnya berhasil: riwayat tetap tersedia dan pengiriman baru berlanjut |
| Pembacaan gagal DS18B20 | Lulus berdasarkan konfirmasi pemilik, 10 November 2026 | Pemilik mengonfirmasi percobaan melepas dan mengembalikan DQ berhasil: diagnosis muncul, tanpa suhu palsu, lalu pengiriman pulih |

Konfirmasi akhir pemilik pada percakapan: "oke udah aman, percobaannya udah kcoba dan bisa". Tidak ada screenshot tambahan atau pengulangan oleh agen yang diklaim untuk dua percobaan ini. Seluruh acceptance criteria tiket 01 selesai; penghambat tiket 02 terpenuhi.

Simpan screenshot dashboard serta log sebelum/sesudah percobaan di `evidence/local/` yang diabaikan Git untuk laporan/presentasi. Hilangkan password, token, dan konfigurasi rahasia dari bukti yang dibagikan.
