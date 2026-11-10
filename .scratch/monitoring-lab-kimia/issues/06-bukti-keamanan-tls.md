# 06: Kerahasiaan dan integritas komunikasi dapat didemonstrasikan

**What to build:** Sediakan dua pengujian terkontrol beserta bukti aktual: perbandingan keterbacaan payload tanpa TLS dan dengan TLS, serta penolakan ciphertext TLS yang dirusak selama perjalanan. Pengujian memakai data serta kredensial khusus demo dan tidak mengubah layanan broker yang sedang dipakai jalur sensor utama.

**Blocked by:** 01: Suhu dari Wokwi tersimpan dan tampil di Grafana.

**Status:** ready-for-agent

- [ ] Tangkapan komunikasi utama menunjukkan MQTT berjalan melalui TLS. Pembanding tanpa TLS dijalankan pada broker uji milik sendiri menggunakan pesan penanda yang diketahui dan kredensial khusus demo.
- [ ] Payload penanda dapat ditemukan sebagai plaintext pada tangkapan tanpa TLS, sedangkan isi pengukuran tidak tampak sebagai plaintext pada tangkapan TLS yang tidak diberi kunci dekripsi.
- [ ] Penjelasan kerahasiaan membedakan isi pesan dari metadata jaringan yang masih terlihat. Kedua koneksi ESP32-broker dan Telegraf-broker diamankan, sementara broker tetap menjadi titik tepercaya yang bisa membaca pesan.
- [ ] Uji integritas memakai klien uji, relay TCP yang hanya meneruskan byte, dan broker MQTT/TLS lokal terisolasi. Sertifikat server tetap diverifikasi oleh klien.
- [ ] Kontrol awal berhasil melakukan koneksi MQTT, mengirim pesan QoS 1 yang unik dan tidak retained, menerima PUBACK, serta memperlihatkan pesan itu pada subscriber independen.
- [ ] Pada koneksi baru, relay baru diaktifkan untuk merusak ciphertext setelah klien menerima MQTT CONNACK. Relay mengubah satu bit dalam badan record TLS tanpa mengubah header atau panjang record; encrypted handshake tidak dipakai sebagai sasaran uji.
- [ ] Saat pesan uji berikutnya dikirim dengan retry dan reconnect otomatis dinonaktifkan, perubahan tersebut menghasilkan bukti kegagalan verifikasi TLS atau penghentian koneksi oleh implementasi TLS, tanpa PUBACK dan tanpa penerimaan pesan penanda pada subscriber.
- [ ] Kontrol normal diulang sesudahnya. Log perubahan relay, hasil TLS aktual, dan hasil subscriber dicatat; ketiadaan pesan saja tidak dianggap bukti yang memadai.
- [ ] Kesimpulan membatasi uji integritas pada deteksi perubahan ciphertext dalam koneksi TLS yang diuji. Uji ini tidak membuktikan kebenaran sensor, integritas data tersimpan, atau keamanan seluruh deployment EMQX.
- [ ] Mengubah nilai sebelum pengiriman melalui koneksi TLS yang sah tidak dipakai sebagai bukti deteksi perubahan selama perjalanan.
- [ ] Petunjuk menjalankan, tangkapan jaringan, dan ringkasan hasil yang dapat digunakan saat presentasi tersedia dengan kredensial disamarkan. Hasil yang belum dijalankan ditandai belum diverifikasi.
