# 01: Buktikan kriptografi ESP32 ke LXC

**What to build:** Satu payload uji dari ESP32/Wokwi dapat dilindungi dengan ML-KEM-512 dan ChaCha20-Poly1305, lalu dibuka oleh penerima di LXC. Kedua pihak memverifikasi tanda tangan uji prospective FN-DSA-512. Bukti ini menentukan kelayakan library sebelum integrasi MQTT.

**Blocked by:** None (can start immediately).

**Status:** done

- [x] Sumber kriptografi, lisensi, versi, konfigurasi, dan hash berkas dikunci agar ESP32 dan LXC memakai implementasi yang sama.
- [x] Build ESP32 berhasil tanpa mengubah firmware sensor utama; penggunaan flash dan RAM statis dicatat.
- [x] Eksekusi ESP32/Wokwi nyata memverifikasi tanda tangan server, melakukan encapsulation ML-KEM-512, menandatangani transcript uji, dan mengenkripsi satu payload dengan ChaCha20-Poly1305.
- [x] Penerima LXC memverifikasi tanda tangan perangkat, melakukan decapsulation, dan memperoleh payload yang sama; bukti terhubung dengan keluaran ESP32 yang benar-benar dijalankan.
- [x] Pengujian negatif menolak tanda tangan/kunci yang salah, transcript yang berubah, serta ciphertext/tag AEAD yang dirusak; kontrol positif tetap lulus.
- [x] Waktu operasi, heap/stack ESP32 saat berjalan, batas buffer, dan hasil aktual tersimpan sebagai bukti; keterbatasan simulator serta status FN-DSA prospektif dijelaskan.
- [x] Rahasia/fixture privat dan artefak build tidak masuk Git. Panduan reproduksi tersedia; tidak ada perubahan layanan monitoring produksi.

## Comments

Selesai 14 November 2026. [Verifikasi dan batas klaim](../../../docs/verifikasi-pqc-tiket-01.md), [ringkasan aktual](../../../docs/evidence/pqc-ticket-01/summary.json), [log simulator yang diberikan pengguna](../../../docs/evidence/pqc-ticket-01/esp32-serial.txt), dan [panduan reproduksi](../../../tools/pqc/README.md).

Pengguna menjalankan image ESP32 di Wokwi dan memberikan log lengkap. Pemeriksaan kriptografi dilakukan langsung di LXC terhadap response 1.624 byte tersebut: signature/transcript diterima, decapsulation dan tag AEAD benar, plaintext sintetis sama persis. Dua kontrol positif dan 13 kasus negatif lulus untuk response simulator serta kontrol native. Vektor RFC 8439 lulus pada kedua target. Ini bukan pengamatan UI oleh agen atau attestation perangkat fisik.

Build proof memakai RAM statis 77.672 byte dan flash 783.849 byte. Log pengguna melaporkan total 12,861140 detik, signature FN-DSA 12,386392 detik, minimum heap 189.732 byte, dan sisa stack task 19.216 byte. Latensi adalah waktu virtual simulator; tiket sesi harus menjaga sensor/alarm tetap terpisah dari operasi tanda tangan.

156 hash berkas upstream lulus. Build default sensor dan pengujian regresi loop/telemetri lulus. API kesehatan Grafana/InfluxDB serta container monitoring tetap berjalan. Kunci uji dan image firmware diabaikan Git; tidak ada push GitHub. Tiket 02 tidak memiliki blocker dari tiket ini; tiket 03 tetap memerlukan 02 sebelum sesi MQTT dapat diintegrasikan.
