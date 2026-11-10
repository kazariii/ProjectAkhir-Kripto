# 07: Demo proyek lengkap dapat diulang

**What to build:** Jadikan sistem satu proyek utuh yang dapat dijalankan dan dipresentasikan kembali: pemantauan satu meja praktikum LPG pada lab kimia dasar, alarm lokal, riwayat di Grafana, pemulihan koneksi, dan bukti kerahasiaan, integritas, serta autentikasi. Panduan memakai hasil aktual dari tiket sebelumnya.

**Blocked by:** 04: Data terlambat ditandai dan koneksi dapat pulih; 05: Perangkat dan akses topik yang tidak sah ditolak; 06: Kerahasiaan dan integritas komunikasi dapat didemonstrasikan.

**Status:** ready-for-agent

- [ ] Panduan menjelaskan prasyarat, pembuatan konfigurasi lokal, pengisian kredensial oleh pemilik akun, menjalankan layanan Docker dan Wokwi, serta membuka Grafana tanpa membutuhkan riwayat chat ini.
- [ ] Petunjuk menjelaskan bahwa MQTT/TLS adalah protokol komunikasi sensor. Telegraf, InfluxDB 2.x, dan Grafana adalah jalur penerimaan, penyimpanan, dan visualisasi yang sudah disepakati.
- [ ] Urutan demo mencakup kondisi normal, gas tinggi saja, suhu tinggi saja, kedua alarm aktif, pengembalian kondisi normal, gangguan koneksi, serta pemulihannya.
- [ ] Bukti memperlihatkan nilai sensor, LED/buzzer, status dashboard, grafik historis, penanda data terlambat, dan riwayat yang tetap tersedia setelah layanan dimulai ulang.
- [ ] Demonstrasi autentikasi/otorisasi dan perbandingan plaintext/TLS dapat diulang; uji perubahan ciphertext dipresentasikan sebagai pengujian TLS terpisah dengan kontrol positifnya.
- [ ] Ringkasan pengujian mencatat hasil aktual, bukti pendukung, langkah reproduksi, dan keterbatasan. Bagian yang belum berhasil tidak ditulis sebagai lulus.
- [ ] Penjelasan menyatakan ambang suhu 40 derajat Celsius adalah ambang demo, pembacaan MQ2 adalah level relatif, dan sensor tidak mengidentifikasi orang atau menjamin keselamatan laboratorium nyata.
- [ ] Penjelasan membedakan confidentiality, integrity, dan authentication yang menjadi fokus tugas. Penanda data terlambat serta reconnect dijelaskan sebagai dukungan availability yang terbatas.
- [ ] Berkas yang disiapkan untuk Git tidak memuat kredensial atau rahasia; konfigurasi contoh dan petunjuk penggantinya tersedia. Push ke GitHub dilakukan sendiri oleh pengguna.
- [ ] Satu pengulangan demo lengkap dari kondisi layanan dimulai telah dilakukan, dan panduan sesuai dengan cara menjalankan yang benar-benar berhasil.
