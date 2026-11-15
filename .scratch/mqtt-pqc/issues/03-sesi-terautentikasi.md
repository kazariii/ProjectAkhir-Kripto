# 03 — Sesi MQTT terautentikasi

## What to build

Bangun sesi interaktif ESP32–LXC melalui MQTT TCP/1883. Identitas dua arah dipasang sebelumnya; prospective FN-DSA-512 menandatangani handshake, ML-KEM-512 menghasilkan rahasia sesi, HKDF-SHA256 memisahkan kunci arah, dan ChaCha20-Poly1305 melindungi payload serta konfirmasi kunci. Ini eksperimen satu payload sintetis; integrasi sensor/InfluxDB merupakan tiket 04.

## Blocked by

- 01 — Bukti kriptografi (done).
- 02 — Koneksi broker privat (done).

## Status

done

## Acceptance criteria

- [x] Firmware dan penerima LXC menggunakan protokol yang sama, dengan pin public key dan tanpa TLS/fallback plaintext.
- [x] Handshake baru, autentikasi dua arah dan konfirmasi kunci selesai melalui MQTT.
- [x] Payload sintetis dari Wokwi didekripsi LXC; balasan terenkripsi diverifikasi ESP32 dan dicocokkan dengan jurnal broker/penerima.
- [x] Uji native menolak manipulasi handshake, identitas salah, payload rusak, replay, sesi kedaluwarsa, dan pesan sebelum sesi aktif.
- [x] Kunci arah dan counter nonce terpisah; replay tidak mengubah counter penerima; kunci sementara dihapus saat reset/kedaluwarsa.
- [x] Build ESP32, kontrol tiket 01/02 dan layanan monitoring lama tetap lulus/berjalan.
- [x] Format protokol, batasan, langkah verifikasi, dan bukti tercatat tanpa private key.

## Comments

Implementasi diminta pengguna pada 14 November 2026. Tidak mengubah jalur telemetri produksi sebelum tiket migrasi.

Selesai 14 November 2026. [Verifikasi](../../../docs/verifikasi-pqc-tiket-03.md), [ringkasan aktual](../../../docs/evidence/pqc-ticket-03/summary.json), [format protokol](../../../docs/protokol-sesi-pqc.md), dan [panduan reproduksi](../../../tools/session/README.md).

Pengguna menjalankan Wokwi dan memberikan log run `87e262e942f35bc4f7e310eba1538c14`, session `a20cbd94bfcf36f556ff25d49c14301f`. Agen memverifikasi event autentikasi/payload/ACK pada LXC serta koneksi broker `esp32-session-87e262e942f3`. ESP32 memverifikasi ACK terenkripsi setelah 12.478 ms virtual. Bukti runtime diatribusikan pada log pengguna, bukan pengamatan UI agen.

71 pemeriksaan protokol native, tujuh pemeriksaan bukti, kontrol tiket 01/02 dan build firmware sesi/proof lulus. Receiver baru aktif di LXC; monitoring lama sehat. Private identity/header/artefak tetap diabaikan Git. Kode belum di-commit atau dipush. Prasyarat tiket 04 terpenuhi; payload saat ini masih sintetis, tanpa penulisan InfluxDB.
