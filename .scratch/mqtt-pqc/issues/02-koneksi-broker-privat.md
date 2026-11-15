# 02: Hubungkan Wokwi ke broker privat

**What to build:** ESP32 di Wokwi VS Code melalui Private Gateway dapat mengirim pesan diagnostik ke Mosquitto privat di LXC dan menerima balasan yang memiliki pengenal run sama. Broker membatasi akun dan arah akses topik. Ini membuktikan konektivitas sebelum integrasi sesi kriptografi.

**Blocked by:** None (can start immediately).

**Status:** done

- [x] Mosquitto versi/digest terkunci berjalan di LXC pada MQTT TCP port 1883 yang dipublikasikan hanya pada IP privat LXC.
- [x] Akun perangkat dan penerima terpisah; anonymous/password salah ditolak dan publish di luar topik/arah yang diizinkan ditolak.
- [x] Penerima LXC membalas pesan diagnostik sintetis dengan pengenal run yang sama, tanpa menulis data ke InfluxDB.
- [x] Build diagnostik ESP32 dan konfigurasi Wokwi VS Code siap dijalankan dengan Private Gateway; rahasia tidak masuk Git.
- [x] Pertukaran dua arah benar-benar dijalankan dari Wokwi VS Code; log ESP32 cocok dengan catatan penerima LXC dan tidak diklaim lulus dari tes native saja.
- [x] Jalur laptop ke port 1883, kebutuhan lisensi simulator, hasil kontrol positif/negatif, dan langkah reproduksi terdokumentasi.
- [x] Firmware sensor dan layanan monitoring yang ada tetap berfungsi; tidak ada migrasi data atau perubahan jalur produksi pada tiket ini.

## Comments

Selesai 14 November 2026. [Verifikasi dan batas klaim](../../../docs/verifikasi-pqc-tiket-02.md), [ringkasan aktual](../../../docs/evidence/pqc-ticket-02/summary.json), dan [panduan reproduksi](../../../tools/mqtt/README.md).

Pengguna mengonfirmasi aktivasi lisensi VS Code dan memberikan log run `3981f73517679858691afa4b7b65009e`. Satu salinan dari dua blok teks identik diperiksa; duplikasi tidak dihitung sebagai run kedua. LXC memiliki event request/reply yang sama dan broker menerima client `esp32-diag-3981f7351767` sebagai akun perangkat. Alamat simulator `10.13.37.2`, MQTT port 1883 tanpa TLS, RTT diagnostik 110 ms menurut simulator. Bukti runtime berasal dari log pengguna, dengan korelasi server yang diperiksa agen.

Kontrol native, penolakan akun/publish di luar izin, kontrol setelah restart broker, serta tiga tes penolakan bukti yang tidak memenuhi syarat lulus. Build diagnostik memakai RAM statis 44.904 byte dan flash 747.109 byte. Regresi loop sensor dan build default lulus; Grafana/InfluxDB dan container monitoring lama tetap sehat. Rahasia/artefak firmware diabaikan Git. Kode belum di-commit atau dipush.

Tiket 03 tidak lagi diblokir oleh 01 atau 02. Integrasi kriptografi aplikasi dan penyimpanan telemetri belum dikerjakan pada tiket ini.
