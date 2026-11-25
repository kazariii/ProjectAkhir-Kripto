# Menjalankan jalur gas, suhu, dan alarm

> **Arsip penyiapan MQTT/TLS lama.** Untuk jalur utama revisi tugas gunakan [operasi MQTT/PQC](operasi-pqc.md). Rangkaian/sensor tetap dipakai, tetapi konfigurasi cloud, CA dan Telegraf di bawah bukan transport utama lagi.

Untuk urutan presentasi dari awal hingga pengujian keamanan, gunakan [panduan demo proyek lengkap](demo-proyek-privat.md). Dokumen ini menjadi rujukan terperinci untuk konfigurasi, rangkaian, dan penyiapan Wokwi.

Implementasi tiket 01–04 tersedia. Demo EMQX/Wokwi sampai dashboard telah diverifikasi; pemasangan baru memerlukan konfigurasi pemilik. Hasil aktual tiket 01 dicatat di [verifikasi-tiket-01.md](verifikasi-tiket-01.md); pengujian gas ada di [verifikasi-tiket-02.md](verifikasi-tiket-02.md), sedangkan perilaku dan bukti alarm ada di [verifikasi-tiket-03.md](verifikasi-tiket-03.md).

## Prasyarat

- Docker Desktop dengan mesin Linux containers berjalan dan Docker Compose v2.
- Python 3.11 serta PlatformIO Core 6.1.19 (`python -m pip install platformio==6.1.19`).
- Editor VS Code/PlatformIO untuk build. Wokwi web menjadi pilihan simulasi tanpa pembelian; gunakan hanya akun demonstrasi dengan izin topik terbatas. Wokwi untuk VS Code dapat meminta lisensi sendiri; jangan membeli paket untuk mengikuti panduan ini.
- Pemilik akun EMQX Cloud melakukan pendaftaran, verifikasi email/akun yang diminta layanan, serta menyetujui ketentuan layanan sendiri. Repository tidak menyertakan akun atau kredensial cloud.
- Internet untuk mengunduh dependensi, NTP, dan koneksi MQTT/TLS.

Versi layanan ditetapkan: `telegraf:1.40.3`, `influxdb:2.9.1`, dan `grafana/grafana:13.3.0`. Compose juga mengunci digest manifest yang diperiksa pada 10 November 2026. Versi ini dipilih agar pengulangan memakai rilis yang sama; InfluxDB tetap berada pada seri 2.x.

## EMQX Cloud Serverless tanpa pengeluaran

1. Masuk ke konsol EMQX Cloud, buat proyek bila diperlukan, lalu buat deployment dengan paket **Serverless**.
2. Pertahankan **Spend Limit = 0** dan periksa nilainya kembali di ringkasan sebelum Deploy. Jangan mengaktifkan limit positif, metode pembayaran, atau opsi melanjutkan penagihan. Batas nol memakai kuota gratis; deployment dapat berhenti ketika kuota habis.
3. Setelah status Running, salin **Address** berbentuk hostname DNS dan port MQTT/TLS `8883`. Jangan menggantinya dengan alamat IP karena nama server harus cocok dengan sertifikat.
4. Unduh **CA Certificate** dari deployment yang sama. CA bersifat publik, tetapi gunakan salinan yang benar untuk deployment tersebut.
5. Pada **Client Authentication / Default Authentication**, buat dua username/password berbeda: `esp32-meja01` dan `telegraf-meja01`. Pastikan koneksi tanpa username/password ditolak. Jangan membuat akun superuser atau aturan autentikasi yang melewati pemeriksaan izin.
6. Pada **Client Authorization / Default Authorization**, gunakan aturan berikut. Kolom username merujuk akun contoh di atas, bukan password.

| Bagian | Subjek | Topik | Operasi | Izin |
| --- | --- | --- | --- | --- |
| Username | `esp32-meja01` | `lab/kimia/meja01/telemetry` | Publish | Allow |
| Username | `telegraf-meja01` | `lab/kimia/meja01/telemetry` | Subscribe | Allow |
| All Users | semua pengguna | `#` | Publish and Subscribe | Deny |

7. Hapus aturan Allow lain yang terlalu luas, termasuk pada tab **Client ID**. Aturan username/client ID dievaluasi sebelum All Users; aturan Allow berdasarkan client ID dapat melewati pembatasan username. Aturan All Users deny `#` menjadi fallback terakhir. Jangan mengandalkan mode blacklist bawaan. Serverless tidak menyediakan tombol perubahan mode whitelist satu klik.
8. Simpan bukti konfigurasi tanpa menampilkan password. Catat hostname, jenis paket, Spend Limit 0, aturan izin, dan hasil koneksi aktual pada lembar verifikasi.

Dokumentasi resmi: [pembuatan Serverless dan Spend Limit](https://docs.emqx.com/en/cloud/latest/create/serverless.html), [urutan aturan serta fallback deny](https://docs.emqx.com/en/cloud/latest/deployments/default_authz.html).

## Kontrak data

Topik tetap `lab/kimia/meja01/telemetry`. Identitas perangkat tetap `esp32-meja01`.

```json
{"device_id":"esp32-meja01","temperature_c":27.5,"gas_raw":1200,"gas_alarm":false,"temperature_alarm":false}
```

`temperature_c` adalah angka derajat Celsius. `gas_raw` adalah integer ADC 12-bit (0–4095) dari AOUT MQ2 setelah penurunan level tegangan. Nilainya menunjukkan level relatif, bukan konsentrasi LPG terkalibrasi atau ppm pengukuran nyata. Atribut/slider `ppm` milik Wokwi hanya stimulus simulasi dan tidak disalin atau dikonversi menjadi ppm pada telemetry.

Firmware memulai konversi suhu setiap 2.000 ms, lalu mengambil ADC dan status MQ2 untuk pesan ketika konversi suhu selesai. DOUT juga diperiksa di tiap iterasi loop untuk alarm lokal. Pembacaan gas tidak menambahkan jeda pada periode ini. DOUT aktif LOW: serial mencetak `ambang=terlampaui (DOUT=LOW)` atau `ambang=belum terlampaui (DOUT=HIGH)`. DOUT LOW langsung mengaktifkan `gas_alarm`, tanpa menunggu konversi suhu. `temperature_alarm` aktif pada suhu valid >=40 Celsius dan hanya kembali tidak aktif setelah suhu valid <40 Celsius. LED merah GPIO 25 dan buzzer GPIO 26 (nada 2 kHz) aktif bila salah satu alarm aktif. Pembacaan gagal mempertahankan status suhu sebelumnya. Saat boot belum ada suhu valid, alarm suhu belum aktif dan belum ada pesan normal yang dikirim. Status tidak disimpan melewati restart ESP32; pembacaan baru diperlukan setelah boot. Jika suhu gagal/belum selesai atau ADC berada di luar rentang, seluruh sampel ditolak dengan diagnosis; firmware tidak menciptakan suhu atau gas pengganti.

Telegraf memakai parser `json_v2`, field float `temperature_c`, field int `gas_raw`, field boolean `gas_alarm` serta `temperature_alarm`, tag wajib `device_id`, dan tanpa `timestamp_path`. Keempat field disimpan pada measurement `suhu` yang sama dengan timestamp penerimaan pesan yang sama. Nama measurement/datasource/UID dashboard lama dipertahankan agar riwayat suhu tetap terbaca. `gas_raw` dan kedua field alarm opsional hanya pada parser untuk kompatibilitas firmware tiket 01–02 saat pembaruan; field yang tidak ada tidak disimpan sebagai nol/false. Firmware baru selalu mengirim keempatnya. Panel alarm hanya menggabungkan status pada timestamp pesan yang sama dan tidak mengisi riwayat lama dengan status normal buatan. MQTT tetap menjadi jalur komunikasi sensor; HTTP internal Docker menghubungkan penerima ke penyimpanan/dashboard.

## Rangkaian MQ2 dan batas tegangan

DS18B20 tetap di GPIO 4 dengan pull-up 4,7 kΩ ke 3,3 V. MQ2 memakai VCC 5 V (`VIN` papan Wokwi) dan GND bersama ESP32. AOUT menuju GPIO 34 (ADC1, tetap tersedia saat Wi-Fi aktif); DOUT menuju GPIO 27 sebagai input digital. Firmware mengatur ADC 12-bit dan atenuasi `ADC_11db`.

Kedua keluaran MQ2 melewati penurun level, bukan langsung ke GPIO. Untuk rangkaian fisik, gunakan **masing-masing satu pembagi 10 kΩ/15 kΩ**:

```text
AOUT atau DOUT MQ2 ── 10 kΩ ──┬── GPIO 34 atau GPIO 27
                             15 kΩ
                              │
                             GND
```

Tegangan pada GPIO = tegangan keluaran × 15/(10+15): maksimum nominal 5 V menjadi 3,0 V. LOW tetap LOW dan HIGH nominal menjadi 3,0 V. Jangan menghubungkan keluaran 5 V langsung ke ESP32, termasuk DOUT. Angka ADC tidak diasumsikan linier atau terkalibrasi terhadap konsentrasi.

Wokwi tidak mendukung pembagi resistor pada komponen analog. Karena itu `diagram.json` memakai satu **model simulasi** `mq2-level`, yang menerapkan rasio 0,6 untuk AOUT dan meneruskan logika DOUT tanpa inversi. Model terdiri dari `mq2-level.chip.c`, `mq2-level.chip.json`, dan binary `mq2-level.chip.wasm` untuk VS Code. Model ini menggantikan dua pembagi pada simulator saja; bukan komponen tambahan untuk perangkat fisik. Perbedaan model ADC simulator/perangkat nyata membuat angka hasil keduanya tidak harus sama.

Alasan dan API resmi: [MQ2 Wokwi, pin dan LOW saat ambang terlampaui](https://docs.wokwi.com/parts/wokwi-gas-sensor), [keterbatasan resistor analog](https://docs.wokwi.com/parts/wokwi-resistor), [ADC1 dan konflik ADC2/Wi-Fi](https://docs.espressif.com/projects/esp-idf/en/v4.4.7/esp32/api-reference/peripherals/adc.html), [resolusi/atenuasi Arduino ESP32](https://docs.espressif.com/projects/arduino-esp32/en/latest/api/adc.html).

## Alarm demonstrasi

LED merah: GPIO 25 → resistor 220 Ω → anode `A`, cathode `C` → GND. Buzzer piezo Wokwi: GPIO 26 → pin positif `2`, pin negatif `1` → GND. Pin sensor dan model penurun level tetap sama. Rangkaian ini untuk simulasi; buzzer fisik yang membutuhkan arus melebihi kemampuan GPIO memerlukan penggerak yang sesuai. Acuan pin: [LED Wokwi](https://docs.wokwi.com/parts/wokwi-led), [buzzer Wokwi](https://docs.wokwi.com/parts/wokwi-buzzer).

Ambang suhu **40 Celsius** dan atribut ambang MQ2 **4,4 V sebelum penurunan level** adalah **pengaturan demonstrasi simulasi, bukan standar keselamatan atau pembuktian deteksi kebakaran**. Alarm gas mengikuti DOUT, bukan perbandingan `gas_raw` terhadap angka ADC tertentu. Keadaan yang ditampilkan: Normal, Peringatan gas, Peringatan suhu, Peringatan gas dan suhu. Tabel riwayat menampilkan waktu, suhu, ADC, kedua status, dan keadaan dari pesan yang sama.

Keputusan alarm dibuat di ESP32; tidak ada perintah kendali dari Grafana. Pemantauan lokal juga berjalan bila konfigurasi jaringan belum diisi. Saat suhu gagal, pesan baru tidak dikirim dan Grafana mempertahankan status terakhir yang diterima; gas lokal tetap dapat berubah. Tiket 04 memisahkan tugas jaringan FreeRTOS (core 0) dari loop sensor/alarm. Koneksi DNS/TCP/TLS/MQTT boleh menunggu pada tugas jaringan tanpa menahan loop lokal. Wi-Fi/MQTT dicoba kembali tiap minimal 5 detik, dengan CA, hostname, port dan kredensial yang sama. Antrean salinan satu sampel menggantikan nilai sebelumnya, dibersihkan saat terputus/selesai handshake, dan menolak sampel berumur >=2 detik; tidak ada antrean offline atau pengiriman ulang. Jika alokasi antrean/tugas gagal, alarm lokal tetap berjalan dengan diagnosis. Detail bukti dan gangguan simulator: [verifikasi-tiket-04.md](verifikasi-tiket-04.md).

## Konfigurasi lokal dan rahasia

Semua perintah berikut dijalankan dari akar repository menggunakan PowerShell, kecuali bila disebutkan lain.

```powershell
Copy-Item .env.example .env
Copy-Item firmware/include/secrets.example.h firmware/include/secrets.h
```

Isi `.env` dengan hostname, akun Telegraf, dan nilai administrator lokal. Isi `firmware/include/secrets.h` dengan hostname yang sama, akun ESP32, dan CA lengkap dari deployment (termasuk baris BEGIN/END CERTIFICATE). Simpan unduhan CA itu juga sebagai `infra/certs/emqx-ca.pem`. Jangan menambahkan `ssl://`, nomor port, atau jalur ke nilai `MQTT_HOST`.

Password dan token diisi pemilik akun; jangan kirim nilainya melalui chat, Git, tangkapan layar, atau laporan. Buat nilai acak terpisah melalui pengelola password; token awal InfluxDB minimal 64 karakter hex dan password minimal 20 karakter hex cukup untuk demo. Salin nilai hanya ke berkas lokal. Nilai `.env` adalah konfigurasi awal: mengganti token/password setelah volume terinisialisasi memerlukan pembaruan akun/token layanan, bukan sekadar mengubah `.env`.

Gunakan password/token demonstrasi acak berupa karakter heksadesimal agar aman melewati substitusi konfigurasi TOML/YAML. Nilai berbeda dipakai untuk masing-masing akun MQTT, administrator InfluxDB, token InfluxDB, dan administrator Grafana. Berkas `.env`, `firmware/include/secrets.h`, CA lokal, hasil build `.pio`, serta `evidence/local/` yang mungkin memuat rahasia dikecualikan dari Git. Jangan menjalankan `docker compose config` tanpa `--quiet` ketika kredensial sudah diisi karena hasil render memuat nilainya.

TLS ESP32 harus memakai CA deployment dan hostname DNS. Sinkronisasi NTP dilakukan sebelum koneksi TLS agar pemeriksaan masa berlaku sertifikat memiliki waktu yang masuk akal. Telegraf menggunakan URL `ssl://<hostname>:8883`, CA yang sama, dan `insecure_skip_verify = false` agar rantai CA serta identitas server diperiksa.

## Menjalankan layanan dan firmware

```powershell
docker info
docker compose config --quiet
docker compose up -d
docker compose ps
docker compose logs --tail 50 telegraf
```

`docker info` harus menunjukkan server Docker tersedia. Jika layanan belum berjalan, mulai Docker Desktop terlebih dahulu. Jangan meneruskan dengan asumsi rendering Compose berarti layanan sudah diuji. Telegraf mulai setelah InfluxDB sehat. Kegagalan CA, DNS, atau autentikasi akan terlihat pada log; perbaiki konfigurasi sumbernya dan jangan menonaktifkan verifikasi TLS.

Build dari subdirektori firmware:

```powershell
Push-Location firmware
python -m platformio run
Pop-Location
```

Tanpa `secrets.h`, build tetap dapat memeriksa kompilasi, tetapi pengiriman jaringan dinonaktifkan dengan diagnosis konfigurasi belum diisi; sensor dan alarm lokal tetap berjalan. Hasil build bukan bukti koneksi cloud.

Pilih salah satu cara simulasi:

- **Wokwi web tanpa pembelian — ikuti dari langkah 1:**

   Saat diminta menyalin isi berkas: buka tautan berkas lokal, klik area teks, tekan **Ctrl+A → Ctrl+C**, lalu klik area kode tab tujuan di Wokwi dan tekan **Ctrl+A → Ctrl+V**. Nama di sebelah kiri tabel adalah sumber di komputer; nama di sebelah kanan adalah tab tujuan di Wokwi.

   1. **Buat proyek ESP32.** Buka [proyek ESP32 baru](https://wokwi.com/projects/new/esp32). Akan terlihat tab `sketch.ino`, `diagram.json`, dan `Library Manager`.

   2. **Isi program utama.** Salin seluruh isi [main.cpp](../firmware/src/main.cpp) ke tab `sketch.ino`. Nama tab di Wokwi tetap `sketch.ino`.

   3. **Tambahkan berkas telemetry.** Gunakan menu **New File** pada editor untuk membuat berkas bernama persis `telemetry.h`. Salin seluruh isi [telemetry.h](../firmware/include/telemetry.h) ke berkas tersebut.

   4. **Tambahkan aturan monitoring dan konfigurasi ESP32.** Buat `monitoring.h` melalui menu **New File**, lalu salin isi [monitoring.h](../firmware/include/monitoring.h). Buat berkas baru bernama `secrets.h`. Salin isi `firmware/include/secrets.h` yang sudah diisi pada langkah konfigurasi lokal. Pastikan hostname, password akun `esp32-meja01`, dan CA sudah menggantikan semua penanda `ISI_...`. `WIFI_SSID` tetap `Wokwi-GUEST` dan `WIFI_PASSWORD` tetap kosong. Jangan membagikan proyek yang berisi password aktif.

   5. **Buat komponen mq2-level.** Di area rangkaian, klik tombol **+** → **Custom Chip**. Isi nama **mq2-level**, pilih bahasa **C**, lalu klik **Create Chip**. Wokwi membuat dua tab baru. Ini model penurun level untuk MQ2 pada simulator. [Petunjuk resmi Custom Chip](https://docs.wokwi.com/chips-api/getting-started).

   6. **Isi dua tab komponen tadi** dengan menyalin isi sumber berikut:

      | Berkas sumber di komputer | Tab tujuan di Wokwi |
      | --- | --- |
      | [mq2-level.chip.c](../firmware/mq2-level.chip.c) | `mq2-level.chip.c` |
      | [mq2-level.chip.json](../firmware/mq2-level.chip.json) | `mq2-level.chip.json` |

   7. **Pasang rangkaian lengkap.** Buka tab `diagram.json`, hapus isinya, lalu salin seluruh isi [diagram.json](../firmware/diagram.json). Rangkaian ESP32, DS18B20, MQ2, mq2-level, LED, dan buzzer beserta kabelnya berasal dari berkas ini; tidak perlu menggambar kabel satu per satu.

   8. **Tambahkan pustaka.** Buka tab **Library Manager**, klik **+**, cari dan pilih **PubSubClient**. Ulangi untuk **OneWire** dan **DallasTemperature**. Setelah tab `libraries.txt` muncul, ganti seluruh isinya dengan [libraries.txt](../firmware/libraries.txt), yaitu:

      ```text
      PubSubClient@2.8
      OneWire@2.3.8
      DallasTemperature@4.0.6
      ```

      Penulisan `@versi` mengunci versi pustaka. [Petunjuk resmi Library Manager](https://docs.wokwi.com/guides/libraries).

   9. **Periksa berkas.** Proyek web harus memuat delapan berkas berikut pada tingkat yang sama:

      ```text
      sketch.ino
      telemetry.h
      monitoring.h
      secrets.h
      diagram.json
      libraries.txt
      mq2-level.chip.c
      mq2-level.chip.json
      ```

   10. **Jalankan simulasi.** Klik tombol **Play** di area rangkaian dan tunggu kompilasi selesai. Wokwi web mengompilasi program serta model C secara otomatis. Buka serial monitor; hasil yang diharapkan adalah `MQTT/TLS tersambung: CA dan hostname diverifikasi`, kemudian baris `Terkirim` dengan nilai sensor. Jika muncul `Konfigurasi belum diisi`, periksa kembali langkah 4. Catat keluaran aktual; keberhasilan build lokal PlatformIO belum membuktikan simulasi web atau koneksi cloud berhasil.

- **Wokwi untuk VS Code jika akses/lisensi sudah tersedia:** buka direktori `firmware` sebagai folder workspace, build dahulu, lalu jalankan **Wokwi: Start Simulator**. `wokwi.toml` menunjuk hasil build lokal pada `.pio/build/esp32dev/`. Jangan membuka akar repository sebagai workspace simulator karena jalur konfigurasi berpusat pada folder firmware. Pembelian lisensi tidak diperlukan untuk mengikuti jalur web di atas.

Binary model untuk VS Code sudah disertakan. Bila sumber model berubah, kompilasi ulang dari folder `firmware` memakai `wokwi-cli chip compile mq2-level.chip.c -o mq2-level.chip.wasm` (diperiksa dengan CLI 0.29.1). CLI mengunduh WASI-SDK serta `wokwi-api.h`; header hasil unduhan diabaikan Git. Lihat [pembuatan Custom Chip web](https://docs.wokwi.com/chips-api/getting-started) dan [kompilasi model dengan CLI](https://github.com/wokwi/wokwi-cli#custom-chip-compilation).

Pada serial monitor 115200 baud, tunggu Wi-Fi/NTP dan diagnosis MQTT/TLS tersambung. Baris `Konversi suhu dimulai ms=...` mestinya berjarak sekitar 2.000 ms saat tersambung, bukan 2.750 ms. Baris `Terkirim` menampilkan payload dan waktu monotonic untuk memeriksa interval. PubSubClient menggunakan publish QoS 0; hasil true berarti diterima stack klien, sehingga bukti penerimaan broker tetap harus diperiksa melalui Telegraf/dashboard.

Buka [Grafana lokal](http://localhost:3000), masuk dengan `GRAFANA_USERNAME`/`GRAFANA_PASSWORD`, lalu pilih folder **Lab Kimia** → **Gas dan suhu lingkungan meja praktikum 01**. Datasource dan tujuh panel dibuat dari provisioning: kondisi/kesegaran, waktu penerimaan terakhir, dua nilai terakhir, dua grafik historis terpisah, dan tabel riwayat pengukuran beserta alarm. Kondisi dan waktu terakhir memakai seluruh riwayat tersimpan serta waktu sekarang, terlepas dari pemilih rentang grafik. Setelah >10 detik tanpa pesan, status menjadi **Data terlambat — kondisi saat ini belum diketahui**; tepat 10 detik masih terkini. Bucket kosong menampilkan **Belum ada data**. Angka suhu/ADC terakhir tetap bisa ditinjau, tetapi tidak menjadi bukti kondisi terkini. Data lama tanpa boolean tidak dianggap Normal. Grafik mempertahankan bucket kosong dan memutus garis untuk jeda >10 detik; tidak ada isian nol/normal buatan. Gas memakai satuan `ADC`, suhu Celsius. Dashboard memperbarui setiap 2 detik; flush Telegraf, jaringan, dan interval kueri dapat menambah jeda. Halaman [InfluxDB lokal](http://localhost:8086) tersedia untuk memeriksa data menggunakan akun InfluxDB. Setelah memperbarui konfigurasi dari tiket 01/02, jalankan `docker compose restart telegraf grafana` lalu perbarui firmware; jangan hapus volume.

## Pengulangan demo dan persistensi

1. Siapkan deployment dan dua akun MQTT beserta aturan izin di atas.
2. Isi konfigurasi lokal dari template dan CA deployment.
3. Jalankan layanan dan simulator dengan langkah di atas.
4. Diagram berisi DQ ke GPIO 4, VCC ke 3,3 V, GND ke GND, serta resistor pull-up 4,7 kΩ antara DQ dan 3,3 V.
5. Buka Grafana lokal, lihat nilai terbaru dan grafik historis. Ubah slider DS18B20 dari 25 ke 35 derajat Celsius dan catat perubahan di serial serta dashboard.
6. Uji pembacaan gagal dengan memutus kabel DQ pada salinan diagram demonstrasi. Periksa diagnosis serial dan pastikan tidak ada titik -127, NaN, nilai di luar rentang sensor, atau nilai startup yang belum dikonversi.
7. Catat beberapa titik suhu beserta waktu penerimaan. Jalankan `docker compose restart`, tunggu layanan pulih, dan periksa titik sebelumnya tetap ada serta titik baru bertambah. Untuk memeriksa pembuatan ulang container, gunakan `docker compose down` lalu `docker compose up -d`; **jangan** memakai opsi `-v` karena itu menghapus volume dan riwayat.
8. Catat hasil aktual, waktunya, dan lokasi bukti. Langkah yang belum dilakukan tetap ditandai belum diverifikasi.

Untuk tiket 04, ikuti [demo gangguan dan pemulihan](verifikasi-tiket-04.md). Untuk tiket 03, ikuti [demo empat keadaan dan pemulihan](verifikasi-tiket-03.md#demo-wokwi-dan-emqx). Untuk tiket 02, ikuti juga [skenario gas naik/suhu tetap, suhu naik/gas tetap, dan restart](verifikasi-tiket-02.md#demo-wokwi-dan-emqx).

Wokwi memakai `Wokwi-GUEST` tanpa password. Gateway publik menyediakan akses keluar ke cloud dan tidak menyediakan akses ke layanan localhost komputer. Karena itu broker jalur utama tetap EMQX Cloud. Jangan mengunggah kredensial permanen ke proyek Wokwi publik; gunakan akun demonstrasi sementara, jangan bagikan proyek yang memuat kredensial, dan hapus/rotasi kredensial sesudah demo.

Firmware menolak NaN, infinity, -127, nilai di luar -55 sampai 125 derajat Celsius, serta hasil sebelum konversi selesai. Nilai 85 derajat Celsius setelah konversi tetap valid; sentinel startup dicegah dengan tidak membaca sebelum konversi. Dokumentasi Wokwi menyebut keterbatasan DallasTemperature pada tepat -55 derajat Celsius; jika simulator/library melaporkannya gagal, diagnosis dan penolakan lebih aman daripada menciptakan suhu pengganti. Gangguan konversi tidak diterbitkan sebagai pesan normal. Nilai Grafana lama tidak membuktikan pemulihan pembacaan; pastikan titik baru terlihat setelah kabel dipasang kembali.

## Pemeriksaan lokal yang dapat diulang

```powershell
python -m platformio pkg install --global --tool platformio/toolchain-gccmingw32
& ./tests/run-telemetry.ps1
python tests/check_firmware_cycle.py
python tests/check_telegraf_parser.py --telegraf C:/lokasi/telegraf.exe
# Alternatif parser melalui image Docker yang dikunci di Compose:
python tests/check_telegraf_parser.py --docker
node tests/check_mq2_level.cjs
python tests/check_monitoring_stack.py
```

Gunakan Telegraf 1.40.3 untuk pemeriksaan parser. Skrip mengambil blok parser produksi dan mengganti input layanan MQTT dengan berkas sementara. Hasilnya membuktikan format field/tag serta waktu penerimaan parser, belum membuktikan koneksi MQTT/TLS atau penyimpanan/dashboard. Jangan memakai `telegraf --test` pada konfigurasi MQTT service input untuk menyimpulkan pesan cloud berhasil diterima.

Uji `check_monitoring_stack.py` memerlukan Docker dan OpenSSL (salinan Git for Windows otomatis ditemukan). Uji ini memakai Compose produksi dengan nama proyek/volume dan port lokal sementara, broker Mosquitto 2.0.22 khusus tes, CA serta akun acak, lalu menghapus hanya resource tes itu. Uji tidak membaca `.env` pemilik. Broker tes tidak menjadi layanan produksi. Hasil membuktikan MQTT/TLS lokal sampai kueri Grafana serta restart/persistensi, belum membuktikan pembacaan sensor Wokwi atau EMQX Serverless.

InfluxDB menyimpan data pada volume `influx-data` dan konfigurasi pada `influx-config`; Grafana memakai volume `grafana-data`. Provisioning dashboard tetap tersimpan di Git dan dimuat kembali saat layanan dijalankan. Berhenti tanpa menghapus riwayat: `docker compose down`.

Sumber resmi: [DS18B20 Wokwi](https://docs.wokwi.com/parts/wokwi-ds18b20), [build PlatformIO untuk Wokwi](https://docs.wokwi.com/vscode/platformio), [jaringan Wokwi](https://docs.wokwi.com/guides/esp32-wifi), [MQTT Consumer Telegraf](https://docs.influxdata.com/telegraf/v1/input-plugins/mqtt_consumer/), [parser JSON v2](https://docs.influxdata.com/telegraf/v1/data_formats/input/json_v2/).

## Demonstrasi pembatasan akses MQTT

Setelah Wokwi dan stack lokal berjalan, jalankan `python tests/check_mqtt_access.py` dari akar repository. Uji tiket 05 memakai akun proyek yang sudah dikonfigurasi untuk membuktikan penolakan kredensial, izin topik, dan CA tidak dipercaya, dengan kontrol sah sebelum/sesudah sampai Grafana. Pesan sintetis memakai tag khusus dan tidak menggantikan data sensor. Petunjuk, aturan fallback yang harus diperiksa, serta bukti aktual tersedia pada [verifikasi-tiket-05.md](verifikasi-tiket-05.md).

## Jika konversi DS18B20 gagal atau MQTT berstatus -2

Pada 10 November 2026, tes yang menjalankan `loop()` firmware dengan waktu dan batas hardware terkendali berhasil mereproduksi diagnosis `konversi belum selesai`: waktu 750 ms sebelumnya dihitung sebelum perintah OneWire selesai dikirim. Firmware sekarang menghitungnya dari timestamp hasil `requestTemperatures()` DallasTemperature 4.0.6, tetap mempertahankan jadwal mulai sampel 2 detik. Bit busy pada pemeriksaan pertama dicoba kembali; konversi yang terus busy dibatasi satu periode sampel dan tidak menghasilkan suhu buatan. Sensor tanpa respons GPIO 4 mendapat diagnosis terpisah.

`python tests/check_firmware_cycle.py` menguji jalur firmware sebenarnya dengan pengganti hardware/waktu: konversi normal, bit selesai pada pemeriksaan berikutnya, konversi macet, dan sensor terputus. Tes ini dan build ESP32 lulus; tes host sendiri tidak membuktikan simulasi web. Demo alarm web terbaru tercatat di [verifikasi-tiket-03.md](verifikasi-tiket-03.md).

Pemeriksaan koneksi terpisah dari PC juga berhasil memakai hostname, CA tertanam, dan akun ESP32 pada konfigurasi lokal melalui TLS 1.2 serta MQTT 3.1.1. Pemeriksaan memakai client ID sementara, tidak mengirim telemetry, dan tidak mengubah izin broker. Ini tidak membuktikan bahwa konfigurasi di editor Wokwi sama atau gateway Wokwi berhasil terhubung.

Untuk mencoba perbaikan di Wokwi web: hentikan simulasi, salin ulang seluruh `firmware/src/main.cpp` ke tab `sketch.ino`, lalu mulai kembali. Bila koneksi masih gagal, ambil baris baru `MQTT/TLS gagal; status=...; TLS=...` beserta teks errornya. Firmware mempertahankan verifikasi CA/hostname. Status -2 berarti koneksi jaringan gagal terbentuk; itu belum membuktikan username/password ditolak. Lihat [kode status PubSubClient](https://pubsubclient.knolleary.net/api#state).
