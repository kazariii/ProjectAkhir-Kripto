# Arsip demo proyek MQTT/TLS

> **Arsip panduan MQTT/TLS lama.** Untuk demo sekarang gunakan [panduan utama MQTT/PQC](demo-proyek.md). Perintah dan hasil di bawah hanya untuk membaca histori/rollback lama; tidak dijalankan pada demo revisi.

Proyek: **Simulasi Monitoring Gas dan Suhu Laboratorium Kimia Dasar Berbasis MQTT over TLS dengan Dashboard Grafana**. Satu ESP32 memantau lingkungan sekitar satu meja praktikum LPG, menjalankan alarm lokal, dan mengirim pengukuran untuk ditinjau melalui dashboard. Panduan ini dapat diikuti tanpa riwayat chat. Hasil pengulangan aktual dan batas buktinya ada di [verifikasi tiket 07](verifikasi-tiket-07.md).

## 1. Arsitektur dan batas demonstrasi

```text
DS18B20 + MQ2 → ESP32/Wokwi → MQTT/TLS :8883 → EMQX Cloud Serverless
                   ↓                              ↓ MQTT/TLS :8883
              LED + buzzer                     Telegraf 1.40.3
                                                  ↓ HTTP internal Docker
                                               InfluxDB 2.9.1
                                                  ↓
                                               Grafana 13.3.0
```

**MQTT melalui TLS adalah protokol komunikasi sensor.** Telegraf menerima pesan, InfluxDB **2.x** menyimpan pengukuran, dan Grafana memvisualisasikannya. Ketiganya adalah jalur yang sudah disepakati; HTTP antara layanan dan browser bukan pengganti MQTT sensor. Broker mengakhiri dua koneksi TLS dan dapat membaca pesan.

Topik: `lab/kimia/meja01/telemetry`; perangkat: `esp32-meja01`. Pesan berisi angka `temperature_c`, integer ADC `gas_raw`, serta boolean `gas_alarm` dan `temperature_alarm`. Telegraf memberikan timestamp penerimaan yang sama pada keempat field; jam ESP32 tidak menjadi timestamp database. NTP ESP32 tetap diperlukan untuk memeriksa masa berlaku sertifikat TLS.

Alarm gas mengikuti **DOUT MQ2 LOW**, terpisah dari alarm suhu valid **>=40 derajat Celsius**. LED/buzzer mengikuti OR kedua alarm. Nilai suhu gagal tidak dianggap aman dan tidak menghapus alarm suhu sebelumnya. Sampel gagal tidak diterbitkan. Loop sensor/alarm terpisah dari tugas jaringan; sampel offline tidak ditimbun atau dikirim ulang setelah reconnect. Diagram dan pin terperinci ada di [panduan rangkaian](jalur-suhu.md#rangkaian-mq2-dan-batas-tegangan).

**40 Celsius adalah ambang demo**, bukan standar keselamatan. MQ2 menghasilkan **level relatif/ADC**, bukan konsentrasi LPG terkalibrasi. Label `ppm` pada kontrol Wokwi hanya stimulus simulator; jangan menyebut angka dashboard sebagai ppm. Sensor mengamati lingkungan meja, bukan nyala api, tidak mengidentifikasi orang, dan **tidak menjamin keselamatan laboratorium nyata**. Kendali katup/kipas, notifikasi eksternal, sensor fisik, serta audit deployment menyeluruh berada di luar cakupan.

## 2. Prasyarat dan konfigurasi pemilik

Siapkan Docker Desktop dengan Linux containers dan Compose v2, Python 3.11, internet, browser dengan Wokwi, serta PlatformIO Core 6.1.19 untuk memeriksa build. Uji keamanan paket memerlukan OpenSSL (Git for Windows dapat dipakai), Wireshark/dumpcap/tshark dan Npcap yang dapat menangkap loopback. Wokwi web cukup; lisensi simulator VS Code tidak diperlukan. Image layanan beserta digest dan versi pustaka sudah dikunci dalam repository.

Semua perintah berikut memakai **PowerShell dari akar repository**. Pemasangan PlatformIO bila belum tersedia: `python -m pip install platformio==6.1.19`. Mesin Docker harus aktif sebelum melanjutkan.

1. Pemilik akun membuat/verifikasi EMQX Cloud **Serverless**, mempertahankan **Spend Limit 0**, dan menunggu Running. Pendaftaran, verifikasi akun, serta ketentuan layanan diselesaikan pemilik. Jangan mengaktifkan pengeluaran; kuota habis dapat menghentikan deployment. Rincian layar: [penyiapan EMQX](jalur-suhu.md#emqx-cloud-serverless-tanpa-pengeluaran).
2. Catat hostname DNS deployment dan port 8883, unduh CA deployment. Buat password acak terpisah untuk dua akun MQTT. Atur autentikasi dan otorisasi:

   | Subjek | Operasi | Topik | Izin |
   | --- | --- | --- | --- |
   | Username `esp32-meja01` | Publish | `lab/kimia/meja01/telemetry` | Allow |
   | Username `telegraf-meja01` | Subscribe | `lab/kimia/meja01/telemetry` | Allow |
   | All Users | Publish & Subscribe | `#` | Deny |

   Periksa tidak ada allow luas tambahan, termasuk pada tab Client ID. Kredensial salah/anonim harus ditolak. Banner mode blacklist bukan bukti fallback deny.
3. Pada **pemasangan pertama saja**, buat konfigurasi lokal berikut. Jangan menimpa berkas yang sudah diisi:

   ```powershell
   Copy-Item .env.example .env
   Copy-Item firmware/include/secrets.example.h firmware/include/secrets.h
   ```

   | Berkas lokal | Isi oleh pemilik |
   | --- | --- |
   | `.env` | `MQTT_HOST` tanpa skema/port; akun/password Telegraf; username/password InfluxDB; token InfluxDB; username/password Grafana |
   | `firmware/include/secrets.h` | Hostname yang sama; username/password ESP32; seluruh CA termasuk BEGIN/END CERTIFICATE; Wi-Fi `Wokwi-GUEST` dan password kosong |
   | `infra/certs/emqx-ca.pem` | CA deployment yang sama dalam format PEM |

   Gunakan password demo hex acak yang berbeda (minimal 20 karakter), token InfluxDB hex minimal 64 karakter. Isi lewat editor lokal, jangan melalui argumen perintah, chat, screenshot, atau Git. `.env` menginisialisasi volume baru; mengedit token/password setelah inisialisasi tidak otomatis mengganti akun layanan. Ikuti pembaruan akun/token bila perlu; jangan menghapus volume untuk menyamakan password.
4. ESP32 tetap memakai `setCACert` dan hostname DNS; Telegraf tetap `ssl://…:8883`, CA deployment dan `insecure_skip_verify=false`. Jangan memakai `setInsecure`, mengosongkan CA, atau mengganti hostname dengan IP untuk mengatasi kegagalan.

## 3. Mulai layanan dan simulator

```powershell
docker info
docker compose config --quiet
docker compose up -d
docker compose ps
docker compose logs --tail 30 telegraf
python -m platformio run --project-dir firmware
```

Harus ada tiga layanan berjalan dan InfluxDB healthy. Periksa diagnosis Telegraf jika belum menerima data; build atau rendering Compose saja belum membuktikan alur sensor. Jangan menjalankan `docker compose config` tanpa `--quiet` karena konfigurasi hasil render memuat rahasia.

Untuk Wokwi web, ikuti [10 langkah penyiapan simulator](jalur-suhu.md#menjalankan-layanan-dan-firmware). Buat proyek ESP32, salin berkas berikut ke tab web; tambahkan **Custom Chip bernama `mq2-level`, bahasa C** sebelum menyalin diagram. Tambahkan pustaka lewat Library Manager, lalu isi `libraries.txt` dengan versi repository.

| Sumber lokal | Tab Wokwi |
| --- | --- |
| `firmware/src/main.cpp` | `sketch.ino` |
| `firmware/include/telemetry.h` | `telemetry.h` |
| `firmware/include/monitoring.h` | `monitoring.h` |
| `firmware/include/secrets.h` yang diisi pemilik | `secrets.h` |
| `firmware/diagram.json` | `diagram.json` |
| `firmware/libraries.txt` | `libraries.txt` |
| `firmware/mq2-level.chip.c` | `mq2-level.chip.c` |
| `firmware/mq2-level.chip.json` | `mq2-level.chip.json` |

Klik Play. Tunggu `MQTT/TLS tersambung: CA dan hostname diverifikasi`, lalu `Terkirim` dan **pengukuran baru** di Grafana. Jika konfigurasi belum diisi, alarm lokal tetap berjalan tetapi jaringan dinonaktifkan. Jangan membagikan/menyimpan proyek publik berisi kredensial aktif. Gunakan akun demo terbatas dan rotasi/hapus akun demo setelah penggunaan sesuai kebutuhan pemilik.

Buka [Grafana lokal](http://127.0.0.1:3000), masuk memakai akun `.env`, pilih folder **Lab Kimia → Gas dan suhu lingkungan meja praktikum 01**. [Tautan dashboard langsung](http://127.0.0.1:3000/d/suhu-meja01) memakai UID tetap. Pilih Last 1 hour/Last 15 minutes yang mencakup demo. Ada tujuh panel: kondisi/kesegaran, waktu penerimaan terakhir, nilai suhu dan ADC, dua grafik historis, serta tabel pengukuran/alarm. Pemilih rentang memengaruhi riwayat; kondisi dan nilai terakhir tetap mengikuti pesan terakhir dalam seluruh riwayat tersimpan. Pakai Refresh sesudah perubahan jika diperlukan.

## 4. Urutan demo sensor dan alarm

Catat waktu mulai (WIB), screenshot rangkaian/serial dan dashboard tiap tahap. Tunggu **sampel lokal valid, `Terkirim`, waktu penerimaan baru, dan label Grafana yang sesuai** sebelum beralih. PubSubClient QoS 0: log `Terkirim` sendiri belum membuktikan penerimaan broker/database.

Klik komponen MQ2 untuk membuka slider gas, DS18B20 untuk suhu; tutup panel komponen sebelum membuka yang lain bila tertutup overlay. Pada kontrol MQ2, fokuskan slider lalu **Home** untuk stimulus 0,1 (DOUT HIGH), **End** untuk tinggi (DOUT LOW). Jika tampilan slider baru belum sesuai pembacaan, gerakkan sekali lalu ke target dan periksa DOUT di serial. Angka stimulus tidak harus sama dengan ADC. Suhu diatur ke 25 atau 40 Celsius. Bawaan diagram memakai stimulus MQ2 400 yang dapat mengaktifkan alarm gas saat boot, jadi atur kondisi normal dahulu.

| Tahap | Suhu valid | MQ2 / DOUT | LED/buzzer | Label Grafana saat data terkini |
| --- | ---: | --- | --- | --- |
| Normal | 25 Celsius | rendah / HIGH | OFF | Normal |
| Gas tinggi saja | 25 Celsius | tinggi / LOW | ON | Peringatan gas |
| Suhu tinggi saja | 40 Celsius | rendah / HIGH | ON | Peringatan suhu |
| Keduanya | 40 Celsius | tinggi / LOW | ON | Peringatan gas dan suhu |
| Gas pulih dahulu | 40 Celsius | rendah / HIGH | ON | Peringatan suhu |
| Kembali normal | 25 Celsius | rendah / HIGH | OFF | Normal |

Periksa grafik suhu dan gas berubah secara mandiri, serta tabel menyimpan empat kombinasi boolean pada timestamp yang sama dengan nilai sensor. Bukti buzzer berupa perintah `tone`/`noTone` dan diagnosis LED/buzzer; bila suara tidak direkam, tuliskan batas itu.

## 5. Gangguan dan pemulihan koneksi

Pertahankan simulator berjalan pada kondisi normal. Dari terminal terpisah, jalankan gangguan sesi MQTT pada deployment demo sendiri:

```powershell
python tests/demo_mqtt_outage.py --seconds 90
```

Skrip menggunakan akun ESP32 yang sudah diisi serta **client ID `esp32-meja01`** berulang untuk mengambil alih sesi simulator, tanpa publish/subscribe. Akun/ID Telegraf tidak diambil alih. Gangguan berakhir otomatis; Ctrl+C dapat menghentikannya lebih awal. Ini memutus sesi MQTT, **bukan** Wi-Fi fisik atau layanan cloud. Bukti lokal ada di `evidence/local/ticket-07/outage.json`. Status `completed` hanya membuktikan proses takeover selesai; dashboard dan alur pulih tetap perlu diamati. Siklus bukan jaminan tidak ada pesan lolos di antara takeover: buktikan jendela tanpa data melalui timestamp/riwayat.

1. Tunggu lebih dari **10 detik tanpa penerimaan baru**, lalu refresh. Label harus **Data terlambat — kondisi saat ini belum diketahui**, dan waktu penerimaan berhenti. Nilai normal lama bukan bukti kondisi sekarang normal. Bucket baru yang belum pernah menerima data menampilkan **Belum ada data**.
2. Saat gangguan masih berjalan, naikkan gas saja; serial/LED/buzzer harus aktif. Turunkan gas, naikkan suhu saja ke 40; keluaran lokal harus tetap mengikuti sensor meski dashboard terlambat. Catat serial `Sampel lokal` dan keadaan output.
3. Setelah gangguan berhenti, **jangan restart ESP32 atau mengubah kredensial/CA**. Tunggu koneksi dan sampel baru sampai InfluxDB/Grafana. Label kembali Peringatan suhu bila suhu masih 40. Kembalikan 25/rendah untuk Normal.
4. Periksa grafik punya jeda tanpa isian nol/normal, data sebelum putus tetap ada, dan tidak ada backfill sampel offline. Reconnect mencoba kembali minimal tiap 5 detik waktu simulasi. Simulator yang lambat atau gateway gagal dapat memperpanjang waktu nyata; jangan menyimpulkan kegagalan autentikasi hanya dari timeout atau status MQTT -2.

## 6. Riwayat setelah layanan dimulai ulang

Catat satu timestamp dan nilai pada tabel serta rentang grafik yang mencakup seluruh demo. Jalankan:

```powershell
docker compose restart
docker compose ps
```

Tunggu InfluxDB healthy, Grafana dapat dibuka, Telegraf kembali menerima, dan **titik ESP32 baru** masuk. Refresh dashboard; titik lama dan transisi alarm harus tetap tersedia dengan timestamp/nilai yang sama. Catat screenshot sebelum/sesudah. Untuk pengujian pembuatan ulang container, alternatifnya `docker compose down` lalu `docker compose up -d`. **Jangan gunakan `down -v`, penghapusan volume, atau reset bucket**: volume `influx-data`, `influx-config`, dan `grafana-data` menyimpan riwayat/konfigurasi.

## 7. Demonstrasi keamanan

Jalankan dengan Wokwi dan ketiga layanan tetap aktif:

```powershell
python tests/check_mqtt_access.py
python tests/check_tls_relay.py
python tests/check_tls_security.py
```

Perintah pertama memakai deployment proyek dan menyimpan JSON `evidence/local/ticket-05/ticket05-<acak>.json`. Harus exit 0: kontrol sah **ESP32 baru sampai Grafana** serta dua pesan sintetis bertag terpisah, penolakan username/password/anonim, penolakan izin topik/wildcard, CA tidak dipercaya, lalu kontrol sah ulang. Perlihatkan juga tiga aturan broker di bagian 2 dan tab Client ID tanpa allow tambahan. Rincian kode respons dan langkah ada di [tiket 05](verifikasi-tiket-05.md). Timeout atau layanan mati bukan bukti penolakan akses.

Dua perintah berikut menjalankan relay fixture dan eksperimen **terpisah pada broker lokal disposable**, bukan merusak koneksi EMQX utama. Lihat [tiket 06](verifikasi-tiket-06.md) untuk pemilihan interface capture. JSON/log/PCAP baru berada di `evidence/local/ticket-06/ticket06-<acak>/`.

- **Confidentiality / kerahasiaan:** bandingkan PUBLISH plaintext dengan TLS tanpa kunci dekripsi. Penanda/payload terbaca pada plaintext; penanda tidak tampak pada capture TLS walau subscriber sah menerima pesan identik. IP, port, arah, ukuran, waktu dan sebagian metadata handshake tetap dapat terlihat. Broker tetap titik tepercaya; ini bukan enkripsi ujung-ke-ujung ESP32–Grafana atau perlindungan HTTP internal.
- **Integrity / integritas:** tunjukkan kontrol normal sebelum/sesudah, CONNACK diterima sebelum relay diaktifkan, tepat satu bit badan ciphertext berubah dengan header/panjang tetap, alert TLS/diagnosis broker, tidak ada PUBACK dan tidak ada penerimaan penanda oleh subscriber independen. Ketiadaan pesan sendiri tidak cukup. Mengubah nilai JSON **sebelum** pengiriman sah bukan uji perubahan ciphertext. Kesimpulan hanya deteksi manipulasi dalam koneksi TLS yang diuji, bukan kebenaran sensor atau integritas database.
- **Authentication / autentikasi:** klien memverifikasi CA/hostname server; broker memeriksa akun MQTT. Pembatasan topik adalah **authorization / otorisasi**. Username/password bukan sertifikat klien, bukan identitas hardware, dan bukan mutual TLS.
- **Availability / ketersediaan:** alarm lokal saat putus, penanda terlambat, reconnect dan persistensi hanya dukungan terbatas. Tidak ada jaminan uptime, penanggulangan semua gangguan, atau penyimpanan sampel offline. Fokus kriptografi tugas adalah confidentiality, integrity, dan authentication.

Capture utama ESP32–EMQX dan Telegraf–EMQX sudah tersedia di [bukti tiket 06](evidence/ticket-06/). Untuk mengambil ulang: [capture jalur utama](verifikasi-tiket-06.md#mengulang-capture-jalur-utama). Saat presentasi buka PCAP utama dengan filter `tcp.port == 8883`, lalu `plaintext-publish.pcapng` (PUBLISH/PUBACK saja), `tls.pcapng`, hasil/log relay. Capture plaintext mentah berisi CONNECT dengan password demo sekali pakai; simpan lokal dan jangan tampilkan/commit CONNECT. Broker cloud utama tidak pernah dibuat plaintext.

## 8. Simpan bukti, hentikan layanan, siapkan Git

Gunakan lembar hasil di [verifikasi tiket 07](verifikasi-tiket-07.md) sebagai contoh: waktu run, langkah, nilai/label, lokasi bukti, kontrol positif/negatif, hasil aktual dan keterbatasan. Langkah yang belum dijalankan atau gagal harus tetap ditulis demikian. Bukti mentah disimpan di `evidence/local/` yang diabaikan Git; ekspor hanya hasil yang diperiksa ke `docs/evidence/`.

```powershell
git status --short
git check-ignore .env firmware/include/secrets.h infra/certs/emqx-ca.pem evidence/local/ticket-07/outage.json
git ls-files -- .env firmware/include/secrets.h infra/certs/emqx-ca.pem evidence/local
git diff --check
```

`check-ignore` harus menampilkan keempat jalur; `ls-files` tidak boleh menampilkan rahasia/bukti mentah itu. Periksa juga **isi** semua berkas yang akan ditambahkan, termasuk berkas baru dan capture, terhadap password/token/private key aktual. Pengecualian Git saja tidak membuktikan isi berkas lain bersih. CA adalah sertifikat publik; jangan tertukar dengan private key. Template `.env.example` dan `secrets.example.h` tetap tersedia tanpa nilai aktif.

Berhenti tanpa kehilangan data: Stop Wokwi lalu `docker compose down` tanpa `-v`. **Push ke GitHub dilakukan sendiri oleh pengguna** setelah peninjauan berkas. Panduan ini tidak membutuhkan push untuk menjalankan demo.
