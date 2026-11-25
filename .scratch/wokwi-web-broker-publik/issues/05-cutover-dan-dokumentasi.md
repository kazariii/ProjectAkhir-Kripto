# 05: Cutover ke broker publik, dokumentasi, dan revisi tes ACL

**What to build:** Broker publik menjadi jalur default demo. Panduan demo memakai Wokwi web. Dokumen yang mengklaim login/ACL broker direvisi agar sesuai jalur publik. Tes ACL ditandai khusus jalur privat. Prosedur rollback ke Mosquitto tertulis dan diuji. Mosquitto tetap hidup sebagai cadangan.

**Blocked by:** 03 Telemetri PQC end-to-end lewat broker.emqx.io dari Wokwi web; 04 Ketahanan di broker publik

**Status:** ready-for-human

- [x] Default build dan dokumen operasi menunjuk jalur publik
- [x] Tidak ada dokumen aktif yang mengklaim login/ACL melindungi jalur publik
- [x] Panduan demo menyebut syarat jaringan untuk Wokwi web (hotspot jika jaringan kampus memblokir) dan cara mengenalinya dari `MQTT_DIAG_WIFI_STATUS` yang berhenti di 0
- [x] Rollback ke jalur privat diuji dan menghasilkan sesi native yang lulus
- [x] Spike tiket 01 dibersihkan (unit sementara dihentikan)
- [ ] Uji coba akhir oleh pengguna mengikuti panduan demo baru

## Comments

Membutuhkan langkah manusia: uji coba akhir mengikuti panduan.

**Bagian agen selesai, 25 November 2026.**

- Default build `firmware/platformio.ini` sekarang `pqc-telemetry-public`, dan `firmware/wokwi.toml` menunjuk `.pio/build/pqc-telemetry-public/`. Kedua env (`pqc-telemetry-public` default dan `pqc-telemetry` eksplisit) berhasil dibangun di LXC. Collector bukti lama `tools/deploy/collect_evidence.py` dan `tools/demo/collect_evidence.py` (tiket 06/07) masih memeriksa default lama, jadi keduanya hanya berlaku untuk state saat itu dan tidak dijalankan ulang.
- Panduan demo:
  - Panduan baru `docs/demo-proyek.md` untuk Wokwi web. Isinya syarat jaringan (hotspot untuk Wokwi, jaringan kampus untuk Grafana), cara mengenali blokir lewat `TELEMETRY_RUN` yang tidak muncul atau `MQTT_DIAG_WIFI_STATUS` yang berhenti di 0, slider MQ2 ke kiri, larangan Pause, empat keadaan alarm, `verify_capture --public`, build ulang bin gabungan, dan rollback.
  - Panduan lama dipindah ke `docs/demo-proyek-privat.md` dan diberi label jalur cadangan/rollback. Tautan di dokumen verifikasi lama diarahkan ke berkas tersebut.
- Klaim login/ACL:
  - README, `docs/operasi-pqc.md`, dan `docs/protokol-sesi-pqc.md` menyatakan broker publik tanpa login/ACL. Klaim login/ACL dibatasi ke jalur privat.
  - `tools/mqtt/README.md` dan `tools/session/README.md` diberi catatan khusus jalur privat.
  - Tes akun/ACL (`tools/mqtt/diagnostic.py check`, `tools/telemetry/check_security.py`) ditandai khusus jalur privat di docstring.
- Rollback (bukti `docs/evidence/wokwi-web-05/`):
  - Receiver publik di-disable. Receiver privat tetap aktif, dan sesi native lewat Mosquitto privat lulus dengan `encrypted_ack_verified:true`.
  - Receiver publik di-enable kembali, dan sesi native dengan identitas demo lewat `broker.emqx.io` lulus. Percobaan publik pertama gagal `MQTT CONNACK timeout` dari broker publik; percobaan ulang langsung lulus. Ini contoh risiko broker pihak ketiga tanpa SLA.
- Unit spike `lab-kimia-public-diag` dihentikan. Unit sementara `lab-kimia-public-attack` sudah selesai. Tidak ada unit `lab-kimia-public-*` yang tersisa.
- Regresi di LXC lulus: 113 checks native, 20 unit test, dan siklus sensor PQC. Receiver privat dan publik `active`, dan receiver publik `enabled`.
- Backup berkas LXC sebelum sinkronisasi: `/opt/lab-kimia-mqtt/evidence/local/backup-wokwi-web-05/`.

**Langkah manusia:** uji coba akhir mengikuti `docs/demo-proyek.md` bagian 2, 4, 5, dan 6 tanpa bantuan agen.
