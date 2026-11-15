# Verifikasi PQC tiket 02: Wokwi ke broker privat

Tanggal: 14 November 2026. [Tiket](../.scratch/mqtt-pqc/issues/02-koneksi-broker-privat.md), [panduan reproduksi](../tools/mqtt/README.md), dan [ringkasan aktual](evidence/pqc-ticket-02/summary.json).

## Hasil

**Lulus untuk konektivitas diagnostik dua arah.** Pengguna mengaktifkan lisensi Wokwi VS Code, menjalankan firmware yang disiapkan, dan memberikan log Serial Monitor. Agen mencocokkan log itu dengan journal penerima serta catatan koneksi broker di LXC; tidak mengklaim pengamatan UI simulator secara langsung.

| Bukti | Hasil |
|---|---|
| Transport | MQTT biasa melalui TCP port 1883, tanpa TLS |
| Endpoint broker | `10.34.211.141:1883`, binding hanya pada IP privat LXC |
| Alamat ESP32 pada Private Gateway | `10.13.37.2` |
| Run pengguna | `3981f73517679858691afa4b7b65009e` |
| Client broker yang cocok | `esp32-diag-3981f7351767`, akun perangkat diagnostik |
| Catatan penerima | `request_received` dan `reply_queued`, dengan run ID yang sama |
| Waktu request diterima LXC | `2026-11-14T14:04:47.894109Z` |
| Waktu balasan diantrikan LXC | `2026-11-14T14:04:47.894186Z` |
| Waktu bolak-balik yang dilaporkan simulator | **110 ms**, untuk marker diagnostik tanpa kriptografi aplikasi |

Log pengguna berisi dua blok identik. Teks tersebut dipertahankan sebagai transkripsi lokal, kedua blok dibandingkan byte demi byte, lalu satu salinan lengkap dipakai untuk verifikasi. Ini **satu bukti run**, bukan dua pengujian independen. [Catatan normalisasi](evidence/pqc-ticket-02/serial-normalization.json) merekam hash transkripsi dan capture yang diperiksa; [log satu salinan](evidence/pqc-ticket-02/esp32-serial.txt) tersedia. Verifier tetap menolak capture gabungan; penghilangan duplikat identik dilakukan terpisah dan dicatat, tanpa melonggarkan pemeriksaan.

## Implementasi dan batas akses

- Mosquitto **2.0.22** dikunci pada digest `sha256:81a6193ae693942a3231cd3ac52875b02b7e3a19da671b2fb4b55cc874c5b279`, project Compose terpisah `lab-kimia-mqtt-pqc`, container read-only dengan UID/GID `1883:1883`.
- Akun perangkat hanya menulis request dan membaca reply; akun penerima memiliki arah sebaliknya. Semua topik lain tidak diberi izin. Password acak dan header firmware privat diabaikan Git.
- Penerima Python memakai Paho MQTT **2.1.0**, dijalankan sebagai systemd DynamicUser dengan LoadCredential. Koneksi yang putus ditangani supervisor dengan proses baru dan subscribe ulang.
- Extension Wokwi VS Code **4.1.0** dipasang dari Marketplace resmi. Trust folder dan aktivasi lisensi dilakukan pengguna. Simulator memakai konfigurasi khusus satu ESP32; firmware monitoring utama tidak diganti.
- Firmware environment `mqtt-diagnostic` memakai PubSubClient **2.8**, RAM statis **44.904 byte** dan flash **747.109 byte**. Image lengkap yang diberikan memiliki SHA-256 `1065a1e8579762b78bd7196e8d7dc5bd8b484dc9fb922529338bfada95777c5b`.

## Kontrol yang diverifikasi

1. TCP dari laptop ke port 1883 LXC berhasil.
2. Native client perangkat memperoleh reply yang cocok dengan run ID-nya melalui penerima yang sama.
3. Publish perangkat ke arah reply dan topik telemetri di luar scope ditolak dengan PUBACK MQTT 5 **135**.
4. Publish penerima ke arah request perangkat ditolak dengan PUBACK **135**.
5. Password salah dan anonymous CONNECT ditolak dengan CONNACK **135**.
6. Akun perangkat tidak menerima pesan request yang tidak berhak dibacanya. Mosquitto memberikan SUBACK **0** untuk filter tersebut; ini dicatat sebagai subscribe diterima dengan delivery tetap difilter oleh ACL, bukan diklaim sebagai penolakan subscribe.
7. Setelah restart broker diagnostik, penerima pulih dan kontrol request/reply serta ACL kembali lulus.
8. [Tiga tes penjagaan bukti](evidence/pqc-ticket-02/capture-validation.json) menolak native run yang disamarkan sebagai log Wokwi, log tidak lengkap, dan gabungan beberapa run. Verifikasi pengguna membutuhkan koneksi broker ber-ID ESP32 yang cocok, bukan hanya journal echo native.
9. Pengujian regresi loop sensor/alarm dan build default `esp32dev` lulus. Grafana melaporkan database `ok`, InfluxDB `pass`, dan ketiga container monitoring lama tetap berjalan setelah penambahan broker.

Tidak ada perubahan firewall atau forwarding port publik. Pengujian membuktikan binding pada IP privat dan jangkauan melalui jaringan laptop; tidak mengklaim audit konfigurasi NAT/router di luar LXC. Autostart broker/penerima dikonfigurasi, tetapi reboot LXC aktual tidak dilakukan pada tiket ini.

## Batas tiket dan kelanjutan

Data yang dipertukarkan adalah marker sintetis. Jalur ini belum memakai sesi ML-KEM/FN-DSA atau enkripsi payload ChaCha20-Poly1305, dan tidak menulis data ke InfluxDB. Autentikasi broker bukan pengganti autentikasi aplikasi yang direncanakan. Kredensial MQTT biasa dapat terlihat pada jaringan privat; batas ini tetap menjadi bagian penjelasan sistem tanpa TLS.

Tiket **01 dan 02 selesai**, sehingga tiket **03: sesi terautentikasi** sudah dapat dimulai. Perubahan repository masih lokal, belum di-commit atau dipush. Broker dan penerima diagnostik berjalan di LXC pada deployment terpisah; migrasi penerimaan sensor produksi tetap berada pada tiket berikutnya.
