# Bukti kelayakan kriptografi ESP32 ke LXC

Ini implementasi tiket 01, terpisah dari firmware monitoring dan layanan Docker yang sedang berjalan. Profilnya ML-KEM-512, ChaCha20-Poly1305 IETF, dan **prospective FN-DSA degree 512**. Tidak ada pengiriman MQTT, penulisan InfluxDB, atau klaim sesi produksi/anti-replay pada bukti satu pesan ini.

## Batas perilaku dan format

1. Penerima LXC membuat kunci ML-KEM dan dua identitas FN-DSA disposable dengan CSPRNG sistem. Fixture privat berpermission 600 di direktori 700; direktori baru wajib dipakai untuk fixture baru.
2. Server menandatangani challenge berisi public key ML-KEM, public key identitas perangkat, dan salt acak. ESP32 sudah memiliki public key server yang dipercaya dan kunci privat perangkat melalui fixture lokal.
3. ESP32 memverifikasi tanda tangan server, melakukan ML-KEM encapsulation dengan 32 byte acak baru, dan menandatangani transcript challenge + ciphertext KEM. Domain tanda tangan server dan perangkat berbeda.
4. HKDF-SHA256 menurunkan kunci data dari rahasia KEM, salt, dan hash transcript. HKDF/SHA256 adalah operasi pendukung; tiga algoritma yang ditetapkan tetap dipakai sesuai fungsinya.
5. Tepat **satu** pesan sintetis dienkripsi per rahasia KEM baru. Nonce 12 byte bernilai nol hanya dipakai sekali di bawah kunci baru itu. Ini tidak boleh diperluas menjadi loop pengiriman dengan kunci yang sama. Transcript dipakai sebagai AAD; signature perangkat mengautentikasi pembentukan kunci, bukan tanda tangan terpisah untuk setiap payload.
6. LXC memverifikasi transcript dan tanda tangan, melakukan decapsulation, lalu memverifikasi tag sebelum menerima plaintext. Panjang dibatasi 160 byte dan padding wajib nol. Kegagalan tidak mengembalikan plaintext parsial.

Challenge tetap 2.395 byte dan response tetap 1.624 byte, hanya field byte tanpa padding struktur. Keduanya lebih besar daripada buffer MQTT lama; penyesuaian transport adalah pekerjaan tiket berikutnya. Workspace FN-DSA 30.239 byte berada di area statis, bukan stack Arduino; worker bukti memakai stack 32.768 byte dan prioritas rendah.

## Sumber dan build

`sources.lock.json` menyimpan commit dan SHA-256 setiap berkas upstream. Sumber beserta lisensinya disertakan di repository, sehingga build tidak memakai branch upstream yang bergerak. Untuk memeriksa salinan lokal:

```powershell
node tools/pqc/verify_sources.mjs
```

`vendor.mjs` hanya diperlukan maintainer ketika mengimpor kembali checkout yang sudah tepat di `evidence/local/pqc-sources/`. Skrip menolak revisi upstream lain. Adapter milik proyek, seperti `library.json` dan `mbedtls_extra.h`, tidak diklaim sebagai sumber upstream.

Pada Linux/LXC, pasang compiler, make, development headers OpenSSL, dan Python venv. Jalankan dari akar salinan proyek yang menjadi direktori uji (deployment pengujian saat ini: `/opt/lab-kimia-suhu/pqc-proof`):

```sh
make -C tools/pqc -j2
evidence/local/pqc-build/pqc-proof init evidence/local/fixture-01
mkdir -p firmware/include
cp evidence/local/fixture-01/pqc_fixture.h firmware/include/pqc_fixture.h
python3 -m venv .venv
.venv/bin/pip install platformio==6.1.19
PLATFORMIO_CORE_DIR="$PWD/evidence/local/platformio" .venv/bin/pio run -d firmware -e pqc-proof -j2
```

Jika fixture sudah dibuat, gunakan kembali fixture untuk memverifikasi capture yang bersangkutan; jangan menjalankan `init` ulang pada direktori yang sama. Kunci fixture bukan kunci produksi. Header privat dan seluruh artefak uji/build diabaikan Git.

SDK Arduino yang dipakai menyediakan header Mbed TLS 2.28.7 tetapi menonaktifkan implementasi ChaCha20/Poly1305/HKDF dalam arsip binernya. Build uji melengkapi empat compilation unit resmi dari versi yang sama dan mengaktifkannya melalui `CONFIG_MBEDTLS_*`. Pemeriksaan versi menggagalkan build jika SDK berganti tanpa peninjauan. Kriptografi tersebut menggunakan komponen Mbed TLS langsung, tanpa koneksi TLS.

Sejak tiket 06, build default adalah `pqc-telemetry`. `pqc-proof` tetap harus dipilih eksplisit untuk fixture satu pesan ini; [operasi utama](../../docs/operasi-pqc.md) memakai private identity/session, bukan fixture tiket 01.

## Kontrol LXC

```sh
evidence/local/pqc-build/pqc-proof respond evidence/local/fixture-01 evidence/local/native-response.bin
evidence/local/pqc-build/pqc-proof verify evidence/local/fixture-01 evidence/local/native-response.bin
evidence/local/pqc-build/pqc-proof selftest evidence/local/fixture-01 evidence/local/native-response.bin
```

Kontrol mencakup vektor ChaCha20-Poly1305 RFC 8439 bagian 2.8.2, plaintext yang harus sama, serta penolakan tanda tangan server/perangkat yang berubah, identitas server salah, challenge/KEM transcript berubah, ciphertext/tag/nonce berubah, panjang kosong/berlebih, padding tidak kanonis, dan kunci privat KEM salah. Kontrol positif diulang setelah mutasi.

## Menjalankan Wokwi

### Browser, untuk bukti tiket 01

Gabungkan image di LXC agar bootloader, partition table, dan aplikasi cocok:

```sh
.venv/bin/python evidence/local/platformio/packages/tool-esptoolpy/esptool.py --chip esp32 merge_bin \
  -o evidence/local/pqc-proof-full.bin \
  0x1000 firmware/.pio/build/pqc-proof/bootloader.bin \
  0x8000 firmware/.pio/build/pqc-proof/partitions.bin \
  0xe000 evidence/local/platformio/packages/framework-arduinoespressif32/tools/partitions/boot_app0.bin \
  0x10000 firmware/.pio/build/pqc-proof/firmware.bin
```

Salin file secara biner dengan SCP. Contoh pada PowerShell dari akar proyek laptop:

```powershell
New-Item -ItemType Directory -Force evidence/local/pqc-firmware
scp root@10.34.211.141:/opt/lab-kimia-suhu/pqc-proof/evidence/local/pqc-proof-full.bin evidence/local/pqc-firmware/pqc-proof-full.bin
```

1. Buka [template custom firmware ESP32 resmi](https://wokwi.com/projects/305457271083631168), supaya proyek monitoring utama tidak perlu diubah.
2. Klik area kode dan tekan **F1**.
3. Pilih **Upload Firmware and Start Simulation…** (nama lama: **Load HEX File and Start Simulation…**).
4. Pilih `evidence/local/pqc-firmware/pqc-proof-full.bin`. Simulasi mulai dari berkas hasil build, tanpa menyalin kode atau library ke editor web.
5. Pertahankan tab aktif. Tunggu `PQC_BEGIN`, satu baris JSON `PQC_METRICS`, satu baris panjang `PQC_RESPONSE`, dan `PQC_DONE`.
6. Salin seluruh keluaran serial itu ke berkas UTF-8 `evidence/local/wokwi-serial.txt`. Jika terdapat `PQC_FAILED`, panic, watchdog, atau reboot, simpan kegagalannya dan jangan mengklaim lulus.

### VS Code, target simulator integrasi berikutnya

Wokwi VS Code memerlukan extension dan lisensi yang sesuai. Salin `firmware.bin` dan `firmware.elf` hasil environment `pqc-proof` ke `evidence/local/pqc-firmware/`, lalu pilih konfigurasi `tools/pqc/simulator/wokwi.toml` melalui **Wokwi: Select Config File** dan jalankan **Wokwi: Start Simulator**. Konfigurasi itu hanya menambahkan satu ESP32 dengan Serial Monitor; tidak mengubah rangkaian monitoring lama.

## Memverifikasi capture ESP32 di LXC

Salin capture serial dengan SCP ke direktori uji. Kemudian:

```sh
python3 tools/pqc/extract_capture.py evidence/local/wokwi-serial.txt evidence/local/esp32-response.bin
evidence/local/pqc-build/pqc-proof verify evidence/local/fixture-01 evidence/local/esp32-response.bin
evidence/local/pqc-build/pqc-proof selftest evidence/local/fixture-01 evidence/local/esp32-response.bin
python3 tools/pqc/collect_evidence.py --capture evidence/local/wokwi-serial.txt \
  --runtime-image evidence/local/pqc-proof-tested.bin \
  --output docs/evidence/pqc-ticket-01/summary.json
```

Simpan salinan image yang benar-benar diunggah sebagai `evidence/local/pqc-proof-tested.bin`, khususnya jika setelahnya ada rebuild. Extractor menolak capture tidak lengkap, gabungan beberapa run, panjang response salah, atau kegagalan yang tercampur. Collector memverifikasi kembali hash sumber, kontrol native, dan response ESP32 sebelum menulis laporan. Tanpa `--capture`, laporan tetap menyatakan `esp32_runtime.verified=false`; build/native tidak dapat mengisi kelulusan runtime secara otomatis.

## Batas klaim

- `c-fn-dsa` yang dikunci adalah implementasi **prospektif**, bukan standar FN-DSA/FIPS 206 final dan bukan sekadar mengganti nama Falcon lama. Format kunci/signature dapat berubah pada revisi berikutnya.
- Ini bukti fungsional dengan fixture sekali pakai, bukan protokol sesi MQTT yang diaudit. Challenge belum interaktif, belum ada liveness/anti-replay sesi, dan belum ada rotasi kunci produksi. Pekerjaan itu tetap diperlukan pada tiket integrasi.
- ESP32 mengaktifkan radio Wi-Fi sebelum mengambil randomness. RNG dan waktu di Wokwi merupakan hasil simulasi; ini tidak membuktikan mutu entropy atau performa papan fisik, ketahanan side channel, maupun fault injection.
- RAM statis tidak mencakup seluruh alokasi Wi-Fi dan task. `PQC_METRICS` melaporkan heap dan sisa stack; minimum heap mencakup masa hidup aplikasi sejak boot, bukan hanya satu operasi kriptografi. `encrypt_us` mencakup HKDF dan AEAD.
- Bukti serial yang disediakan pengguna harus diatribusikan demikian; tanda tangan valid bukan attestation bahwa sebuah chip fisik menjalankan kode.

Referensi: [ML-KEM/FIPS 203](https://csrc.nist.gov/pubs/fips/203/final), [mlkem-native](https://github.com/pq-code-package/mlkem-native), [prospective c-fn-dsa](https://github.com/pornin/c-fn-dsa), [Mbed TLS 2.28.7](https://github.com/Mbed-TLS/mbedtls/tree/v2.28.7), [RFC 8439](https://www.rfc-editor.org/rfc/rfc8439.html), [custom firmware Wokwi](https://docs.wokwi.com/guides/esp32#custom-application-firmware).
