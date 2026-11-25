# 04: Ketahanan di broker publik

**What to build:** Bukti bahwa pihak asing di broker publik tidak dapat membaca, memalsukan, atau mengulang telemetri, dan bahwa receiver tidak crash saat menerima frame palsu, replay, retained junk, atau banjir handshake. Sesi pulih setelah gangguan berhenti. Batas ketersediaan dicatat sebagai risiko yang diterima.

**Blocked by:** 03 Telemetri PQC end-to-end lewat broker.emqx.io dari Wokwi web

**Status:** done

- [x] Frame palsu, replay, dan retained message di topik `up`/`down` ditolak dan tercatat
- [x] Tidak ada titik InfluxDB dari frame yang tidak terautentikasi
- [x] Banjir handshake tidak membuat receiver crash; sesi terbentuk kembali setelah banjir berhenti
- [x] Risiko DoS dan metadata yang terlihat (topik, ukuran, waktu) didokumentasikan

## Comments

Membutuhkan langkah manusia: simulasi Wokwi web berjalan selama serangan dan log serial dikirim.

**Mode native lulus, 25 November 2026** (`tools.session.check_public native`, bukti `docs/evidence/wokwi-web-04/native.json` di LXC).

- Outsider anonim yang subscribe `lkpqc-b16bef88/session/#` melihat 6 frame, tanpa plaintext.
- 5 frame palsu, 1 frame data yang di-tamper (frame baru, sehingga ditolak oleh tag dan bukan oleh counter), dan 1 replay frame data semuanya ditolak (event `rejected`) tanpa balasan terautentikasi. Sesi tetap hidup setelahnya.
- Replay ClientHello milik device saat sesi aktif tidak memutus sesi.
- Retained junk di `up`/`down` diterima subscriber baru lalu ditolak oleh channel. Retained dibersihkan di akhir.
- Flood 300 frame (25/s selama 12 s, 20 hello acak dan replay hello asli): receiver tetap `active` tanpa restart, dan sesi baru terbentuk 1,5 s setelah flood. Hanya 96 dari 300 frame flood yang tercatat `rejected`; sisanya dibuang tanpa log oleh antrean receiver yang dibatasi 4 frame. Inilah batas ketersediaan: selama flood, frame sah juga bisa ikut terbuang.
- Selama uji: 0 event `telemetry_stored` dan 0 titik InfluxDB. Probe tiket 03 dipakai agar uji tidak menulis data. Jurnal receiver tanpa traceback.

**Mode attack (dengan Wokwi web):** job `lab-kimia-public-attack` (systemd-run, sementara) menunggu sampai 30 menit hingga 5 frame data ESP32 terlihat. Setelah itu job me-replay dan men-tamper frame ESP32 asli, mengirim frame palsu ke `up`/`down`, menaruh retained frame ESP32 di `down`, dan melakukan flood 12 s. Hasil: `docs/evidence/wokwi-web-04/attack.json` di LXC.

**Mode attack lulus, 25 November 2026** (bukti `docs/evidence/wokwi-web-04/attack.json`).

- Dua percobaan pertama tidak menyerang. Percobaan pertama timeout karena simulator belum jalan. Pada percobaan kedua, outsider tidak pernah melihat frame ESP32: koneksi `MqttConnection` dibuat tanpa reconnect, sehingga kemungkinan besar putus saat menunggu lama dan subscribe-nya hilang tanpa tanda. Loop tunggu sekarang menyambung ulang outsider bila koneksi putus.
- Run Wokwi web `eff89fd184b7b1201a42e00dc391f10f` (hotspot, `local_ip` `10.10.0.2`). Sesi `3749f971eb3b9c816b218beb51596d78` terbentuk 07:50:29 UTC. Keempat keadaan tercakup: normal, suhu saja, suhu dan gas, gas saja.
- Serangan berlangsung 07:50:40–07:50:52 UTC, di tengah sesi aktif:
  - 5 frame data ESP32 asli di-replay dan di-tamper.
  - Frame palsu dikirim ke `up` dan `down`.
  - Satu frame ESP32 dijadikan retained di `down`.
  - Flood 300 frame selama 12 s.
- Hasil di receiver:
  - Outsider melihat 23 frame tanpa plaintext.
  - Receiver tetap `active` tanpa restart dan mencatat 100 event `rejected`.
  - Tidak ada `telemetry_stored` ganda.
- Sesi ESP32 tidak terputus. Jurnal mencatat counter 1–69 tersimpan berurutan tanpa celah dan tanpa duplikat, dengan satu `session_established`. Log serial menunjukkan `STORED` `ack_verified:true` terus muncul selama dan sesudah serangan.
- Log serial run ini tidak disimpan di repo karena hasil salinannya terpotong. Bukti keterkaitan diambil dari `session_id` yang sama di log serial dan di jurnal receiver.

**Risiko yang diterima (dokumentasi):**

- **DoS.** Siapa pun di broker publik bisa membanjiri topik. Antrean receiver dibatasi 4 frame, sehingga saat flood lebih cepat dari pemrosesan, frame sah bisa ikut terbuang tanpa log. Data tidak pernah palsu atau tercatat ganda, tetapi bisa hilang selama gangguan. Firmware hanya menganggap sampel tersimpan setelah ACK terenkripsi terverifikasi, dan setelah gangguan berhenti sesi pulih atau dibentuk ulang. Pada run attack, sesi tidak terputus sama sekali.
- **Metadata.** Outsider tetap melihat beberapa hal walaupun isinya terenkripsi:
  - Nama topik.
  - Ukuran frame: 69 dan 1519 byte untuk handshake, 207 byte untuk data.
  - Waktu kirim: data tiap sekitar 2 s, renewal tiap 180 s.
  - Kapan device online.

  Isi telemetri, identitas, dan nilai sensor tetap tidak terlihat. Prefix topik bukan rahasia dan bukan kontrol akses.
- **Broker pihak ketiga.** `broker.emqx.io` tanpa SLA. Uji flood dibatasi 25/s selama 12 s agar tidak membebani layanan bersama.
