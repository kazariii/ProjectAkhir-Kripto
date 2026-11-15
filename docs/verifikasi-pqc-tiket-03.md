# Verifikasi PQC tiket 03 — sesi terautentikasi

**Lulus pada 14 November 2026.** Pengguna menjalankan Wokwi VS Code melalui Private Gateway dan memberikan [log serial lengkap](evidence/pqc-ticket-03/esp32-serial.txt). Agen mencocokkannya dengan jurnal receiver dan koneksi broker LXC. Hasil tidak disimpulkan dari uji native atau pengoperasian UI oleh agen.

| Bukti | Hasil |
|---|---|
| Run Wokwi | `87e262e942f35bc4f7e310eba1538c14` |
| Session ID | `a20cbd94bfcf36f556ff25d49c14301f` |
| MQTT | TCP/1883, `tls=false`; IP gateway ESP32 `10.13.37.2` |
| Client broker | `esp32-session-87e262e942f3`, akun perangkat |
| Autentikasi dan key confirmation | Dua arah, lulus |
| Payload LXC | Probe `ticket-03`, perangkat `esp32-meja01`, suhu sintetis 26.25, run/session cocok |
| Balasan | ACK dienkripsi LXC, didekripsi dan diverifikasi ESP32 |
| Durasi simulator | 12.478 ms = 12,478 detik termasuk koneksi dan handshake |
| Build firmware sesi | RAM statis 83.220/327.680 byte; flash 811.405/1.310.720 byte |

[Validasi capture](evidence/pqc-ticket-03/capture-validation.json) menyimpan tiga event server terurut: sesi terautentikasi, payload diterima, ACK terenkripsi diantrekan. ACK juga harus diterima/terverifikasi pada log ESP32; event antrean server sendiri tidak dianggap bukti penerimaan. [Ringkasan mesin](evidence/pqc-ticket-03/summary.json) memuat hasil kontrol dan hash sumber/artefak private tanpa isi kunci.

Uji native protokol lulus **71 pemeriksaan**: kontrol handshake sah, identitas palsu tanpa private key yang benar, manipulasi KEM/signature/finished, replay M2 terhadap nonce baru, data sebelum sesi, perubahan ID/counter/length/ciphertext/tag/padding, replay payload, pemisahan kunci arah, expiry/reset dan rekey yang gagal tanpa merusak sesi aktif. Tujuh pemeriksaan bukti menolak capture tidak lengkap/bercampur, native yang menyamar sebagai ESP32, dan event LXC yang tidak cocok.

Regresi bukti tiket 01 tetap lulus: dua kontrol positif, 13 pemeriksaan negatif dan vektor AEAD RFC 8439. Build environment `pqc-proof` juga tetap lulus setelah primitive crypto dibagi dengan sesi. Kontrol MQTT tiket 02 tetap lulus: echo berkorelasi, akun salah/anonim serta publish tanpa izin ditolak, read di luar ACL tidak bocor. Semua 156 berkas vendor tetap cocok dengan hash sumber yang dikunci.

Regresi loop firmware sensor lama dan pengujian `telemetry_test.cpp` lulus: ritme pembacaan, alarm lokal independen, pembacaan invalid dan pemulihan jaringan tetap bekerja. [Tiga kontrol bukti tiket 02](evidence/pqc-ticket-03/mqtt-capture-regression.json) juga tetap menolak capture yang tidak memenuhi syarat setelah lifecycle MQTT dipindah ke helper bersama.

Receiver baru `lab-kimia-pqc-session.service` dan diagnostik aktif di `/opt/lab-kimia-mqtt`. Broker eksperimen direcreate untuk memperbarui bind mount ACL; layanan penerima tersambung kembali melalui systemd. Container Telegraf/InfluxDB/Grafana jalur lama tetap berjalan, Grafana melaporkan database `ok`, InfluxDB `pass`. Tidak ada penghapusan volume atau migrasi telemetri pada tiket ini.

Implementasi menggunakan pin FN-DSA kedua pihak, ephemeral ML-KEM setiap handshake, HKDF untuk kunci arah, dan ChaCha20-Poly1305 dengan counter nonce. FN-DSA masih **prospektif**, sesuai sumber tiket 01; keberhasilan uji bukan audit keamanan atau kepatuhan FIPS 206 final. MQTT credentials/metadata tetap terbuka tanpa TLS. Batas protokol dan ukuran frame dijelaskan dalam [format sesi](protokol-sesi-pqc.md); [panduan reproduksi](../tools/session/README.md) mencantumkan provisioning, service, build dan Wokwi.

**Tiket 04 sudah tidak diblokir oleh tiket 03.** Pekerjaan selanjutnya menghubungkan sensor/alarm yang ada melalui sesi ini ke InfluxDB dan Grafana. Saat ini payload masih sintetis. Perubahan kode berada di workspace lokal dan deployment uji LXC; belum di-commit atau dipush ke GitHub.
