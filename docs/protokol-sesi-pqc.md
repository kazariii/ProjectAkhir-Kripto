# Protokol eksperimen sesi PQC, LK3 versi 1

Satu implementasi C++ [`Channel`](../firmware/lib/pqc-proof/src/pqc_session.h) berjalan pada ESP32 (Mbed TLS) dan LXC (OpenSSL). Python hanya mengatur MQTT, antrean dan lifecycle melalui adapter C ABI. Satu worker memiliki satu Channel dan workspace FN-DSA; operasi tanda tangan tidak berjalan pada callback jaringan. Primitive bersama dipakai juga oleh bukti tiket 01, tanpa mengubah format proof lama.

Profil tetap: ML-KEM-512, prospective FN-DSA degree 512, HKDF-SHA256, ChaCha20-Poly1305 IETF. Sumber vendor mengikuti [lock tiket 01](../tools/pqc/sources.lock.json). Tidak ada negosiasi algoritma, TLS atau fallback plaintext. Ini protokol lab khusus yang belum diaudit independen; tidak diklaim sebagai standar transport aman atau implementasi final FIPS 206.

## Identitas dan transport

Kedua pihak menyimpan secret/public FN-DSA sendiri dan public peer yang dipin sebelum koneksi. Binding identitas adalah `SHA256(server_public || client_public)`. Tidak ada TOFU maupun distribusi private key melalui MQTT. Setiap handshake menghasilkan pasangan ML-KEM server baru; secret ML-KEM dan shared secret dibuang setelah pembentukan sesi.

Transport MQTT biasa TCP/1883 memakai dua topik: `lab/kimia/pqc/session/up` untuk client→server dan `.../down` untuk server→client. Data binary, QoS 0, `retain=false`, MQTT clean session. Receiver membuang retained messages; callback PubSubClient tidak mengekspos flag retain, sehingga firmware mengandalkan nonce/transcript baru serta pemeriksaan sesi/counter untuk menolak replay. ACL hanya memberi tiap pihak arah topiknya. Header maksimum 1519 byte, di bawah batas broker 4096 dan buffer firmware 4096.

MQTT password dan metadata topik tetap terbuka pada transport ini. Autentikasi aplikasi berasal dari pin/tanda tangan serta konfirmasi kunci, bukan kerahasiaan password broker. Broker/jaringan dapat menghapus, menunda atau membanjiri pesan; ketersediaan tidak dijamin oleh algoritma ini.

## Wire format

Semua panjang tetap, tanpa native struct/padding atau parser JSON pada handshake. Header `H(type)` adalah byte `4c 4b 33 01` diikuti type satu byte. Semua integer wire little-endian. Semua frame menolak magic, versi, tipe, ukuran atau fase yang tidak sesuai.

| Tipe | Isi setelah header 5 byte | Ukuran total |
|---|---|---:|
| 1 ClientHello (M1) | binding identitas 32; client nonce acak 32 | 69 |
| 2 ServerHello (M2) | server nonce acak 32; session ID acak 16; ephemeral ML-KEM public key 800; signature server 666 | 1519 |
| 3 ClientKey (M3) | KEM ciphertext 768; signature client 666; client finished tag 16 | 1455 |
| 4 ServerFinished (M4) | session ID 16; server finished tag 16 | 37 |
| 5 Data | session ID 16; counter uint64 8; length uint16 2; ciphertext slot 160; tag 16 | 207 |

`M2body` tidak mencakup signature. `M3body` hanya header+KEM ciphertext. `M3signed` mencakup signature client, tanpa finished tag.

1. Client menghasilkan M1 baru. Server memeriksa binding kedua identitas, membuat nonce/session ID/KEM keypair baru dan menandatangani `M1 || M2body` dengan context `lab-kimia/session-v1/server`.
2. Client memverifikasi signature M2 terhadap pin server dan M1 yang masih pending. Client mengenkapsulasi ke public KEM M2, lalu menandatangani `M1 || M2 || M3body` dengan context `lab-kimia/session-v1/device`.
3. Kedua pihak menghitung `T = SHA256(M1 || M2 || M3signed)`. Server terlebih dahulu memverifikasi signature client terhadap pin, baru melakukan decapsulation. KEM saja tidak mengautentikasi peer; tanda tangan dan konfirmasi kunci menjadi bagian protokol ini. Lihat [NIST SP 800-227](https://csrc.nist.gov/pubs/sp/800/227/final).
4. Dengan shared secret KEM, salt=server nonce 32 byte, HKDF menghasilkan kunci 32 byte terpisah: info=`T || ASCII("c2s")` atau `T || ASCII("s2c")`. Penggunaan info mengikat hasil ke transcript dan arah. Lihat [RFC 5869](https://www.rfc-editor.org/rfc/rfc5869.html).
5. Client finished merupakan AEAD tag atas plaintext kosong, c2s key, nonce 12 byte nol, AAD=`T || ASCII("client-finished")`. Server hanya mengaktifkan sesi setelah signature dan tag ini benar, kemudian mengirim M4 dengan server finished memakai s2c key, nonce nol dan AAD=`T || ASCII("server-finished")`. Header M4 dan session ID harus sesuai fase/pending session. Client mengaktifkan sesi setelah tag server ini benar.

## Payload, nonce dan lifecycle

Data memakai nonce `zero[4] || counter_le64`, counter mulai **1** pada setiap arah; nonce 0 hanya untuk finished. Kunci dua arah berbeda. Tidak ada tanda tangan per payload. AAD adalah header data 31 byte (magic/version/type, session ID, counter, length) diikuti T. Plaintext 1–160 byte; sisa slot ciphertext harus nol. Counter tak pernah wrap dan konsumsi counter pengirim tidak dibatalkan bila pengiriman gagal. Keunikan nonce per kunci mengikuti persyaratan [RFC 8439](https://www.rfc-editor.org/rfc/rfc8439.html).

Penerima menolak session ID asing, counter 0/duplikat/lebih kecil, ukuran/padding tidak kanonis, dan tag tidak sah. Counter penerima diperbarui **hanya sesudah** AEAD berhasil. Counter yang melompat diperbolehkan karena QoS 0 dapat kehilangan pesan; pesan terlambat setelah counter lebih tinggi diterima akan ditolak.

Handshake pending kedaluwarsa setelah 120 detik monotonik. Sesi aktif dibatasi 300 detik. `tick`/`receive`/`encrypt` melakukan pengecekan usia dan menghapus secret/key saat reset/kedaluwarsa. Pada disconnect firmware mengirim reset ke crypto worker; hasil worker dari generasi koneksi lama dibuang. Receiver menutup Channel dan direstart supervisor saat koneksi hilang. Request rekey yang belum terautentikasi hanya mengganti state pending; kunci aktif tetap berlaku sampai sesi baru terkonfirmasi atau kedaluwarsa.

Uji tiket 03 berhenti setelah satu probe sintetis `temperature_c=26.25` dan ACK terenkripsi berisi `run_id` yang sama. Firmware menghapus session state sesudah ACK. Receiver membatasi antrean input pada empat frame dan memproses kriptografi berurutan. Batas waktu menyebabkan kegagalan tertutup bila frame hilang/antrean penuh. Penjadwalan rekey otomatis, retry handshake saat kehilangan pesan, sensor nyata, dan penulisan InfluxDB ditangani tiket berikutnya; pengujian reset/rekey dasar sudah tersedia pada tiket ini.

### Pemulihan yang ditambahkan tiket 05

Client telemetri mencoba ulang handshake setelah 5 detik pada clock lokal, dari worker pemilik Channel. `retry()` menyalin M1 atau M3 beserta tag finished persis seperti pengiriman pertama. Ia tidak menghasilkan ciphertext baru dengan nonce lama. Setelah dua retry tanpa kemajuan, client memulai M1 dengan nonce baru untuk menangani peer yang telah restart. Operasi signature tidak diinterupsi retry dari task jaringan. Telemetri tidak dikirim ulang.

Server membalas duplikasi M1 pending dengan M2 yang sama tanpa mengganti ephemeral key atau menggeser deadline 120 detik. Sesudah commit, server menyimpan hash SHA-256 M3 lengkap dan tag M4 selama umur sesi aktif. M3 yang identik hanya mendapat salinan M4, bukan event Established kedua, reset counter, atau perpanjangan umur kunci. M3 berbeda tetap harus melewati signature/finished sesuai state pending; cache dihapus bersama sesi. Hal ini memulihkan M4 yang hilang pada QoS 0.

Pada umur sesi **180 detik** menurut salah satu endpoint, client mulai rekey. Server mengirim `{"renew_session":true}` sebagai payload Data biasa yang dienkripsi s2c, memakai counter/nonce berikutnya dan AAD yang sama. Firmware mengenali JSON itu secara persis **hanya sesudah** autentikasi AEAD dan pemeriksaan replay. Perintah ini tidak membawa kunci dan tidak memperpanjang sesi: M1–M4 lengkap tetap wajib. Server mengulangi permintaan paling cepat setiap 5 detik sampai sesi baru terbentuk. Margin 120 detik sebelum expiry memberi waktu saat clock simulator tertinggal. Jika ACK penyimpanan tidak maju selama 10 detik lokal, client juga mulai handshake baru. Perlambatan ekstrem atau Pause panjang tetap dapat menyebabkan jeda; tidak ada jaminan delivery tanpa celah.

Randomness ESP32 diambil setelah Wi-Fi aktif. Keberhasilan dan waktu Wokwi adalah hasil simulator; tidak membuktikan entropy RNG papan fisik, side channel, atau kecepatan hardware. Identity/kredensial lab di dalam image perlu diperlakukan sebagai artefak private; jangan memakai kunci demo ini untuk deployment sungguhan.
