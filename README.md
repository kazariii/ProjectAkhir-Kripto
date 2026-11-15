# Monitoring gas dan suhu meja praktikum

Jalur utama memakai **MQTT TCP/1883 tanpa TLS** ke broker privat LXC. ESP32/Wokwi membaca DS18B20 dan MQ2; ML-KEM-512 membentuk rahasia sesi, prospective FN-DSA degree 512 mengautentikasi kedua pihak saat handshake, dan ChaCha20-Poly1305 mengenkripsi telemetri beserta ACK. Receiver menulis langsung ke InfluxDB; Grafana menampilkan nilai terbaru, riwayat dan empat keadaan alarm.

```text
DS18B20 + MQ2 → ESP32/Wokwi → Mosquitto privat :1883 → receiver PQC
                                                       ↓ HTTP loopback
                                                   InfluxDB → Grafana
```

Monitoring berjalan di **LXC `10.34.211.141`**. Laptop cukup untuk Wokwi VS Code dengan Private Gateway dan membuka [dashboard meja 01](http://10.34.211.141:3000/d/suhu-meja01). Build default **`pqc-telemetry`** dan konfigurasi utama **`firmware/wokwi.toml`** memilih jalur ini. Telegraf lama tidak termasuk Compose default. Kredensial cloud/CA lama tidak diperlukan untuk menjalankan jalur utama.

## Menjalankan proyek yang sudah dikonfigurasi

Mulai dari **[panduan demo lengkap MQTT/PQC](docs/demo-proyek.md)** untuk langkah laptop/LXC, expected output, empat keadaan alarm, keamanan, gangguan/pemulihan, pengambilan bukti dan penutupan. [Verifikasi tiket 07](docs/verifikasi-pqc-tiket-07.md) membedakan pengujian baru dan bukti Wokwi yang dipakai ulang.

1. Buka folder **`firmware`** di VS Code. Header private MQTT dan pin identitas harus sudah tersedia; jangan mengunggah header atau image build ke proyek publik. Pada laptop pengujian ini image/ELF hasil build LXC sudah disalin ke `.pio/build/pqc-telemetry/`.
2. Jika membangun sendiri, jalankan `pio run` dari folder `firmware`; default kini PQC. Detail provisioning, build pada LXC dan rollback ada di [operasi MQTT/PQC](docs/operasi-pqc.md).
3. F1 → **Wokwi: Start Simulator**, memakai lisensi dan Private Gateway yang sudah aktif. Tunggu `TELEMETRY_AUTHENTICATED` lalu `TELEMETRY_STORED` dengan `ack_verified:true`. Tetap tampilkan simulator; jangan Pause ketika menguji aliran data.
4. Buka Grafana dengan akun yang sudah ada. Timestamp adalah waktu penerimaan LXC. Status menjadi **Data terlambat** setelah >10 detik tanpa titik baru, dengan nilai/waktu terakhir tetap terlihat.

LED merah/buzzer aktif bila DOUT MQ2 LOW atau suhu valid ≥40°C. Pembacaan suhu gagal mempertahankan alarm suhu sebelumnya; alarm gas tetap independen. Sensor/alarm berjalan tiap 2 detik selama koneksi/handshake. Satu antrean sampel terbaru mencegah pengiriman backlog. ACK terenkripsi hanya dibentuk sesudah Influx mengonfirmasi write; frame tanpa ACK tidak diklaim tersimpan.

DS18B20 mengukur lingkungan meja, bukan nyala api langsung. MQ2 dilaporkan sebagai ADC/level relatif, bukan ppm LPG terkalibrasi. Ambang alarm adalah pengaturan demonstrasi, bukan standar keselamatan.

## Dokumen dan bukti revisi

- [Operasi LXC, migrasi dan rollback](docs/operasi-pqc.md)
- [Protokol sesi, nonce, replay dan lifecycle](docs/protokol-sesi-pqc.md)
- [01 — Kelayakan algoritma pada ESP32/LXC](docs/verifikasi-pqc-tiket-01.md)
- [02 — Konektivitas MQTT privat Wokwi–LXC](docs/verifikasi-pqc-tiket-02.md)
- [03 — Sesi terautentikasi dua arah](docs/verifikasi-pqc-tiket-03.md)
- [04 — Sensor sampai Influx/Grafana](docs/verifikasi-pqc-tiket-04.md)
- [05 — Serangan dan pemulihan](docs/verifikasi-pqc-tiket-05.md)
- [06 — Migrasi jalur utama](docs/verifikasi-pqc-tiket-06.md)
- [07 — Panduan demo dan verifikasi akhir](docs/verifikasi-pqc-tiket-07.md)
- [Pengujian sensor dan capture](tools/telemetry/README.md)

Algoritma tetap sesuai penetapan dosen. Implementasi FN-DSA masih **prospektif**; protokol lab ini belum diaudit independen dan tidak diklaim memenuhi FIPS 206 final. MQTT tanpa TLS tetap memperlihatkan password broker, topik, ukuran dan waktu pesan. Autentikasi payload memerlukan private identity, bukan sekadar password MQTT. Re-key dapat menghasilkan celah data; ini bukan jaminan delivery atau ketahanan DoS.

Kode dan bukti disimpan lokal; **push GitHub dilakukan sendiri oleh pengguna**. [Panduan demo TLS lama](docs/demo-proyek-tls-arsip.md), [deployment lama](docs/deploy-lxc.md), dan `compose.legacy.yaml` adalah arsip/rollback yang harus dipilih secara eksplisit; tidak ada fallback otomatis ke jalur lama.
