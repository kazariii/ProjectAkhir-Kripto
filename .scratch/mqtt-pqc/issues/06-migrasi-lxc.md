# 06 — Migrasi jalur utama di LXC

**What to build:** Jadikan sensor MQTT/PQC sebagai build dan simulator default, hentikan ingress Telegraf/TLS lama, dan tetapkan operasi receiver/broker LXC sebagai jalur monitoring utama. Pertahankan Grafana, InfluxDB, histori, kredensial dan pin yang sudah dipakai; sediakan rollback manual tanpa fallback otomatis.

**Blocked by:** 05 — Serangan dan pemulihan sesi PQC (`done`).

**Status:** done

## Acceptance criteria

- [x] Build default dan konfigurasi Wokwi utama memilih firmware sensor PQC; MQTT TCP/1883 tanpa TLS.
- [x] Telegraf lama berhenti dan tidak dapat kembali melalui Compose default/autostart; jalur utama tidak memerlukan konfigurasi cloud/CA lama.
- [x] Receiver terautentikasi dan broker privat aktif dengan restart/autostart; diagnostic proof tidak wajib berjalan.
- [x] Volume, bucket, dashboard/datasource UID, histori, private identity dan kredensial tetap sama.
- [x] Kontrol valid baru tersimpan sesudah cutover serta restart layanan; histori tetap terbaca.
- [x] Wokwi dari folder firmware utama mengirim data baru yang cocok dengan ACK, journal, Influx dan Grafana setelah cutover.
- [x] Dokumen operasi utama dan rollback sesuai keadaan aktual; bukti publik disanitasi dan tidak ada commit/push.

## Comments

Kode TLS/Telegraf disimpan sebagai arsip rollback yang harus dipilih eksplisit. Tidak ada pemilihan algoritma baru atau fallback ke plaintext. Panduan demo lengkap tetap tiket 07. Autostart diverifikasi dari konfigurasi/enable state dan restart layanan; reboot seluruh LXC tidak termasuk uji tanpa kebutuhan eksplisit.

15 November 2026: migrasi diterapkan dua kali secara idempoten dengan baseline private yang sama. Telegraf stateless dihapus, Compose utama hanya Influx/Grafana; konfigurasi ini lulus tanpa variabel MQTT cloud. Broker privat/receiver tetap aktif, diagnostic service disabled. Kredensial dan pin cocok byte demi byte dengan sebelum migrasi. Dua kontrol native sebelum/sesudah restart tersimpan dan terbaca, empat titik historis tiket 04/05 dipertahankan.

Build `pio run` tanpa `-e` memilih PQC dan lulus. Run Wokwi dari **folder firmware utama**, ID `3066a27ea869a9b9f201019f5537cf99`, menghasilkan **169 SENT/169 ACK**, tiga sesi dan empat keadaan alarm. Semua ACK cocok dengan Influx/Grafana. Capture selesai pada kondisi normal; reader, simulator dan listener port 4000 ditutup. Override rollback divalidasi tanpa mengaktifkan kembali cloud ingress lama.

[Verifikasi](../../../docs/verifikasi-pqc-tiket-06.md), [operasi](../../../docs/operasi-pqc.md), [ringkasan](../../../docs/evidence/pqc-ticket-06/summary.json). Perubahan lokal dan deployment LXC telah diperbarui; belum commit/push. Tiket 07 tidak lagi terhambat tiket 06.
