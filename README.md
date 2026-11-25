# Monitoring gas dan suhu meja praktikum

Jalur demo utama memakai **Wokwi web** dan broker MQTT publik **`broker.emqx.io:1883`, tanpa TLS dan tanpa login**. ESP32/Wokwi membaca DS18B20 dan MQ2; ML-KEM-512 membentuk rahasia sesi, prospective FN-DSA degree 512 mengautentikasi kedua pihak saat handshake, dan ChaCha20-Poly1305 mengenkripsi telemetri beserta ACK. Receiver di LXC tersambung keluar ke broker publik dan menulis langsung ke InfluxDB; Grafana menampilkan nilai terbaru, riwayat dan empat keadaan alarm.

```text
DS18B20 + MQ2 → ESP32/Wokwi web → broker.emqx.io:1883 (publik) → receiver PQC (LXC)
                                                                 ↓ HTTP loopback
                                                             InfluxDB → Grafana
```

Monitoring berjalan di **LXC `10.34.211.141`**; buka [dashboard meja 01](http://10.34.211.141:3000/d/suhu-meja01) dari jaringan kampus. Build default **`pqc-telemetry-public`** memakai identitas FN-DSA demo, terpisah dari identitas lab. Broker publik tidak memberi login/ACL: siapa pun dapat publish/subscribe pada topik, jadi kerahasiaan, integritas dan autentikasi sepenuhnya berasal dari protokol sesi. Jalur privat lama (Wokwi VS Code → Mosquitto `10.34.211.141:1883` dengan login/ACL) tetap hidup sebagai cadangan dan rollback.

## Menjalankan proyek yang sudah dikonfigurasi

Mulai dari **[panduan demo utama (Wokwi web)](docs/demo-proyek.md)**: syarat jaringan, pemeriksaan LXC, proyek Wokwi web, empat keadaan alarm, bukti otomatis, build ulang, dan rollback. Untuk jalur privat, gangguan terukur dan uji keamanan native, gunakan [panduan jalur privat](docs/demo-proyek-privat.md).

1. Laptop yang menjalankan Wokwi web harus memakai **hotspot**; jaringan kampus memblokir Wi-Fi simulasi Wokwi web. Perangkat yang membuka Grafana harus di jaringan kampus.
2. Di wokwi.com, pakai `firmware/diagram.json` dan chip `mq2-level`, lalu F1 → **Upload Firmware and Start Simulation...** dengan `pqc-telemetry-public-full.bin` (diabaikan Git; dibagikan hanya untuk demo).
3. Geser slider MQ2 ke paling kiri segera setelah Start. Tunggu `TELEMETRY_AUTHENTICATED` lalu `TELEMETRY_STORED` dengan `ack_verified:true`. Jangan Pause.
4. Buka Grafana dengan akun yang sudah ada. Timestamp adalah waktu penerimaan LXC. Status menjadi **Data terlambat** setelah >10 detik tanpa titik baru, dengan nilai/waktu terakhir tetap terlihat.

LED merah/buzzer aktif bila DOUT MQ2 LOW atau suhu valid ≥40°C. Pembacaan suhu gagal mempertahankan alarm suhu sebelumnya; alarm gas tetap independen. Sensor/alarm berjalan tiap 2 detik selama koneksi/handshake. Satu antrean sampel terbaru mencegah pengiriman backlog. ACK terenkripsi hanya dibentuk sesudah Influx mengonfirmasi write; frame tanpa ACK tidak diklaim tersimpan.

DS18B20 mengukur lingkungan meja, bukan nyala api langsung. MQ2 dilaporkan sebagai ADC/level relatif, bukan ppm LPG terkalibrasi. Ambang alarm adalah pengaturan demonstrasi, bukan standar keselamatan.

## Dokumen dan bukti revisi

- [Operasi LXC, jalur publik/privat, migrasi dan rollback](docs/operasi-pqc.md)
- [Migrasi ke Wokwi web dan broker publik](.scratch/wokwi-web-broker-publik/spec.md)
- [Protokol sesi, nonce, replay dan lifecycle](docs/protokol-sesi-pqc.md)
- [01 — Kelayakan algoritma pada ESP32/LXC](docs/verifikasi-pqc-tiket-01.md)
- [02 — Konektivitas MQTT privat Wokwi–LXC](docs/verifikasi-pqc-tiket-02.md)
- [03 — Sesi terautentikasi dua arah](docs/verifikasi-pqc-tiket-03.md)
- [04 — Sensor sampai Influx/Grafana](docs/verifikasi-pqc-tiket-04.md)
- [05 — Serangan dan pemulihan](docs/verifikasi-pqc-tiket-05.md)
- [06 — Migrasi jalur utama](docs/verifikasi-pqc-tiket-06.md)
- [07 — Panduan demo dan verifikasi akhir](docs/verifikasi-pqc-tiket-07.md)
- [Pengujian sensor dan capture](tools/telemetry/README.md)

Algoritma tetap sesuai penetapan dosen. Implementasi FN-DSA masih **prospektif**; protokol lab ini belum diaudit independen dan tidak diklaim memenuhi FIPS 206 final. MQTT tanpa TLS tetap memperlihatkan topik, ukuran dan waktu pesan (serta password broker pada jalur privat). Autentikasi payload memerlukan private identity, bukan sekadar akses ke broker. Banjir pesan di broker publik dapat membuat frame sah terbuang; bin publik memuat kunci klien demo. Re-key dapat menghasilkan celah data; ini bukan jaminan delivery atau ketahanan DoS.

Kode dan bukti disimpan lokal; **push GitHub dilakukan sendiri oleh pengguna**. [Panduan demo TLS lama](docs/demo-proyek-tls-arsip.md), [deployment lama](docs/deploy-lxc.md), dan `compose.legacy.yaml` adalah arsip/rollback yang harus dipilih secara eksplisit; tidak ada fallback otomatis ke jalur lama.
