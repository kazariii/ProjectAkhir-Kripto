# 07 — Panduan demo MQTT/PQC lengkap

**What to build:** Jadikan proyek hasil revisi siap dijalankan/dipresentasikan tanpa membaca chat: satu panduan utama berisi arsitektur, setup existing, urutan sensor/alarm, keamanan, gangguan/pemulihan, restart/persistensi, troubleshooting, pengambilan bukti dan penutupan. Bedakan bukti Wokwi, kontrol native, dan pemeriksaan yang baru dilakukan.

**Blocked by:** 06 — Migrasi jalur utama di LXC (`done`).

**Status:** done

## Acceptance criteria

- [x] Panduan utama dan README memakai MQTT TCP/1883 tanpa TLS; panduan lama diarsipkan dengan tautan tetap jelas.
- [x] Langkah LXC/laptop, folder/file, perintah, expected output dan empat keadaan alarm bisa diikuti berurutan.
- [x] Peran ML-KEM, ChaCha20-Poly1305 dan prospective FN-DSA dijelaskan, termasuk nonce/replay, pin dan batas kerahasiaan metadata/password MQTT.
- [x] Demo mencakup gangguan/pemulihan, stale, restart/persistensi, serta keamanan dengan kontrol valid dan negatif; tidak menjalankan dua perangkat/ingress bersamaan.
- [x] Pengulangan uji/capture dapat memakai lokasi hasil baru tanpa menimpa bukti tiket sebelumnya.
- [x] Perintah dan tautan diperiksa; state LXC dan kontrol keamanan diperiksa ulang. Bukti Wokwi/skenario gangguan terdahulu yang dipakai ulang disebutkan secara eksplisit.
- [x] Bukti publik disanitasi, private artifact tetap ignored, dan tidak ada commit/push.

## Comments

Tiket ini melengkapi panduan, bukan mengganti algoritma atau firmware yang sudah lulus pada tiket 06. Reboot seluruh LXC, uji fisik/akustik dan audit kriptografi tidak menjadi klaim panduan. Arsip TLS tetap tersedia hanya untuk histori/rollback manual.

15 November 2026: panduan utama diganti untuk MQTT/PQC, arsip TLS dipertahankan, README dan operasi diperbarui. CLI output baru dan mode fault diverifikasi; folder hasil existing ditolak tanpa perubahan report/restart receiver. Uji native baru: 21 kasus, 8 titik cocok; C++ 113, Python 12, loop sensor/startup gagal lulus ulang. State LXC dan semua titik ACK dari capture Wokwi tiket 05/06 dicocokkan ulang dengan Influx/Grafana; tidak ada run simulator baru pada tiket 07. Native/historis dipisahkan dalam manifest. Dokumen/perintah/bukti disinkronkan ke LXC tanpa mengubah firmware/pin/algoritma.

[Panduan](../../../docs/demo-proyek.md), [verifikasi](../../../docs/verifikasi-pqc-tiket-07.md), [ringkasan](../../../docs/evidence/pqc-ticket-07/summary.json). Seluruh tiket revisi 01–07 selesai. Kode/bukti belum di-commit/dipush.
