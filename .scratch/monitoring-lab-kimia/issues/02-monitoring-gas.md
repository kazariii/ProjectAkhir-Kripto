# 02: Level gas tampil bersama suhu

**What to build:** Tambahkan MQ2 pada ESP32 yang sama agar indikasi gas di meja praktikum lab kimia dapat dipantau bersama suhu. Nilai relatif gas melewati jalur MQTT/TLS, Telegraf, InfluxDB, dan Grafana yang sudah berjalan, sehingga pengunjung dashboard dapat membandingkan kedua pengukuran dari waktu ke waktu.

**Blocked by:** 01: Suhu dari Wokwi tersimpan dan tampil di Grafana.

**Status:** ready-for-agent

- [ ] Komponen MQ2 Wokwi terpasang pada ESP32 yang sama dengan DS18B20. Pemilihan pin dan penyesuaian level tegangan mempertimbangkan batas masukan ESP32.
- [ ] ESP32 membaca keluaran analog MQ2 sebagai `gas_raw` dan keluaran digitalnya sebagai indikasi ambang gas. Keluaran digital aktif LOW ditafsirkan dengan benar.
- [ ] `gas_raw` ditambahkan sebagai angka pada pesan perangkat yang sama, dengan identitas dan timestamp penyimpanan yang konsisten dengan pengukuran suhu.
- [ ] Pembacaan gas tampil sebagai ADC/level relatif. Dashboard dan penjelasan tidak menyebutnya sebagai konsentrasi LPG terkalibrasi atau ppm hasil pengukuran nyata.
- [ ] Grafana memiliki nilai gas terkini dan grafik historis gas terpisah dari grafik suhu, dengan nama serta satuan yang jelas.
- [ ] Perubahan gas di Wokwi terlihat pada data tersimpan dan dashboard tanpa menghentikan pembaruan suhu setiap 2 detik saat terhubung.
- [ ] Pengujian mencakup gas yang meningkat dengan suhu tetap dan suhu yang meningkat dengan gas tetap; riwayat kedua sensor tetap tersedia setelah layanan dimulai ulang.
