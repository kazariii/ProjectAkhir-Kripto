# Panduan demo dan verifikasi akhir PQC — tiket 07

Status **done**, **15 November 2026**. [Panduan demo utama](demo-proyek.md) sekarang memuat jalur MQTT TCP/1883 tanpa TLS dan dapat diikuti tanpa riwayat chat. [Ringkasan pemeriksaan](evidence/pqc-ticket-07/summary.json) mencatat hasil dan provenance. Kode/bukti tetap lokal dan disinkronkan ke source LXC; tidak ada commit/push.

## Perubahan yang diselesaikan

- Panduan lengkap memisahkan Terminal A laptop dan Terminal B SSH LXC, serta menyebut folder/file, perintah, expected output, build/default Wokwi, akun existing, tujuh panel Grafana dan pengambilan bukti.
- Urutan demo mencakup normal, gas saja, suhu saja, kedua alarm, pemulihan normal; gangguan receiver/broker/Influx, stale, key renewal, reconnect, serta restart/persistensi.
- Pemetaan tiga algoritma menjelaskan pembentukan rahasia, signature dengan pin, AEAD/tag, counter/nonce, anti-replay, ACK sesudah write dan batas metadata/password MQTT tanpa TLS. Prospective FN-DSA, dukungan availability yang terbatas dan batas sensor fisik ditulis eksplisit.
- Troubleshooting, naskah presentasi singkat, penutupan capture dan pemeriksaan Git disertakan. Panduan TLS lama tetap ada sebagai [arsip](demo-proyek-tls-arsip.md), tidak menjadi instruksi transport utama.
- Alat security/fault menerima `--output-dir` untuk hasil run baru. Security menolak `security.json` existing sebelum mengganggu layanan. Verifier capture menyediakan `--fault-test` dan menyatakan mode nominal/fault, sambil mempertahankan pemeriksaan panic/ACK/session/Influx/Grafana.

## Pengujian baru pada tiket 07

[Kontrol keamanan baru](evidence/pqc-ticket-07/security.json) dijalankan pada broker privat LXC dengan Wokwi berhenti. **21 kasus lulus**, empat sesi dan delapan titik sintetis berlabel native. Subscriber independen mengamati byte publish identik; perubahan frame, replay, plaintext/schema tidak sah dan secret signature palsu tidak menghasilkan respons atau titik Influx pada jendela uji. Kontrol valid sebelum/sesudah serta gangguan receiver/broker/Influx kembali berhasil. Delapan titik dicocokkan ulang dengan Influx/Grafana.

**113 pemeriksaan C++**, **12 tes Python** dan regresi loop sensor PQC/startup gagal juga lulus ulang. CLI `--help` diperiksa untuk tiga alat yang berubah. Penolakan folder hasil existing dicoba terhadap laporan historis: proses gagal dengan alasan yang diharapkan, hash laporan tidak berubah, dan PID receiver tetap sama. Ini membuktikan guard dijalankan sebelum restart layanan.

Kesehatan Influx/Grafana, baseline volume/bucket/dashboard/private state, broker privat, receiver aktif/enabled, diagnostic disabled dan tidak adanya Telegraf diperiksa lagi sesudah kontrol. Tautan berkas/heading pada README, panduan, operasi dan laporan ini diperiksa. Collector read-only dapat dijalankan dari source LXC:

```sh
cd /opt/lab-kimia-mqtt
.venv/bin/python -m tools.demo.collect_evidence
```

Collector memakai laporan security tiket 07 yang sudah ada, memeriksa sumber/image serta database aktual dan menulis ringkasan tiket 07. Ia tidak menjalankan simulator, mengulang mutasi/gangguan, atau menimpa laporan tiket 05/06.

## Bukti Wokwi yang dipakai ulang

**Tidak ada run Wokwi baru atau Computer Use pada tiket 07.** Firmware/protokol tidak diubah. Hash source runtime/image dibandingkan dengan manifest tiket 06; implementasi Channel/native dibandingkan dengan manifest tiket 05. Capture yang dipakai ulang tetap milik run asal dan diverifikasi kembali terhadap journal, Influx serta kueri Grafana saat penutupan tiket 07.

| Bukti asal | Run ID | Hasil asal yang dicocokkan ulang | Pemakaian |
|---|---|---|---|
| [05 — Gangguan Wokwi](verifikasi-pqc-tiket-05.md) | `8f337e9c0273ef3c232b05be37524edc` | 136 ACK dari 148 SENT, lima sesi, empat keadaan alarm | Pemulihan gangguan dan alarm lokal; 12 frame tanpa ACK tidak dihitung tersimpan |
| [06 — Folder firmware utama](verifikasi-pqc-tiket-06.md) | `3066a27ea869a9b9f201019f5537cf99` | 169 ACK dari 169 SENT, tiga sesi, empat keadaan alarm | Default PQC dan alur sensor sampai Grafana sesudah migrasi |

Waktu/gap sampel, pemulihan 20 detik layanan, LED/buzzer ON/OFF, dan renewal server pada umur 180,219 detik adalah observasi run tiket 05/06, **bukan observasi interaktif baru pada tiket 07**. Demikian pula dua kontrol native sebelum/sesudah restart lengkap stack tetap berasal dari tiket 06. Uji baru tiket 07 memakai klien native dan tidak boleh dilabeli pembacaan sensor ESP32 baru.

## Bukti, batas dan keadaan akhir

Panduan menempatkan hasil ulang pada `evidence/local/<run-baru>` dan mengharuskan `--output` untuk validasi capture agar tidak menimpa bukti lama. Raw key/credential, `.env`, identity/header, binary/ELF dan baseline tetap ignored. Pemeriksaan kandidat Git dilakukan tanpa staging/commit/push; port capture tidak dibuka pada tiket ini.

Pemeriksaan state/histori dan query Grafana dilakukan terhadap LXC yang aktif. Dashboard yang stale setelah pengiriman berhenti adalah expected; titik sintetis native bukan bukti simulator sedang aktif. Hasil 169/169 pada run asal bukan jaminan delivery tanpa kehilangan. Tidak ada klaim reboot seluruh LXC, audio buzzer, kualitas RNG/side channel/performa hardware, kalibrasi fisik, audit kriptografi, atau implementasi final FIPS 206. Ketentuan tugas tetap memakai tiga algoritma yang telah dipilih dan tidak menghidupkan transport TLS lama.
