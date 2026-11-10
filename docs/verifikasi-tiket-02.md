# Verifikasi tiket 02

Tanggal pemeriksaan: 10 November 2026. Acuan: [02-monitoring-gas.md](../.scratch/monitoring-lab-kimia/issues/02-monitoring-gas.md). Spesifikasi induk `spec.md`, glosarium, dan ADR belum tersedia. Tiket 01 dan tiket 02 telah selesai. Tiket 02 ditutup berdasarkan pengujian lokal, screenshot/log demo Wokwi–Grafana dari pemilik, dan konfirmasi pemilik bahwa restart berhasil. Tabel hasil lokal berikut tetap mencatat batas masing-masing pengujian sebelum demo pemilik.

## Perubahan dan batasnya

- Satu ESP32 membaca DS18B20 di GPIO 4, MQ2 AOUT di GPIO 34 (ADC1), dan DOUT di GPIO 27. GPIO 34 tidak memakai ADC2 yang berbagi akses dengan Wi-Fi.
- MQ2 mendapat 5 V; model Wokwi `mq2-level` menurunkan AOUT dengan rasio 0,6 dan mempertahankan logika DOUT. Rangkaian fisik menggunakan dua pembagi 10 kΩ/15 kΩ sebagaimana [panduan rangkaian](jalur-suhu.md#rangkaian-mq2-dan-batas-tegangan). Model diperlukan karena resistor Wokwi tidak mendukung pembagi analog; tidak ada library firmware atau layanan produksi tambahan.
- Pembacaan gas dilakukan pada siklus konversi suhu yang sama. Jadwal mulai konversi tetap 2.000 ms; tidak ada delay pemanasan atau konversi gas tambahan. DOUT LOW dicetak sebagai ambang terlampaui. Field alarm, LED/buzzer, dan data terlambat tetap milik tiket berikutnya.
- Pesan berisi `device_id`, angka `temperature_c`, dan integer `gas_raw` (0–4095). Sampel dengan suhu gagal atau ADC di luar rentang ditolak, tanpa nilai pengganti. Kegagalan suhu masih menahan seluruh pesan seperti jalur sebelumnya.
- Telegraf menyimpan kedua field pada measurement `suhu`, tag perangkat yang sama, dan timestamp penerimaan pesan yang sama. `gas_raw` opsional pada parser untuk pembaruan bertahap dari firmware lama, tanpa menciptakan nilai nol. Nama measurement, UID, dan volume lama dipertahankan.
- Dashboard memiliki empat panel: suhu terkini, gas terkini, riwayat suhu, dan riwayat gas. Gas diberi satuan ADC/level relatif; tidak ada konversi menjadi konsentrasi LPG terkalibrasi atau ppm hasil pengukuran nyata.

## Hasil lokal aktual

| Pemeriksaan | Hasil aktual | Batas bukti |
| --- | --- | --- |
| Tes C++ telemetry, GCC MinGW, C++11, warning sebagai error | Lulus: payload bersama; gas 1200 → 3000 pada suhu 27,5; suhu 27,5 → 40 pada gas 1200; ADC 0/4095 diterima, -1/4096 ditolak; suhu invalid dan konversi startup tetap ditolak | Menjalankan batas pembentuk pesan, bukan sensor/simulator |
| Build ESP32 PlatformIO | SUCCESS; RAM 26.524/327.680 byte (8,1%), flash 551.033/1.310.720 byte (42,0%) | Template tanpa kredensial; firmware belum membuktikan koneksi cloud |
| Model MQ2, Wokwi CLI 0.29.1/WASI-SDK 25 | Berhasil dikompilasi; binary 65.640 byte disertakan | Kompilasi bukan bukti simulasi penuh |
| Binary model melalui Node/WebAssembly dengan batas API Wokwi | Lulus: input 0, 2,5, 4,4, 5 V menghasilkan rasio 0,6 dan tidak melebihi 3,0 V; LOW/HIGH DOUT diteruskan tanpa inversi | Input/output API dikendalikan tes; tidak menjalankan mesin Wokwi |
| Lint diagram Wokwi CLI | Exit 0, tidak ada error/warning; dua informasi tipe ESP32/DS18B20 lama tidak didokumentasikan oleh registry linter | Belum membuktikan interaksi slider |
| Parser Telegraf 1.40.3 dari image produksi | Sembilan kasus lulus: angka suhu/gas, perubahan mandiri kedua sensor, ADC nol, payload lama tanpa gas, waktu penerimaan, dan penolakan field wajib/teks nonnumerik | Input file sementara menggantikan MQTT hanya pada tes parser |
| MQTT/TLS lokal → Telegraf produksi → InfluxDB 2.9.1 | Lulus: `(27,5;1200)`, `(27,5;3000)`, `(40;3000)` tersimpan berurutan dengan pasangan field pada timestamp yang sama | Publisher fixture menggantikan ESP32, broker tes Mosquitto 2.0.22 menggantikan EMQX |
| Grafana 13.3.0 aktual | Provisioning empat panel berhasil; keempat kueri dashboard melalui API Grafana mengembalikan angka; stat terbaru 40 Celsius dan 3000 ADC | Menguji kueri datasource dan provisioning, bukan rendering browser |
| Restart semua layanan tes | Lulus: timestamp/nilai tiga titik sebelumnya identik; titik baru `(40;4000)` masuk setelah koneksi TLS/subscription pulih; keempat kueri panel tetap berhasil dan stat gas menjadi 4000 ADC | Volume tes terisolasi, bukan volume demo pemilik |
| Compose dan pembersihan | Konfigurasi produksi berhasil dirender; proyek/volume/port sementara dipakai; tidak ada container atau volume `ticket02-test-*` tersisa sesudah tes | Tidak memakai `.env`, CA, atau kredensial EMQX pemilik |

Build masih menunjukkan dua warning dari dependensi OneWire pada baris 599/600 (`extra tokens at end of #undef directive`) seperti tiket 01; build berhasil. Tidak ada perubahan dependensi firmware.

Perintah pengulangan dari akar repository:

```powershell
& ./tests/run-telemetry.ps1
python -m platformio run --project-dir firmware
node tests/check_mq2_level.cjs
python tests/check_telegraf_parser.py --docker
python tests/check_monitoring_stack.py
```

Tes stack memerlukan Docker Linux containers, Docker Compose v2, dan OpenSSL (salinan Git for Windows dideteksi otomatis). Broker Mosquitto dikunci dengan digest dan hanya merupakan fixture tes. Tes membentuk CA/sertifikat hostname lokal serta dua akun MQTT sementara; verifikasi TLS Telegraf tetap aktif. Tidak ada koneksi cloud, perubahan `.env`, atau penghapusan volume produksi. Test publisher mengirim lewat MQTT/TLS, bukan langsung ke HTTP InfluxDB. HTTP dipakai hanya untuk memeriksa hasil penyimpanan dan kueri dashboard.

## Demo Wokwi dan EMQX

Prosedur berikut menjadi acuan pengulangan demo. Hasil aktual pemilik tercatat pada tabel sesudahnya; hasil lokal di atas tetap dibedakan dari bukti sensor Wokwi dan layanan demo.

1. Jalankan firmware dan diagram baru dengan model `mq2-level`. Pastikan serial terhubung MQTT/TLS, payload memuat dua angka dan identitas `esp32-meja01`, dan baris mulai konversi berjarak sekitar 2.000 ms selama terhubung.
2. Pertahankan slider DS18B20 pada 25 Celsius. Naikkan stimulus gas Wokwi bertahap, misalnya `ppm` 400 → 3000 → 10000. Angka stimulus itu bukan hasil pengukuran. Catat `gas_raw` yang benar-benar terbaca; jangan mengharuskan ADC tertentu untuk stimulus tertentu. Pastikan gas naik pada serial, titik InfluxDB, stat gas, dan grafik gas, sementara suhu tetap 25 dan terus diperbarui.
3. Uji DOUT di kedua sisi ambang. Default atribut `threshold` = 4,4 V merujuk keluaran MQ2 sebelum penurunan level. Jika perlu untuk demonstrasi, atur `threshold` agar stimulus gas melintasinya. Pastikan serial `HIGH/belum terlampaui` berubah ke `LOW/terlampaui` dan kembali saat gas diturunkan. Ambang ini pengaturan demonstrasi.
4. Pertahankan stimulus gas. Naikkan suhu dari 25 → 35 Celsius. Pastikan suhu berubah dan gas tetap pada level relatif sebelumnya; titik baru keduanya tetap bertambah setiap siklus. Nilai ADC simulator tidak diklaim sama dengan perangkat fisik.
5. Catat beberapa timestamp/nilai dari kedua field di InfluxDB. Gunakan rentang waktu dashboard yang mencakupnya. Jalankan `docker compose restart`, tunggu pemulihan, lalu periksa titik lama tetap identik dan titik baru masuk dari simulator. Jangan memakai `down -v` pada layanan demo.
6. Simpan bukti serial, pasangan field/timestamp, dan dashboard tanpa rahasia di `evidence/local/` sebelum menuliskan ringkasan yang disamarkan.

| Percobaan pemilik | Tanggal/waktu dan bukti disamarkan | Hasil aktual |
| --- | --- | --- |
| Diagram/model, GPIO, pembacaan ADC dan kedua status DOUT | 10 November 2026; screenshot Wokwi | ESP32, DS18B20, MQ2 dan mq2-level terlihat; serial pada suhu 23,62 Celsius menunjukkan 2190 ADC dengan LOW/terlampaui lalu 2162 ADC dengan HIGH/belum terlampaui |
| MQTT/TLS Wokwi → EMQX → dashboard, interval 2 detik | 10 November 2026; log serial dan screenshot Grafana | Pesan memakai identitas esp32-meja01 dan kedua field numerik. Contoh ms=44046, 46046, 48046 berjarak 2.000 ms saat stabil; dashboard menampilkan pembacaan serta kedua riwayat |
| Gas naik dengan suhu tetap dan terus diperbarui | 10 November 2026; log serial dan screenshot Grafana | Suhu 25,00 Celsius tetap saat gas berubah dari 2177 hingga 2425 ADC; screenshot dashboard menunjukkan 25,00 Celsius dan 2425 ADC |
| Suhu berubah dengan gas tetap | 10 November 2026; screenshot riwayat kedua sensor | Grafik suhu menampilkan perubahan pada segmen gas relatif datar; diterima bersama bukti perubahan sensor mandiri dari pengujian lokal |
| Restart layanan demo mempertahankan kedua riwayat | 10 November 2026; konfirmasi pemilik dalam percakapan | Pemilik menyatakan sudah restart dan hasil tetap baik. Tidak ada pengulangan agen atau screenshot khusus sebelum/sesudah; persistensi juga telah lulus pada stack tes lokal |

Bukti mentah pemilik disimpan pada `evidence/local/ticket-02/` yang diabaikan Git: `serial-wokwi.txt`, `grafana-gas-naik-suhu-tetap.png`, `wokwi-dout-low-high.png`, dan `grafana-riwayat-dua-sensor.png`. Screenshot sumber juga memuat area desktop lain sehingga tetap disimpan lokal; repository hanya memuat ringkasan hasil yang relevan.

Log mencatat beberapa koneksi ulang MQTT/TLS, termasuk satu `status=-2; TLS=-1 ERROR - Generic error`, lalu kembali tersambung dan menerbitkan data. Jadi demo membuktikan periode 2 detik ketika koneksi stabil serta pemulihan, bukan koneksi tanpa gangguan. Penyebab putus-sambung belum ditentukan dari bukti ini; jika gangguan berlanjut saat demo berikutnya, periksa koneksi/gateway dan diagnosis baru. Hal ini tidak membatalkan bukti kriteria tiket 02 yang mensyaratkan interval saat terhubung.

Tiket 02 berstatus `done`; seluruh tujuh acceptance criteria telah dicentang dan penghambat tiket 03 telah terpenuhi. Penyelesaian ini berlaku untuk demonstrasi simulasi yang diminta tiket, bukan validasi keselamatan laboratorium atau kalibrasi konsentrasi gas.
