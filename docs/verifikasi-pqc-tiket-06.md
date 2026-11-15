# Migrasi jalur utama MQTT/PQC — tiket 06

Status **done**, 15 November 2026. Deployment LXC dan laptop telah diperbarui; kode/bukti belum di-commit atau di-push. Tiket 07 dapat dilanjutkan. [Ringkasan mesin](evidence/pqc-ticket-06/summary.json) memuat hash source/image dan hasil acceptance.

## Keadaan setelah migrasi

- Default `pio run` memilih **`pqc-telemetry`**; `firmware/wokwi.toml` memakai binary/ELF environment itu. Jalur sensor menggunakan MQTT TCP/1883 tanpa TLS, ML-KEM-512, prospective FN-DSA degree 512 dan ChaCha20-Poly1305.
- Container Telegraf lama dihentikan dan dihapus. Compose default hanya memuat InfluxDB/Grafana serta lulus konfigurasi saat seluruh variabel MQTT cloud dihilangkan. `compose.legacy.yaml` menyimpan ingress lama untuk rollback manual, bukan fallback runtime.
- Mosquitto tetap bind **`10.34.211.141:1883`**, akun/ACL tetap sama, container `unless-stopped`. Receiver `lab-kimia-pqc-session.service` aktif dan enabled; proof diagnostic dinonaktifkan. Docker enabled saat boot.
- Source ingress tetap `/opt/lab-kimia-mqtt`; `.env` initialized dan volume monitoring tetap `/opt/lab-kimia-suhu`. Tidak ada migrasi/copy data volume, reset bucket atau rotasi identity/token.

Skrip [migrasi](../tools/deploy/migrate.py) menyimpan baseline dan compose sebelumnya di `evidence/local/migration06` (0700, file 0600). Ia dijalankan ulang dan menolak perubahan state private yang tidak sesuai baseline. Kegagalan tidak otomatis menghidupkan transport TLS lama. Hash private hanya berada pada baseline ignored; laporan publik tidak memuat nilai secret maupun hash secret tersebut.

## State dan restart

[Bukti cutover](evidence/pqc-ticket-06/cutover.json) dan [uji restart](evidence/pqc-ticket-06/restart.json) memeriksa:

- Volume bernama `lab-kimia-suhu_influx-data`, `lab-kimia-suhu_influx-config`, `lab-kimia-suhu_grafana-data` tetap sama.
- Bucket telemetry, dashboard UID `suhu-meja01`, datasource `influx-suhu`, `.env`, account/password files, identitas/pin serta token writer dipertahankan. Private state dibandingkan byte/hash dalam proses tanpa mencetaknya.
- Empat titik historis dari capture tiket 04/05 tetap ada dengan timestamp dan empat field persis sama.
- Dua kontrol **native**, sebelum dan sesudah restart InfluxDB/Grafana, broker dan receiver, mendapat ACK penyimpanan. Keduanya masih terbaca setelah restart; sesi setelah restart mempunyai ID baru. Kueri dashboard dan token write-only juga lulus.

Pengujian ini mencakup restart layanan dan konfigurasi autostart, **bukan reboot seluruh LXC/Proxmox**. Riwayat laptop lama juga tidak diklaim dimigrasikan; yang dipertahankan adalah state initialized LXC.

## Build dan ESP32/Wokwi

`pio run` tanpa `-e` pada source LXC lulus dan hanya membangun environment default `pqc-telemetry`: RAM **83.644 byte**, flash **861.561 byte**. Application binary/ELF disalin melalui SCP ke `firmware/.pio/build/pqc-telemetry/` pada laptop. Format application image PlatformIO mengikuti [konfigurasi Wokwi](https://docs.wokwi.com/vscode/project-config#esp32-application-image-vs-full-image).

Run dari **folder `firmware` utama**, bukan fixture `tools/telemetry/simulator`, memiliki ID **`3066a27ea869a9b9f201019f5537cf99`**. [Serial lengkap](evidence/pqc-ticket-06/esp32-serial.txt) direkam otomatis tanpa Pause; [provenance/hash](evidence/pqc-ticket-06/esp32-serial.provenance.json) mencatat asal dan foldernya.

Hasilnya **169 SENT, 169 ACK, tiga sesi, empat keadaan alarm**, tanpa frame SENT yang tidak terkonfirmasi pada run ini. [Join lengkap](evidence/pqc-ticket-06/capture-validation.json) mencocokkan setiap ACK dengan sampel lokal, autentikasi/session, event write dan ACK LXC, titik Influx pada timestamp yang sama, serta kueri Grafana. Ini bukti Wokwi terpisah dari dua kontrol native. Tiga sesi juga menunjukkan pembaruan berkala berjalan pada jalur default.

UI gas sempat mempertahankan stimulus 400 walaupun diagram sudah 0.1; kontrol diturunkan langsung sampai DOUT HIGH. Suhu/gas kemudian diubah untuk mencakup normal, gas saja, suhu saja dan kedua alarm. Run diakhiri pada 25°C/gas rendah setelah ACK normal. Log mengonfirmasi LED/buzzer ON/OFF; suara tidak direkam secara akustik. Reader dan simulator dihentikan, konfigurasi RFC2217 kembali nonaktif, jendela uji ditutup dan port 4000 terverifikasi sudah tidak mendengarkan.

## Operasi dan batas

[README utama](../README.md) dan [operasi LXC/rollback](operasi-pqc.md) sekarang mengarah ke PQC. Panduan TLS lama diberi label arsip; penyusunan demo utuh tetap tiket 07. Override rollback berhasil divalidasi dengan kredensial/CA lama yang masih private; cloud ingress lama tidak diaktifkan kembali untuk uji ini.

Protokol lab belum diaudit independen dan FN-DSA masih prospektif, tanpa klaim FIPS 206 final. MQTT tanpa TLS tetap memperlihatkan password broker dan metadata; private identity masih diperlukan untuk memalsukan payload yang diterima aplikasi. Keberhasilan 169/169 pada run ini bukan jaminan delivery tanpa kehilangan: handshake/rekey, jaringan atau Pause lama tetap dapat menghasilkan celah. Tidak ada bukti RNG/side channel hardware, kalibrasi fisik atau keselamatan laboratorium. Raw binary/ELF dan private state tetap ignored, tidak dimasukkan ke bukti publik.
