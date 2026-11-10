# 05: Perangkat dan akses topik yang tidak sah ditolak

**What to build:** Sediakan demonstrasi yang dapat diulang untuk membuktikan autentikasi perangkat, verifikasi identitas server, dan pembatasan izin topik pada jalur MQTT proyek. Uji menggunakan lingkungan dan akun proyek sendiri dengan data pengenal khusus agar hasilnya dapat dibedakan dari pengukuran biasa.

**Blocked by:** 01: Suhu dari Wokwi tersimpan dan tampil di Grafana.

**Status:** ready-for-agent

- [ ] Kontrol positif menunjukkan ESP32 dapat mengirim pada topik yang diizinkan dan Telegraf dapat membacanya sampai pengukuran tampil di Grafana.
- [ ] Klien dengan username atau password salah ditolak; ada bukti penolakan dari klien atau layanan yang tersedia, dan pesan uji tidak muncul sebagai pengukuran baru.
- [ ] Akun pengirim tidak dapat berlangganan atau mengakses topik di luar izinnya; akun penerima tidak dapat menerbitkan pesan atau membaca topik di luar izinnya.
- [ ] Aturan fallback secara eksplisit menolak operasi yang tidak cocok dengan izin, sehingga keberhasilan satu aturan allow tidak meninggalkan akses lain terbuka.
- [ ] Klien yang tidak mempercayai CA server gagal membentuk koneksi TLS. Pengujian tidak menonaktifkan verifikasi untuk membuat koneksi tersebut berhasil.
- [ ] Kontrol positif diulang setelah uji negatif untuk menunjukkan bahwa sistem sah masih berfungsi; penolakan tidak disimpulkan hanya dari broker yang kebetulan tidak tersedia.
- [ ] Bukti memisahkan autentikasi kredensial, otorisasi topik, dan verifikasi sertifikat server. Tidak ada klaim bahwa konfigurasi username/password merupakan mutual TLS.
- [ ] Sandi, token, dan private key tidak tercantum pada berkas yang akan di-push, tangkapan layar, atau laporan; petunjuk uji menggunakan nama variabel atau contoh pengganti.
