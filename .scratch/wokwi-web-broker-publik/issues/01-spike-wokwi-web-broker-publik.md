# 01: Spike — Wokwi web menjangkau broker.emqx.io

**What to build:** Bukti bahwa firmware hasil build PlatformIO dapat di-upload ke wokwi.com, tersambung lewat Wokwi-GUEST ke `broker.emqx.io:1883` tanpa TLS, dan dijawab responder di LXC, termasuk frame 1519 byte (header sesi PQC terbesar). Spike juga membuktikan chip custom MQ2 dapat dimuat di Wokwi web dan LXC dapat keluar ke port 1883.

**Blocked by:** None (can start immediately)

**Status:** done

- [x] LXC dapat membuka koneksi keluar ke `broker.emqx.io:1883`
- [x] Env firmware diagnostik publik ter-build; bin tidak memuat IP privat, akun, atau password
- [x] Env diagnostik privat lama tetap ter-build; regresi capture diagnostik lulus di LXC
- [x] Responder publik di LXC menjawab echo kecil dan frame 1519 byte; payload asing tidak dibalas (kontrol native dari laptop)
- [x] Wokwi web: firmware ter-upload dan menghasilkan satu `MQTT_DIAG_RESULT` dengan `passed:true` dan `large_frame_bytes:1519`, diikuti `MQTT_DIAG_DONE`
- [x] `run_id` dari log Wokwi web cocok dengan event `request_received` dan `large_received` di jurnal responder LXC
- [x] Diagram lengkap dengan chip `mq2-level` dimuat di Wokwi web tanpa error chip

## Comments

**Bagian agen selesai, 25 November 2026.**

- Prefix topik spike: `lkpqc-b16bef88/diag`. Env PlatformIO: `mqtt-diagnostic-public`. Mode publik di firmware dan responder hanya aktif lewat flag; perilaku default privat tidak berubah.
- Responder berjalan sebagai unit sementara `lab-kimia-public-diag` (systemd-run, DynamicUser). Unit hilang saat reboot. Hentikan dengan `systemctl stop lab-kimia-public-diag` setelah spike selesai.
- Kontrol native laptop: echo kecil 0,547 s, echo 1519 byte utuh, payload `big:` pendek dan `diag:NOTHEX` tidak dibalas.
- Bin lokal: `evidence/local/public-diag-firmware/mqtt-diagnostic-public-full.bin` (merged, offset 0x0, diabaikan Git). Backup berkas LXC sebelum sinkronisasi: `/opt/lab-kimia-mqtt/evidence/local/backup-wokwi-web-01/`.
- `tests/check_mqtt_capture.py` membutuhkan `journalctl`, jadi hanya dapat dijalankan di LXC.

**Langkah manusia:**

1. Buka wokwi.com, buat proyek ESP32 baru.
2. Ganti isi `diagram.json` dengan `firmware/diagram.json`. Tambahkan berkas `mq2-level.chip.json` dan `mq2-level.chip.c` dari folder `firmware/` dengan nama yang sama.
3. Klik editor kode, tekan F1, pilih **Upload Firmware and Start Simulation...**, lalu pilih bin di atas.
4. Tunggu sampai `MQTT_DIAG_DONE` atau `MQTT_DIAG_FAILED` (maksimal 120 detik). Salin seluruh serial monitor ke agen.
5. Catat apakah ada error terkait chip `mq2-level` saat simulasi dimulai.

**Run Wokwi web, 25 November 2026.**

- Run pertama dan kedua, saat laptop memakai jaringan kampus: Wi-Fi simulasi berhenti di `WL_IDLE_STATUS` (0) dan tidak pernah tersambung. Responder LXC tidak menerima apa pun dari ESP32. Firmware kemudian ditambah log `MQTT_DIAG_WIFI_STATUS` dan `MQTT_DIAG_STATE` untuk membedakan kegagalan gateway dari kegagalan broker.
- Run ketiga, saat laptop memakai hotspot HP: Wi-Fi tersambung dengan `local_ip=10.10.0.2`, dan hasilnya `passed:true`, `roundtrip_ms:1290`, `large_frame_bytes:1519`, `run_id` `0f11eef15aef09561edb432e36c3cbca`. Log serial ada di `docs/evidence/wokwi-web-01/esp32-serial.txt`. Diagram dengan chip `mq2-level` dimuat tanpa error.
- Kesimpulan sementara: jaringan kampus memblokir jalur Wi-Fi Wokwi web, sedangkan hotspot tidak. Penyebab persisnya, misalnya WebSocket atau firewall, belum diperiksa. **Risiko demo:** perangkat yang menjalankan Wokwi web di kampus harus memakai jaringan lain seperti hotspot, atau jaringan kampus harus diuji ulang terlebih dahulu.
- Pencocokan `run_id` dengan jurnal LXC tertunda karena laptop yang memakai hotspot tidak punya rute ke `10.34.211.141`. Langkahnya: `journalctl -u lab-kimia-public-diag -o cat --no-pager | grep 0f11eef15aef09561edb432e36c3cbca`. Unit sementara hilang bila LXC reboot sebelum pengecekan ini.
- Pencocokan selesai: jurnal LXC memuat `request_received`, `reply_queued`, `large_received` (1519 byte), dan `large_reply_queued` untuk `run_id` yang sama, pada 03:38:17–03:38:19 UTC. Salinan ada di `docs/evidence/wokwi-web-01/responder-journal.txt`. Semua acceptance criteria lulus.
- Unit `lab-kimia-public-diag` dibiarkan aktif sebagai alat diagnosis untuk tiket berikutnya; pembersihannya masuk tiket 05.
