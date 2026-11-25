# Verifikasi tiket 07

> **Arsip hasil MQTT/TLS 10 November 2026.** Panduan yang dipakai saat itu disimpan di [arsip demo TLS](demo-proyek-tls-arsip.md). Hasil revisi MQTT/PQC ada pada [verifikasi PQC tiket 07](verifikasi-pqc-tiket-07.md).

Tanggal: **10 November 2026, WIB (UTC+7)**. Acuan: [07-demo-proyek-lengkap.md](../.scratch/monitoring-lab-kimia/issues/07-demo-proyek-lengkap.md). Penghambat 04, 05 dan 06 sudah `done`. Seluruh 10 acceptance criteria terpenuhi. Spesifikasi induk, glosarium, dan ADR belum tersedia; acceptance criteria tiket menjadi acuan.

## Hasil dan perubahan

[Panduan demo lengkap](demo-proyek-privat.md) menjadi pintu masuk dari README: prasyarat, konfigurasi pemilik dari template, EMQX Serverless/Spend Limit 0, Docker, delapan tab Wokwi, Grafana, alarm, gangguan/pemulihan, restart, keamanan dan penyiapan Git. Rincian rangkaian/penyiapan sebelumnya dipakai kembali melalui tautan. Tidak ada perubahan firmware, kontrak pesan, parser, dashboard, layanan produksi, akun atau izin broker pada tiket 07.

[Skrip gangguan demo](../tests/demo_mqtt_outage.py) memindahkan prosedur takeover yang sebelumnya hanya berada di bukti lokal menjadi perintah yang bisa diulang. Memakai probe MQTT serta pembaca konfigurasi tiket 05, TLS terverifikasi dan ID ESP32 tetap; tidak publish/subscribe atau mengambil alih Telegraf. Durasi dibatasi 1–300 detik (default 90); selesai otomatis/Ctrl+C, dan menyimpan hasil tanpa rahasia di jalur yang diabaikan Git. Ini alat demo, bukan layanan aplikasi baru. Tidak ada dependensi tambahan.

## Satu pengulangan lengkap

Simulator dihentikan, lalu **`docker compose config --quiet`, `docker compose down`, `docker compose up -d`, `docker compose ps`** berhasil. Volume dipertahankan. Ketiga layanan berjalan, InfluxDB healthy; snapshot awal **21:04:32 WIB** memperlihatkan 767 titik lama dan status Data terlambat ketika simulator masih berhenti. Wokwi kemudian dijalankan dari Play dengan sumber/konfigurasi pemilik yang sudah tersedia. Proses ini menguji mulai ulang layanan dan simulator, bukan instalasi akun baru atau bucket kosong.

Selanjutnya semua tahap berikut dijalankan pada jalur **ESP32/Wokwi → MQTT/TLS EMQX → Telegraf → InfluxDB 2.9.1 → Grafana**. Nilai/timestamp tabel berasal dari sampel terakhir snapshot database masing-masing tahap; pemeriksaan panel dilakukan berurutan sehingga screenshot dapat berisi sampel yang sedikit lebih baru. Tujuh kueri panel produksi berhasil tanpa error pada setiap snapshot. Kode kondisi Grafana: 0 Normal, 1 gas, 2 suhu, 3 keduanya, -1 terlambat.

| Tahap | Waktu penerimaan sampel (WIB) | Celsius / ADC | Gas / suhu | Kondisi dan keluaran lokal |
| --- | --- | --- | --- | --- |
| Normal | 21:06:22,837 | 25 / 506 | false / false | Normal; OFF |
| Gas saja | 21:06:58,410 | 25 / 2424 | true / false | Peringatan gas; ON |
| Suhu saja | 21:10:12,640 | 40 / 506 | false / true | Peringatan suhu; ON |
| Keduanya | 21:10:53,590 | 40 / 2425 | true / true | Peringatan gas dan suhu; ON |
| Gas pulih | 21:11:17,928 | 40 / 506 | false / true | Peringatan suhu bertahan; ON |
| Kembali normal | 21:12:00,662 | 25 / 506 | false / false | Normal; OFF |
| Gangguan, gas lokal dinaikkan | snapshot 21:13:13 | database masih 25 / 506; lokal 25 / 2425 | database false / false; lokal true / false | Data terlambat; alarm lokal ON |
| Gangguan, gas diturunkan dan suhu dinaikkan | snapshot 21:13:48 | database masih 25 / 506; lokal 40 / 506 | database false / false; lokal false / true | Data terlambat; alarm lokal ON |
| Pulih tanpa restart ESP32 | 21:14:20,237 | 40 / 506 | false / true | Peringatan suhu; ON |
| Normal sebelum restart layanan | 21:15:24,990 | 25 / 506 | false / false | Normal; OFF |
| Sesudah restart layanan | 21:16:09,148 | 25 / 506 | false / false | Normal; OFF; data baru masuk |

Stimulus rendah MQ2 adalah 0,1; gas tinggi memakai End dan pada tahap gas saja satu ArrowLeft (sekitar 95499 pada kontrol). Nilai slider hanya stimulus simulator. Setelah boot bawaan diagram 400 menghasilkan alarm gas sampai kontrol diturunkan. Suhu diatur 25/40 Celsius. Serial lengkap merekam perubahan LED/buzzer ON/OFF, pembacaan DOUT, sampel lokal, handshake, serta pengiriman. LED yang menyala/mati diamati; suara buzzer tidak direkam secara akustik. Tidak ada klaim pengukuran sensor fisik atau konsentrasi gas nyata.

### Putus dan pulih

Perintah aktual: **`python tests/demo_mqtt_outage.py --seconds 120`**, exit 0. Berjalan **21:12:05–21:14:06 WIB**, 75 takeover sah dan **0 publish**. Penambahan waktu sekitar satu detik di luar durasi target berasal dari penyelesaian operasi koneksi yang sedang berjalan, bukan timer realtime presisi. Gangguan ini mengenai sesi MQTT, bukan Wi-Fi fisik.

Penerimaan terakhir sebelum jeda: **21:12:03,657693607**; titik pertama setelah pulih: **21:14:17,291290240**, jeda **133,633597 detik**. Snapshot offline gas dan offline suhu sama-sama memuat **876 titik yang identik**; label -1 terlihat meskipun nilai database sebelumnya Normal. Gas dan suhu lokal tetap dapat mengaktifkan alarm. Simulator tidak direstart, kredensial/CA tidak diubah, lalu suhu aktif tiba di dashboard; akhirnya kembali 25/506 Normal. Seluruh 876 titik lama tetap identik setelah pemulihan, tanpa titik baru di jendela jeda tersebut. Grafik memperlihatkan jeda; tidak ada isian normal/backfill sampel lokal offline.

### Persistensi

Setelah kondisi normal pulih, **`docker compose restart`** berhasil untuk ketiga layanan. Sebelum restart ada **904 titik**; snapshot sesudahnya **922 titik**. Perbandingan `_time`, `device_id`, suhu, ADC dan dua boolean memastikan seluruh **904 titik lama tetap identik**, dan 18 titik tambahan tersedia pada snapshot sesudah restart, termasuk titik penerimaan baru setelah layanan pulih. InfluxDB kembali healthy, ketiga layanan berjalan, seluruh kueri Grafana tetap berhasil; grafik/tabel riwayat dan pengiriman baru tetap tersedia. Tidak memakai `-v`, menghapus bucket atau volume.

## Pengulangan keamanan

| Pemeriksaan aktual | Hasil | Bukti |
| --- | --- | --- |
| `python tests/check_mqtt_access.py` | Exit 0; **17 pemeriksaan lulus**, run `ticket05-bc717ec5d8c7`. ESP32 baru dan kontrol sah sampai Grafana sebelum/sesudah; kredensial/anonim ditolak, operasi topik/wildcard ditolak, CA tidak dipercaya gagal, penanda negatif tidak tersimpan dalam jendela observasi. | [mqtt-access.json](evidence/ticket-07/mqtt-access.json) |
| Konsol EMQX dibaca ulang | Client ID tanpa aturan; ESP32 Publish Allow dan Telegraf Subscribe Allow hanya pada topik utama; All Users `#` Publish & Subscribe Deny. Tidak ada perubahan aturan. | Snapshot teks `acl-*.txt` lokal; prosedur dan bukti sebelumnya di [tiket 05](verifikasi-tiket-05.md) |
| `python tests/check_tls_relay.py` | Exit 0; tes fragmentasi/coalescing/gate relay lulus. Ini pemeriksaan alat, bukan bukti keamanan tersendiri. | Keluaran aktual; pengujian yang sama pada [tiket 06](verifikasi-tiket-06.md) |
| `python tests/check_tls_security.py` | Exit 0; **5 tahap lulus**, run `ticket06-a3a922059c3e`: plaintext terbaca, TLS tidak menampakkan penanda, kontrol awal, manipulasi ciphertext, kontrol akhir. | [tls-experiment.json](evidence/ticket-07/tls-experiment.json); PCAP/log baru tetap lokal |
| `python tests/check_tls_primary.py --esp32-capture docs/evidence/ticket-06/esp32-emqx.pcapng --telegraf-capture docs/evidence/ticket-06/telegraf-emqx.pcapng` | Exit 0; kedua capture utama memuat protected TLS di 8883 tanpa plaintext field sensor. **Capture tiket 06 dipakai kembali**, bukan capture utama baru pada run tiket 07. | [Capture dan hasil tiket 06](verifikasi-tiket-06.md) |

Eksperimen integritas baru memakai **TLS 1.3 lokal**, CA/hostname tetap diverifikasi, relay hanya meneruskan byte. Kontrol sah sebelum/sesudah memperoleh CONNACK/PUBACK 0 dan payload identik pada subscriber independen. Uji rusak diaktifkan setelah CONNACK, satu bit badan record berubah, header/panjang tetap. Klien menerima **`SSLV3_ALERT_BAD_RECORD_MAC`**, broker mencatat **`decryption failed or bad record mac`**; tanpa PUBACK dan tanpa penerimaan penanda. Nama reason OpenSSL itu bukan versi protokol SSLv3. Ini tidak menguji integritas database atau membuktikan seluruh deployment cloud aman.

## Bukti yang disertakan

- [summary.json](evidence/ticket-07/summary.json): dua belas snapshot tahap, hasil tujuh kueri tiap tahap, jeda penerimaan, perbandingan persistensi, identitas run keamanan dan batas klaim.
- [sensor.csv](evidence/ticket-07/sensor.csv): pengukuran ESP32 pada run ini dengan timestamp asli dan dua boolean, tanpa pengukuran sintetis tiket 05.
- [serial.txt](evidence/ticket-07/serial.txt): serial run Wokwi dari boot, tanpa isi `secrets.h`.
- [Kedua alarm](evidence/ticket-07/both-grafana.png), [data terlambat](evidence/ticket-07/stale-grafana.png), [kondisi akhir](evidence/ticket-07/final-grafana.png), [grafik historis](evidence/ticket-07/history-grafana.png), [tabel riwayat](evidence/ticket-07/table-grafana.png), [LED menyala setelah reconnect](evidence/ticket-07/recovered-wokwi.png), dan [LED mati saat normal](evidence/ticket-07/normal-wokwi.png).
- [manifest.json](evidence/ticket-07/manifest.json): SHA-256 salinan publik. Hash memeriksa kesamaan salinan, bukan tanda tangan atau bukti integritas database.

Snapshot database lengkap sebelum/saat/sesudah, hasil semua panel, semua screenshot tahapan, aturan broker, dan alat pengumpulan sementara berada di `evidence/local/ticket-07/` yang diabaikan Git. Capture/log eksperimen keamanan baru berada di `evidence/local/ticket-06/ticket06-a3a922059c3e/`; raw plaintext CONNECT berisi kredensial demo sekali pakai dan sengaja tidak diekspor. Untuk presentasi PCAP publik, gunakan salinan PUBLISH/PUBACK aman di tiket 06 dengan provenance run sebelumnya yang jelas.

## Reproduksi dan batas penerimaan

Ikuti **bagian 2–7 [panduan demo](demo-proyek-privat.md)** berurutan, dari mulai layanan dan Wokwi, enam tahap sensor, gangguan MQTT, pulih, restart, lalu uji akses dan TLS. Urutan uji keamanan bisa dijalankan saat kondisi sensor stabil; uji TLS lokal terisolasi tidak mengubah broker utama. Hasil run baru harus dicatat sendiri, tidak disalin sebagai kelulusan dari tabel ini.

Pemasangan akun/kredensial baru tidak diulang: konfigurasi pemilik yang sudah berhasil pada tiket 01–06 dipakai kembali. Kredensial tetap diisi oleh pemilik. Build firmware/parser/stack lokal sebelumnya dipakai sebagai bukti pendukung; tidak diklaim dijalankan ulang pada tiket dokumentasi ini. Pembuktian baru berfokus pada demo nyata, pengujian keamanan, perbandingan data dan alat takeover. Konfigurasi contoh tersedia, rahasia lokal diabaikan/tidak dilacak Git; isi kandidat berkas diperiksa terhadap nilai password/token aktual dan penanda private key sebelum penyelesaian. Tidak ada push GitHub.

Kecepatan Wokwi berkisar di bawah waktu nyata, sehingga periode 2 detik simulasi tidak berarti penerimaan tiap 2 detik nyata. Batas kesegaran tetap >10 detik waktu server dan dapat menandai simulator yang lambat. Reconnect, alarm lokal, data terlambat dan persistensi hanya dukungan **availability terbatas**. **Confidentiality, integrity, authentication** tetap dibedakan; broker membaca pesan, tidak ada mutual TLS atau identifikasi orang, ambang 40 Celsius hanya demo, MQ2 relatif, dan sistem tidak menjamin keselamatan lab nyata. Tidak ada langkah yang gagal/belum dilakukan yang dinyatakan lulus di luar batas tersebut.
