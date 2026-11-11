# Monitoring gas dan suhu meja praktikum

Satu ESP32 membaca DS18B20 dan MQ2 di Wokwi, lalu mengirim suhu lingkungan serta level gas relatif sekitar meja praktikum LPG melalui MQTT over TLS ke EMQX Cloud Serverless. Telegraf menerima pesan, InfluxDB 2.x menyimpan kedua pengukuran dengan waktu penerimaan yang sama, dan Grafana menampilkan nilai terbaru, grafik historis terpisah, serta empat keadaan alarm dan riwayatnya. ESP32 mengaktifkan LED merah/buzzer bila DOUT MQ2 LOW atau suhu valid mencapai 40 Celsius; pembacaan suhu gagal tidak menghapus alarm suhu sebelumnya.

Mulai dari **[panduan demo lengkap](docs/demo-proyek.md)**: konfigurasi dari template, layanan Docker/Wokwi, semua kondisi alarm, gangguan/pemulihan, restart tanpa kehilangan riwayat, serta demonstrasi autentikasi dan TLS. Stack monitoring sekarang tersedia di **[LXC 10.34.211.141](docs/deploy-lxc.md)**; laptop cukup untuk membuka dashboard dan menjalankan simulator. [Hasil pengulangan tiket 07](docs/verifikasi-tiket-07.md) mencatat bukti aktual dan batasnya. Push GitHub dilakukan sendiri oleh pengguna.

```text
DS18B20 + MQ2 → ESP32/Wokwi → MQTT/TLS :8883 → EMQX Cloud Serverless
                                            ↓ MQTT/TLS :8883
                                         Telegraf
                                            ↓ HTTP jaringan Docker
                                         InfluxDB 2.x → Grafana
```

Sensor menggambarkan lingkungan sekitar meja, bukan nyala api langsung. MQ2 ditampilkan sebagai ADC/level relatif, bukan konsentrasi LPG terkalibrasi atau ppm pengukuran nyata. Panduan ini menyiapkan demonstrasi simulasi, bukan sistem keselamatan laboratorium.

- [Petunjuk jalur gas dan suhu](docs/jalur-suhu.md)
- [Rencana dan batas verifikasi tiket 01](docs/verifikasi-tiket-01.md)
- [Tiket sumber](.scratch/monitoring-lab-kimia/issues/01-end-to-end-suhu.md)
- [Verifikasi dan demo tiket 02](docs/verifikasi-tiket-02.md)
- [Tiket monitoring gas](.scratch/monitoring-lab-kimia/issues/02-monitoring-gas.md)
- [Verifikasi dan demo alarm tiket 03](docs/verifikasi-tiket-03.md)
- [Tiket alarm mandiri](.scratch/monitoring-lab-kimia/issues/03-alarm-gas-suhu.md)
- [Verifikasi keterlambatan dan pemulihan tiket 04](docs/verifikasi-tiket-04.md)
- [Tiket koneksi dan data terlambat](.scratch/monitoring-lab-kimia/issues/04-koneksi-data-terlambat.md)
- [Demonstrasi autentikasi, izin topik, dan verifikasi CA tiket 05](docs/verifikasi-tiket-05.md)
- [Tiket keamanan akses MQTT](.scratch/monitoring-lab-kimia/issues/05-autentikasi-otorisasi.md)
- [Demonstrasi kerahasiaan dan integritas TLS tiket 06](docs/verifikasi-tiket-06.md)
- [Tiket bukti keamanan TLS](.scratch/monitoring-lab-kimia/issues/06-bukti-keamanan-tls.md)

Tugas jaringan ESP32 terpisah dari loop sensor/alarm. Grafana memperlihatkan waktu penerimaan terakhir dan menandai data terlambat setelah >10 detik tanpa pesan; kondisi saat ini tidak disimpulkan dari nilai normal lama. Sampel selama koneksi putus tidak dikirim ulang. Ambang 40 Celsius dan MQ2 adalah pengaturan demonstrasi simulasi, bukan standar keselamatan atau bukti deteksi kebakaran. Tiket 05 menyediakan uji berulang terhadap akun proyek untuk penolakan kredensial, izin topik, serta CA tidak dipercaya, dengan kontrol sah sebelum/sesudah. Tiket 06 menyediakan capture TLS jalur utama, perbandingan plaintext/TLS pada broker demo lokal, dan penolakan perubahan satu bit ciphertext dengan kontrol normal sebelum/sesudah. Build, parser, broker TLS lokal sampai kueri Grafana, dan persistensi dapat diperiksa tanpa kredensial cloud. Demo Wokwi sampai EMQX dan Grafana juga telah diverifikasi; pemasangan baru tetap memerlukan konfigurasi akun pemilik.
