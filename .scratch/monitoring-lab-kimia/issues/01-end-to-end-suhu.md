# 01: Suhu dari Wokwi tersimpan dan tampil di Grafana

**What to build:** Jalur pertama yang dapat didemonstrasikan untuk proyek "Simulasi Monitoring Gas dan Suhu Laboratorium Kimia Dasar Berbasis MQTT over TLS dengan Dashboard Grafana". Satu ESP32 di Wokwi membaca DS18B20 di sekitar satu meja praktikum dengan pembakar Bunsen berbahan bakar LPG. Perubahan suhu sampai ke Grafana melalui EMQX Cloud Serverless, Telegraf, dan InfluxDB. Pembacaan suhu menggambarkan lingkungan sekitar meja, bukan nyala api langsung.

**Blocked by:** None (can start immediately).

**Status:** done

- [x] Rangkaian dan program Wokwi dapat dijalankan ulang, memakai satu ESP32 dan DS18B20, dengan pembacaan serta pengiriman setiap 2 detik saat terhubung.
- [x] Broker memakai EMQX Cloud Serverless dengan batas pengeluaran nol; kebutuhan akun dan verifikasi pemilik dijelaskan tanpa menyimpan rahasia di dokumentasi.
- [x] ESP32 mengirim ke topik `lab/kimia/meja01/telemetry`. Pesan JSON minimal memuat `device_id` dan `temperature_c`; nilai suhu memakai derajat Celsius dan identitas perangkat konsisten.
- [x] ESP32 dan Telegraf sama-sama menggunakan MQTT melalui TLS serta memverifikasi CA dan identitas server. Konfigurasi tidak menonaktifkan verifikasi sertifikat.
- [x] Kredensial terpisah membatasi ESP32 untuk mengirim pada topik tersebut dan Telegraf untuk membacanya. Akses anonim dan operasi yang tidak diizinkan ditolak melalui aturan fallback yang sesuai.
- [x] Telegraf, InfluxDB 2.x, dan Grafana dapat dijalankan bersama melalui Docker dengan versi yang ditetapkan. Token, sandi, dan berkas lokal berisi rahasia dikecualikan dari Git.
- [x] Telegraf menyimpan suhu sebagai angka dan `device_id` sebagai identitas seri; waktu penerimaan digunakan sebagai timestamp pengukuran agar tidak bergantung pada jam ESP32 yang belum tersinkronisasi.
- [x] Grafana menampilkan suhu terbaru dan grafik historis dari InfluxDB. Perubahan suhu yang dilakukan di Wokwi dapat diamati pada dashboard selama layanan berjalan.
- [x] Penyimpanan InfluxDB dan konfigurasi dashboard persisten; mulai ulang layanan mempertahankan data sebelumnya dan memungkinkan pengiriman baru berlanjut.
- [x] Pembacaan DS18B20 yang tidak valid tidak disimpan sebagai suhu normal atau nilai Celsius palsu. Kegagalan pembacaan terlihat pada keluaran diagnosis.
- [x] Petunjuk menjalankan jalur suhu beserta bukti hasil aktual tersedia. Jalur utama tetap memakai MQTT; koneksi internal Telegraf ke InfluxDB dan akses web dashboard bukan pengganti protokol sensor.

## Comments

10 November 2026: implementasi kode tersedia pada branch `integration/ticket-01-suhu`, commit implementasi `bf77608` dan merge `44dd245`. Cakupan hanya tiket 01; tiket 02–07 belum dikerjakan. Spesifikasi induk `spec.md` belum tersedia, sehingga acceptance criteria tiket ini menjadi acuan.

Hasil aktual lokal: build ESP32 berhasil; tes C++ keluaran firmware lulus; lima kasus parser Telegraf 1.40.3 lulus; rendering Docker Compose dan pemeriksaan pengecualian rahasia dari Git lulus. Pengujian lokal dijalankan ulang dari direktori proyek utama. Tinjauan standar dan kesesuaian spesifikasi masing-masing menemukan nol masalah kode yang memerlukan perbaikan.

Status `ready-for-human` dipakai karena pemilik perlu menyiapkan/verifikasi akun EMQX Serverless, Spend Limit 0, dua akun MQTT dan aturan fallback deny, lalu mengisi kredensial serta CA pada berkas lokal yang diabaikan Git. Docker Desktop saat pemeriksaan gagal memulai mesinnya. Setelah lingkungan tersedia, jalankan Wokwi dan layanan, buktikan handshake TLS/izin topik, interval 2 detik, perubahan suhu sampai Grafana, kegagalan pembacaan sensor, serta persistensi setelah restart. Belum ada klaim keberhasilan demo cloud atau container.

Panduan pengulangan: [docs/jalur-suhu.md](../../../docs/jalur-suhu.md). Bukti lokal dan lembar verifikasi pemilik: [docs/verifikasi-tiket-01.md](../../../docs/verifikasi-tiket-01.md). Checklist penerimaan tetap terbuka sampai jalur sebenarnya dan bukti hasilnya diverifikasi; tiket ini belum selesai dan tiket yang bergantung padanya belum dibuka penghambatnya.

Pembaruan demo 10 November 2026: pemilik menyediakan screenshot Serverless Running/Spend Limit $0, dua akun, izin username pada topik yang benar, dan fallback All Users deny `#`. Log Wokwi setelah perbaikan timer menunjukkan suhu/gas valid serta pengiriman berjarak 2.000 ms. Telegraf produksi sudah diaktifkan dan tersambung TLS ke EMQX. Pemeriksaan InfluxDB menemukan 34 titik dalam jendela satu jam, dengan beberapa perubahan suhu dan identitas `esp32-meja01`; panel stat dan historis Grafana melalui API mengembalikan angka tanpa error. Pemilik menyatakan perubahan suhu berhasil. Rahasia lokal tetap diabaikan Git dan tidak dilacak.

Sembilan pemeriksaan MQTT 5 aktual lulus dengan client ID sementara: autentikasi sah sebelum/sesudah uji negatif; anonim dan password salah ditolak; Telegraf dapat Subscribe topik utama; ESP32 ditolak Subscribe topik utama dan Publish topik lain; Telegraf ditolak Publish topik utama dan Subscribe topik lain. Uji tidak menerbitkan pengukuran normal palsu dan tidak mengubah aturan broker. Rincian bukti diperbarui pada dokumen verifikasi.

Sisa acceptance criteria yang belum dicentang: restart stack demo mempertahankan riwayat dan menerima data baru dari Wokwi; serta pemutusan DQ di Wokwi menghasilkan diagnosis tanpa titik suhu palsu. Keduanya masih memerlukan pengulangan demo pemilik. Status tetap `ready-for-human`; penghambat tiket 02 belum dinyatakan selesai. Implementasi gas tiket 02 sudah ada pada direktori kerja saat pembaruan ini, namun itu tidak menggantikan dua bukti tiket 01 yang tersisa.

Penyelesaian 10 November 2026: pemilik mengonfirmasi kedua percobaan terakhir telah dijalankan dan berhasil, yakni restart mempertahankan riwayat/pengiriman baru, serta pemutusan dan pemulihan DQ menghasilkan diagnosis yang benar tanpa suhu palsu. Bukti akhir kedua percobaan adalah konfirmasi pemilik dalam percakapan; agen tidak mengklaim menjalankan ulang atau menerima screenshot tambahan. Seluruh 11 acceptance criteria telah dicentang. Status `done` mengikuti pemetaan penyelesaian pada `docs/agents/triage-labels.md`. Tiket 01 selesai dan tidak lagi menghambat tiket 02; catatan kesiapan sebelumnya di atas merupakan riwayat.
