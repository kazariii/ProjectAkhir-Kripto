# 03: Telemetri PQC end-to-end lewat broker.emqx.io dari Wokwi web

**What to build:** Simulasi sensor lengkap di Wokwi web mengirim telemetri terenkripsi lewat `broker.emqx.io`. Receiver kedua di LXC menyimpan ke InfluxDB yang sama dan data tampil di Grafana. Firmware publik memakai identitas FN-DSA demo yang terpisah dari identitas lab. Jalur privat tetap berjalan berdampingan.

**Blocked by:** 01 Spike — Wokwi web menjangkau broker.emqx.io; 02 Prefactor — host broker dan prefix topik dapat dikonfigurasi

**Status:** done

- [x] Pasangan identitas demo dibuat; identitas lab tidak dirotasi atau disalin
- [x] Bin publik tidak memuat identitas lab, kredensial privat, atau IP privat
- [x] Receiver publik berjalan sebagai layanan terpisah dengan restart otomatis; receiver privat tetap aktif
- [x] Run Wokwi web: sesi terautentikasi dua arah, ACK terenkripsi, dan setiap ACK cocok dengan titik InfluxDB/Grafana
- [x] Keadaan alarm suhu/gas tetap teramati di Wokwi web

## Comments

Membutuhkan langkah manusia: menjalankan simulasi di Wokwi web dan mengirim log serial.

**Bagian agen selesai, 25 November 2026.**

- `tools.session.provision --profile demo` membuat identitas di `evidence/local/session-demo/` dan header `firmware/include/pqc_session_identity_demo.h` (diabaikan Git). Provisioning dijalankan dua kali tanpa rotasi, dan hash identitas lab sama sebelum dan sesudahnya. Provisioning menolak profil yang berbagi public key.
- Firmware memilih identitas lewat `PQC_IDENTITY_HEADER`. Env `pqc-telemetry-public` memakai `broker.emqx.io`, prefix `lkpqc-b16bef88/session`, dan identitas demo. Setting receiver ada di `evidence/local/public-broker/session.json` dengan prefix yang sama (`public: true`).
- Audit bin publik: tidak ada `10.34.211.141`, `diag-device`, host EMQX lama, atau potongan kunci rahasia/publik lab. Identitas demo ada di dalamnya. Kontrol audit: bin lab memuat kunci lab dan tidak memuat identitas demo.
- `lab-kimia-pqc-session-public.service` aktif dan enabled, dengan event `ready` `broker:broker.emqx.io`, `topic_prefix:lkpqc-b16bef88/session`, `public:true`. Receiver privat tetap aktif.
- Kontrol native: identitas demo lewat broker publik lulus (`run_id` `b316adfbfa51ebcab22ba5341adeeb87`, ACK terenkripsi terverifikasi). Identitas lab ke receiver publik ditolak (event `rejected`, klien timeout). Jalur privat tetap lulus.
- `verify_capture --public` mencocokkan run Wokwi web dengan jurnal receiver publik, InfluxDB, dan Grafana. Log broker publik tidak tersedia, jadi bukti asal ESP32 adalah `session_id` 128-bit yang sama di log serial dan jurnal receiver.
- Regresi di LXC: 113 checks, 20 unit test, siklus sensor, dan capture diagnostik lulus.
- **Risiko yang diterima:** siapa pun yang memegang bin publik dapat mengekstrak kunci klien demo lalu mengirim telemetri sah ke InfluxDB lewat receiver publik. Bagikan bin hanya untuk demo. Matikan `lab-kimia-pqc-session-public.service` atau rotasi identitas demo bila bin bocor.

**Run Wokwi web, 25 November 2026 (laptop memakai hotspot).**

- Run diterima: `run_id` `8e88b610329a0b7b444f20dcea3142f8`, `local_ip` `10.10.0.2`, satu sesi `0938415ec9aa5b94fa0ce88232dece22`. Ada 25 SENT dan 25 STORED (`ack_verified:true`), tanpa frame tanpa ACK. Keempat keadaan tercakup: normal (counter 1–5), suhu saja (6–10), suhu dan gas (11–16), gas saja (17–25).
- `verify_capture --public` lulus. Ke-25 ACK cocok dengan event `session_established`, `telemetry_stored`, dan `stored_ack_queued` di jurnal `lab-kimia-pqc-session-public.service`, dengan 25 titik InfluxDB dan query panel Grafana. Bukti: `docs/evidence/wokwi-web-03/esp32-serial.txt` dan `capture-validation.json`. Hash capture di JSON dihitung dari salinan LF di LXC; salinan repo memakai CRLF (autocrlf).
- Tiga run sebelumnya ditolak sebagai bukti. Run pertama dan ketiga: gas sudah alarm sejak boot karena Wokwi mengingat posisi slider, sehingga keadaan normal dan suhu saja tidak tercakup. Run kedua: simulasi di-pause sehingga koneksi terputus dan log yang dikirim hanya potongan. Pause tidak merusak data, karena sampel selama pemulihan tidak dikirim dan tidak diklaim tersimpan, tetapi run bukti harus tanpa pause.
- Catatan untuk panduan demo (tiket 05): geser slider MQ2 ke paling kiri segera setelah Start, dan jangan pause.

**Langkah manusia:** upload `evidence/local/public-telemetry-firmware/pqc-telemetry-public-full.bin` di proyek Wokwi web yang sama (diagram `firmware/diagram.json` dan chip MQ2), dengan laptop memakai hotspot. Lewati empat keadaan alarm, lalu kirim seluruh log serial.
