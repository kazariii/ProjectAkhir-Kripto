# 04: Data terlambat ditandai dan koneksi dapat pulih

**What to build:** Petugas dapat membedakan data terkini dari data yang sudah lama ketika jaringan terputus. ESP32 tetap membaca sensor dan menjalankan alarm lokal selama mencoba tersambung kembali; setelah koneksi pulih, pengukuran baru kembali masuk ke InfluxDB dan Grafana.

**Blocked by:** 03: Peringatan gas dan suhu bekerja secara mandiri.

**Status:** ready-for-agent

- [ ] Dashboard menampilkan waktu pengukuran terakhir yang diterima dan menandai data terlambat ketika tidak ada pengukuran baru selama lebih dari 10 detik.
- [ ] Dashboard yang belum pernah menerima data menampilkan keadaan belum ada data. Nilai lama yang normal tidak disajikan sebagai kepastian bahwa kondisi saat ini normal ketika data terlambat.
- [ ] Percobaan koneksi ulang Wi-Fi/MQTT tidak menghentikan pembacaan sensor dan pemeriksaan alarm lokal secara berkepanjangan.
- [ ] Saat koneksi MQTT diputus dalam pengujian, menaikkan gas atau suhu di Wokwi tetap mengaktifkan LED dan buzzer sesuai aturan alarm.
- [ ] Setelah koneksi dipulihkan, ESP32 kembali mengirim melalui TLS dengan verifikasi server dan kredensial yang sama; data baru terlihat di penyimpanan dan dashboard.
- [ ] Koneksi ulang tidak menghapus riwayat. Rentang tanpa pengukuran tetap dapat dikenali dan tidak diisi dengan nilai normal buatan.
- [ ] Pengujian memuat bukti sebelum putus, saat data terlambat dan alarm lokal bekerja, serta setelah pengiriman pulih. Penyebab putus dan keterbatasan simulator dicatat bila memengaruhi hasil.
