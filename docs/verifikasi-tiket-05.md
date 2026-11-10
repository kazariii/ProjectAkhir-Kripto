# Verifikasi tiket 05

Tanggal: 10 November 2026. Acuan: [05-autentikasi-otorisasi.md](../.scratch/monitoring-lab-kimia/issues/05-autentikasi-otorisasi.md). Penghambat tiket 01 sudah `done`. Seluruh acceptance criteria lulus pada deployment proyek; status `done`. `spec.md`, glosarium, dan ADR belum tersedia; acceptance criteria tiket menjadi acuan.

## Alur dan batas perubahan

Jalur sah yang sudah ada dipakai kembali: ESP32/Wokwi → MQTT/TLS EMQX Serverless → Telegraf → InfluxDB → Grafana. ESP32 dan Telegraf memiliki username berbeda; izin dimiliki broker, pemeriksaan sertifikat dimiliki klien TLS. Tidak perlu perubahan firmware, parser, dashboard, akun, atau aturan broker untuk tiket ini.

Tambahan berupa [pengujian berulang](../tests/check_mqtt_access.py) dan [probe MQTT 5](../tests/mqtt_probe.py). Probe mengikuti pola pengujian stack yang sudah memakai socket/SSL Python. Cakupannya hanya CONNECT, SUBSCRIBE satu filter, PUBLISH QoS 1, serta pembacaan respons; bukan klien aplikasi umum. Tidak ada dependensi Python tambahan, reconnect otomatis, retry pesan, retained publish, atau sesi persisten. MQTT 5 dipakai agar alasan penolakan terlihat; firmware tetap memakai MQTT 3.1.1/QoS 0.

Kontrol sensor tetap memakai identitas `esp32-meja01`. Pesan sintetis memakai `device_id=ticket05-<acak>-<kasus>` agar terpisah dari pengukuran ESP32. Dua pesan kontrol sintetis dikirim pada topik sah, tersimpan dengan tag khusus, dan diverifikasi melalui datasource produksi di API Grafana. Pesan itu tidak muncul di panel sensor karena panel memfilter `esp32-meja01`. Bukti tampilan panel sensor berasal dari ESP32 yang terus berjalan, bukan dari pesan sintetis.

## Cara mengulang

1. Ikuti [panduan jalur sensor](jalur-suhu.md), jalankan Compose dan Wokwi. Gunakan hanya deployment serta akun demonstrasi proyek milik sendiri. Pertahankan Spend Limit 0.
2. Pastikan `.env`, `firmware/include/secrets.h`, dan `infra/certs/emqx-ca.pem` sudah diisi lokal dan diabaikan Git. Skrip membaca konfigurasi itu langsung tanpa mencetak nilainya. Format yang didukung adalah nilai literal sederhana sesuai template proyek; password/token hex dianjurkan. Jangan menyalin sandi ke argumen perintah, chat, atau laporan.
3. Periksa **Client Authorization → Default Authorization**. Simpan bukti tiga aturan berikut, serta tab **Client ID** yang tidak memiliki allow tambahan. Bila terdapat sumber otorisasi lain, tinjau agar tidak melewati kebijakan ini.

   | Subjek | Topik | Operasi | Izin |
   | --- | --- | --- | --- |
   | Username `esp32-meja01` | `lab/kimia/meja01/telemetry` | Publish | Allow |
   | Username `telegraf-meja01` | `lab/kimia/meja01/telemetry` | Subscribe | Allow |
   | All Users | `#` | Publish & Subscribe | Deny |

   Serverless memakai fallback deny eksplisit ini. Jangan menganggap banner blacklist bawaan sebagai bukti penolakan. Aturan username/client ID dicocokkan sebelum All Users; allow tambahan yang luas dapat melewati pembatasan. Perilaku ini dijelaskan dalam [dokumentasi EMQX](https://docs.emqx.com/en/cloud/latest/deployments/default_authz.html#configure-whitelist-mode-via-rules).

4. Dari akar repository, jalankan:

   ```powershell
   python tests/check_mqtt_access.py
   ```

   Python 3.11 dan layanan yang sudah berjalan cukup; skrip tidak memasang paket atau memulai/mengubah layanan. Semua client ID baru dan berbeda dari ID produksi, sehingga tidak mengambil alih sesi Wokwi/Telegraf. Proses selesai dengan exit code 0 hanya jika seluruh uji lulus. Exit code 1 dan `failed_step` pada JSON berarti belum lulus; timeout, koneksi terputus, atau layanan tidak tersedia tidak dihitung sebagai penolakan autentikasi/otorisasi.

5. Periksa JSON baru di `evidence/local/ticket-05/ticket05-<acak>.json`. Hasil hanya memuat penanda, kode respons, timestamp, dan ringkasan; tidak ada kredensial/header HTTP. Bukti aturan harus diperiksa di konsol karena akun MQTT tidak dapat membaca konfigurasi ACL. Skrip tidak mengklaim memeriksa konfigurasi fallback melalui API administrasi.
6. Saat presentasi, tunjukkan serial Wokwi, panel Grafana, aturan allow/deny, dan ringkasan uji. Sembunyikan `.env`, `secrets.h`, layar password, token, serta private key. Jangan menampilkan hasil render konfigurasi Compose atau log mentah yang belum diperiksa.

Urutan uji otomatis: tunggu **sampel ESP32 baru** dan kueri Grafana → kontrol sintetis sah dengan subscriber pembanding → penolakan kredensial → penolakan operasi topik → kegagalan verifikasi CA → ulangi kontrol sintetis dan **sampel ESP32 baru** → tunggu 5 detik, lalu periksa ketiadaan seluruh penanda negatif di InfluxDB. Tiap penantian sampel dibatasi 60 detik; terhambatnya simulator dapat membuat kontrol gagal dan harus diperbaiki sebelum menyimpulkan hasil.

Payload publish yang diuji memiliki field sensor valid, tetapi tag khusus; bila kebijakan keliru mengizinkannya, parser dapat menyimpannya dan uji akan gagal. Untuk kredensial salah, PUBLISH **tidak dikirim** setelah CONNACK penolakan karena sesi MQTT belum terbentuk. Untuk CA tidak dipercaya, CONNECT MQTT pun belum dikirim. Ketiadaan pengukuran bukan satu-satunya bukti; respons penolakan/kegagalan verifikasi TLS menjadi bukti utama. Waktu observasi ketiadaan dibatasi, bukan klaim bahwa pesan tidak mungkin pernah muncul pada masa depan.

## Hasil aktual

Run `ticket05-f2c780fb91d9`, **20:31:06–20:31:48 WIB**, 10 November 2026: **17 pemeriksaan lulus**, exit code 0. [JSON hasil yang sudah diperiksa](evidence/ticket-05-access.json) disertakan agar bukti kode respons dapat ditinjau tanpa membuka konfigurasi lokal.

| Lapisan / percobaan | Bukti aktual |
| --- | --- |
| ESP32 sah sebelum uji negatif | Sampel baru `esp32-meja01` diterima 20:31:08,628424376 WIB; terbaca InfluxDB dan kueri Grafana |
| Kontrol sintetis awal | CONNACK 0, SUBACK 0, PUBACK 0; payload identik diterima subscriber pembanding dengan akun penerima; satu titik 25,5 Celsius pada 20:31:13,024770391 WIB, terbaca Grafana |
| Username salah | CONNACK **135**; CONNECT ditolak, tidak mengirim PUBLISH |
| Username sah/password salah | CONNACK **134**; CONNECT ditolak, tidak mengirim PUBLISH |
| Tanpa kredensial | CONNACK **134**; CONNECT ditolak, tidak mengirim PUBLISH |
| Pengirim Subscribe topik utama, topik di luar izin, dan `lab/kimia/#` | Tiga SUBACK **135**, setelah autentikasi sah pada setiap sesi |
| Pengirim Publish topik di luar izin | PUBACK **135**, setelah autentikasi sah |
| Penerima Subscribe topik di luar izin dan `lab/kimia/#` | Dua SUBACK **135**, setelah autentikasi sah |
| Penerima Publish topik utama dan di luar izin | Dua PUBACK **135**, setelah autentikasi sah |
| Klien tanpa CA tepercaya | `SSLCertVerificationError`, verify code **20**; trust store kosong, `CERT_REQUIRED` dan pemeriksaan hostname tetap aktif; belum ada CONNECT/PUBLISH MQTT |
| Kontrol sintetis akhir | CONNACK 0, SUBACK 0, PUBACK 0; subscriber menerima payload identik; satu titik 25,5 Celsius pada 20:31:38,580826019 WIB, terbaca Grafana |
| ESP32 sah setelah uji negatif | Sampel baru diterima 20:31:41,976103790 WIB; InfluxDB dan Grafana tetap terbaca |
| Penanda negatif | Seluruh enam tag negatif tidak memiliki titik baru dalam jendela run setelah penantian 5 detik, lebih panjang dari flush Telegraf 2 detik |
| Konfigurasi fallback | Konsol diamati: dua izin username sesuai tabel, Client ID tidak memiliki aturan, All Users deny `#` untuk Publish & Subscribe; tidak mengubah konfigurasi |
| Tampilan demo akhir | Serial Wokwi tetap `Terkirim` dengan suhu 25/506 ADC; dashboard Normal, suhu 25,00 Celsius/506 ADC dan waktu penerimaan terus bertambah (capture 20:32:46 WIB) |

Menurut [spesifikasi MQTT 5 OASIS](https://docs.oasis-open.org/mqtt/mqtt/v5.0/os/mqtt-v5.0-os.html), 134 berarti *Bad User Name or Password*, sedangkan 135 berarti *Not authorized*. CONNACK 135 untuk username yang tidak dikenal tetap merupakan penolakan pada fase autentikasi, bukan hasil uji izin publish. SUBACK/PUBACK 135 diperoleh setelah CONNACK sah, sehingga bukti otorisasi dipisahkan dari kegagalan login.

Autentikasi perangkat di sini berarti akun username/password MQTT; ini tidak membuktikan identitas perangkat keras atau kebenaran sensor. Verifikasi sertifikat server memeriksa kepercayaan CA dan nama server melalui TLS. Tidak ada sertifikat/private key klien dan **tidak ada klaim mutual TLS**. TLS Python positif memakai CA deployment dengan pemeriksaan hostname aktif; ESP32 tetap `setCACert` dan Telegraf tetap `insecure_skip_verify=false` sesuai jalur yang sudah diverifikasi. Uji negatif CA adalah probe PC, bukan perubahan konfigurasi firmware/Telegraf. Pengujian ini tidak mencakup penyadapan atau perubahan ciphertext tiket 06, semua kemungkinan topik, maupun audit keseluruhan deployment.

## Berkas bukti dan rahasia

`evidence/local/ticket-05/` diabaikan Git. Di sana tersedia JSON run, `emqx-fallback.txt/.png`, `emqx-username-rules.txt/.png`, `emqx-client-id-rules.txt/.png`, `wokwi-serial.txt`, `wokwi-after.png`, dan `grafana-after.txt/.png`. Capture hanya memperlihatkan aturan, kode biasa, hasil sensor, serta dashboard; tidak membuka tab konfigurasi rahasia. JSON yang disertakan di `docs/evidence/` berisi hasil yang sama tanpa akun/password/token/private key.

Berkas `.env`, `firmware/include/secrets.h`, CA lokal, dan seluruh bukti lokal tetap diabaikan Git. Pemeriksaan berkas yang berpotensi di-push mencakup nilai literal kredensial/token dan penanda private key. Tidak ada sandi, token, atau private key yang ditambahkan oleh tiket ini. Dua pengukuran sintetis bertag khusus dibiarkan sebagai bukti; tidak ada penghapusan data atau volume.
