# Panduan demo proyek MQTT/PQC (Wokwi web)

Proyek: **Simulasi Monitoring Gas dan Suhu Laboratorium Kimia Dasar dengan Kriptografi Aplikasi pada MQTT dan Dashboard Grafana**.

Sejak 25 November 2026, demo utama berjalan di **wokwi.com** (Wokwi web) dan memakai broker MQTT publik `broker.emqx.io:1883`. Receiver, InfluxDB, dan Grafana tetap berjalan di LXC `10.34.211.141`. Jalur privat lama (Wokwi VS Code dan Mosquitto LXC) tetap hidup sebagai cadangan; lihat [panduan jalur privat](demo-proyek-privat.md).

Transport adalah **MQTT biasa TCP/1883, tanpa TLS dan tanpa login**, karena aturan tugas melarang TLS. Perlindungan sepenuhnya berasal dari kriptografi aplikasi: **ML-KEM-512, ChaCha20-Poly1305, dan prospective FN-DSA degree 512**.

## 1. Gambaran sistem

```text
DS18B20 + MQ2 → ESP32 (Wokwi web, laptop di hotspot)
                  │ publish/subscribe, frame terenkripsi
                  ▼
          broker.emqx.io:1883 (publik)
                  ▲ koneksi keluar dari LXC
                  │
          receiver PQC publik (LXC) → InfluxDB → Grafana (LXC)
```

| Bagian | Keterangan |
|---|---|
| Firmware | Env PlatformIO `pqc-telemetry-public` (default build). Bin gabungan untuk Wokwi web: `pqc-telemetry-public-full.bin` |
| Topik | `lkpqc-b16bef88/session/up` (ESP32 → receiver) dan `lkpqc-b16bef88/session/down` (arah balik). Prefix hanya mencegah tabrakan nama, **bukan rahasia dan bukan kontrol akses** |
| Identitas | Pasangan identitas FN-DSA **demo**, terpisah dari identitas lab. Bin publik tidak memuat identitas lab, kredensial Mosquitto, atau IP privat |
| Receiver | `lab-kimia-pqc-session-public.service` di LXC, enabled, restart otomatis. Menulis ke InfluxDB yang sama dengan jalur privat |
| Dashboard | [Grafana meja 01](http://10.34.211.141:3000/d/suhu-meja01) |

Peran algoritma, format handshake, dan siklus sesi sama dengan jalur privat; lihat [protokol sesi](protokol-sesi-pqc.md) dan bagian 1 [panduan jalur privat](demo-proyek-privat.md#1-gambaran-sistem-dan-bahan-penjelasan).

**Apa yang dilindungi di broker publik:**

- Siapa pun dapat subscribe dan publish ke topik di atas, karena broker publik tidak punya login/ACL.
- Isi telemetri tetap rahasia: pihak luar hanya melihat byte terenkripsi.
- Frame palsu, frame yang diubah, replay, dan retained message ditolak oleh receiver, dan tidak ada data palsu yang masuk InfluxDB. Lihat [bukti tiket 04](../.scratch/wokwi-web-broker-publik/issues/04-ketahanan-broker-publik.md).
- Yang **tidak** dilindungi:
  - Ketersediaan. Banjir pesan dapat membuat frame sah ikut terbuang.
  - Metadata: topik, ukuran frame, waktu kirim, dan kapan device online.
  - Layanan broker pihak ketiga tanpa SLA.

**Risiko yang diterima:** bin publik memuat kunci klien demo. Siapa pun yang memegang bin dapat mengekstraknya dan mengirim telemetri sah lewat receiver publik. Bagikan bin hanya untuk demo. Bila bin bocor, matikan receiver publik (`systemctl disable --now lab-kimia-pqc-session-public.service`) atau rotasi identitas demo.

## 2. Syarat jaringan

Jaringan kampus terbukti memblokir Wi-Fi simulasi Wokwi web, sedangkan hotspot HP berhasil. Penyebab persisnya belum diperiksa. Akibatnya:

- **Perangkat yang menjalankan Wokwi web harus memakai hotspot** (atau jaringan lain di luar kampus).
- **Perangkat yang membuka Grafana harus punya rute ke `10.34.211.141`**, yaitu jaringan kampus.
- Satu perangkat tidak bisa melakukan keduanya sekaligus. Pakai dua perangkat: laptop A di hotspot untuk Wokwi, laptop B di Wi-Fi kampus untuk Grafana. Bila hanya ada satu laptop, jalankan Wokwi di hotspot, lalu pindah ke Wi-Fi kampus untuk melihat Grafana. Data yang masuk selama itu tetap tersimpan.

**Cara mengenali jaringan yang memblokir Wokwi:**

- Firmware telemetri: baris `TELEMETRY_RUN {... "local_ip":"10.10.0.2"}` tidak muncul dalam sekitar 30 detik setelah Start. Data berhenti di `Sampel lokal`.
- Firmware diagnostik (`mqtt-diagnostic-public-full.bin`): `MQTT_DIAG_WIFI_STATUS` berhenti di `0` (`WL_IDLE_STATUS`) dan tidak pernah mencapai `3` (`WL_CONNECTED`).

Bila terjadi: pastikan laptop benar-benar memakai hotspot (matikan Wi-Fi kampus dan LAN), **tutup lalu buka ulang tab Wokwi** setelah pindah jaringan, lalu Start lagi.

## 3. Periksa layanan LXC

Dari perangkat yang memakai jaringan kampus:

```sh
ssh root@10.34.211.141
systemctl is-active lab-kimia-pqc-session-public.service
journalctl -u lab-kimia-pqc-session-public.service -n 5 --no-pager -o cat
curl -fsS http://127.0.0.1:8086/health
curl -fsS http://10.34.211.141:3000/api/health
```

Expected: receiver `active`; jurnal memuat event `ready` dengan `broker: broker.emqx.io`, `topic_prefix: lkpqc-b16bef88/session`, `public: true`; Influx `status:pass`; Grafana `database:ok`. Bila receiver mati: `systemctl enable --now lab-kimia-pqc-session-public.service`.

Grafana memakai akun deployment yang sudah ada; jangan menampilkan `.env` saat presentasi.

## 4. Siapkan proyek Wokwi web

Cukup sekali per akun Wokwi; proyek yang sudah dibuat bisa dipakai ulang.

1. Buka [wokwi.com](https://wokwi.com), buat proyek ESP32 baru.
2. Ganti isi `diagram.json` dengan [`firmware/diagram.json`](../firmware/diagram.json).
3. Tambahkan berkas `mq2-level.chip.json` dan `mq2-level.chip.c` dari folder `firmware/` dengan nama yang sama (chip MQ2 custom).
4. Siapkan bin di laptop: `evidence/local/public-telemetry-firmware/pqc-telemetry-public-full.bin` (diabaikan Git; lihat bagian 8 bila perlu build ulang).

## 5. Jalankan simulasi

1. Pastikan laptop Wokwi memakai **hotspot**.
2. Di editor kode Wokwi tekan F1 → **Upload Firmware and Start Simulation...**, lalu pilih `pqc-telemetry-public-full.bin`.
3. **Segera geser slider MQ2 ke paling kiri.** Wokwi mengingat posisi slider dari run sebelumnya, sehingga gas bisa langsung alarm sejak boot. Pastikan serial menulis `DOUT=HIGH`.
4. Tunggu urutan berikut di serial monitor:
   - `TELEMETRY_RUN` dengan `run_id` baru dan `local_ip` `10.10.0.2` (Wi-Fi tersambung).
   - `TELEMETRY_AUTHENTICATED` dengan `mqtt_port:1883`, `tls:false`, dan `session_id` 32 digit hex. Biasanya muncul dalam 15–20 detik, karena handshake ML-KEM dan FN-DSA.
   - `TELEMETRY_SENT` lalu `TELEMETRY_STORED` dengan counter yang sama dan `ack_verified:true`, kira-kira tiap 2 detik.
5. **Jangan Pause.** Pause memutus koneksi MQTT (keepalive 15 detik), lalu sesi dibentuk ulang. Sampel selama jeda tidak dikirim dan tidak diklaim tersimpan; untuk demo atau bukti, jalankan tanpa Pause.

`Sampel lokal` saja belum membuktikan publish, dan `SENT` saja belum membuktikan database. `STORED` berarti ESP32 memverifikasi ACK terenkripsi yang dibuat receiver setelah InfluxDB mengonfirmasi write. Marker `ticket=04` pada `TELEMETRY_BEGIN` berasal dari nama firmware sensor awal.

## 6. Demonstrasikan empat keadaan alarm

Buka [dashboard](http://10.34.211.141:3000/d/suhu-meja01) dari perangkat di jaringan kampus, rentang **Last 15 minutes**, refresh **2s**. Klik DS18B20 untuk slider suhu dan MQ2 untuk slider gas. Tahan tiap keadaan sekitar 10–30 detik sampai beberapa `STORED` muncul.

| Tahap | Suhu | Gas/DOUT | Flag gas/suhu | LED/buzzer |
|---|---:|---|---|---|
| 1. Normal | 25°C | slider kiri / HIGH | false/false | OFF |
| 2. Suhu saja | ≥40°C (mis. slider kanan) | kiri / HIGH | false/true | ON |
| 3. Suhu dan gas | ≥40°C | kanan / LOW | true/true | ON |
| 4. Gas saja | <40°C | kanan / LOW | true/false | ON |

Ambang suhu adalah **≥40°C**. Saat slider suhu digeser cepat, serial bisa menulis `gagal baca DS18B20: nilai tidak valid; tidak dikirim`. Itu perilaku yang benar: nilai tidak valid tidak dikirim dan tidak dianggap normal.

Dashboard menampilkan **Data terlambat** setelah lebih dari 10 detik tanpa titik baru, misalnya setelah simulasi di-Stop.

## 7. Bukti otomatis (opsional)

Untuk mencocokkan run dengan jurnal receiver, InfluxDB, dan Grafana:

1. Setelah Stop, salin **seluruh** serial monitor ke berkas, misalnya `evidence/local/wokwi-web-demo-01.txt`.
2. Pindah ke jaringan kampus, lalu kirim berkas ke LXC dan validasi:

   ```powershell
   scp evidence/local/wokwi-web-demo-01.txt root@10.34.211.141:/opt/lab-kimia-mqtt/evidence/local/wokwi-web-demo-01.txt
   ```

   ```sh
   cd /opt/lab-kimia-mqtt
   .venv/bin/python -m tools.telemetry.verify_capture evidence/local/wokwi-web-demo-01.txt --public --output evidence/local/wokwi-web-demo-01.json
   ```

Expected `verified:true`, `four_states:true`, `grafana:true`, dan `transport` publik. Validasi menolak capture yang memakai IP Wokwi VS Code (`10.13.37.2`). Log broker publik tidak tersedia, jadi bukti asal ESP32 adalah `session_id` 128-bit yang sama di serial dan jurnal receiver.

Uji ketahanan terhadap pihak luar di broker publik: `python -m tools.session.check_public native --output ...` (tanpa Wokwi) atau `attack` (saat Wokwi berjalan). Hasil tiket 04 ada di `docs/evidence/wokwi-web-04/`.

## 8. Build ulang bin publik (bila firmware berubah)

Header identitas demo `firmware/include/pqc_session_identity_demo.h` dibuat oleh `python -m tools.session.provision --profile demo` dan diabaikan Git. Build di LXC:

```sh
cd /opt/lab-kimia-mqtt
PIO=/opt/lab-kimia-suhu/pqc-proof/evidence/local/platformio
PLATFORMIO_CORE_DIR=$PIO /opt/lab-kimia-suhu/pqc-proof/.venv/bin/pio run -d firmware -e pqc-telemetry-public
B=firmware/.pio/build/pqc-telemetry-public
O=evidence/local/public-telemetry-firmware
install -d -m 700 $O
/opt/lab-kimia-suhu/pqc-proof/.venv/bin/python $PIO/packages/tool-esptoolpy/esptool.py --chip esp32 merge_bin \
  -o $O/pqc-telemetry-public-full.bin 0x1000 $B/bootloader.bin 0x8000 $B/partitions.bin \
  0xe000 $PIO/packages/framework-arduinoespressif32/tools/partitions/boot_app0.bin 0x10000 $B/firmware.bin
strings $O/pqc-telemetry-public-full.bin | grep -c -E '10\.34\.211\.141|diag-device'
```

Perintah terakhir harus mencetak `0` (tidak ada IP privat atau akun Mosquitto di bin). Lalu salin bin ke laptop:

```powershell
scp root@10.34.211.141:/opt/lab-kimia-mqtt/evidence/local/public-telemetry-firmware/pqc-telemetry-public-full.bin evidence/local/public-telemetry-firmware/
```

Wokwi VS Code juga bisa menjalankan build default ini (`wokwi.toml` menunjuk `.pio/build/pqc-telemetry-public/`), asalkan laptop memakai jaringan yang tidak diblokir.

## 9. Jika hasil belum sesuai

| Gejala | Periksa dan tindakan |
|---|---|
| Tidak ada `TELEMETRY_RUN` | Jaringan memblokir Wokwi web; lihat bagian 2 |
| `TELEMETRY_RUN` ada, `AUTHENTICATED` tidak muncul | Receiver publik aktif? Lihat jurnal `lab-kimia-pqc-session-public`. Event `rejected` berarti identitas di bin tidak cocok dengan receiver; build ulang dari identitas demo yang sama |
| Gas langsung alarm saat boot | Slider MQ2 diingat Wokwi; geser ke paling kiri sampai `DOUT=HIGH` |
| `SENT` tanpa `STORED`, lalu `AUTHENTICATED` baru | Koneksi lambat atau putus sebentar (hotspot, Pause, broker publik). Sesi pulih sendiri; sampel tanpa ACK tidak diklaim tersimpan |
| Grafana tidak berubah | Perangkat Grafana harus di jaringan kampus; cocokkan waktu penerimaan terbaru |
| SSH/Grafana timeout | Perangkat sedang memakai hotspot; pindah ke jaringan kampus |

## 10. Rollback ke jalur privat

Jalur privat tidak pernah dimatikan. Untuk kembali (misalnya bila broker publik bermasalah):

1. Build eksplisit `pio run -e pqc-telemetry` dan arahkan `firmware/wokwi.toml` ke `.pio/build/pqc-telemetry/firmware.bin`/`.elf`.
2. Jalankan Wokwi VS Code dengan Private Gateway dan ikuti [panduan jalur privat](demo-proyek-privat.md).
3. Opsional: `systemctl disable --now lab-kimia-pqc-session-public.service` agar hanya satu jalur aktif.

Detail dan hasil uji rollback ada di [operasi MQTT/PQC](operasi-pqc.md#jalur-publik-dan-rollback-ke-jalur-privat).
