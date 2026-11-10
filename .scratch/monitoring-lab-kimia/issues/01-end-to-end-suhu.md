# 01: Suhu dari Wokwi tersimpan dan tampil di Grafana

**What to build:** Jalur pertama yang dapat didemonstrasikan untuk proyek "Simulasi Monitoring Gas dan Suhu Laboratorium Kimia Dasar Berbasis MQTT over TLS dengan Dashboard Grafana". Satu ESP32 di Wokwi membaca DS18B20 di sekitar satu meja praktikum dengan pembakar Bunsen berbahan bakar LPG. Perubahan suhu sampai ke Grafana melalui EMQX Cloud Serverless, Telegraf, dan InfluxDB. Pembacaan suhu menggambarkan lingkungan sekitar meja, bukan nyala api langsung.

**Blocked by:** None (can start immediately).

**Status:** ready-for-agent

- [ ] Rangkaian dan program Wokwi dapat dijalankan ulang, memakai satu ESP32 dan DS18B20, dengan pembacaan serta pengiriman setiap 2 detik saat terhubung.
- [ ] Broker memakai EMQX Cloud Serverless dengan batas pengeluaran nol; kebutuhan akun dan verifikasi pemilik dijelaskan tanpa menyimpan rahasia di dokumentasi.
- [ ] ESP32 mengirim ke topik `lab/kimia/meja01/telemetry`. Pesan JSON minimal memuat `device_id` dan `temperature_c`; nilai suhu memakai derajat Celsius dan identitas perangkat konsisten.
- [ ] ESP32 dan Telegraf sama-sama menggunakan MQTT melalui TLS serta memverifikasi CA dan identitas server. Konfigurasi tidak menonaktifkan verifikasi sertifikat.
- [ ] Kredensial terpisah membatasi ESP32 untuk mengirim pada topik tersebut dan Telegraf untuk membacanya. Akses anonim dan operasi yang tidak diizinkan ditolak melalui aturan fallback yang sesuai.
- [ ] Telegraf, InfluxDB 2.x, dan Grafana dapat dijalankan bersama melalui Docker dengan versi yang ditetapkan. Token, sandi, dan berkas lokal berisi rahasia dikecualikan dari Git.
- [ ] Telegraf menyimpan suhu sebagai angka dan `device_id` sebagai identitas seri; waktu penerimaan digunakan sebagai timestamp pengukuran agar tidak bergantung pada jam ESP32 yang belum tersinkronisasi.
- [ ] Grafana menampilkan suhu terbaru dan grafik historis dari InfluxDB. Perubahan suhu yang dilakukan di Wokwi dapat diamati pada dashboard selama layanan berjalan.
- [ ] Penyimpanan InfluxDB dan konfigurasi dashboard persisten; mulai ulang layanan mempertahankan data sebelumnya dan memungkinkan pengiriman baru berlanjut.
- [ ] Pembacaan DS18B20 yang tidak valid tidak disimpan sebagai suhu normal atau nilai Celsius palsu. Kegagalan pembacaan terlihat pada keluaran diagnosis.
- [ ] Petunjuk menjalankan jalur suhu beserta bukti hasil aktual tersedia. Jalur utama tetap memakai MQTT; koneksi internal Telegraf ke InfluxDB dan akses web dashboard bukan pengganti protokol sensor.
