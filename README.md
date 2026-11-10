# Monitoring suhu meja praktikum

Jalur tiket 01: satu ESP32 dan DS18B20 di Wokwi mengirim suhu lingkungan sekitar meja praktikum LPG melalui MQTT over TLS ke EMQX Cloud Serverless. Telegraf menerima pesan, InfluxDB 2.x menyimpan riwayat, dan Grafana menampilkan suhu terbaru serta grafik historis.

```text
DS18B20 → ESP32/Wokwi → MQTT/TLS :8883 → EMQX Cloud Serverless
                                            ↓ MQTT/TLS :8883
                                         Telegraf
                                            ↓ HTTP jaringan Docker
                                         InfluxDB 2.x → Grafana
```

Sensor menggambarkan lingkungan sekitar meja, bukan nyala api langsung. Panduan ini menyiapkan demonstrasi simulasi, bukan sistem keselamatan laboratorium.

- [Petunjuk jalur suhu](docs/jalur-suhu.md)
- [Rencana dan batas verifikasi tiket 01](docs/verifikasi-tiket-01.md)
- [Tiket sumber](.scratch/monitoring-lab-kimia/issues/01-end-to-end-suhu.md)

Gas, alarm LED/buzzer, penanda data terlambat, dan eksperimen keamanan lanjutan mengikuti tiket berikutnya. Lihat hasil verifikasi aktual sebelum menganggap jalur cloud sudah berhasil.
