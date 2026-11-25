# MQTT privat: konektivitas tiket 02

> **Khusus jalur privat.** Login, ACL, dan kontrol akun di dokumen ini hanya berlaku untuk Mosquitto LXC. Broker publik `broker.emqx.io` (jalur demo utama sejak 25 November 2026) tidak punya login/ACL; mode `serve --public --prefix ...` hanya dipakai untuk spike Wokwi web. Lihat [operasi](../../docs/operasi-pqc.md#jalur-publik-dan-rollback-ke-jalur-privat).

Tujuan: ESP32 pada **Wokwi VS Code dengan Private Gateway** mengirim `diag:<run_id>` ke Mosquitto TCP/1883 di LXC; penerima LXC membalas `ack:<run_id>`. Hanya marker sintetis yang dikirim. Tidak ada pembacaan sensor, penulisan InfluxDB, atau sesi ML-KEM/FN-DSA pada tiket konektivitas ini. Autentikasi kriptografi aplikasi adalah tiket 03.

## Instalasi LXC

Deployment terpisah berada di `/opt/lab-kimia-mqtt`. Salin `infra/mqtt`, `tools/mqtt`, sumber diagnostik ESP32, dan konfigurasi PlatformIO ke direktori itu. Direktori kode dapat dibaca, tetapi `evidence/local/mqtt-private` wajib tetap privat. Dari akar deployment:

```sh
python3 tools/mqtt/setup_private.py --bind 10.34.211.141
docker compose -f infra/mqtt/compose.yaml config --quiet
docker compose -f infra/mqtt/compose.yaml up -d
python3 -m venv .venv
.venv/bin/pip install -r tools/mqtt/requirements.txt
sudo cp infra/mqtt/diagnostic.service /etc/systemd/system/lab-kimia-mqtt-diagnostic.service
sudo systemctl daemon-reload
sudo systemctl enable --now lab-kimia-mqtt-diagnostic.service
.venv/bin/python tools/mqtt/diagnostic.py check
```

Setup memerlukan Docker dan hak root untuk membatasi permission serta menetapkan pemilik password file. Image Mosquitto 2.0.22 dikunci digest; Paho MQTT dikunci 2.1.0. Jika image belum tersedia, Docker akan mengambilnya dari registry resmi.

Setup hanya menerima alamat IPv4 RFC1918; tidak menerima wildcard, loopback, atau IP publik. Port 1883 dipublikasikan khusus pada IP privat tersebut, bukan semua interface. Tidak ada penerusan port publik atau perubahan firewall. Laptop harus memiliki rute LAN/VPN ke LXC.

Password acak dibuat hanya untuk akun diagnostik `diag-device` dan `diag-receiver`. Password tidak dicetak atau dikirim lewat argument command line. Mosquitto memakai hash password; JSON dan header firmware lokal yang memuat password tetap diabaikan Git. Pengulangan setup mempertahankan kredensial dan menolak keadaan parsial/perubahan endpoint implisit.

Penerima memakai systemd DynamicUser dan LoadCredential agar hanya menerima credential yang diperlukan. Ia hanya menerima marker tepat 32 digit hex dan tidak me-republish retained message. Supervisor memulai ulang dan melakukan subscribe baru setelah koneksi putus. Status `active` saja tidak membuktikan echo sudah siap; pemeriksaan `check` membuktikan request/reply aktual.

## Build ESP32

Header privat dihasilkan sebagai `firmware/include/mqtt_diag_secrets.h`. Build environment `mqtt-diagnostic` hanya menyertakan sumber diagnostik dan PubSubClient 2.8. Sejak tiket 06, default sensor adalah `pqc-telemetry`; [operasi utama](../../docs/operasi-pqc.md) juga memakai kredensial ini. Service diagnostic tidak diaktifkan otomatis lagi: aktifkan manual hanya bila mengulang proof tiket 02, lalu hentikan/nonaktifkan setelah uji.

```sh
.venv/bin/pip install platformio==6.1.19
PLATFORMIO_CORE_DIR="$PWD/evidence/local/platformio" .venv/bin/pio run -d firmware -e mqtt-diagnostic -j2
```

Pada deployment uji saat ini, interpreter PlatformIO berada di `/opt/lab-kimia-suhu/pqc-proof/.venv/bin/pio` dan cache toolchain di `/opt/lab-kimia-suhu/pqc-proof/evidence/local/platformio`. Build menggunakan salinan sumber di `build-firmware/` pada deployment MQTT agar kode eksperimen tiket 01 tidak perlu dipindahkan.

Image lengkap digabungkan dari bootloader, partisi, boot_app0 dan aplikasi dengan `esptool merge_bin`, kemudian disimpan sebagai `evidence/local/mqtt-diagnostic-full.bin` di LXC. Salinan laptop berada di `evidence/local/mqtt-firmware/` bersama ELF hasil build. Seluruh artefak ini tetap di luar Git karena memuat kredensial diagnostik.

## Menjalankan Wokwi VS Code

1. Pastikan laptop terhubung ke jaringan/VPN yang dapat mencapai LXC. Periksa di PowerShell:

   ```powershell
   Test-NetConnection 10.34.211.141 -Port 1883
   ```

   Hasil `TcpTestSucceeded` harus `True`.

2. Extension **Wokwi Simulator v4.1.0** telah dipasang pada laptop ini. Instalasi ulang pada komputer lain dapat dilakukan melalui Marketplace resmi. Lisensi harus sesuai penggunaan proyek; [halaman lisensi resmi](https://wokwi.com/license) menyediakan lisensi personal 30 hari dan menyatakan penggunaan open source gratis. Jangan menganggap lisensi sudah aktif hanya karena extension terpasang.
3. Buka folder **`tools/mqtt/simulator`** di VS Code. File `wokwi.toml` telah menunjuk image lengkap dan ELF lokal; `diagram.json` menyediakan satu ESP32 dengan Serial Monitor.
4. Jika tampil **Restricted Mode**, pemilik komputer perlu mengizinkan trust pada folder simulator itu agar extension dapat berjalan.
5. Tekan **F1 → Wokwi: Request a new License**, ikuti halaman akun Wokwi, dan tunggu pemberitahuan **License activated**. Proses login/aktivasi dilakukan pemilik akun.
6. Tekan **F1 → Wokwi: Start Simulator**. Extension menyertakan Private Gateway yang memakai rute jaringan laptop. Pertahankan tab simulator terlihat.
7. Serial Monitor harus menampilkan `MQTT_DIAG_BEGIN`, alamat lokal gateway privat, `MQTT_DIAG_CONNECTED port=1883 tls=false`, satu JSON `MQTT_DIAG_RESULT` dengan `passed:true`, dan **`MQTT_DIAG_DONE`**. Setiap boot memakai `run_id` acak baru. Nilai balasan harus cocok dengan run itu.

Contoh **struktur**, bukan bukti run aktual:

```text
MQTT_DIAG_BEGIN ticket=02 transport=MQTT-TCP
MQTT_DIAG_WIFI local_ip=10.13.37.2
MQTT_DIAG_CONNECTED port=1883 tls=false
MQTT_DIAG_RESULT {"passed":true,"run_id":"<32 digit hex aktual>","mqtt_port":1883,"tls":false,"local_ip":"10.13.37.2","roundtrip_ms":<hasil aktual>}
MQTT_DIAG_DONE
```

Jika muncul `CONNECT_FAILED` atau timeout, periksa gateway privat, rute laptop ke LXC, broker, akun, dan penerima. Jangan menonaktifkan autentikasi untuk meloloskan pengujian. Public Gateway Wokwi web tidak menyediakan akses langsung ke jaringan privat ini; bukti tiket ini harus memakai jalur privat yang dipilih.

## Mengumpulkan bukti

Simpan log serial lengkap sebagai `evidence/local/mqtt-serial.txt`, lalu salin ke LXC dengan SCP. Jalankan:

```sh
.venv/bin/python tools/mqtt/diagnostic.py verify-capture --capture evidence/local/mqtt-serial.txt
.venv/bin/python tools/mqtt/collect_evidence.py --capture evidence/local/mqtt-serial.txt \
  --output docs/evidence/pqc-ticket-02/summary.json
```

Collector memerlukan bukti TCP laptop `evidence/local/mqtt-private/laptop-network.json`, log build `build-esp32.log`, dan `evidence/local/restart-check.json` hasil kontrol setelah restart broker. Ia memeriksa binding privat dan image container yang benar, menjalankan kontrol native, lalu mencocokkan capture dengan journal penerima dan koneksi client `esp32-diag-<prefix_run_id>` di broker. Run native dengan client ID `mqtt-check-*` tidak boleh menggantikan bukti Wokwi. Tanpa `--capture`, laporan tetap menyatakan `simulator_runtime.verified=false`.

Mosquitto bisa memberikan SUBACK sukses untuk filter yang tidak berhak menerima data; ACL read tetap memfilter delivery. Karena itu tes mencatat SUBACK secara apa adanya dan memeriksa tidak adanya request yang bocor ke akun perangkat, bukan mengklaim semua subscribe terlarang pasti ditolak. Publish terlarang diuji dengan MQTT 5 QoS 1 dan harus mendapat PUBACK `135` (Not authorized).

## Operasi dan batas

```sh
docker compose -f infra/mqtt/compose.yaml ps
docker compose -f infra/mqtt/compose.yaml logs --tail 30 broker
systemctl status lab-kimia-mqtt-diagnostic.service
journalctl -u lab-kimia-mqtt-diagnostic.service -n 30 -o cat
```

Kredensial broker dikirim melalui MQTT biasa di jaringan privat; itu belum menjadi bukti confidentiality atau autentikasi aplikasi. Proteksi payload dan identitas ujung-ke-ujung tetap pekerjaan tiket sesi. Jangan memakai marker diagnostik sebagai telemetry produksi. Deployment MQTT ini memakai project Compose tersendiri; InfluxDB, Grafana, Telegraf, dan volumenya tidak perlu dihentikan untuk pengujian.

Referensi: [Wokwi VS Code dan lisensi](https://docs.wokwi.com/vscode/getting-started), [Private Gateway bawaan](https://docs.wokwi.com/vscode/project-config#iot-gateway-esp32-wifi), [autentikasi Mosquitto](https://mosquitto.org/documentation/authentication-methods/), [Paho MQTT](https://eclipse.dev/paho/files/paho.mqtt.python/html/client.html).
