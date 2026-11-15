# Verifikasi serangan dan pemulihan PQC — tiket 05

Status **done**, 15 November 2026. Jalur yang diuji tetap MQTT TCP/1883 tanpa TLS, ML-KEM-512, ChaCha20-Poly1305, dan prospective FN-DSA degree 512. [Ringkasan mesin](evidence/pqc-ticket-05/summary.json) menyimpan hash source/image dan hasil pemeriksaan. Seluruh perubahan masih lokal; tidak ada commit/push GitHub.

## Perubahan perilaku

`Channel` kini menyediakan retry M1/M3 persis seperti sebelumnya. Duplikasi M1 pending mendapat challenge yang sama; duplikasi M3 yang telah diautentikasi hanya mendapat M4 cache. Duplikasi tidak mengaktifkan sesi kedua, mereset counter atau memperpanjang deadline/umur kunci. Worker mencoba ulang setelah 5 detik lokal; setelah dua retry tanpa kemajuan ia menghasilkan nonce/M1 baru. Sampel telemetri tidak dikirim ulang.

Client memulai rekey pada umur 180 detik. LXC juga mengirim `{"renew_session":true}` dalam Data s2c terenkripsi ketika clock server mencapai 180 detik, memberi margin 120 detik sebelum expiry. Client memeriksa tag, sesi dan counter sebelum menindaklanjutinya. Rekey tetap membutuhkan ML-KEM, signature dua pihak dan finished tags baru. Guard 10 detik tanpa kemajuan ACK tetap tersedia. [Format dan invariant](protokol-sesi-pqc.md) menjelaskan rincian protokol.

## Bukti protokol dan broker

- **113 pemeriksaan C++**: pin/secret palsu, perubahan KEM/signature/finished/data, counter, ukuran/padding, arah, nonce nol, expiry/reset, rekey, kehilangan M2/M4, duplikasi tanpa perpanjangan TTL/reset counter, dan renewal dengan clock client tertinggal.
- **12 tes Python**: schema ketat, write sebelum ACK, write gagal tanpa ACK, pencocokan capture. Mode capture gangguan mengizinkan kegagalan koneksi yang disengaja; panic/watchdog/LEDC tetap ditolak.
- Regresi loop sensor PQC dan legacy lulus; build ESP32 PQC lulus, RAM **83.644 byte**, flash **861.561 byte**. Semua 156 berkas vendor tetap cocok dengan lock.
- [21 kasus broker/storage aktual](evidence/pqc-ticket-05/security.json) menggunakan klien native yang diberi label terpisah. Subscriber MQTT independen menerima byte publish identik. JSON sensor/teks yang diketahui tidak muncul pada frame Data terenkripsi yang diuji. Ini demonstrasi payload, bukan pembuktian formal kriptografi.
- Mutasi magic/versi/tipe/session ID/counter/length/ciphertext/tag/padding, truncation, replay/urutan lama, plaintext JSON, schema tidak sah, serta secret penandatangan palsu dengan public binding benar tidak menghasilkan respons maupun titik Influx pada jendela masing-masing. Paket valid sesudah modifikasi tetap diterima, membuktikan tag palsu tidak memajukan counter.
- Kontrol valid sebelum/sesudah gangguan menghasilkan **8 titik** yang cocok tepat dengan Influx dan kueri Grafana. Kehilangan M2/M4 dipulihkan melalui broker dengan respons cache identik. Signature server palsu dan kedua pin salah juga diuji di C++.

## Bukti ESP32/Wokwi

Capture [serial](evidence/pqc-ticket-05/esp32-serial.txt) diambil otomatis melalui RFC2217, tanpa Pause. [Provenance](evidence/pqc-ticket-05/esp32-serial.provenance.json) menyimpan hash byte UART. Run **`8f337e9c0273ef3c232b05be37524edc`** memiliki lima sesi, **148 SENT dan 136 ACK**. Semua ACK cocok dengan sampel lokal, journal receiver, timestamp/empat field Influx, dan kueri dashboard Grafana. [Validasi lengkap](evidence/pqc-ticket-05/capture-validation.json) memuat join tersebut, termasuk empat keadaan alarm.

| Gangguan disengaja | Durasi berhenti | Penyimpanan kembali setelah Start layanan | Hasil |
|---|---:|---:|---|
| Receiver | 20 detik | 16,874 detik | Sesi baru, counter mulai 1, ACK terverifikasi |
| Broker | sekitar 20 detik | 23,289 detik | Koneksi dan sesi baru, ACK terverifikasi |
| InfluxDB | sekitar 20 detik | 8,940 detik | Enam write tidak terkonfirmasi tanpa ACK; sesi baru dan sampel baru tersimpan |

Waktu mencakup jadwal simulator, koneksi ulang dan biaya signature; bukan SLA atau benchmark papan fisik. [Catatan gangguan](evidence/pqc-ticket-05/wokwi-faults.jsonl) memuat waktu mulai/pulih dan titik pemulihan. [Event receiver](evidence/pqc-ticket-05/receiver-events.json) menyimpan hasil yang terkait sesi run ini.

Renewal berkala juga teramati tanpa mematikan layanan: LXC meminta pembaruan pada umur **180,219 detik**. Saat sesi baru dikonfirmasi, pertambahan waktu virtual Wokwi baru **174.000ms**, sehingga trigger server memang mendahului timer 180 detik client. Data dan ACK kembali berjalan. Gap pengukuran lokal maksimum **2000ms** selama seluruh run; setiap SENT menggunakan pengukuran lokal terbaru dan sampel pertama setelah handshake diukur setelah autentikasi. Log alarm mencakup ON/OFF; suara buzzer tidak direkam secara akustik.

**12 frame SENT tanpa ACK tidak diklaim tersimpan.** Tidak adanya ACK secara umum berarti write belum terkonfirmasi, bukan bukti pasti tidak terjadi write. Pada outage Influx yang diuji, receiver mencatat enam kegagalan write. Sampel lama tidak diretry; gap tetap gap. Sensor kembali 25°C/gas rendah dan mendapat ACK sebelum simulasi dihentikan.

## Kondisi akhir dan batas

Receiver/diagnostic aktif kembali; Influx dan Grafana sehat. Token receiver tetap write-only: query admin melihat data sedangkan query identik dengan token writer menghasilkan HTTP 404. UID dashboard, bucket, volume, history dan ingress legacy dipertahankan. Firmware default masih legacy sampai tiket migrasi **06**. Jalankan hanya satu perangkat/simulator.

Transport tanpa TLS tetap memperlihatkan password broker, topik, ukuran dan waktu pesan. Autentikasi aplikasi memerlukan private identity yang dipin; password broker saja tidak cukup untuk memalsukan telemetri. Protokol lab ini belum diaudit independen, memakai prospective FN-DSA dan tidak diklaim memenuhi FIPS 206 final. Serangan DoS, kualitas RNG/side channel hardware, kalibrasi sensor dan keselamatan sistem fisik tidak dibuktikan oleh simulasi.

Untuk mengulang, gunakan [panduan transport dan skrip uji](../tools/telemetry/README.md). Raw image mengandung kunci/kredensial dan tetap di direktori ignored/private. Opsi RFC2217 kembali dinonaktifkan pada konfigurasi. Setelah simulator berhenti, Computer Use dihentikan melalui Escape saat pemeriksaan pembersihan; menutup/reload jendela VS Code akan melepas listener RFC2217 yang masih dimiliki extension dari run tadi.
