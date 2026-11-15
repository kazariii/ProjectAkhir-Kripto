# Verifikasi PQC tiket 04 — telemetri ke Grafana

**Tiket 04 selesai.** Run Wokwi `f1cecf1e31692ad79413cff2e86b215a` menghasilkan 176 sampel dengan ACK terenkripsi yang cocok dengan jurnal LXC, titik InfluxDB, dan panel Grafana. Seluruh empat keadaan alarm lulus. [Ringkasan mesin](evidence/pqc-ticket-04/summary.json) mencatat `verified=true`; prasyarat tiket 05 terpenuhi.

[Serial lengkap](evidence/pqc-ticket-04/esp32-serial.txt) diambil agen melalui RFC2217 saat mengoperasikan kontrol sensor Wokwi dengan Computer Use. [Provenance dan hash](evidence/pqc-ticket-04/esp32-serial.provenance.json) mencatat salinan byte-for-byte tanpa normalisasi. [Validasi capture](evidence/pqc-ticket-04/capture-validation.json) menggabungkan sampel lokal, counter SENT/STORED, sesi terautentikasi, koneksi broker `esp32-telemetry-f1cecf1e3169`, hasil write, dan hasil kueri Grafana. Keberhasilan ini berasal dari simulator, bukan attestation chip fisik.

Firmware baru memakai environment `pqc-telemetry` dan loop sensor/alarm `main.cpp` yang sama dengan firmware lama. Sensor berjalan setiap 2 detik, DS18B20 tetap menunggu konversi selesai, MQ2 dibaca pada siklus yang sama, dan alarm lokal tidak bergantung pada jaringan. Transport memiliki task MQTT dan crypto worker tersendiri. MQTT ke LXC hanya TCP/1883 dengan session LK3/1 tiket 03; nilai telemetri/ACK dienkripsi ChaCha20-Poly1305 setelah handshake ML-KEM dan prospective FN-DSA terautentikasi.

| Pemeriksaan otomatis | Hasil |
|---|---|
| Unit schema/storage/ACK dan gate bukti | 11 test lulus, termasuk subtest tipe/rentang/duplikasi key dan kegagalan write |
| Loop sensor pada pilihan PQC | Empat keadaan, ritme 2 detik, latest-only, latch pembacaan invalid, recovery, alarm saat startup jaringan gagal |
| Regresi loop legacy | Lulus seluruh skenario sensor/alarm/koneksi/antrean |
| Regresi protokol tiket 03 | 71 pemeriksaan lulus |
| Build PQC sensor | RAM statis 83.580 byte, flash 860.701 byte |
| Build default legacy | Lulus, RAM statis 26.660 byte, flash 557.873 byte |
| Native MQTT → Influx | Empat titik dari empat keadaan, schema salah/tamper/replay tidak menambah write/ACK |
| Grafana | Titik cocok pada tabel riwayat; panel suhu/gas, empat status alarm dan waktu penerimaan cocok pada waktu titik |
| Histori lama | Titik lama masih tersedia; volume/dashboard UID/datasource tetap dipakai |
| Token receiver | Satu izin write pada bucket telemetri; query read identik yang berhasil dengan admin tidak dapat dibaca token service (HTTP 404) |
| Wokwi sensor aktual | Normal, suhu saja, gas dan suhu, gas saja, serta pemulihan ke Normal; seluruhnya cocok dengan Influx/Grafana |
| Serial final | Satu boot/run, dua sesi, 182 frame SENT, 176 ACK terverifikasi; tanpa error LEDC, panic atau watchdog |

Enam frame terakhir pada sesi pertama (counter 114–119) tidak memiliki ACK dan tidak dihitung tersimpan. Sesi baru `6031710b4aa72b64cf4e4fcb81436467` kemudian menyimpan seluruh 63 frame yang dikirim pada sesi tersebut; sesi awal `79023128dccac3dabb68a5f7bbce51d8` menyimpan 113 frame. Tidak ada klaim delivery tanpa kehilangan. Waktu virtual Wokwi dapat tertinggal dari waktu nyata LXC, sehingga rotasi dapat menimbulkan jeda. Status Grafana pada pemeriksaan setelah simulator dihentikan adalah `-1` (Data terlambat), bukan kondisi Normal yang dianggap masih segar.

[Kontrol native MQTT](evidence/pqc-ticket-04/native-mqtt.json) memiliki provenance `native-control`. [Hasil Influx/Grafana](evidence/pqc-ticket-04/native-storage-grafana.json) menyimpan empat field pada timestamp callback yang tepat, hasil panel, serta kontrol scope token. Validasi label historis memakai jam kueri waktu titik+100ms; status pada jam server sebenarnya dicatat terpisah. Ini tidak mengklaim titik lama masih segar.

Receiver `lab-kimia-pqc-session.service` menulis langsung ke InfluxDB lokal dengan token write-only melalui systemd LoadCredential. ACK hanya dibuat sesudah respons HTTP 204. Tidak ada spool/retry; write tanpa konfirmasi tidak mendapat ACK. Schema mensyaratkan tepat lima key: device_id tetap, suhu finite −55..125, ADC integer 0..4095 dan dua boolean. Alarm berasal dari firmware, bukan dihitung ulang dari ADC atau suhu dua desimal. Probe tiket 03 tetap didukung tanpa write Influx.

Antrean sensor satu sampel; umur ≥2 detik dibuang sebelum enkripsi/publish. Generation ID membuang hasil crypto koneksi lama. Data menunggu ≥2 detik pada queue receiver juga dibuang. Ini tidak membuktikan batas latensi seluruh jaringan. Rekey dimulai umur lokal 240 detik, dengan masa berlaku kunci 300 detik pada clock masing-masing endpoint. Jika tidak ada kemajuan ACK selama 10 detik virtual, client memulai handshake baru; waktu peer yang lebih cepat dapat menyebabkan sebagian frame ditolak sebelum itu. Signature simulator sekitar 12 detik dapat membuat celah data, sementara sensor/alarm dan loop MQTT tetap berjalan. Grafana menandai umur penerimaan >10 detik sebagai data terlambat. Penyelarasan waktu dan pengujian gangguan lebih lanjut tetap menjadi pekerjaan tiket 05.

Run awal pengguna menunjukkan timeout broker setelah Pause serta error LEDC pada startup. Pause menghentikan jam firmware sementara broker tetap memakai waktu nyata. Pengujian ulang dilakukan tanpa Pause, dan keepalive firmware sensor diberi margin 120 detik untuk perlambatan simulator. Error buzzer diperbaiki dengan tidak memanggil `noTone()` sebelum kanal tersedia dan menyiapkan kanal default tone pada SDK 2.0.17 sebelum pemakaian pertama. Tes pada loop firmware mereproduksi kedua panggilan LEDC yang belum diinisialisasi sebelum perbaikan; kedua pilihan firmware dan capture final kemudian lulus. Jalur SDK 3 tetap memakai API tone milik SDK tersebut.

[Run parsial awal](evidence/pqc-ticket-04/partial-run-b0e937.json) tetap disimpan sebagai bukti diagnosis, tidak dipakai untuk menutup tiket. Stimulus 400 pada run itu masih menghasilkan DOUT LOW. Kontrol rendah sekitar 0,1 pada uji final terbukti menghasilkan DOUT HIGH dan kondisi Normal; DOUT tetap menjadi acuan alarm, tanpa mengganti aturan firmware atau menebak cutoff ADC.

Layanan sensor cloud/Telegraf lama dipertahankan untuk migrasi tiket 06; jangan menjalankan kedua simulator bersamaan saat pengujian. Image default belum dialihkan. Deskripsi waktu dashboard diperbarui menjadi waktu penerimaan server; query, UID, field type dan data historis tidak diubah. MQTT metadata/password tetap plaintext sesuai keputusan tanpa TLS, dan FN-DSA tetap versi prospektif yang dikunci tiket 01. Hasil lab bukan audit keamanan, bukti entropy/performa chip fisik, atau kalibrasi LPG.

Langkah Wokwi, build, provisioning, dan verifikasi tersedia di [panduan tiket 04](../tools/telemetry/README.md). Source dan image laptop cocok dengan hash build LXC. Capture reader sudah dihentikan dan opsi RFC2217 kembali nonaktif secara default. Pemeriksaan penutupan mengonfirmasi receiver/diagnostik aktif, Grafana `database=ok`, InfluxDB `status=pass`, dan tidak ada listener capture pada port 4000 laptop. Kode lokal dan receiver LXC telah diperbarui; belum di-commit atau dipush. Tiket 05 dapat dilanjutkan, sedangkan pengalihan default firmware dan penghentian Telegraf tetap berada pada tiket migrasi 06.
