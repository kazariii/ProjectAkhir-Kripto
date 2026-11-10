# 06: Kerahasiaan dan integritas komunikasi dapat didemonstrasikan

**What to build:** Sediakan dua pengujian terkontrol beserta bukti aktual: perbandingan keterbacaan payload tanpa TLS dan dengan TLS, serta penolakan ciphertext TLS yang dirusak selama perjalanan. Pengujian memakai data serta kredensial khusus demo dan tidak mengubah layanan broker yang sedang dipakai jalur sensor utama.

**Blocked by:** 01: Suhu dari Wokwi tersimpan dan tampil di Grafana.

**Status:** done

- [x] Tangkapan komunikasi utama menunjukkan MQTT berjalan melalui TLS. Pembanding tanpa TLS dijalankan pada broker uji milik sendiri menggunakan pesan penanda yang diketahui dan kredensial khusus demo.
- [x] Payload penanda dapat ditemukan sebagai plaintext pada tangkapan tanpa TLS, sedangkan isi pengukuran tidak tampak sebagai plaintext pada tangkapan TLS yang tidak diberi kunci dekripsi.
- [x] Penjelasan kerahasiaan membedakan isi pesan dari metadata jaringan yang masih terlihat. Kedua koneksi ESP32-broker dan Telegraf-broker diamankan, sementara broker tetap menjadi titik tepercaya yang bisa membaca pesan.
- [x] Uji integritas memakai klien uji, relay TCP yang hanya meneruskan byte, dan broker MQTT/TLS lokal terisolasi. Sertifikat server tetap diverifikasi oleh klien.
- [x] Kontrol awal berhasil melakukan koneksi MQTT, mengirim pesan QoS 1 yang unik dan tidak retained, menerima PUBACK, serta memperlihatkan pesan itu pada subscriber independen.
- [x] Pada koneksi baru, relay baru diaktifkan untuk merusak ciphertext setelah klien menerima MQTT CONNACK. Relay mengubah satu bit dalam badan record TLS tanpa mengubah header atau panjang record; encrypted handshake tidak dipakai sebagai sasaran uji.
- [x] Saat pesan uji berikutnya dikirim dengan retry dan reconnect otomatis dinonaktifkan, perubahan tersebut menghasilkan bukti kegagalan verifikasi TLS atau penghentian koneksi oleh implementasi TLS, tanpa PUBACK dan tanpa penerimaan pesan penanda pada subscriber.
- [x] Kontrol normal diulang sesudahnya. Log perubahan relay, hasil TLS aktual, dan hasil subscriber dicatat; ketiadaan pesan saja tidak dianggap bukti yang memadai.
- [x] Kesimpulan membatasi uji integritas pada deteksi perubahan ciphertext dalam koneksi TLS yang diuji. Uji ini tidak membuktikan kebenaran sensor, integritas data tersimpan, atau keamanan seluruh deployment EMQX.
- [x] Mengubah nilai sebelum pengiriman melalui koneksi TLS yang sah tidak dipakai sebagai bukti deteksi perubahan selama perjalanan.
- [x] Petunjuk menjalankan, tangkapan jaringan, dan ringkasan hasil yang dapat digunakan saat presentasi tersedia dengan kredensial disamarkan. Hasil yang belum dijalankan ditandai belum diverifikasi.

## Comments

10 November 2026: implementasi memakai probe MQTT tiket 05, broker Mosquitto disposable, serta relay TCP tanpa terminasi TLS. Run aktual `ticket06-8162f83ddc98` (20:55:04–20:55:55 WIB) lulus lima tahap: keterbacaan plaintext/TLS, kontrol awal, satu bit ciphertext rusak setelah CONNACK, dan kontrol akhir. Klien menerima `SSLV3_ALERT_BAD_RECORD_MAC` pada TLS 1.3; broker mencatat `decryption failed or bad record mac`. Header/ukuran tetap, tepat satu bit berubah, tidak ada PUBACK/penerimaan subscriber, kontrol sebelum/sesudah menerima PUBACK 0 serta payload identik. Tes fragmentasi/coalescing dan gate relay juga lulus.

Capture aktual Wokwi dan Telegraf memperlihatkan record TLS di kedua hop utama tanpa plaintext field pengukuran. Tidak ada perubahan konfigurasi atau layanan broker utama. Panduan reproduksi, hasil dan batas klaim ada di [docs/verifikasi-tiket-06.md](../../../docs/verifikasi-tiket-06.md); JSON, log relay/broker, dan PCAP untuk presentasi ada di [docs/evidence/ticket-06/](../../../docs/evidence/ticket-06/). CONNECT berkredensial demo dikeluarkan dari capture plaintext publik; bukti mentah berada di `evidence/local/` yang diabaikan Git. Seluruh 11 acceptance criteria lulus; status `done` mengikuti `docs/agents/triage-labels.md`. Tiket 06 tidak lagi menghambat tiket 07.
