# Verifikasi PQC tiket 01: ESP32 ke LXC

Tanggal: 14 November 2026. [Tiket](../.scratch/mqtt-pqc/issues/01-bukti-kriptografi.md) dan [panduan reproduksi](../tools/pqc/README.md).

## Hasil

**Lulus pada batas bukti kelayakan satu payload.** Pengguna menjalankan firmware ESP32 di Wokwi dan mengirim log Serial Monitor. Response 1.624 byte dari log tersebut berhasil diverifikasi dan didekripsi oleh executable native di LXC. Ini bukan pengamatan UI simulator oleh agen atau hardware attestation; bukti runtime berasal dari log yang diberikan pengguna dan diperiksa secara kriptografis di LXC.

- ML-KEM-512 membentuk rahasia yang dapat dipakai kedua sisi.
- ESP32 melaporkan verifikasi tanda tangan server dan menghasilkan tanda tangan perangkat prospective FN-DSA degree 512; LXC memverifikasi tanda tangan perangkat terhadap transcript yang sama.
- ChaCha20-Poly1305 mengembalikan plaintext yang sama: perangkat uji `pqc-proof-only`, suhu 26,25 Celsius, gas relatif 321 ADC, kedua alarm false. Payload ini sintetis, bukan pengukuran sensor.
- Vektor ChaCha20-Poly1305 RFC 8439 lulus pada native LXC dan firmware ESP32. Dua kontrol positif dan 13 penolakan input rusak lulus, termasuk saat memakai response hasil simulator.
- Build firmware sensor utama dengan konfigurasi contoh dan regresi sensor/alarm juga lulus. Grafana dan InfluxDB tetap sehat; ketiga container monitoring tetap berjalan.

## Ukuran dan runtime

Build environment `pqc-proof`: Espressif platform 6.9.0, Arduino framework 3.20017.241212, Xtensa GCC 8.4.0. RAM statis **77.672 / 327.680 byte**, flash **783.849 / 1.310.720 byte** pada partisi aplikasi.

| Operasi / pengukuran | Hasil simulator ESP32 |
|---|---:|
| Verifikasi tanda tangan server | 234,340 ms |
| Encapsulation ML-KEM-512 | 175,921 ms |
| Tanda tangan FN-DSA | 12.386,392 ms |
| HKDF + enkripsi AEAD | 19,874 ms |
| Total bukti, termasuk self-test | 12.861,140 ms |
| Heap bebas sebelum / sesudah | 193.292 / 193.224 byte |
| Minimum heap sejak boot | 189.732 byte |
| Sisa stack worker 32.768 byte | 19.216 byte |
| Response biner | 1.624 byte |

Waktu di atas berasal dari jam virtual simulator, bukan benchmark papan fisik. Minimum heap mencakup alokasi aplikasi/Wi-Fi sejak boot. Satu pengukuran sebelum/sesudah tidak membuktikan bebas kebocoran memori.

Latensi tanda tangan sekitar **12,39 detik** merupakan batas integrasi yang nyata. Tiket sesi berikutnya perlu mempertahankan pemisahan tugas jaringan/kriptografi dari sensor dan alarm. FN-DSA digunakan saat pembentukan sesi; jangan memanggilnya ulang untuk setiap sampel dua detik.

## Kontrol negatif

Penerima/klien menolak: signature server rusak; challenge server tidak autentik pada jalur `respond`; public key server salah; isi challenge berubah; signature perangkat rusak; ciphertext KEM berubah; ciphertext data berubah; tag berubah; nonce berubah; panjang berlebih; panjang kosong; padding tidak kanonis; dan private key KEM yang salah. Kontrol positif diulang sesudah mutasi untuk membedakan penolakan yang benar dari penerima yang rusak.

## Bukti dan reproduksibilitas

- [Ringkasan terstruktur](evidence/pqc-ticket-01/summary.json) merekam hash sumber, versi/commit, kontrol native, response dan capture hash, ukuran build, serta runtime ESP32.
- [Log Serial Monitor dari pengguna](evidence/pqc-ticket-01/esp32-serial.txt) disalin sebagai teks LF. Hash capture mengacu pada salinan tersimpan ini, bukan berkas asli yang diunduh langsung dari simulator.
- Image yang diberikan untuk run pengguna: SHA-256 `c52b258e0ae4c18dbc0693eade143589e3aa124e017b73a5dc5b2cab009e3bc3`. Rebuild setelah penambahan pemeriksaan padding receiver memiliki hash berbeda; laporan memisahkan hash build terakhir dan image yang diuji. Data operasi pengirim dan ukuran build tetap sama.
- Fixture privat berada di direktori uji LXC, dengan berkas 600 dan direktori 700. Header fixture dan image firmware yang mengandung kunci uji disposable diabaikan Git. Serial log hanya memuat response publik/terenkripsi, bukan private key atau shared secret.
- Pemeriksaan SHA-256 atas 156 berkas upstream lulus. Lisensi disertakan. Prospective `c-fn-dsa` dikunci pada `1b858880dcac091b5e5f84f0e4d8617c35ba1392`; ML-KEM native v2.0.0 pada `d1b2fe782888bdb761a50336012923180be7f502`; komponen tambahan Mbed TLS 2.28.7 pada `555f84735aecdbd76a566cf087ec8425dfb0c8ab`.

## Batas tiket

Tiket ini membuktikan operasi dan interoperabilitas kriptografi, bukan sesi MQTT langsung atau pengiriman sensor ke Grafana. Challenge masih berupa fixture; anti-replay/liveness sesi, reconnect produksi, ACL broker baru, dan migrasi penerimaan merupakan tiket lanjutan. Implementasi FN-DSA bersifat prospektif dan tidak diklaim memenuhi FIPS 206 final. Simulator tidak membuktikan mutu entropy perangkat fisik atau ketahanan side channel.

Perubahan berada lokal pada repository dan direktori uji LXC. Tidak ada push GitHub atau penggantian layanan monitoring produksi.
