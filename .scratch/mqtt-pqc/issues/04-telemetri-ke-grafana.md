# 04 — Sensor melalui sesi PQC ke Grafana

## What to build

Gunakan loop DS18B20/MQ2 dan alarm lokal yang ada untuk mengirim telemetri berulang melalui sesi tiket 03. Receiver LXC memvalidasi payload terautentikasi lalu menulis langsung ke bucket/measurement lama, sehingga dashboard dan histori tetap tersedia. Jalur legacy dipertahankan untuk migrasi terpisah pada tiket 06.

## Blocked by

- 03 — Sesi MQTT terautentikasi (done).

## Status

done

## Acceptance criteria

- [x] Sensor dan alarm memakai implementasi bersama dengan firmware lama; alarm lokal tetap mandiri saat handshake/koneksi gagal.
- [x] Firmware terpisah `pqc-telemetry` memakai MQTT TCP/1883 dan sesi tiket 03, tanpa TLS atau publish telemetri plaintext.
- [x] Sampel terbaru saja diantrekan; sampel lama/saat handshake/disconnect tidak dikirim ulang. Sesi diperbarui berkala sebelum masa berlaku lokal berakhir; ACK yang berhenti memicu handshake baru.
- [x] Receiver menolak schema/tipe/rentang tidak sah dan hanya ACK sesudah InfluxDB mengonfirmasi write. Token service terbatas ke write bucket telemetri.
- [x] Satu titik `suhu` berisi temperature_c float, gas_raw integer, gas_alarm/temperature_alarm boolean dengan tag device_id dan waktu penerimaan server; histori/dashboard lama dipertahankan.
- [x] Telemetri Wokwi aktual, ACK, jurnal penerima, titik InfluxDB dan hasil kueri Grafana dicocokkan. Nilai normal serta perubahan suhu/gas dibuktikan.
- [x] Build, pengujian schema/write/failure, protokol tiket 03 dan regresi sensor lulus; layanan lama tetap sehat.
- [x] Panduan, bukti dan batas klaim diperbarui tanpa kunci/kredensial masuk Git. Tiket 05 baru dibuka setelah semua kriteria ini lulus.

## Comments

Diminta pengguna 14 November 2026. Tidak menghapus stack/volume legacy atau mengganti default firmware sebelum tiket migrasi.

Implementasi firmware/receiver aktif di LXC; 11 unit test, 71 kontrol sesi, kedua pilihan loop sensor dan kedua build lulus. Empat keadaan native telah dicocokkan dengan InfluxDB/Grafana; histori lama tetap ada. Token service write-only, pengujian schema/tamper/replay tidak menghasilkan write tambahan/ACK.

Selesai setelah run Wokwi `f1cecf1e31692ad79413cff2e86b215a`: 176 sampel ber-ACK dicocokkan dengan broker, receiver, Influx dan panel Grafana; seluruh empat keadaan lulus. Capture UART RFC2217 diambil agen saat mengoperasikan kontrol Wokwi melalui Computer Use. Run final bebas error LEDC/panic/watchdog. Kanal tone SDK 2 dipersiapkan sebelum dipakai; default stimulus rendah memakai 0.1 dan DOUT tetap menjadi acuan.

Rekaman mencakup dua sesi dan 182 frame SENT. Enam frame terakhir sesi pertama tidak mendapat ACK dan tidak diklaim tersimpan. Perbedaan jam virtual Wokwi/jam nyata LXC dapat menyebabkan peer kedaluwarsa lebih awal; guard 10 detik tanpa kemajuan ACK membentuk sesi baru. Kriteria lifecycle diperjelas sebagai pembaruan berkala menurut clock lokal dan pemulihan tertutup, bukan janji delivery tanpa jeda. Batas ini dicatat untuk uji gangguan/pemulihan tiket 05; tidak ada retry sampel lama atau fallback plaintext.

[Verifikasi](../../../docs/verifikasi-pqc-tiket-04.md), [panduan](../../../tools/telemetry/README.md), [ringkasan](../../../docs/evidence/pqc-ticket-04/summary.json). Kode belum di-commit/dipush. Prasyarat tiket 05 terpenuhi; migrasi penuh tetap tiket 06.
