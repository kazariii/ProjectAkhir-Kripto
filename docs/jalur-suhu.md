# Menjalankan jalur suhu

Implementasi lokal tersedia. Demonstrasi EMQX/Wokwi sampai dashboard masih memerlukan konfigurasi pemilik dan mesin Docker yang berjalan. Hasil yang benar-benar dijalankan dicatat di [verifikasi-tiket-01.md](verifikasi-tiket-01.md).

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
{"device_id":"esp32-meja01","temperature_c":27.5}
```

`temperature_c` adalah angka derajat Celsius. Firmware memulai konversi setiap 2.000 ms selama koneksi berjalan, menunggu konversi selesai sebelum membaca, dan tidak membuat nilai pengganti ketika pembacaan gagal. Pesan tanpa timestamp perangkat memakai waktu penerimaan Telegraf. Measurement `suhu`, field float `temperature_c`, dan tag `device_id` menjadi kontrak kueri dashboard.

Telegraf memakai parser `json_v2`, `type = "float"`, tag wajib `device_id`, serta tanpa `timestamp_path`. MQTT tetap menjadi jalur komunikasi sensor; HTTP pada jaringan internal Docker hanya menghubungkan penerima ke penyimpanan dan dashboard.

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

Tanpa `secrets.h`, build tetap dapat memeriksa kompilasi, tetapi firmware berhenti dengan diagnosis bahwa konfigurasi belum diisi. Hasil build bukan bukti koneksi cloud.

Pilih salah satu cara simulasi:

- **Wokwi web tanpa pembelian:** buka proyek baru ESP32 di [Wokwi](https://wokwi.com/), lalu salin isi `firmware/src/main.cpp` ke `sketch.ino`. Tambahkan berkas **pada direktori editor yang sama** bernama `telemetry.h` dari `firmware/include/telemetry.h` dan `secrets.h` dari konfigurasi lokal; jangan mempertahankan subdirektori `src`/`include` di editor web. Ganti `diagram.json` dan `libraries.txt` dengan isi berkas bernama sama dari direktori `firmware`. Jika UI mengharuskan Library Manager dahulu, tambahkan PubSubClient, OneWire, dan DallasTemperature, lalu periksa versi `@` di `libraries.txt`. Mulai simulasi. Build web memakai toolchain Arduino milik Wokwi, sehingga bukti build PlatformIO tidak membuktikan build web; catat hasil aktualnya.
- **Wokwi untuk VS Code jika akses/lisensi sudah tersedia:** buka direktori `firmware` sebagai folder workspace, build dahulu, lalu jalankan **Wokwi: Start Simulator**. `wokwi.toml` menunjuk hasil build lokal pada `.pio/build/esp32dev/`. Jangan membuka akar repository sebagai workspace simulator karena jalur konfigurasi berpusat pada folder firmware. Pembelian lisensi tidak diperlukan untuk mengikuti jalur web di atas.

Pada serial monitor 115200 baud, tunggu Wi-Fi/NTP dan diagnosis MQTT/TLS tersambung. Baris `Konversi suhu dimulai ms=...` mestinya berjarak sekitar 2.000 ms saat tersambung, bukan 2.750 ms. Baris `Terkirim` menampilkan payload dan waktu monotonic untuk memeriksa interval. PubSubClient menggunakan publish QoS 0; hasil true berarti diterima stack klien, sehingga bukti penerimaan broker tetap harus diperiksa melalui Telegraf/dashboard.

Buka [Grafana lokal](http://localhost:3000), masuk dengan `GRAFANA_USERNAME`/`GRAFANA_PASSWORD`, lalu pilih folder **Lab Kimia** → **Suhu lingkungan meja praktikum 01**. Datasource dan dua panel dibuat dari provisioning. Dashboard memperbarui setiap 2 detik; flush Telegraf, jaringan, dan interval kueri dapat menambah jeda. Halaman [InfluxDB lokal](http://localhost:8086) tersedia untuk memeriksa data menggunakan akun InfluxDB.

## Pengulangan demo dan persistensi

1. Siapkan deployment dan dua akun MQTT beserta aturan izin di atas.
2. Isi konfigurasi lokal dari template dan CA deployment.
3. Jalankan layanan dan simulator dengan langkah di atas.
4. Diagram berisi DQ ke GPIO 4, VCC ke 3,3 V, GND ke GND, serta resistor pull-up 4,7 kΩ antara DQ dan 3,3 V.
5. Buka Grafana lokal, lihat nilai terbaru dan grafik historis. Ubah slider DS18B20 dari 25 ke 35 derajat Celsius dan catat perubahan di serial serta dashboard.
6. Uji pembacaan gagal dengan memutus kabel DQ pada salinan diagram demonstrasi. Periksa diagnosis serial dan pastikan tidak ada titik -127, NaN, nilai di luar rentang sensor, atau nilai startup yang belum dikonversi.
7. Catat beberapa titik suhu beserta waktu penerimaan. Jalankan `docker compose restart`, tunggu layanan pulih, dan periksa titik sebelumnya tetap ada serta titik baru bertambah. Untuk memeriksa pembuatan ulang container, gunakan `docker compose down` lalu `docker compose up -d`; **jangan** memakai opsi `-v` karena itu menghapus volume dan riwayat.
8. Catat hasil aktual, waktunya, dan lokasi bukti. Langkah yang belum dilakukan tetap ditandai belum diverifikasi.

Wokwi memakai `Wokwi-GUEST` tanpa password. Gateway publik menyediakan akses keluar ke cloud dan tidak menyediakan akses ke layanan localhost komputer. Karena itu broker jalur utama tetap EMQX Cloud. Jangan mengunggah kredensial permanen ke proyek Wokwi publik; gunakan akun demonstrasi sementara, jangan bagikan proyek yang memuat kredensial, dan hapus/rotasi kredensial sesudah demo.

Firmware menolak NaN, infinity, -127, nilai di luar -55 sampai 125 derajat Celsius, serta hasil sebelum konversi selesai. Nilai 85 derajat Celsius setelah konversi tetap valid; sentinel startup dicegah dengan tidak membaca sebelum konversi. Dokumentasi Wokwi menyebut keterbatasan DallasTemperature pada tepat -55 derajat Celsius; jika simulator/library melaporkannya gagal, diagnosis dan penolakan lebih aman daripada menciptakan suhu pengganti. Gangguan konversi tidak diterbitkan sebagai pesan normal. Nilai Grafana lama tidak membuktikan pemulihan pembacaan; pastikan titik baru terlihat setelah kabel dipasang kembali.

## Pemeriksaan lokal yang dapat diulang

```powershell
python -m platformio pkg install --global --tool platformio/toolchain-gccmingw32
& ./tests/run-telemetry.ps1
python tests/check_telegraf_parser.py --telegraf C:/lokasi/telegraf.exe
```

Gunakan Telegraf 1.40.3 untuk pemeriksaan parser. Skrip mengambil blok parser produksi dan mengganti input layanan MQTT dengan berkas sementara. Hasilnya membuktikan format field/tag serta waktu penerimaan parser, belum membuktikan koneksi MQTT/TLS atau penyimpanan/dashboard. Jangan memakai `telegraf --test` pada konfigurasi MQTT service input untuk menyimpulkan pesan cloud berhasil diterima.

InfluxDB menyimpan data pada volume `influx-data` dan konfigurasi pada `influx-config`; Grafana memakai volume `grafana-data`. Provisioning dashboard tetap tersimpan di Git dan dimuat kembali saat layanan dijalankan. Berhenti tanpa menghapus riwayat: `docker compose down`.

Sumber resmi: [DS18B20 Wokwi](https://docs.wokwi.com/parts/wokwi-ds18b20), [build PlatformIO untuk Wokwi](https://docs.wokwi.com/vscode/platformio), [jaringan Wokwi](https://docs.wokwi.com/guides/esp32-wifi), [MQTT Consumer Telegraf](https://docs.influxdata.com/telegraf/v1/input-plugins/mqtt_consumer/), [parser JSON v2](https://docs.influxdata.com/telegraf/v1/data_formats/input/json_v2/).
