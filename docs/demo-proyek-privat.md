# Panduan demo jalur privat (Wokwi VS Code dan Mosquitto LXC)

> **Jalur cadangan dan rollback.** Sejak 25 November 2026, demo utama memakai Wokwi web lewat broker publik `broker.emqx.io`; lihat [panduan demo utama](demo-proyek.md). Panduan ini tetap berlaku untuk jalur privat: Wokwi VS Code dengan Private Gateway, Mosquitto `10.34.211.141:1883` dengan login/ACL, identitas lab, dan build eksplisit `pio run -e pqc-telemetry` dengan `wokwi.toml` yang diarahkan kembali ke `.pio/build/pqc-telemetry/`. Klaim login/ACL di bawah hanya berlaku untuk jalur privat ini. Skrip gangguan (`wokwi_fault`), `check_security`, dan `verify_capture` tanpa `--public` bekerja pada receiver privat `lab-kimia-pqc-session.service`.

Proyek: **Simulasi Monitoring Gas dan Suhu Laboratorium Kimia Dasar dengan Kriptografi Aplikasi pada MQTT dan Dashboard Grafana**. Panduan ini memakai deployment yang selesai dimigrasikan pada tiket 06. Laptop menjalankan Wokwi VS Code dan browser; broker, receiver, InfluxDB dan Grafana berjalan di LXC.

Transport sensor adalah **MQTT biasa TCP/1883, tanpa TLS**. Algoritma yang ditetapkan dosen tetap **ML-KEM-512, ChaCha20-Poly1305, dan prospective FN-DSA degree 512**. Panduan TLS lama disimpan sebagai [arsip](demo-proyek-tls-arsip.md); jangan mengikutinya untuk demo revisi ini.

## 1. Gambaran sistem dan bahan penjelasan

```text
DS18B20 + MQ2 → ESP32/Wokwi → Mosquitto privat :1883 → receiver PQC
                   ↓                                    ↓ HTTP loopback
               LED/buzzer                           InfluxDB → Grafana
```

| Bagian | Fungsi dalam proyek |
|---|---|
| DS18B20, GPIO 4 | Suhu lingkungan sekitar meja, bukan suhu nyala api |
| MQ2 AOUT melalui adapter, GPIO 34 | ADC relatif 0–4095; bukan ppm LPG terkalibrasi |
| MQ2 DOUT, GPIO 27 | Alarm gas aktif ketika LOW, independen dari ADC/suhu |
| LED GPIO 25, buzzer GPIO 26 | ON ketika salah satu alarm aktif |
| ML-KEM-512 | Membentuk rahasia bersama baru pada handshake, bukan mengenkripsi JSON langsung |
| Prospective FN-DSA degree 512 | Signature identitas dua arah pada handshake, diverifikasi terhadap public key yang sudah dipin |
| ChaCha20-Poly1305 | Enkripsi dan pemeriksaan tag untuk telemetri, ACK, serta permintaan renewal |
| HKDF-SHA256 | Pendukung derivasi kunci dua arah dari rahasia dan transcript; bukan pengganti tiga algoritma utama |
| Receiver LXC | Verifikasi/dekripsi, validasi schema, write Influx, lalu ACK terenkripsi |
| InfluxDB/Grafana | Satu timestamp penerimaan LXC untuk empat field, riwayat dan kondisi terbaru |

ML-KEM adalah mekanisme pembentukan rahasia bersama menurut [NIST FIPS 203](https://csrc.nist.gov/pubs/fips/203/final); AEAD ChaCha20-Poly1305 menggabungkan enkripsi dan autentikator menurut [RFC 8439](https://www.rfc-editor.org/rfc/rfc8439). Implementasi FN-DSA pada proyek ini **prospektif** dan dikunci berdasarkan commit; jangan menyebutnya implementasi final FIPS 206 atau hasil audit keamanan.

Fokus pembuktian tugas adalah **confidentiality, integrity, dan authentication**. Dalam istilah CIA yang umum, A berarti **availability**, seperti pada [glosarium NIST](https://csrc.nist.gov/glossary/term/cia). Autentikasi dibahas secara eksplisit di sini; alarm lokal dan pemulihan hanya mendukung ketersediaan terbatas, bukan jaminan uptime.

Topik binary: `lab/kimia/pqc/session/up` untuk ESP32→receiver dan `lab/kimia/pqc/session/down` untuk arah balik. ID perangkat: `esp32-meja01`. JSON di dalam enkripsi mempunyai tepat lima key: `device_id`, `temperature_c`, `gas_raw`, `gas_alarm`, `temperature_alarm`. Timestamp database berasal dari callback penerimaan server, bukan jam ESP32.

Handshake berjalan M1→M2→M3→M4: nonce client; challenge/public KEM dan signature server; ciphertext KEM, signature client dan finished tag; kemudian finished tag server. Data hanya diterima pada sesi sah. Signature tidak dihitung ulang pada setiap sampel. Counter mulai 1 per arah, nonce 0 khusus finished; arah memakai kunci berbeda. Tag palsu tidak memajukan counter penerima. Replay/urutan lama ditolak. [Detail format dan lifecycle](protokol-sesi-pqc.md).

**Batas:** MQTT tanpa TLS tetap memperlihatkan password broker, topik, ukuran dan waktu pesan. Payload yang sudah didekripsi berada pada receiver/Influx/Grafana; browser Grafana memakai HTTP privat. Jangan menyebut seluruh jalur sampai browser terenkripsi ujung ke ujung. Data sensor yang dikirim sah tetapi keliru juga bukan masalah yang diselesaikan kriptografi.

## 2. Siapkan dua terminal dan akses

- **Terminal A, laptop:** PowerShell pada root repository; dipakai untuk SCP dan reader serial. VS Code dibuka pada subfolder `firmware`.
- **Terminal B, LXC:** SSH untuk memeriksa layanan, menjalankan kontrol native dan gangguan terukur. Jangan menjalankan kontrol native bersamaan dengan Wokwi: saat ini satu perangkat/sesi aktif per pin.

Di PowerShell laptop:

```powershell
Set-Location -LiteralPath 'C:\Kuliah\Semester 5\Kriptografi\ProjekAkhir-IoT'
Test-NetConnection 10.34.211.141 -Port 1883
ssh root@10.34.211.141
```

Hasil pemeriksaan TCP harus `TcpTestSucceeded : True`. Keberhasilan TCP hanya membuktikan rute/port, belum autentikasi atau penyimpanan. Pertahankan akses jaringan privat/VPN laptop ke LXC. Terminal SSH berikut adalah **Terminal B**, bukan tempat menjalankan `code`/Wokwi.

[Grafana meja 01](http://10.34.211.141:3000/d/suhu-meja01): login dengan akun yang sudah dipakai pada deployment. Nilai login disimpan private dalam `.env` initialized di `/opt/lab-kimia-suhu`; jangan menampilkan file itu saat presentasi. Influx hanya tersedia pada loopback server `127.0.0.1:8086`.

Deployment existing telah memiliki Docker, venv Paho, native library, toolchain, akun MQTT, identity/pin dan token writer. **Tidak perlu membuat akun cloud, CA, bucket, token atau lisensi ulang.** Bila menyiapkan server baru, ikuti provisioning [broker](../tools/mqtt/README.md), [identity/session](../tools/session/README.md), [token writer](../tools/telemetry/README.md), lalu [operasi/migrasi](operasi-pqc.md). Jangan menimpa private state existing untuk memperbaiki kegagalan.

## 3. Mulai dan periksa layanan LXC

Jalankan di **Terminal B**:

```sh
cd /opt/lab-kimia-suhu
docker compose config --quiet
docker compose up -d --wait --wait-timeout 120
cd /opt/lab-kimia-mqtt/infra/mqtt
docker compose config --quiet
docker compose up -d --wait --wait-timeout 60
systemctl enable --now lab-kimia-pqc-session.service
systemctl is-active lab-kimia-pqc-session.service
docker ps --format '{{.Names}}'
curl -fsS http://127.0.0.1:8086/health
curl -fsS http://10.34.211.141:3000/api/health
```

Expected: receiver `active`; container `lab-kimia-mqtt-pqc-broker-1`, `lab-kimia-suhu-influxdb-1`, dan `lab-kimia-suhu-grafana-1`; Influx `status:pass`, Grafana `database:ok`. Tidak ada container Telegraf pada jalur utama. Diagnostic proof bukan layanan wajib dan tetap disabled. Jangan menjalankan `docker compose config` lengkap karena hasilnya dapat memuat secret.

Untuk memastikan baseline migrasi tidak berubah, di Terminal B:

```sh
cd /opt/lab-kimia-mqtt
.venv/bin/python -c "from tools.deploy.migrate import verify_state; verify_state(); print('STATE_OK')"
```

Expected `STATE_OK`: volume/bucket/dashboard/private state tetap sesuai baseline, receiver enabled, Telegraf tidak aktif, dan empat titik historis masih cocok. Ini bukan pemeriksaan bahwa simulator sedang mengirim.

## 4. Build dan buka simulator utama

1. Di VS Code pilih **File → Open Folder → `C:\Kuliah\Semester 5\Kriptografi\ProjekAkhir-IoT\firmware`**. Gunakan folder ini, bukan fixture `tools/mqtt/simulator` atau `tools/session/simulator`.
2. Build eksplisit env `pqc-telemetry` (default `platformio.ini` kini `pqc-telemetry-public`), lalu pastikan `wokwi.toml` menunjuk `.pio/build/pqc-telemetry/firmware.bin` dan `.elf`. Rangkaian berada pada `diagram.json`; custom chip `mq2-level.chip.wasm` sudah tersedia.
3. Pada laptop pengujian, binary/ELF dan header private sudah tersedia. Bila source firmware berubah, build ulang pada Terminal B:

   ```sh
   cd /opt/lab-kimia-mqtt
   PLATFORMIO_CORE_DIR=/opt/lab-kimia-suhu/pqc-proof/evidence/local/platformio \
     /opt/lab-kimia-suhu/pqc-proof/.venv/bin/pio run -d firmware -e pqc-telemetry -j2
   ```

   Expected environment `pqc-telemetry` dan `SUCCESS`. Kemudian dari PowerShell laptop pada root repo:

   ```powershell
   New-Item -ItemType Directory -Force firmware/.pio/build/pqc-telemetry | Out-Null
   scp root@10.34.211.141:/opt/lab-kimia-mqtt/firmware/.pio/build/pqc-telemetry/firmware.bin firmware/.pio/build/pqc-telemetry/firmware.bin
   scp root@10.34.211.141:/opt/lab-kimia-mqtt/firmware/.pio/build/pqc-telemetry/firmware.elf firmware/.pio/build/pqc-telemetry/firmware.elf
   ```

   Image/ELF memuat key dan kredensial demo; keduanya tetap private/ignored. Jangan upload ke proyek publik.
4. Jika VS Code menampilkan Workspace Trust, pemilik meninjau dan menanganinya sendiri. Lisensi Wokwi sudah diaktifkan pada pengujian sebelumnya. Bila pada komputer lain belum ada lisensi, pemilik memakai F1 → `Wokwi: Request a new License` dan menyelesaikan login/aktivasi sendiri.
5. Gunakan **Private Gateway** yang sama seperti tiket 02–06, lalu **F1 → `Wokwi: Start Simulator`**. Pertahankan tab simulator terlihat dan **jangan Pause**. Jam virtual berhenti ketika Pause, sedangkan LXC/broker tetap menghitung waktu nyata.
6. Tunggu `TELEMETRY_RUN` dengan `run_id` baru dan IP Wokwi `10.13.37.2`, lalu `TELEMETRY_AUTHENTICATED` berisi `mqtt_port:1883`, `tls:false` dan `session_id` 32 digit hex. Setelah itu harus ada `TELEMETRY_SENT` dan `TELEMETRY_STORED` dengan SID/counter sama serta `ack_verified:true`.

`Sampel lokal` saja belum membuktikan publish; `SENT` saja belum membuktikan database. `STORED` menunjukkan ESP32 memverifikasi ACK terenkripsi yang baru dibentuk sesudah Influx mengonfirmasi write. Biaya signature sekitar 12 detik **virtual** pada run sebelumnya; waktu nyata bisa lebih panjang. Stream ini berjalan terus dan tidak mempunyai marker DONE. Marker startup masih menyebut `ticket=04` karena nama firmware sensor asal, bukan berarti folder/default masih versi lama.

Jika ingin bukti otomatis, lakukan bagian capture berikut **sebelum Start**. Jangan menghentikan/memulai ulang run untuk sekadar menyalin serial.

## 5. Capture satu run tanpa Pause

Pilih nama run baru; contoh `demo-pqc-20261115-01`. Ganti akhiran pada pengulangan. Semua bukti percobaan baru masuk `evidence/local/`, bukan menimpa `docs/evidence/pqc-ticket-04/05/06`.

1. Saat simulator Stop, aktifkan sementara baris `rfc2217ServerPort = 4000` pada `firmware/wokwi.toml`.
2. Di **Terminal A**, root repo laptop:

   ```powershell
   node tools/telemetry/capture_serial.mjs evidence/local/demo-pqc-20261115-01.txt
   ```

   Expected `waiting for Wokwi`, kemudian `connected to localhost:4000` setelah simulator Start. Reader menulis byte UART dan menolak menimpa file existing; ia tidak mengirim perintah serial/reset.
3. Start Wokwi, lakukan seluruh tahap sensor dan, bila dipilih, gangguan dalam run yang sama. Jangan Pause. Catat `run_id` dan SID setiap pergantian sesi.
4. Setelah ACK kondisi akhir, Stop Wokwi dahulu, lalu Ctrl+C pada reader. Bagian 10 menjelaskan pemindahan/validasi capture.

## 6. Buka Grafana dan demonstrasikan sensor/alarm

Buka [dashboard](http://10.34.211.141:3000/d/suhu-meja01), pilih **Last 15 minutes** atau rentang yang mencakup run, refresh **2s**. Ada tujuh panel: suhu terbaru, gas terbaru, dua grafik riwayat, kondisi/kesegaran, tabel pengukuran/alarm, dan waktu penerimaan terakhir. Pemilih rentang mengatur riwayat; kondisi/nilai terakhir tetap dihitung dari seluruh riwayat dan waktu sekarang.

Klik MQ2 untuk membuka slider gas, klik DS18B20 untuk suhu. Tutup overlay komponen sebelum membuka komponen lain. Turunkan gas sampai DOUT HIGH; diagram memakai stimulus 0.1 tetapi UI Wokwi dapat mengingat 400 yang sudah menyalakan alarm. Naikkan gas sampai DOUT LOW, tanpa menuntut angka ADC tertentu. Label `ppm` pada slider hanya stimulus simulator.

Lakukan tabel berurutan. Tunggu **minimal 8 detik virtual dan beberapa ACK**, lalu pastikan waktu penerimaan serta label Grafana berubah sebelum lanjut. Jika ada renewal/handshake, tunggu data baru sesudahnya.

| Tahap | Suhu | Gas/DOUT | Flag gas/suhu | LED/buzzer | Grafana saat data terkini |
|---|---:|---|---|---|---|
| 1. Normal awal | 25°C | rendah/HIGH | false/false | OFF | Normal |
| 2. Gas saja | 25°C | tinggi/LOW | true/false | ON | Peringatan gas |
| 3. Normal sementara | 25°C | rendah/HIGH | false/false | OFF | Normal |
| 4. Suhu saja | 45°C | rendah/HIGH | false/true | ON | Peringatan suhu |
| 5. Kedua alarm | 45°C | tinggi/LOW | true/true | ON | Peringatan gas dan suhu |
| 6. Suhu pulih dahulu | 25°C | tinggi/LOW | true/false | ON | Peringatan gas |
| 7. Normal akhir | 25°C | rendah/HIGH | false/false | OFF | Normal |

Ambang suhu kode adalah **>=40°C**; 45°C dipakai agar demo jelas. Pembacaan suhu invalid tidak dianggap 0/normal dan tidak menghapus alarm suhu sebelumnya; gas tetap independen. Catat grafik suhu berubah saat gas tetap dan sebaliknya. Tabel harus menyimpan kedua angka serta dua flag pada satu timestamp server. Log LED/buzzer ON/OFF membuktikan perintah output; jangan mengklaim rekaman suara bila tidak ada audio.

## 7. Demo gangguan dan pemulihan saat Wokwi berjalan

Gunakan **Terminal B** untuk gangguan; Wokwi tetap terlihat/berjalan. Jangan menjalankan klien native ketika Wokwi aktif. Siapkan direktori bukti pada LXC (contoh ini harus baru pada pengulangan):

```sh
cd /opt/lab-kimia-mqtt
demo_run_dir=evidence/local/demo-pqc-20261115-01
install -d -m 700 "$demo_run_dir"
```

1. Tunggu `TELEMETRY_STORED` terbaru, salin SID dari serial, lalu ganti nilai assignment berikut dengan SID **run saat ini**:

   ```sh
   session_id=ISI_SESSION_ID_TERBARU_DARI_SERIAL
   .venv/bin/python -m tools.telemetry.wokwi_fault receiver "$session_id" --seconds 20 --output-dir "$demo_run_dir"
   ```

   Skrip menolak sesi yang tidak mempunyai baseline write dalam 15 detik terakhir. Tidak perlu mengganti password, key, broker atau firmware.
2. Ketika receiver berhenti, periksa `Sampel lokal` tetap tiap sekitar 2 detik dan ubah gas/suhu untuk menunjukkan output lokal tetap bekerja. Tunggu >10 detik nyata tanpa penerimaan baru: Grafana menjadi **Data terlambat — kondisi saat ini belum diketahui**. Nilai/waktu terakhir tetap tersedia, bukan dianggap normal saat ini.
3. Skrip menyalakan layanan kembali pada `finally`, menunggu sampai 110 detik nyata untuk write pemulihan, dan menyimpan `wokwi-faults.jsonl`. Cari sesi baru, counter awal, `STORED`, dan titik baru di Grafana. Jangan restart ESP32 sebagai bagian pemulihan normal.
4. Tunggu ACK terbaru lagi, **perbarui SID** bila berubah, lalu ulangi dengan pilihan `broker`. Serial boleh menunjukkan `TELEMETRY_DISCONNECTED` dan `TELEMETRY_CONNECT_FAILED` selama broker sengaja mati. Setelah pulih, SID baru wajib terbentuk dan data baru masuk.
5. Untuk menguji kegagalan write, ulangi dengan pilihan `influx`. Selama Influx mati, receiver mencatat `write_failed` dan tidak memberi ACK penyimpanan. Kueri Grafana dapat menampilkan error datasource sementara karena database mati; jangan memaksanya dianggap status stale. Sesudah pulih, tunggu titik/ACK baru. SID dapat tetap atau berganti sesuai timeout/renewal; yang diperiksa adalah write/ACK baru dan tidak ada replay sampel lama.
6. Setelah tiap skenario, periksa rentang grafik: data sebelum putus masih ada, gap tidak diisi nol/normal, dan sampel offline tidak dikirim ulang. Kembalikan 25°C/gas rendah dan tunggu ACK.

Tiga pilihan adalah gangguan layanan lab yang berbeda, **bukan pemutusan Wi-Fi fisik atau simulasi semua kegagalan jaringan**. Durasi skrip dibatasi 1–30 detik. Hasil `passed` skrip harus dibaca bersama capture Wokwi/Influx; jangan menjalankan perangkat kedua selama percobaan.

Pembaruan sesi normal terjadi pada umur endpoint **180 detik**, expiry **300 detik**. LXC mengirim perintah renewal terenkripsi saat jamnya lebih dahulu; client tetap melakukan handshake lengkap dengan pin, signature dan finished tags baru. Retry M1/M3 mengirim byte yang sama, dua kali dengan jeda 5 detik lokal sebelum nonce/M1 baru; duplikasi tidak memperpanjang TTL atau mereset counter. Tidak ada retry data sensor. Celah sekitar 12 detik virtual ketika signature bukan alasan menyebut sistem kehilangan fungsi alarm lokal.

## 8. Restart layanan dan periksa persistensi

Catat satu timestamp serta nilai/flag pada tabel Grafana. Biarkan rentang riwayat mencakup titik tersebut. Dari **Terminal B**:

```sh
cd /opt/lab-kimia-suhu
docker compose restart
docker compose up -d --wait --wait-timeout 120
cd /opt/lab-kimia-mqtt/infra/mqtt
docker compose restart
systemctl restart lab-kimia-pqc-session.service
```

Expected: Influx/Grafana sehat, receiver aktif, Wokwi membentuk sesi baru dan titik baru ber-ACK masuk. Timestamp/nilai titik sebelum restart tetap persis sama di tabel/grafik. Jalankan `STATE_OK` pada bagian 3 untuk kontrol state/histori lama. Jangan menjalankan `down -v`, reset bucket, atau menghapus volume. Restart layanan ini tidak membuktikan reboot seluruh LXC/Proxmox. Docker/receiver enabled dan policy restart telah diperiksa; reboot host belum diuji.

## 9. Demonstrasi confidentiality, integrity dan authentication

Untuk pengujian native, **Stop Wokwi lebih dahulu** dan selesaikan capture jika sedang merekam. Gunakan direktori hasil baru di **Terminal B**:

```sh
cd /opt/lab-kimia-mqtt
.venv/bin/python -m tools.telemetry.check_security --output-dir evidence/local/security-demo-20261115-01
```

Expected JSON akhir: `passed:true`, `cases:21`, `sessions:4`, `stored:8`. Hasil `security.json` berlabel **native-client on real MQTT/LXC**, bukan pembacaan sensor Wokwi. Delapan titik sintetis memakai device ID meja demo sehingga dapat muncul di Grafana sebagai 27.5°C/ADC 1234/normal. Jalankan Wokwi lagi bila ingin presentasi berakhir dengan data sensor asli.

Skrip sengaja mengganggu receiver, broker dan Influx sebentar serta memulihkannya pada `finally`. Ia tidak menghapus volume/token/histori. Jika `security.json` pada lokasi tujuan sudah ada, skrip berhenti **sebelum** mengganggu layanan; pilih nama run baru. Jangan mengubah file lama untuk membuat hasil terlihat baru.

| Aspek | Bukti yang dibuka | Kesimpulan yang boleh disampaikan |
|---|---|---|
| Confidentiality | `known_plaintext_absent_in_data_frames` dan subscriber independen menerima byte publish identik | Penanda JSON/teks sensor yang diuji tidak terlihat pada frame Data terenkripsi |
| Integrity | Mutasi counter/length/ciphertext/tag/padding ditolak; paket valid sesudahnya tetap diterima | Perubahan tidak menghasilkan balasan atau titik Influx pada jendela uji; tag palsu tidak memajukan replay counter |
| Authentication | Secret signature salah dengan public binding benar dan akun broker sah ditolak | Password MQTT saja tidak membuktikan kepemilikan identitas aplikasi; private key yang dipin diperlukan |
| Replay | Counter duplikat/lama, out-of-order dan SID sesi sebelumnya ditolak | Paket lama tidak ditulis ulang sebagai data baru |
| Pemulihan | M2/M4 sengaja diabaikan lalu retry; receiver/broker/Influx direstart | Pertukaran baru/retry yang sah dapat pulih, bukan bukti tahan semua DoS |

Tes pin server/signature server palsu dan batas nonce/expiry juga tersedia pada native C++:

```sh
cd /opt/lab-kimia-mqtt
make -C tools/session test
.venv/bin/python -m unittest tests.test_pqc_telemetry tests.test_telemetry_capture
.venv/bin/python -m tests.check_pqc_sensor_cycle
```

Expected saat versi panduan ini: `SESSION_NATIVE_RESULT` dengan **113 checks**, **12 tes Python OK**, dan PASS loop sensor PQC. Ini tes perilaku kode, bukan bukti sensor/entropy RNG hardware. Build berhasil saja juga bukan bukti autentikasi atau alur Wokwi.

Demo keamanan memakai frame aplikasi pada broker privat, **tidak memakai TLS atau pembandingan TLS sebagai perlindungan utama**. Tidak perlu menjalankan skrip/capture TLS dari arsip. Ketiadaan ACK tanpa kontrol positif bukan bukti serangan ditolak: bisa saja broker/DB mati. Di sini kontrol valid sebelum/sesudah, subscriber independen, journal dan query Influx membatasi kesimpulan. Kredensial MQTT dan metadata tetap terbuka karena transport biasa; tidak ada klaim kriptanalisis formal, audit, atau kepatuhan FN-DSA final.

## 10. Pindahkan dan validasi capture baru

Setelah Stop Wokwi dan Ctrl+C reader, buat folder hasil pada LXC sesuai bagian 7. Dari **PowerShell laptop** pada root repo:

```powershell
scp evidence/local/demo-pqc-20261115-01.txt root@10.34.211.141:/opt/lab-kimia-mqtt/evidence/local/demo-pqc-20261115-01/esp32-serial.txt
```

Di **Terminal B**, jika capture hanya run normal:

```sh
cd /opt/lab-kimia-mqtt
.venv/bin/python -m tools.telemetry.verify_capture evidence/local/demo-pqc-20261115-01/esp32-serial.txt --output evidence/local/demo-pqc-20261115-01/capture-validation.json
```

Jika run yang sama mencakup gangguan receiver/broker/Influx yang dicatat, gunakan **`--fault-test`** pada perintah itu. Mode tersebut mengizinkan `CONNECT_FAILED` yang diharapkan saat gangguan; panic/watchdog/LEDC tetap gagal, dan empat keadaan alarm serta semua ACK yang diklaim tetap harus cocok dengan journal/Influx/Grafana. Hasil menyatakan `capture_mode:nominal` atau `fault`; simpan bersama `wokwi-faults.jsonl`. Mode fault tidak berarti startup tanpa gangguan sudah lulus.

Expected ringkasan `verified:true`, `four_states:true`, `grafana:true`. Jumlah sampel berasal dari run baru, tidak harus 169. Periksa `unconfirmed_sent_frames`; jangan menghitungnya sebagai titik tersimpan. Tidak ada ACK berarti write belum terkonfirmasi, bukan kepastian database tidak menulis. Bukti TLS lama, log native, capture campuran beberapa reboot, atau screenshot titik historis saja tidak menggantikan bukti ESP32 baru.

Untuk lembar hasil, catat **waktu dan zona**, run ID/SID, langkah/stimulus, sampel/flag/label aktual, jumlah SENT/ACK/tidak terkonfirmasi, timestamp titik lama sebelum/sesudah restart, lokasi capture/journal/JSON, dan langkah yang belum dijalankan. Keluaran UTC pada JSON jangan diubah labelnya menjadi WIB; WIB adalah UTC+7.

## 11. Jika hasil belum sesuai

| Gejala | Periksa dan tindakan |
|---|---|
| TCP 1883 tidak terjangkau, state -2 | Rute/VPN laptop, Private Gateway, broker privat hidup; timeout bukan bukti kredensial ditolak |
| AUTHENTICATED belum muncul | Tetap tampilkan Wokwi, tunggu signature; periksa log receiver dan pin/identity existing; jangan menonaktifkan verifikasi |
| SENT tanpa STORED | Lihat `write_failed`, health Influx, expiry/rekey dan koneksi; jangan menyimpulkan seluruh SENT tersimpan |
| Grafana tidak berubah | Cocokkan SID/counter ACK, timestamp penerimaan baru, datasource/receiver; data lama atau kontrol native tidak membuktikan simulator aktif |
| Selalu alarm gas saat awal | Wokwi mungkin mengingat stimulus 400; turunkan slider sampai DOUT HIGH, bukan sekadar mengasumsikan angka 400 normal |
| Suhu invalid | Periksa DS18B20/pin/pull-up; alarm suhu sebelumnya ditahan, tidak ada publikasi suhu palsu 0°C |
| Sesi putus setelah Pause/background | Resume/tampilkan simulator dan tunggu handshake baru; jam LXC tidak ikut Pause, jangan mengganti algoritma/password |
| Fault script menolak baseline | Salin SID dari STORED terbaru (<15 detik nyata); update setelah rekey, jangan memakai SID contoh/bukti lama |
| Reader menunggu terus | Pastikan RFC2217 aktif sebelum Start, tidak ada dua simulator, dan port 4000 tidak dipakai sesi lama |
| `Evidence already exists` | Pilih direktori hasil baru; jangan menimpa bukti historis |
| Data terlambat setelah Stop | Expected setelah >10 detik tanpa titik baru; mulai Wokwi untuk memperoleh data terkini |

## 12. Naskah presentasi singkat dan penutupan

Urutan presentasi: jelaskan satu meja/sensor/ambang demo → tunjukkan MQTT TCP/1883 dan tiga peran algoritma → tunjukkan AUTHENTICATED/STORED serta empat keadaan alarm → gangguan terukur dan alarm lokal/stale/pemulihan → riwayat setelah restart → bukti keamanan berlabel native → nyatakan batas dan kembalikan kondisi normal. Buka [verifikasi tiket 07](verifikasi-pqc-tiket-07.md) untuk provenance bukti, bukan mengklaim semua file dibuat dalam satu run baru.

Setelah demo: Stop Wokwi, Ctrl+C reader, komentari lagi `rfc2217ServerPort`, lalu tutup preview/reload VS Code bila port belum lepas. Layanan LXC boleh tetap aktif; dashboard akan stale saat simulator berhenti. Jangan menghidupkan kembali Telegraf/TLS atau melakukan rollback kecuali pemilik memang memilih prosedur [rollback manual](operasi-pqc.md#rollback-manual).

Di PowerShell laptop, periksa sebelum pengguna melakukan push:

```powershell
git status --short
git diff --check
git check-ignore firmware/include/pqc_session_identity.h firmware/include/mqtt_diag_secrets.h firmware/.pio/build/pqc-telemetry/firmware.bin evidence/local/demo-pqc-20261115-01.txt
git ls-files --cached --ignored --exclude-standard
```

`check-ignore` harus menampilkan private paths tersebut; `ls-files --cached --ignored` harus kosong. Review juga **isi** file/capture baru terhadap key/password/token, bukan hanya aturan ignore. Raw key, `.env`, identity/header, binary/ELF dan baseline private tetap di lokasi ignored. Bukti publik hanya hasil yang diperiksa dan diberi provenance. **Commit/push GitHub dilakukan sendiri oleh pengguna.**
