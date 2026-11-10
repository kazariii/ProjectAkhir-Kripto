# Verifikasi tiket 03

Tanggal: 10 November 2026. Acuan: [03-alarm-gas-suhu.md](../.scratch/monitoring-lab-kimia/issues/03-alarm-gas-suhu.md). Tiket 02 sudah selesai. Tidak ada `spec.md`, glosarium, atau ADR tambahan. Tiket 03 berstatus `done` berdasarkan tes lokal dan demo Wokwi → EMQX → Telegraf → InfluxDB → Grafana yang diamati langsung.

## Perilaku dan cakupan

- `gas_alarm` mengikuti MQ2 DOUT di GPIO 27: LOW aktif, HIGH tidak aktif. DOUT diperiksa setiap iterasi loop, termasuk ketika DS18B20 belum selesai atau gagal. ADC tidak menentukan alarm gas.
- `temperature_alarm` aktif pada suhu **valid >=40 Celsius** dan kembali tidak aktif pada suhu **valid <40 Celsius**. Satu aturan validitas dipakai oleh alarm dan pembentuk pesan: konversi selesai, nilai finite, dan rentang -55 sampai 125 Celsius. Kegagalan, sensor hilang, atau konversi belum selesai mempertahankan status suhu sebelumnya; tidak menghasilkan pesan normal buatan.
- LED merah GPIO 25 melalui resistor 220 Ω serta buzzer piezo GPIO 26 dengan nada 2 kHz mengikuti OR kedua alarm. Keputusan berada di ESP32. Inisialisasi sensor/output mendahului pemeriksaan konfigurasi jaringan, sehingga alarm lokal juga berjalan tanpa kredensial.
- Header `monitoring.h` memiliki aturan/status lokal; `telemetry.h` menambahkan kedua status sebagai JSON boolean dalam sampel suhu/ADC yang sama. Buffer pesan 160 byte cukup untuk seluruh rentang sensor dan tetap muat pada buffer MQTT 256 byte beserta topiknya. Tidak ada dependensi atau layanan produksi baru.
- Telegraf menyimpan boolean pada measurement `suhu`, identitas dan timestamp penerimaan yang sama dengan suhu/ADC. Field alarm opsional untuk pembaruan dari firmware lama; field yang hilang tidak diciptakan sebagai false. UID, measurement, volume, dan riwayat lama dipertahankan.
- Grafana menambahkan stat dengan teks **Normal**, **Peringatan gas**, **Peringatan suhu**, **Peringatan gas dan suhu**, serta tabel waktu/suhu/ADC/kedua alarm/keadaan. Kueri melakukan pivot berdasarkan timestamp yang sama; tidak mencampurkan status dari pesan berbeda atau menganggap firmware lama normal.
- Ambang **40 Celsius** dan MQ2 **4,4 V sebelum penurunan level** adalah **pengaturan demonstrasi simulasi, bukan standar keselamatan atau pembuktian deteksi kebakaran**. Kendali katup/kipas dan notifikasi eksternal tidak ditambahkan.

Saat boot, suhu belum diketahui sampai konversi valid pertama; tidak ada telemetry normal yang dibuat dari pembacaan gagal. Status alarm bersifat RAM dan tidak dipertahankan melewati restart ESP32. Setelah kegagalan suhu, Grafana menampilkan status terakhir yang diterima; alarm gas lokal tetap berjalan. Deteksi data terlambat dan penghilangan jeda akibat koneksi ulang sinkron tetap cakupan tiket 04.

## Hasil pengujian lokal

| Pemeriksaan | Hasil | Batas bukti |
| --- | --- | --- |
| C++11 dengan warning sebagai error | Lulus: format boolean, empat kombinasi, batas ADC/suhu, tepat 40 dan 39,99 Celsius, latch setelah nilai gagal/belum selesai, pemulihan valid, kapasitas payload | Aturan dan pembentuk pesan tanpa hardware |
| Loop firmware sebenarnya dengan batas hardware/waktu terkendali | Lulus: GPIO 27 LOW/HIGH, gas saat suhu terputus, suhu saja, keduanya, LED GPIO 25 dan perintah buzzer GPIO 26, latch saat sensor hilang/NaN, pemulihan, operasi tanpa MQTT/config | Mengamati perintah `tone`/`noTone`, bukan mengukur suara fisik |
| Regresi konversi | Lulus: timestamp sesudah perintah OneWire, periode mulai 2 detik, bit selesai pada tick berikutnya, konversi macet ditolak, sensor terputus tidak menghasilkan telemetry | Waktu terkendali pada host |
| Build ESP32, PlatformIO/espressif32 6.9.0 | SUCCESS; RAM 46.496/327.680 byte; flash 918.693/1.310.720 byte | Konfigurasi lokal tersedia; nilai rahasia tidak dicetak atau disalin ke laporan |
| Parser Telegraf 1.40.3 dari image produksi | 13 kasus lulus, termasuk empat kombinasi boolean, waktu penerimaan dan kompatibilitas pesan lama | Menggunakan file input untuk parser, bukan MQTT |
| MQTT/TLS lokal → konfigurasi produksi Telegraf/InfluxDB/Grafana | Lulus: empat keadaan lalu normal, tipe boolean asli, timestamp bersama, enam kueri panel dan label riwayat | Publisher fixture dan broker Mosquitto tes; bukan sensor Wokwi atau EMQX |
| Restart stack tes | Lulus: lima titik sebelumnya identik; titik baru masuk dan keenam kueri tetap berhasil setelah restart | Resource tes terisolasi dan dibersihkan; tidak menghapus volume demo |
| Wokwi web | Kompilasi dan rangkaian baru berjalan; LED tampak menyala saat alarm dan mati saat normal; pesan memuat kedua boolean | Suara browser tidak direkam/dinilai secara akustik; perintah nada diuji pada batas firmware |

Wokwi web memakai API ESP32 yang lebih baru daripada build PlatformIO. Percobaan awal dengan `ledcSetup`/`ledcAttachPin` ditolak oleh kompilasi web. Implementasi akhir memakai `tone`/`noTone` Arduino standar dan berhasil pada keduanya. Dua warning OneWire bawaan tentang `#undef` masih muncul saat kompilasi penuh, seperti tiket sebelumnya; bukan kegagalan build.

Pengulangan dari akar repository:

```powershell
& ./tests/run-telemetry.ps1
python tests/check_firmware_cycle.py
python -m platformio run --project-dir firmware
python tests/check_telegraf_parser.py --docker
python tests/check_monitoring_stack.py
```

## Demo Wokwi dan EMQX

Demo dilakukan pada proyek Wokwi web yang sudah berisi konfigurasi pemilik, tanpa menyalin ulang atau menampilkan rahasia. `sketch.ino`, `telemetry.h`, `diagram.json` diperbarui dan `monitoring.h` ditambahkan. Layanan Telegraf/Grafana dimulai ulang untuk memuat parser/dashboard; volume dipertahankan. Proyek web tetap berupa proyek baru yang belum diterbitkan; sumber yang dapat diulang berada di repository. Saat menyiapkan proyek lain, ikuti [panduan lengkap](jalur-suhu.md).

Hasil berikut berasal dari **data InfluxDB layanan demo**, dicocokkan dengan log Wokwi dan label Grafana. Waktu adalah WIB (UTC+7), tanggal 10 November 2026; dibulatkan ke detik untuk tabel ini. CSV lokal menyimpan timestamp lengkap.

| Waktu diterima (WIB) | Suhu (Celsius) | Gas (ADC) | `gas_alarm` | `temperature_alarm` | Grafana / keluaran lokal |
| --- | ---: | ---: | --- | --- | --- |
| 19:46:15 | 25 | 2177 | true | false | Peringatan gas; LED/buzzer ON |
| 19:47:28 | 25 | 506 | false | false | Normal; LED/buzzer OFF |
| 19:48:11 | 40 | 506 | false | true | Peringatan suhu; LED/buzzer ON |
| 19:49:17 | 40 | 2176 | true | true | Peringatan gas dan suhu; LED/buzzer ON |
| 19:49:57 | 40 | 506 | false | true | Gas pulih; peringatan suhu tetap aktif |
| 19:50:13 | 25 | 506 | false | false | Normal kembali; LED/buzzer OFF |

Stimulus MQ2 400 (lalu sekitar 398) pada slider simulator menghasilkan DOUT LOW; stimulus 0,1 menghasilkan HIGH. Angka slider adalah stimulus simulasi, bukan ppm hasil pengukuran atau konsentrasi terkalibrasi. ADC 2177/2176 dan 506 adalah hasil yang benar-benar diamati. Jangan memakai angka ADC ini sebagai ambang firmware. Suhu 40 Celsius diatur melalui kontrol DS18B20; perintah nada/LED dan kedua field mengikuti aturan yang sama dengan tes lokal.

Log menunjukkan jadwal konversi dalam waktu simulasi sekitar 2.000 ms, misalnya mulai `26781`, `28781`, `30782` serta pengiriman `27532`, `29532`, `31533`. Kecepatan simulator pada browser berada di bawah waktu nyata; jeda timestamp penerimaan nyata dapat lebih panjang dari 2 detik. Keberhasilan demo ini tidak diklaim sebagai jaminan latensi atau koneksi tanpa gangguan.

Prosedur pengulangan:

1. Jalankan firmware/diagram terbaru; pastikan `monitoring.h` tersedia. Tunggu MQTT/TLS tersambung dan titik baru masuk. Jangan menerbitkan proyek yang berisi kredensial aktif.
2. Pada suhu 25 Celsius, ubah gas dari DOUT HIGH ke LOW. Cocokkan `gas_alarm=true`, `temperature_alarm=false`, LED/buzzer aktif, dan label **Peringatan gas**.
3. Turunkan gas hingga HIGH; tunggu pesan berikutnya dan label **Normal**, dengan output mati.
4. Dengan gas tetap HIGH, naikkan suhu ke tepat 40 Celsius. Periksa **Peringatan suhu** dan output aktif.
5. Pertahankan suhu dan naikkan gas hingga LOW. Periksa **Peringatan gas dan suhu**.
6. Turunkan gas saja: alarm suhu harus bertahan. Kembalikan suhu ke 25 Celsius: kedua status false, output mati, dan dashboard Normal. Periksa tabel riwayat; semua keadaan sebelumnya tetap tersedia bersama pengukurannya.
7. Untuk pengulangan gangguan sensor, putuskan DQ pada salinan demo setelah kondisi panas. Status suhu sebelumnya harus bertahan, tidak ada sampel normal buatan, dan gas lokal tetap berfungsi. Pasang kembali dan ambil suhu valid <40 untuk pemulihan. Skenario gangguan ini telah diuji pada loop host; tidak diulang dengan pemutusan kabel pada demo browser tiket 03.

## Bukti lokal

Berkas di `evidence/local/ticket-03/` diabaikan Git:

- `serial-wokwi.txt`: serial simulasi final, termasuk payload, perubahan output, dan interval waktu simulasi.
- `pengukuran-influx.csv`, `transisi-alarm.json`: hasil baca layanan demo, empat kombinasi dan pemulihan dengan timestamp bersama.
- `grafana-gas.jpg`, `grafana-normal.jpg`, `grafana-suhu.jpg`, `grafana-keduanya.jpg`, `grafana-pulih.jpg`: label keadaan yang terlihat saat demo.
- `wokwi-gas.jpg`, `wokwi-normal.jpg`, `wokwi-suhu.jpg`, `wokwi-keduanya.jpg`, `wokwi-pulih.jpg`: rangkaian/output dan serial terkait.
- `grafana-riwayat.jpg`, `riwayat-dashboard.txt`: tabel pengukuran dengan label Aktif/Tidak aktif dan keadaan, tanpa bergantung pada warna.

Seluruh sembilan acceptance criteria terpenuhi pada batas bukti di atas. Tidak ada klaim validasi sensor fisik, standar keselamatan, atau perekaman suara.
