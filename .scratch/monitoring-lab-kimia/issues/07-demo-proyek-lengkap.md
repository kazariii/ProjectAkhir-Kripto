# 07: Demo proyek lengkap dapat diulang

**What to build:** Jadikan sistem satu proyek utuh yang dapat dijalankan dan dipresentasikan kembali: pemantauan satu meja praktikum LPG pada lab kimia dasar, alarm lokal, riwayat di Grafana, pemulihan koneksi, dan bukti kerahasiaan, integritas, serta autentikasi. Panduan memakai hasil aktual dari tiket sebelumnya.

**Blocked by:** 04: Data terlambat ditandai dan koneksi dapat pulih — selesai; 05: Perangkat dan akses topik yang tidak sah ditolak — selesai; 06: Kerahasiaan dan integritas komunikasi dapat didemonstrasikan — selesai. Tidak lagi menghambat.

**Status:** done

- [x] Panduan menjelaskan prasyarat, pembuatan konfigurasi lokal, pengisian kredensial oleh pemilik akun, menjalankan layanan Docker dan Wokwi, serta membuka Grafana tanpa membutuhkan riwayat chat ini.
- [x] Petunjuk menjelaskan bahwa MQTT/TLS adalah protokol komunikasi sensor. Telegraf, InfluxDB 2.x, dan Grafana adalah jalur penerimaan, penyimpanan, dan visualisasi yang sudah disepakati.
- [x] Urutan demo mencakup kondisi normal, gas tinggi saja, suhu tinggi saja, kedua alarm aktif, pengembalian kondisi normal, gangguan koneksi, serta pemulihannya.
- [x] Bukti memperlihatkan nilai sensor, LED/buzzer, status dashboard, grafik historis, penanda data terlambat, dan riwayat yang tetap tersedia setelah layanan dimulai ulang.
- [x] Demonstrasi autentikasi/otorisasi dan perbandingan plaintext/TLS dapat diulang; uji perubahan ciphertext dipresentasikan sebagai pengujian TLS terpisah dengan kontrol positifnya.
- [x] Ringkasan pengujian mencatat hasil aktual, bukti pendukung, langkah reproduksi, dan keterbatasan. Bagian yang belum berhasil tidak ditulis sebagai lulus.
- [x] Penjelasan menyatakan ambang suhu 40 derajat Celsius adalah ambang demo, pembacaan MQ2 adalah level relatif, dan sensor tidak mengidentifikasi orang atau menjamin keselamatan laboratorium nyata.
- [x] Penjelasan membedakan confidentiality, integrity, dan authentication yang menjadi fokus tugas. Penanda data terlambat serta reconnect dijelaskan sebagai dukungan availability yang terbatas.
- [x] Berkas yang disiapkan untuk Git tidak memuat kredensial atau rahasia; konfigurasi contoh dan petunjuk penggantinya tersedia. Push ke GitHub dilakukan sendiri oleh pengguna.
- [x] Satu pengulangan demo lengkap dari kondisi layanan dimulai telah dilakukan, dan panduan sesuai dengan cara menjalankan yang benar-benar berhasil.

## Comments

Penyelesaian 10 November 2026: [panduan demo terpadu](../../../docs/demo-proyek.md) ditautkan dari README dan panduan rangkaian. Memakai implementasi tiket 01–06 yang sudah ada, ditambah perintah takeover MQTT berdurasi terbatas untuk pengulangan gangguan; tidak menambah layanan/dependensi atau mengubah firmware/izin broker.

Pengulangan nyata dimulai dengan simulator berhenti, Compose down/up tanpa menghapus volume, kemudian Play Wokwi. Normal, gas saja, suhu saja, keduanya, gas pulih, dan Normal berhasil sampai Grafana. Gangguan 120 detik (75 takeover, tanpa publish) menghasilkan jeda penerimaan 133,633597 detik serta label terlambat sementara gas/suhu lokal tetap mengaktifkan alarm; reconnect pulih tanpa restart ESP32. Sesudah ketiga layanan restart, seluruh 904 titik sebelumnya identik dan snapshot berikutnya memuat 922 titik termasuk penerimaan baru. Ketujuh kueri panel berhasil di setiap tahap. Uji akses diulang: 17 pemeriksaan lulus; eksperimen TLS lokal terpisah: 5 tahap lulus dengan kontrol sebelum/sesudah dan alert bad record MAC. Rahasia lokal tetap diabaikan/tidak dilacak; kandidat berkas ditinjau. Tidak melakukan push.

[Verifikasi, bukti dan keterbatasan](../../../docs/verifikasi-tiket-07.md) serta [ringkasan JSON](../../../docs/evidence/ticket-07/summary.json) tersedia. Capture utama tiket 06 dipakai kembali dan diperiksa ulang, bukan diklaim capture baru. Konfigurasi akun pemilik dipakai kembali; tidak mengklaim instalasi akun baru, sensor fisik, atau rekaman akustik buzzer. Seluruh 10 acceptance criteria terpenuhi pada batas tersebut; status `done` mengikuti `docs/agents/triage-labels.md`.
