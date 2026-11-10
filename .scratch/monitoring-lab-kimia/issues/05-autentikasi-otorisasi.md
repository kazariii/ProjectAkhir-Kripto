# 05: Perangkat dan akses topik yang tidak sah ditolak

**What to build:** Sediakan demonstrasi yang dapat diulang untuk membuktikan autentikasi perangkat, verifikasi identitas server, dan pembatasan izin topik pada jalur MQTT proyek. Uji menggunakan lingkungan dan akun proyek sendiri dengan data pengenal khusus agar hasilnya dapat dibedakan dari pengukuran biasa.

**Blocked by:** 01: Suhu dari Wokwi tersimpan dan tampil di Grafana.

**Status:** done

- [x] Kontrol positif menunjukkan ESP32 dapat mengirim pada topik yang diizinkan dan Telegraf dapat membacanya sampai pengukuran tampil di Grafana.
- [x] Klien dengan username atau password salah ditolak; ada bukti penolakan dari klien atau layanan yang tersedia, dan pesan uji tidak muncul sebagai pengukuran baru.
- [x] Akun pengirim tidak dapat berlangganan atau mengakses topik di luar izinnya; akun penerima tidak dapat menerbitkan pesan atau membaca topik di luar izinnya.
- [x] Aturan fallback secara eksplisit menolak operasi yang tidak cocok dengan izin, sehingga keberhasilan satu aturan allow tidak meninggalkan akses lain terbuka.
- [x] Klien yang tidak mempercayai CA server gagal membentuk koneksi TLS. Pengujian tidak menonaktifkan verifikasi untuk membuat koneksi tersebut berhasil.
- [x] Kontrol positif diulang setelah uji negatif untuk menunjukkan bahwa sistem sah masih berfungsi; penolakan tidak disimpulkan hanya dari broker yang kebetulan tidak tersedia.
- [x] Bukti memisahkan autentikasi kredensial, otorisasi topik, dan verifikasi sertifikat server. Tidak ada klaim bahwa konfigurasi username/password merupakan mutual TLS.
- [x] Sandi, token, dan private key tidak tercantum pada berkas yang akan di-push, tangkapan layar, atau laporan; petunjuk uji menggunakan nama variabel atau contoh pengganti.

## Comments

10 November 2026: jalur dan aturan tiket 01 dipakai kembali tanpa mengubah layanan, firmware, atau izin broker. `tests/check_mqtt_access.py` menyediakan demonstrasi berulang dengan probe MQTT 5 tanpa dependensi tambahan, client ID baru, dan tag `ticket05-<acak>-<kasus>` untuk memisahkan pesan sintetis dari sensor.

Run aktual `ticket05-f2c780fb91d9` pada 20:31:06–20:31:48 WIB lulus 17 pemeriksaan: kontrol ESP32 serta pesan bertag sampai Grafana sebelum/sesudah, tiga penolakan autentikasi, delapan penolakan operasi topik (termasuk filter wildcard), penolakan CA tidak dipercaya, dan ketiadaan enam penanda negatif di InfluxDB. Konsol EMQX memperlihatkan dua allow username, Client ID tanpa aturan, serta fallback All Users deny `#` Publish & Subscribe. Serial Wokwi dan dashboard akhir juga diamati. Tidak ada klaim mutual TLS atau pengujian integritas ciphertext tiket 06.

Panduan, hasil, dan batas bukti: [docs/verifikasi-tiket-05.md](../../../docs/verifikasi-tiket-05.md). JSON hasil tanpa rahasia: [docs/evidence/ticket-05-access.json](../../../docs/evidence/ticket-05-access.json). Screenshot dan capture lokal di `evidence/local/ticket-05/` tetap diabaikan Git. Semua delapan acceptance criteria lulus; status `done` mengikuti `docs/agents/triage-labels.md`.
