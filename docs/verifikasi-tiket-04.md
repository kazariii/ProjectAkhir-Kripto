# Verifikasi tiket 04

Tanggal: 10 November 2026. Acuan: [04-koneksi-data-terlambat.md](../.scratch/monitoring-lab-kimia/issues/04-koneksi-data-terlambat.md). Penghambat tiket 03 sudah `done`. Seluruh acceptance criteria tiket 04 lulus; status `done`. Tidak ada `spec.md`, glosarium, atau ADR tambahan.

## Perilaku dan kepemilikan

- Loop Arduino tetap memiliki pembacaan DS18B20/MQ2, status alarm, LED dan buzzer. Tidak ada operasi Wi-Fi, DNS, TCP, TLS, MQTT atau penantian antrean pada jalur itu. DOUT diperiksa setiap iterasi; konversi suhu tetap asinkron dalam periode mulai 2.000 ms.
- Satu tugas FreeRTOS pada core 0 memiliki seluruh klien jaringan, termasuk inisialisasi, koneksi ulang Wi-Fi dan MQTT, keepalive serta publish. Koneksi sinkron PubSubClient/WiFiClientSecure hanya menahan tugas ini. Percobaan ulang dibatasi minimal 5.000 ms antarmulai; aritmetika selisih unsigned tetap bekerja saat `millis()` melingkar. Tidak ada dependensi atau layanan produksi baru. Biaya tambahan: stack tugas 8.192 byte dan antrean satu sampel di RAM saat runtime.
- Antrean FreeRTOS menyalin satu sampel lengkap dengan waktu monotonic pembacaan. Penulisan tidak menunggu; sampel terbaru menggantikan sebelumnya. Antrean dibuang selama putus/belum NTP dan setelah handshake selesai, termasuk handshake berhasil. Sampel berumur >=2 detik atau gagal publish tidak dicoba ulang. Tidak ada backlog offline, retained publish, isian normal, atau perubahan timestamp data lama.
- CA deployment, hostname DNS/SNI, port 8883, NTP dan username/password tetap digunakan saat tersambung kembali. Tidak ada `setInsecure`, perubahan izin broker, perubahan kredensial atau penghapusan volume.
- Jika alokasi antrean/tugas gagal, log memberi diagnosis dan monitoring lokal tetap berjalan.
- Grafana menambahkan **Waktu pengukuran terakhir diterima** berdasarkan timestamp Telegraf. Panel **Kondisi dan kesegaran data** menampilkan empat kondisi alarm hanya bila pengukuran terakhir masih terkini; setelah umur **>10 detik** menjadi **Data terlambat — kondisi saat ini belum diketahui**. Tepat 10 detik masih terkini. Penanda terlihat pada refresh berikutnya (default 2 detik), bukan timer perangkat.
- Status, waktu terakhir, serta angka terakhir memakai seluruh riwayat tersimpan dan waktu sekarang, terlepas dari pemilih rentang riwayat. Bucket yang belum menerima data secara eksplisit menampilkan **Belum ada data**. Sampel terakhir tanpa boolean alarm menampilkan **Status alarm tidak tersedia**; tidak mengambil Normal/status lain dari pesan lama. Angka terakhir tetap bisa ditinjau dengan penanda kesegaran di atasnya.
- Grafik memakai bucket agregasi kosong/null, `spanNulls=false` dan pemutusan garis untuk jeda >10 detik. Tidak ada `fill` nol/normal; tabel tetap menyimpan hanya pesan nyata. UID, measurement, datasource, volume dan riwayat lama dipertahankan.

## Bukti otomatis

| Pemeriksaan | Hasil dan batas |
| --- | --- |
| Loop firmware sebenarnya, hardware/waktu terkontrol | Lulus: koneksi ditahan selama 20 detik simulasi sambil loop sensor dijalankan oleh scheduler fixture; periode 2 detik, gas saja/suhu saja dan perintah LED/buzzer tetap mengikuti pembacaan. Ini bukan pengukuran penjadwalan ESP32 fisik. |
| Pemulihan jaringan pada loop host | Lulus: retry Wi-Fi/MQTT, hostname/CA/port/kredensial tetap, tidak replay sampel offline/kedaluwarsa/gagal publish, retry 5 detik dan rollover. Kegagalan alokasi antrean/tugas tidak mematikan alarm. |
| Regresi sensor/alarm | Lulus: konversi 750 ms dari timestamp setelah perintah, busy satu tick, timeout, sensor hilang, NaN, empat kondisi, latch suhu gagal dan pulih valid, monitoring tanpa konfigurasi. |
| Build ESP32 PlatformIO/espressif32 6.9.0 | SUCCESS; RAM statis 46.504/327.680 byte, flash 919.293/1.310.720 byte. Stack/antrean dialokasikan saat runtime. |
| C++11 telemetry | Lulus: boolean, empat kondisi, batas sensor/ADC dan kapasitas pesan. |
| Stack produksi terisolasi melalui MQTT/TLS | Lulus: bucket kosong, seluruh tujuh kueri Grafana, empat kondisi terkini, batas tepat 10 detik dan 10 detik +1 mikrodetik, rentang dashboard kemarin, umur >1 jam, timestamp terakhir tetap tersedia. |
| Putus/pulih broker lokal dan restart | Lulus: Normal lama menjadi terlambat memakai jam server sebenarnya, tidak ada titik selama putus, histori identik setelah restart, titik baru masuk, grafik memiliki null pada jeda, dan firmware lama tanpa boolean tidak memakai keadaan sebelumnya. Broker Mosquitto/CA tes, bukan EMQX/Wokwi. |

Perintah dari akar repository:

```powershell
& ./tests/run-telemetry.ps1
python tests/check_firmware_cycle.py
python -m platformio run --project-dir firmware
python tests/check_monitoring_stack.py
```

Tes stack memakai nama proyek/volume/port sementara dan akun/CA acak, tanpa membaca `.env` pemilik. Resource yang dibersihkan hanya resource tes itu. Pemakaian `option now` pada pengujian batas waktu tidak mengubah kueri produksi; pengujian putus broker juga memakai jam nyata.

## Demo Wokwi → EMQX → layanan lokal

Firmware baru dikompilasi dan dijalankan di proyek Wokwi web yang sudah berisi konfigurasi pemilik. Tidak ada kredensial baru yang diunggah atau dipublikasikan. Dashboard lokal dimuat ulang melalui provisioning tanpa menghapus volume.

Gangguan MQTT disengaja menggunakan klien tes lokal yang **tidak publish**, memakai client ID `esp32-meja01` yang sama dengan simulator. Broker memutus sesi sebelumnya ketika ID diambil alih. Pengulangan takeover mempertahankan gangguan saat firmware mencoba kembali; setelah proses tes dihentikan, firmware boleh menyambung kembali secara otomatis. Ini gangguan sesi MQTT, bukan pemutusan Wi-Fi fisik, pencabutan akun, atau penghentian deployment. Pesan log handshake berhasil selama takeover tidak membuktikan pengiriman berhasil; InfluxDB menjadi bukti penerimaan.

Hasil aktual berikut memakai WIB (UTC+7), 10 November 2026:

| Tahap | Bukti |
| --- | --- |
| Sebelum gangguan | Grafana Normal pada 25 Celsius/1039 ADC; waktu penerimaan bertambah. Pesan terakhir sebelum jeda diterima **20:17:01,036259308**. |
| Saat putus | Grafana **Data terlambat — kondisi saat ini belum diketahui**, waktu terakhir tetap 20:17:01. InfluxDB tidak bertambah selama alarm offline. |
| Gas naik saat putus | DOUT LOW, suhu 25/2176 ADC, `gas_alarm=true`, `temperature_alarm=false`, LED terlihat menyala dan serial LED/buzzer ON. Sampel lokal `52422`, `54422`, `56422` ms; tidak diterima penyimpanan. Gas diturunkan ke HIGH/506 ADC, output OFF. |
| Suhu naik saat putus | Gas normal, suhu valid 40/506 ADC, `gas_alarm=false`, `temperature_alarm=true`, serial LED/buzzer ON dan LED menyala. Sampel lokal `62422`, `64422`, `66422` ms. Jadwal konversi tetap berjarak 2.000 ms selama percobaan koneksi ulang. |
| Pulih tanpa restart ESP32 | Pesan pertama diterima **20:18:45,560506237**, suhu 40/506 ADC dengan alarm suhu aktif; Grafana **Peringatan suhu**. Firmware tetap memakai CA/hostname/kredensial yang sama. |
| Normal kembali | Suhu diturunkan ke 25; kedua boolean false, LED/buzzer OFF, titik baru dan label **Normal** terlihat. Screenshot final menampilkan penerimaan 20:20:57. |
| Integritas riwayat | Jeda aktual **104,524247 detik** antara dua pesan di atas. Seluruh **217** titik dalam capture saat putus masih identik pada kueri seluruh riwayat setelah pulih; capture awal juga tetap utuh. Sampel gas tinggi offline tidak dibackfill. |

Capture awal/saat putus memakai rentang satu jam relatif; pemeriksaan akhir memakai seluruh riwayat agar titik yang keluar dari pemilih waktu tidak keliru dianggap terhapus. `demo-summary.json` menyimpan perbandingan timestamp/nilai, dan CSV menyimpan presisi aslinya. Beberapa timestamp penerimaan bisa berdekatan karena gateway membatch lalu lintas; cadence sensor dinilai dari waktu monotonic serial, bukan selisih penerimaan tersebut.

Prosedur pengulangan:

1. Perbarui `sketch.ino` dari `firmware/src/main.cpp`; `telemetry.h`, `monitoring.h`, model dan diagram tetap tersedia sesuai [panduan](jalur-suhu.md). Jalankan simulator dan tunggu pesan baru benar-benar tersimpan. Pada suhu 25 Celsius dan DOUT gas HIGH (alarm tidak aktif), dashboard harus Normal dengan waktu penerimaan yang bertambah.
2. Putus sesi MQTT pada lingkungan demo milik sendiri, sambil mempertahankan simulator dan sensor berjalan. Contoh yang diuji: klien lokal ber-TLS dengan akun ESP32 dan client ID yang sama, tanpa publish, mengambil alih sesi berulang. Jangan memakai ID Telegraf karena itu hanya memutus penerima, bukan koneksi ESP32.
3. Setelah >10 detik tanpa pesan masuk, periksa label **Data terlambat** dan waktu penerimaan yang berhenti. Naikkan stimulus MQ2 sampai DOUT LOW: LED/buzzer harus ON meski data dashboard belum bertambah. Turunkan gas sampai HIGH: output harus OFF.
4. Dengan gas normal, naikkan suhu ke 40 Celsius. Setelah konversi lokal valid, LED/buzzer harus ON. Catat serial `Sampel lokal` dan cadence konversi; tidak boleh menafsirkan label terlambat sebagai kondisi normal.
5. Hentikan klien pengganggu tanpa restart ESP32 atau mengganti konfigurasinya. Tunggu handshake dan sampel baru. Cocokkan suhu 40/boolean suhu aktif di InfluxDB serta label **Peringatan suhu**. Turunkan suhu ke 25 untuk pemulihan Normal.
6. Bandingkan CSV sebelum/saat/sesudah. Titik lama harus identik; rentang gangguan tetap kosong dan sampel lokal offline tidak dibackfill. Jangan menghapus volume.

Keterbatasan: percobaan awal gateway publik Wokwi gagal membuka `wss://netwi.wokwi.com/`; restart simulator memulihkannya sebelum pengujian takeover. Kecepatan browser berada di bawah waktu nyata; 2.000 ms waktu simulasi tidak menjamin penerimaan tiap 2 detik nyata, sehingga penanda >10 detik juga bisa muncul ketika simulator terlalu lambat. Alarm lokal tetap memakai waktu simulasi. Suara buzzer tidak direkam secara akustik; perintah `tone`/`noTone`, serial dan LED diamati. Ambang tetap untuk demonstrasi simulasi, bukan standar keselamatan.

## Bukti lokal

Log, screenshot, CSV dan skrip pengganggu/capture tersedia di `evidence/local/ticket-04/` yang diabaikan Git:

- `grafana-before.jpg`, `grafana-stale.jpg`, `grafana-recovered.jpg`, `grafana-normal.jpg` dan snapshot teks terkait.
- `wokwi-before.jpg`, `wokwi-offline-gas.jpg`, `wokwi-offline-suhu.jpg`, `wokwi-recovered.jpg`, `wokwi-normal.jpg`, serta log serial tahapan dan `serial-wokwi.txt`.
- `before-influx.csv`, `offline-influx.csv`, `after-influx.csv`, `demo-summary.json`.
- `sketch-tested.ino`: sumber dari editor Wokwi dicocokkan persis dengan firmware lokal setelah normalisasi akhir baris.

Skrip lokal membaca konfigurasi yang sudah ada dan tidak mencetak nilainya. Berkas ini bukan layanan atau dependensi aplikasi. Proses takeover sudah dihentikan; simulator dan layanan lokal dibiarkan berjalan normal. Tidak ada klaim pengujian sensor fisik atau suara akustik.

Rujukan perilaku platform: [tugas FreeRTOS ESP32 dan ukuran stack dalam byte](https://docs.espressif.com/projects/esp-idf/en/latest/esp32/api-reference/system/freertos_additions.html), [pengaturan null dan disconnect Grafana](https://grafana.com/docs/grafana/latest/visualizations/panels-visualizations/visualizations/time-series/).
