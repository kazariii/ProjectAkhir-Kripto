# Verifikasi tiket 06

Tanggal: 10 November 2026. Acuan: [06-bukti-keamanan-tls.md](../.scratch/monitoring-lab-kimia/issues/06-bukti-keamanan-tls.md). Penghambat tiket 01 sudah `done`. Seluruh 11 acceptance criteria lulus; status `done`. Spesifikasi induk, glosarium, dan ADR belum tersedia; acceptance criteria tiket menjadi acuan.

## Alur dan batas perubahan

Jalur utama tetap ESP32/Wokwi → MQTT/TLS EMQX → MQTT/TLS Telegraf → InfluxDB → Grafana. Firmware memakai `setCACert` serta hostname DNS; Telegraf memakai `ssl://…:8883`, CA, dan `insecure_skip_verify=false`. Tidak ada perubahan firmware, layanan Compose, ACL, atau akun EMQX.

Eksperimen terpisah memakai Mosquitto 2.0.22 dengan image/digest yang sudah digunakan pengujian stack, sertifikat CA/server berumur satu hari, serta akun acak khusus demo. Port broker dan relay hanya dipublikasikan pada loopback dengan nomor sementara. Container tidak bergabung dengan jaringan Compose utama dan tidak memakai volume/data utama. Kredensial dan private key sementara dihapus setelah uji; container demo juga dibersihkan.

Probe MQTT 5 tiket 05 dipakai kembali, dengan tambahan TCP biasa hanya ketika konteks TLS secara eksplisit `None`. Semua pengiriman uji QoS 1, DUP=0, RETAIN=0, Clean Start, tanpa retry atau reconnect otomatis. Tidak ada dependensi Python baru. Wireshark/dumpcap diperlukan untuk capture paket nyata; OpenSSL dan Docker sudah digunakan pengujian proyek sebelumnya.

Alur integritas:

```text
klien MQTT + TLS terverifikasi → relay TCP byte → broker MQTT + TLS lokal
                                                    ↓
                                   subscriber TLS independen (tanpa relay)
```

Relay tidak mengakhiri TLS, tidak memiliki sertifikat/private key atau kunci sesi, dan tidak mengubah nilai JSON. Relay merangkai record lengkap melintasi potongan TCP. Klien menyelesaikan handshake serta menerima CONNACK 0 lebih dahulu, lalu mengaktifkan relay dan langsung mengirim satu PUBLISH. Hanya badan record protected berikutnya yang diubah satu bit; header dan panjang tetap. Dengan urutan ini encrypted handshake bukan sasaran eksperimen. Kontrol sebelum/sesudah juga melewati relay, masing-masing memakai koneksi baru, sedangkan subscriber yang sama tetap aktif selama ketiga tahap.

## Mengulang eksperimen lokal

Prasyarat: Python 3.11, Docker Desktop aktif, OpenSSL (salinan Git for Windows dideteksi), Wireshark 4.6 dengan dumpcap/tshark serta Npcap yang dapat menangkap loopback. Skrip menggunakan instalasi yang tersedia; tidak memasang software atau mengubah konfigurasi jaringan. Jalankan dari akar repository:

```powershell
python tests/check_tls_relay.py
python tests/check_tls_security.py
```

Uji pertama memeriksa fragmentasi/coalescing TCP, penerusan record sebelum relay aktif, perubahan tepat satu bit, dan record berikutnya yang tetap utuh. Record uji ini sintetis dan bukan bukti keamanan TLS. Uji kedua melakukan koneksi MQTT/TLS dan penangkapan paket sebenarnya, sekitar satu menit.

Windows memakai `\Device\NPF_Loopback` secara default; Linux memakai `lo`. Jika berbeda, lihat daftar interface dan pilih loopback:

```powershell
& 'C:/Program Files/Wireshark/dumpcap.exe' -D
python tests/check_tls_security.py --interface '<interface-loopback-dari-daftar>'
```

Skrip menjalankan perbandingan plaintext/TLS, kontrol integritas awal, percobaan ciphertext rusak, dan kontrol akhir. Semua koneksi TLS memverifikasi CA demo serta identitas `127.0.0.1` pada SAN sertifikat. Eksperimen lokal sengaja memakai TLS 1.3; tidak menurunkan konfigurasi TLS jalur utama. Key logging tidak diaktifkan, termasuk bila `SSLKEYLOGFILE` ada pada lingkungan pengguna. Analisis TShark juga mengosongkan `tls.keylog_file`.

Hasil berada di `evidence/local/ticket-06/ticket06-<acak>/`: `result.json`, capture `plaintext.pcapng`, `tls.pcapng`, `integrity.pcapng`, log broker, log capture, serta stream ciphertext dan log relay setiap tahap. Exit code 0 berarti seluruh uji lulus; exit code 1 berarti gagal dengan `failed_step`, bukan bukti penolakan. Timeout klien tidak dihitung sebagai keberhasilan uji integritas. Jika Docker gagal dibersihkan, JSON menyebut nama container khusus run yang perlu diperiksa.

Capture plaintext mentah mencakup password demo sekali pakai dalam CONNECT. Simpan di direktori lokal yang diabaikan Git dan jangan tampilkan CONNECT saat presentasi. Salinan publik [plaintext-publish.pcapng](evidence/ticket-06/plaintext-publish.pcapng) hanya mengekspor frame PUBLISH/PUBACK; tidak memuat CONNECT atau password. Jangan mengganti akun demo dengan akun proyek utama.

## Mengulang capture jalur utama

1. Jalankan Wokwi dan stack seperti [panduan jalur sensor](jalur-suhu.md). Tunggu serial `Terkirim` dan data baru di Grafana. Pertahankan CA/hostname verification pada kedua klien.
2. Pada Wokwi yang sedang berjalan, klik indikator WiFi → **Download PCAP file**. Simpan lokal. Capture ini berasal dari sisi ESP32 virtual, bukan capture WebSocket browser. Tidak perlu mengubah sketch atau menghentikan simulator.
3. Untuk sisi Telegraf, temukan interface jaringan aktif dengan `dumpcap -D`. Ambil capture pendek, dibatasi hostname deployment dan TCP 8883. Contoh PowerShell berikut membaca **hostname saja**, tanpa menampilkan konfigurasi atau kredensial:

   ```powershell
   $demoBrokerHost = ((Get-Content .env | Where-Object { $_ -match '^MQTT_HOST=' }) -split '=',2)[1].Trim()
   & 'C:/Program Files/Wireshark/dumpcap.exe' -i '<interface-aktif>' -f "host $demoBrokerHost and tcp port 8883" -a duration:20 -w evidence/local/ticket-06/telegraf-emqx.pcapng
   ```

   Pada Docker Desktop, capture host dapat memperlihatkan alamat/port NAT. Cocokkan tujuan dengan koneksi aktif Telegraf (`/proc/net/tcp` pada container) dan hostname proyek; hindari menjalankan probe MQTT lain selama jendela capture. Capture di tengah sesi dapat hanya memuat record protected tanpa ClientHello/ServerHello. Jangan menyimpulkan versi cipher dari nomor port saja, dan jangan mengulang koneksi produksi hanya untuk menangkap handshake.
4. Periksa kedua berkas tanpa kunci dekripsi:

   ```powershell
   python tests/check_tls_primary.py --esp32-capture '<capture-Wokwi.pcap>' --telegraf-capture evidence/local/ticket-06/telegraf-emqx.pcapng
   ```

   Hasil `primary-result.json` tersimpan lokal. Pemeriksaan membutuhkan record protected TLS di TCP 8883 dan tidak menemukan nama field/identitas pengukuran sebagai plaintext. TShark merangkai stream TCP sebelum pencarian agar batas segmen tidak menyembunyikan penanda. Identitas aplikasi MQTT pada capture terenkripsi tetap berasal dari provenance simulator, koneksi Telegraf, konfigurasi, dan alur data yang telah diamati; skrip tidak mengklaim mendekripsi isi MQTT.

## Hasil aktual

Run final **`ticket06-8162f83ddc98`**, **20:55:04–20:55:55 WIB**, 10 November 2026: kelima tahap eksperimen lulus, exit code 0. Runtime klien OpenSSL 3.0.13, broker Mosquitto 2.0.22, TShark 4.6.7. [Hasil JSON](evidence/ticket-06/result.json) menyimpan penanda, kode respons, log TLS aktual, detail perubahan, dan hash bukti lokal. [Manifest ekspor](evidence/ticket-06/manifest.json) mencatat hash berkas publik; capture plaintext publik difilter sehingga hash-nya memang berbeda dari capture mentah lokal.

| Percobaan | Hasil aktual |
| --- | --- |
| Plaintext lokal, port 58979 | CONNACK/SUBACK/PUBACK 0; subscriber menerima payload identik. Penanda `ticket06-8162f83ddc98-plaintext` terlihat pada stream TCP |
| TLS lokal, port 58978 | CONNACK/SUBACK/PUBACK 0; subscriber menerima payload identik. Penanda `ticket06-8162f83ddc98-tls` tidak ditemukan dalam stream TCP tanpa kunci; 19 frame record protected |
| Kontrol integritas awal | Koneksi TLS baru, CONNACK 0, PUBACK 0, penanda `…-before` diterima subscriber; stream relay identik, 0 bit berubah |
| Ciphertext rusak | CONNACK 0 diterima sebelum arming. Record klien ke-5, offset badan 63, byte **50 → 51** (XOR 1). Header tetap **`170303007e`**, ukuran tetap **131 byte**. Perbandingan keseluruhan stream memastikan tepat **1 bit** berubah |
| Bukti TLS aktual | Klien: `SSLError`, library `SSL`, reason **`SSLV3_ALERT_BAD_RECORD_MAC`**. Broker: **`decryption failed or bad record mac`**, diikuti `record layer failure` dan pemutusan koneksi |
| Hasil MQTT/subscriber saat rusak | Tidak menerima PUBACK; subscriber tidak menerima pesan selama observasi 2 detik. Ketiadaan ini didukung alert TLS dan diagnosis broker, bukan dijadikan bukti tunggal |
| Kontrol integritas akhir | Koneksi TLS baru, CONNACK 0, PUBACK 0, penanda `…-after` diterima subscriber yang tetap aktif; 0 bit berubah |
| Versi pada ketiga tahap integritas | **TLSv1.3**, **TLS_AES_256_GCM_SHA384**, verifikasi CA dan SAN/hostname aktif |
| Capture ESP32 utama | **796** frame TCP 8883, **277** frame protected; sembilan ServerHello TLS 1.2, cipher `0xc02f` (ECDHE_RSA_AES_128_GCM_SHA256); nama field dan identitas sensor tidak tampak sebagai plaintext |
| Capture Telegraf utama | **17** frame TCP 8883 dalam 20 detik, **9** frame protected pada koneksi ke broker. Capture dimulai di tengah sesi sehingga tidak mengklaim versi/cipher dari handshake yang tidak tertangkap. Field pengukuran tidak tampak sebagai plaintext |

Nama reason `SSLV3_ALERT_BAD_RECORD_MAC` merupakan label error OpenSSL; koneksi yang diuji **TLS 1.3**, bukan SSLv3. Dalam TLS 1.3, outer type 23 juga dapat membawa encrypted handshake/alert; jumlah frame protected bukan jumlah pesan MQTT. Gate setelah CONNACK memastikan record yang dirusak berasal dari PUBLISH sesudah handshake.

Capture Wokwi diunduh dari simulasi yang telah berjalan (termasuk koneksi ulang sebelumnya); pemeriksaan Telegraf memakai filter broker proyek dan memperlihatkan satu flow aktif, konsisten dengan tujuan koneksi pada container. Capture ini tidak menyertakan kunci dekripsi. [Ringkasan capture utama](evidence/ticket-06/primary-result.json) mencatat hasil pemeriksaan terhadap salinan PCAP publik yang hanya memuat TCP 8883.

## Bahan presentasi dan kesimpulan

Buka berkas di [direktori bukti](evidence/ticket-06/). Urutan singkat:

1. `esp32-emqx.pcapng` dan `telegraf-emqx.pcapng`: filter `tcp.port == 8883`; perlihatkan TLS record. Capture ini berasal dari jalur utama.
2. `plaintext-publish.pcapng`: **Decode As → MQTT**, port 58979. **Follow → TCP Stream** memperlihatkan penanda serta JSON suhu/gas. CONNECT sudah dikeluarkan dari salinan ini.
3. `tls.pcapng`: **Decode As → TLS**, port 58978. **Follow → TCP Stream** tidak memperlihatkan penanda JSON, meskipun subscriber dalam hasil uji menerima payload identik.
4. `result.json`, `tampered-relay.json`, dan `broker.txt`: perlihatkan kontrol awal, arming setelah CONNACK, perubahan satu bit, alert aktual, tidak adanya PUBACK/penerimaan, lalu kontrol akhir. `integrity.pcapng` merekam sisi broker; pasangan `tampered-client-original.tls`/`tampered-client-forwarded.tls` adalah byte ciphertext yang benar-benar diterima/diteruskan relay.

**Kerahasiaan:** TLS menyembunyikan isi pesan dari pengamat di perjalanan pada koneksi yang diuji. IP, port, arah, ukuran, waktu, dan sebagian metadata handshake (misalnya SNI/sertifikat bila terlihat pada versi itu) masih dapat diamati. Kedua hop ESP32–broker dan Telegraf–broker memakai TLS. Broker mengakhiri kedua koneksi dan tetap menjadi titik tepercaya yang dapat membaca pesan: ini bukan enkripsi ujung-ke-ujung ESP32 ke Grafana. Koneksi HTTP internal Docker/dashboard berada di luar klaim kerahasiaan MQTT ini.

**Integritas:** perubahan ciphertext selama perjalanan terdeteksi pada koneksi TLS 1.3 lokal yang diuji. Sesuai [RFC 8446 §5.2](https://www.rfc-editor.org/rfc/rfc8446.html#section-5.2), kegagalan membuka record protected menyebabkan penghentian koneksi dengan `bad_record_mac`. Uji ini tidak membuktikan kebenaran sensor, kejujuran pengirim, integritas data tersimpan, semua versi/cipher TLS, atau keamanan seluruh deployment EMQX. Pengirim sah yang mengubah nilai **sebelum** mengenkripsi dan mengirimnya bukan eksperimen perubahan ciphertext selama perjalanan.

Autentikasi/otorisasi akun dan penolakan CA tidak dipercaya dibuktikan terpisah pada [tiket 05](verifikasi-tiket-05.md); tidak ada klaim mutual TLS. Bukti aktual tiket 06 sudah dijalankan. Belum ada klaim audit keamanan deployment secara menyeluruh atau deteksi manipulasi sensor/database.

Semua password/token/private key lokal tetap dikecualikan dari Git. Bukti yang disertakan hanya payload demo, ciphertext, metadata jaringan proyek, serta log tanpa rahasia; capture plaintext mentah tetap di `evidence/local/`. Tidak ada data/volume utama yang dihapus.
