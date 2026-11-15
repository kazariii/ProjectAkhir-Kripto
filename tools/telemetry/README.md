# Sensor → MQTT/PQC → InfluxDB → Grafana

Tiket 04 memakai `firmware/src/main.cpp` yang sama untuk DS18B20, MQ2, dan alarm lokal. Sejak tiket 06, environment **`pqc-telemetry` adalah default** dan folder **`firmware` adalah simulator utama**; `esp32dev` hanya arsip rollback eksplisit. [Operasi saat ini](../../docs/operasi-pqc.md) menggantikan petunjuk deployment eksperimen. Bagian di bawah mempertahankan cara menjalankan fixture tiket 04/05. Loop sensor hanya menimpa satu salinan sampel terbaru; library transport memiliki task MQTT dan worker crypto terpisah.

## Menjalankan Wokwi

1. Buka folder **`tools/telemetry/simulator`** di VS Code. Artefak deployment saat ini sudah disalin ke `evidence/local/telemetry-firmware/`. Gunakan lisensi Wokwi dan **Private Gateway** yang sudah digunakan pada tiket 02/03. Jika ada Workspace Trust, tinjau dan izinkan sendiri folder proyek.
2. F1 → **Wokwi: Start Simulator**. Diagram sudah berisi DS18B20 di GPIO 4, MQ2 melalui level adapter ke GPIO 34/27, LED GPIO 25, dan buzzer GPIO 26. Custom chip memakai `.wasm`/`.json` yang sama dari direktori `firmware`; tidak perlu mengganti rangkaian.
3. Tunggu sekitar 20 detik sampai ada `TELEMETRY_AUTHENTICATED`, lalu `TELEMETRY_SENT` dan `TELEMETRY_STORED`. Yang terakhir berarti ESP32 sudah memverifikasi ACK terenkripsi setelah write Influx dikonfirmasi. `Sampel lokal` selama handshake menunjukkan pembacaan lokal; sampel-sampel itu dibuang untuk jaringan.
4. Buka [dashboard meja 01](http://10.34.211.141:3000/d/suhu-meja01) dengan akun Grafana yang sudah ada. Refresh 2 detik. Suhu/level gas dan status alarm mengikuti data baru; riwayat lama tetap tersedia.
5. Untuk bukti empat keadaan, tunggu setidaknya 8 detik setiap langkah: 25°C/gas rendah (Normal); ubah DS18B20 menjadi 45°C (Peringatan suhu); naikkan MQ2 sampai DOUT LOW (Peringatan gas dan suhu); kembalikan suhu 25°C (Peringatan gas); turunkan gas sampai DOUT HIGH (Normal). Diagram tiket 04 memakai stimulus awal 0.1. Bila kontrol Wokwi masih memperlihatkan nilai awal lain, turunkan slider gas langsung sampai serial menunjukkan DOUT HIGH; sekitar 0,1 terbukti Normal pada run final, sedangkan 400 belum tentu Normal. Klik komponen sensor untuk mengubah kontrolnya dan jadikan DOUT HIGH/LOW sebagai acuan, bukan asumsi nilai ppm. Angka gas merupakan kontrol simulator, bukan pengukuran LPG terkalibrasi.
6. Tetap tampilkan tab simulator dan **jangan Pause** selama pengujian. Jam firmware berhenti saat Pause, sedangkan broker/session LXC tetap memakai jam nyata. Hentikan simulasi setelah kondisi terakhir mendapat beberapa ACK. Simpan seluruh serial mulai `TELEMETRY_BEGIN` sampai ACK terakhir sebagai UTF-8 `docs/evidence/pqc-ticket-04/esp32-serial.txt`. Stream ini berjalan terus, sehingga tidak memiliki marker DONE. Jangan mencampur beberapa reboot/run.
7. Sesudah >10 detik tanpa sampel, dashboard harus menampilkan **Data terlambat**, dengan nilai/waktu terakhir tetap tersedia. Nilai normal lama tidak dianggap kondisi saat ini.

Jalankan satu simulator/perangkat saja; receiver/pin saat ini untuk `esp32-meja01`. Jangan menjalankan firmware cloud lama bersamaan. Sejak tiket 06, container Telegraf lama dihapus dan hanya tersedia melalui override rollback eksplisit.

### Capture serial otomatis

Untuk capture baru, aktifkan baris opsional `rfc2217ServerPort = 4000` di bagian `[wokwi]` pada `simulator/wokwi.toml`, lalu gunakan F1 → Wokwi: Start Simulator agar konfigurasi dimuat. [RFC2217 bawaan Wokwi](https://docs.wokwi.com/vscode/project-config#serial-port-forwarding) menyediakan port serial; reader terhubung melalui localhost dan mendukung IPv4/IPv6. Jalankan reader dari akar repo laptop **sebelum** Start Simulator:

```sh
node tools/telemetry/capture_serial.mjs evidence/local/wokwi-ticket04-serial.txt
```

Reader menunggu simulator, menyaring negosiasi Telnet, lalu menyimpan byte UART ke file. Ia tidak mengirim perintah serial atau mereset ESP32. File yang sudah ada tidak ditimpa; pilih nama lain untuk run berikutnya. Hentikan reader dengan Ctrl+C setelah simulator berhenti dan nonaktifkan kembali opsi RFC2217 jika tidak dibutuhkan. Tidak perlu Pause untuk menyalin log. Salin satu run lengkap ke nama capture publik setelah diperiksa; sertakan provenance/hash bila pengambilan dilakukan otomatis.

## Deployment LXC

Salinan eksperimen berada di `/opt/lab-kimia-mqtt`, monitoring lama di `/opt/lab-kimia-suhu`. Influx hanya melalui `127.0.0.1:8086`. Dari akar salinan eksperimen:

```sh
.venv/bin/python -m tools.telemetry.provision_influx
install -m 644 infra/mqtt/session.service /etc/systemd/system/lab-kimia-pqc-session.service
systemctl daemon-reload
systemctl restart lab-kimia-pqc-session.service
journalctl -u lab-kimia-pqc-session.service -n 10 --no-pager
```

Provisioning memakai kredensial admin dari `.env` deployment lama di dalam proses, membuat **satu token write-only bucket `telemetry`**, dan menyimpan token di `evidence/local/session-private/influx.json` (0600, parent 0700). State existing diperiksa dan tidak dirotasi. Receiver DynamicUser memperoleh token dari systemd `LoadCredential`, bukan argumen command line. Tidak ada penggantian bucket, datasource, UID dashboard atau volume. Deskripsi dashboard menyebut waktu penerimaan server karena ingress sekarang dapat berasal dari receiver PQC maupun Telegraf selama transisi.

Format Influx tetap `suhu,device_id=esp32-meja01`, empat field: `temperature_c` float, `gas_raw` integer, `gas_alarm` dan `temperature_alarm` boolean. Semua field ditulis pada **satu timestamp nanodetik** dari waktu penerimaan callback server, bukan jam ESP32. JSON harus tepat lima key, tanpa duplikasi/field tambahan: ID tetap, suhu finite −55..125°C, ADC integer 0..4095, flags boolean. Alarm dipertahankan dari firmware: DOUT independen dari ADC, dan alarm suhu dihitung sebelum suhu diformat dua desimal.

ACK data adalah plaintext aplikasi `{"stored_counter":N}` yang dienkripsi s2c. Receiver hanya membentuknya setelah respons HTTP 204 Influx; error/timeout tidak mendapat ACK dan tidak diantrekan untuk retry. Tidak adanya ACK berarti write belum terkonfirmasi, bukan bukti bahwa database pasti tidak menyimpan apa pun. Paket MQTT rusak/replay ditolak sebelum parsing/write. Probe sintetis tiket 03 tetap didukung dan tidak ditulis ke InfluxDB.

## Build dan pemeriksaan

Private header MQTT/pin dari tiket 03 tetap digunakan. Toolchain/cache sama dengan tiket sebelumnya:

```sh
PLATFORMIO_CORE_DIR=/opt/lab-kimia-suhu/pqc-proof/evidence/local/platformio \
  /opt/lab-kimia-suhu/pqc-proof/.venv/bin/pio run -d firmware -e pqc-telemetry -j2
.venv/bin/python -m unittest tests.test_pqc_telemetry tests.test_telemetry_capture
.venv/bin/python -m tests.check_pqc_sensor_cycle
python3 tests/check_firmware_cycle.py --compiler /usr/bin/g++
evidence/local/pqc-session-build/session-test
```

Gabungkan bootloader/partition/boot_app0/aplikasi seperti [panduan sesi](../session/README.md), menggunakan build `pqc-telemetry` dan output `evidence/local/telemetry-firmware/pqc-telemetry-full.bin`; salin ELF juga ke direktori tersebut. Artefak memuat kunci/kredensial lab: gunakan SCP, batasi permission `.pio` dan direktori artefak ke owner, dan jangan commit/unggah ke proyek publik.

Kontrol native melakukan write empat kondisi sintetis pada perangkat/bucket lab yang sama dan mencatat provenance terpisah. Jalankan bergiliran dengan Wokwi:

```sh
.venv/bin/python -m tools.telemetry.check_mqtt
.venv/bin/python -m tools.telemetry.verify_lxc
```

Kontrol token membandingkan query yang berisi data menggunakan admin dengan query identik memakai token writer. InfluxDB 2.9.1 mengembalikan 404 untuk bucket yang tidak memiliki izin read; ini tidak berarti bucket aslinya hilang.

Setelah serial Wokwi disalin ke LXC:

```sh
.venv/bin/python -m tools.telemetry.verify_capture docs/evidence/pqc-ticket-04/esp32-serial.txt
```

Verifier mencocokkan run/client ESP32, sesi terautentikasi, timestamp sampel lokal, counter SENT/STORED, event write/ACK, empat field pada timestamp Influx yang persis sama, dan hasil kueri dashboard Grafana. Semua empat keadaan harus ada. Kontrol native maupun capture parsial tidak dapat menggantikan bukti ini. Untuk memeriksa label pada titik historis, verifier mengatur jam kueri ke waktu titik+100ms; nilai status saat verifikasi menggunakan jam server nyata dan dicatat terpisah.

## Batas operasional

Sampel berumur ≥2 detik dibuang sebelum enkripsi/publish; antrean sensor berisi satu sampel, bukan backlog. Queue callback receiver maksimum empat frame; data yang menunggu ≥2 detik di queue dibuang. Ini tidak mengukur seluruh latensi jaringan. Disconnect membuang generasi/kunci lama dan membentuk sesi baru, tanpa mengirim ulang pembacaan offline.

Sejak tiket 05, rekey dimulai pada umur sesi **180 detik** pada clock client atau melalui perintah pembaruan terenkripsi dari LXC. Masa berlaku tetap 300 detik pada setiap endpoint. Bila ACK tidak maju selama 10 detik virtual, client juga memulai handshake baru. Handshake mengulang byte M1/M3 setelah 5 detik tanpa kemajuan, paling banyak dua kali sebelum nonce/M1 baru. Duplikasi M1/M3 mendapat respons cache tanpa memperpanjang deadline, umur kunci atau mengulang penyimpanan. Detailnya berada pada [protokol sesi](../../docs/protokol-sesi-pqc.md).

Selama handshake/signature, crypto worker menunda telemetri dan membuang sampel yang terkumpul; sensor/alarm dan loop MQTT tetap berjalan. Dengan biaya FN-DSA simulator sekitar 12 detik, rekey dapat menghasilkan celah data yang ditandai dashboard sebagai terlambat. Keepalive MQTT 120 detik memberi margin perlambatan, tetapi Pause lama tetap dapat memutus koneksi. Frame tanpa ACK tidak diklaim tersimpan atau dikirim ulang. Tidak ada fallback TLS/plaintext. Catatan enam frame tanpa ACK pada run tiket 04 merupakan hasil versi sebelumnya dan tetap dipertahankan sebagai bukti historis.

Uji serangan/pemulihan pada LXC **saat simulator berhenti**: `python -m tools.telemetry.check_security --output-dir evidence/local/demo-baru`. Pilih direktori baru; `security.json` existing ditolak sebelum mengganggu layanan. Skrip mematikan receiver/broker dan Influx sebentar lalu memulihkan pada `finally`, tanpa menghapus volume/token/histori. Untuk Wokwi gunakan `python -m tools.telemetry.wokwi_fault receiver <session_id> --seconds 20 --output-dir evidence/local/demo-baru` (pilihan lain `broker`, `influx`) hanya saat sesi itu mendapat ACK. Hasil fault ditambahkan pada berkas run tersebut. Default lama tetap menunjuk tiket 05 untuk kompatibilitas; gunakan `--output-dir` saat mengulang agar bukti historis tidak tercampur. [Panduan demo utama](../../docs/demo-proyek.md) menjelaskan urutannya.

Sumber algoritma dan batas prospective FN-DSA mengikuti [profil sesi tiket 03](../../docs/protokol-sesi-pqc.md). Keberhasilan Wokwi bukan bukti RNG/performa papan fisik atau keselamatan laboratorium.
