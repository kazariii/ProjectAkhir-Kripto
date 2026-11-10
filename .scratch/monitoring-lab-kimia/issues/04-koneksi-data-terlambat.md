# 04: Data terlambat ditandai dan koneksi dapat pulih

**What to build:** Petugas dapat membedakan data terkini dari data yang sudah lama ketika jaringan terputus. ESP32 tetap membaca sensor dan menjalankan alarm lokal selama mencoba tersambung kembali; setelah koneksi pulih, pengukuran baru kembali masuk ke InfluxDB dan Grafana.

**Blocked by:** 03: Peringatan gas dan suhu bekerja secara mandiri — selesai; tidak lagi menghambat.

**Status:** done

- [x] Dashboard menampilkan waktu pengukuran terakhir yang diterima dan menandai data terlambat ketika tidak ada pengukuran baru selama lebih dari 10 detik.
- [x] Dashboard yang belum pernah menerima data menampilkan keadaan belum ada data. Nilai lama yang normal tidak disajikan sebagai kepastian bahwa kondisi saat ini normal ketika data terlambat.
- [x] Percobaan koneksi ulang Wi-Fi/MQTT tidak menghentikan pembacaan sensor dan pemeriksaan alarm lokal secara berkepanjangan.
- [x] Saat koneksi MQTT diputus dalam pengujian, menaikkan gas atau suhu di Wokwi tetap mengaktifkan LED dan buzzer sesuai aturan alarm.
- [x] Setelah koneksi dipulihkan, ESP32 kembali mengirim melalui TLS dengan verifikasi server dan kredensial yang sama; data baru terlihat di penyimpanan dan dashboard.
- [x] Koneksi ulang tidak menghapus riwayat. Rentang tanpa pengukuran tetap dapat dikenali dan tidak diisi dengan nilai normal buatan.
- [x] Pengujian memuat bukti sebelum putus, saat data terlambat dan alarm lokal bekerja, serta setelah pengiriman pulih. Penyebab putus dan keterbatasan simulator dicatat bila memengaruhi hasil.

## Comments

Penyelesaian 10 November 2026: tugas jaringan FreeRTOS dipisahkan dari loop sensor/alarm, dengan antrean satu sampel yang tidak menunggu, retry Wi-Fi/MQTT, penghapusan sampel offline/kedaluwarsa dan TLS terverifikasi yang sama. Grafana menambah waktu penerimaan terakhir, penanda >10 detik, keadaan bucket kosong dan gap grafik; keadaan saat ini tidak mengikuti pemilih rentang historis. Tidak ada dependensi/layanan produksi baru atau penghapusan volume.

Tes loop host (termasuk koneksi tertahan 20 detik), C++ telemetry, build ESP32 dan stack MQTT/TLS terisolasi hingga ketujuh kueri Grafana lulus. Demo langsung Wokwi/EMQX juga lulus: sesi MQTT diputus dengan takeover client ID, gas saja dan suhu saja tetap mengaktifkan LED/buzzer, dashboard menjadi terlambat, lalu pengiriman pulih otomatis tanpa restart ESP32. Penerimaan berhenti pada 20:17:01 WIB dan pulih pada 20:18:45 WIB (jeda 104,524247 detik). Seluruh 217 titik capture saat putus dipertahankan persis dan tidak ada backfill normal/sampel offline. Akhir demo kembali Normal. Gangguan gateway awal, kecepatan simulator dan batas bukti buzzer dicatat.

Bukti, hasil aktual dan prosedur: [docs/verifikasi-tiket-04.md](../../../docs/verifikasi-tiket-04.md). Log/screenshot/CSV disimpan lokal di `evidence/local/ticket-04/` yang diabaikan Git. Seluruh acceptance criteria terpenuhi; status `done`.
