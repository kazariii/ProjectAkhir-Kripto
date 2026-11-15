# Sesi MQTT terautentikasi — tiket 03

Eksperimen satu perangkat, satu payload sintetis, dan ACK terenkripsi. Sensor, alarm, penulisan InfluxDB dan dashboard masuk tiket 04; sejak tiket 06 jalur PQC menjadi default. Untuk sensor gunakan [operasi utama](../../docs/operasi-pqc.md), sedangkan petunjuk di bawah khusus pengulangan proof tiket 03. Lihat [hasil aktual](../../docs/verifikasi-pqc-tiket-03.md) dan [format protokol](../../docs/protokol-sesi-pqc.md).

## Menjalankan kembali di laptop

1. Pastikan laptop memiliki rute ke LXC `10.34.211.141:1883`. Layanan `lab-kimia-pqc-session.service` harus aktif di LXC.
2. Buka folder **`tools/session/simulator`** di VS Code. Lisensi Wokwi yang sudah diaktifkan untuk tiket 02 tetap digunakan. Jika VS Code meminta Workspace Trust, pemilik meninjau dan mengizinkan sendiri folder ini.
3. Pastikan `evidence/local/session-firmware/pqc-session-full.bin` dan `firmware.elf` tersedia. Keduanya sudah disiapkan untuk deployment uji ini. File biner memuat identitas/kredensial lab; jangan commit atau unggah ke proyek web publik.
4. F1 → **Wokwi: Start Simulator**. Gunakan **Private Gateway**, seperti tiket 02. Public IoT Gateway tidak memiliki rute ke LXC privat. Tidak perlu menyalin source/library ke editor web.
5. Tunggu `SESSION_BEGIN`, `SESSION_WIFI local_ip=10.13.37.2`, `SESSION_CONNECTED port=1883 tls=false`, `SESSION_AUTHENTICATED`, satu `SESSION_RESULT` dan `SESSION_DONE`. Operasi FN-DSA ESP32 membutuhkan sekitar 12 detik virtual; loop MQTT tetap dipompa task utama.
6. Pastikan `passed`, `mutual_auth`, `key_confirmation`, dan `encrypted_ack_verified` bernilai `true`. Hentikan simulator setelah `SESSION_DONE`. Jika `SESSION_FAILED`, panic, watchdog, atau reboot muncul, simpan kegagalannya; jangan menggabungkannya dengan run lain.
7. Simpan **satu run lengkap** sebagai UTF-8 `docs/evidence/pqc-ticket-03/esp32-serial.txt`, kirim ke salinan repo LXC, lalu cocokkan dengan jurnal menggunakan perintah di bawah. Sukses native saja tidak cukup untuk bukti Wokwi.

## Provisioning/build LXC

Prasyarat: tiket 01/02, salinan sumber di `/opt/lab-kimia-mqtt`, gcc/g++, OpenSSL development headers, venv Paho dari tiket 02. Private state yang sudah ada dipertahankan. Jalankan dari akar salinan tersebut:

```sh
make -C tools/session test -j2
.venv/bin/python -m tools.session.provision
.venv/bin/python tools/mqtt/setup_private.py --bind 10.34.211.141
```

Provisioning membuat pasangan FN-DSA khusus sesi ini, terpisah dari fixture tiket 01. Jika kedua identity file sudah ada, tidak ada rotasi. Keadaan parsial atau pin yang tidak berpasangan ditolak. Private identity berada di `evidence/local/session-private/` (direktori 0700, berkas 0600); header ESP32 `firmware/include/pqc_session_identity.h` diabaikan Git. Receiver memperoleh identitas/kredensial lewat systemd `LoadCredential`.

ACL memperluas dua akun lab tiket 02: perangkat menulis `session/up` dan membaca `session/down`, penerima sebaliknya. Topik diagnostik lama tetap tersedia. Setelah menyalin ACL baru, recreate hanya broker eksperimen agar bind mount menunjuk berkas terbaru; SIGHUP saja tidak memperbaiki mount yang masih menunjuk inode lama:

```sh
docker compose --env-file infra/mqtt/.env -f infra/mqtt/compose.yaml up -d --force-recreate broker
install -m 644 infra/mqtt/session.service /etc/systemd/system/lab-kimia-pqc-session.service
systemctl daemon-reload
systemctl enable --now lab-kimia-pqc-session.service
journalctl -u lab-kimia-pqc-session.service -n 10 --no-pager
```

Tunggu event `ready`. Jika kode penerima/library yang sedang berjalan diperbarui, gunakan `systemctl restart lab-kimia-pqc-session.service` agar proses memuat versi baru. Supervisor mengulang koneksi setelah broker tersedia. Tidak perlu menghentikan stack monitoring lama atau menghapus volume.

```sh
.venv/bin/python -m tools.session.check_mqtt
```

Hasil ini berlabel `native-control`, menggunakan client ID `native-session-*`. Jalankan bergiliran dengan simulator karena receiver menangani satu identitas/perangkat aktif.

Build ESP32 pada deployment saat ini memakai venv/cache toolchain yang sudah dipasang tiket 01:

```sh
PLATFORMIO_CORE_DIR=/opt/lab-kimia-suhu/pqc-proof/evidence/local/platformio \
  /opt/lab-kimia-suhu/pqc-proof/.venv/bin/pio run -d firmware -e pqc-session -j2
mkdir -p evidence/local/session-firmware
/opt/lab-kimia-suhu/pqc-proof/.venv/bin/python \
  /opt/lab-kimia-suhu/pqc-proof/evidence/local/platformio/packages/tool-esptoolpy/esptool.py \
  --chip esp32 merge_bin -o evidence/local/session-firmware/pqc-session-full.bin \
  0x1000 firmware/.pio/build/pqc-session/bootloader.bin \
  0x8000 firmware/.pio/build/pqc-session/partitions.bin \
  0xe000 /opt/lab-kimia-suhu/pqc-proof/evidence/local/platformio/packages/framework-arduinoespressif32/tools/partitions/boot_app0.bin \
  0x10000 firmware/.pio/build/pqc-session/firmware.bin
cp firmware/.pio/build/pqc-session/firmware.elf evidence/local/session-firmware/firmware.elf
chmod 700 firmware/.pio evidence/local/session-firmware
chmod 600 evidence/local/session-firmware/*
```

Salin kedua artefak secara biner menggunakan SCP ke direktori laptop dengan nama yang sama. Header private sesi dan MQTT juga perlu ada bila membangun di mesin lain; jangan menampilkan nilainya di log/argumen shell. Wokwi langsung memakai image lengkap, sehingga build firmware sensor default tidak berubah.

## Verifikasi bukti

Dari akar repo LXC, dengan serial satu run sudah disalin:

```sh
.venv/bin/python -m tools.session.verify_capture \
  docs/evidence/pqc-ticket-03/esp32-serial.txt \
  --output docs/evidence/pqc-ticket-03/capture-validation.json
.venv/bin/python -m tests.check_session_capture
```

Verifier mensyaratkan marker lengkap, keberhasilan ACK, `run_id`/`session_id` yang cocok dengan event `session_established`, `payload_accepted`, `encrypted_ack_queued`, serta koneksi broker `esp32-session-<12 karakter awal run_id>`. Jurnal/broker log harus masih tersedia; salin hasil validasi sebelum log dirotasi atau container direcreate.

`tools.session.collect_evidence` mengumpulkan ringkasan deployment ini, termasuk kontrol native, regresi tiket 01/02, kesehatan layanan dan hash artefak. Ia memerlukan log build yang disimpan sebagai `evidence/local/session-esp32-build.log` dan `proof-esp32-regression.log`, fixture tiket 01 yang sudah ada di LXC, dan capture Wokwi sah. Ia gagal jika bukti MCU/server belum lengkap.
