# 03: Peringatan gas dan suhu bekerja secara mandiri

**What to build:** Sistem memberi peringatan lokal melalui LED merah dan buzzer serta memperlihatkan status yang sama di Grafana. Alarm gas tidak bergantung pada kenaikan suhu, dan alarm suhu tidak bergantung pada gas. Riwayat pengukuran memuat kondisi alarm agar kejadian sebelumnya dapat ditinjau.

**Blocked by:** 02: Level gas tampil bersama suhu — selesai; tidak lagi menghambat.

**Status:** done

- [x] Alarm gas aktif saat keluaran digital MQ2 menunjukkan ambang terlampaui; status LOW dari pin sensor berarti alarm gas aktif.
- [x] Alarm suhu aktif pada pembacaan valid DS18B20 yang mencapai atau melebihi 40 derajat Celsius dan kembali tidak aktif saat pembacaan valid berada di bawah ambang tersebut.
- [x] LED merah dan buzzer aktif jika salah satu alarm aktif. Keputusan alarm dibuat di ESP32 berdasarkan pembacaan lokal.
- [x] Pesan dan penyimpanan menambahkan `gas_alarm` serta `temperature_alarm` sebagai status boolean; nilai kedua status dapat ditampilkan bersama pengukuran yang bersangkutan.
- [x] Grafana membedakan empat keadaan: normal, peringatan gas, peringatan suhu, dan kedua peringatan aktif. Label atau teks tetap menjelaskan keadaan tanpa bergantung pada warna saja.
- [x] Keempat keadaan berhasil didemonstrasikan dari Wokwi sampai dashboard, termasuk gas tinggi dengan suhu normal dan suhu tinggi dengan gas normal.
- [x] Setelah kedua pembacaan valid kembali di bawah ambang, LED, buzzer, dan status dashboard mengikuti keadaan normal; pembacaan suhu gagal tidak dianggap bukti bahwa suhu kembali aman.
- [x] Ambang 40 derajat Celsius dan ambang MQ2 dinyatakan sebagai pengaturan demonstrasi simulasi, bukan standar keselamatan atau pembuktian deteksi kebakaran.
- [x] Pekerjaan dibatasi pada dashboard, LED, dan buzzer. Kendali katup gas, kipas jarak jauh, serta notifikasi eksternal berada di luar cakupan.

## Comments

10 November 2026: tiket 02 selesai setelah peninjauan screenshot/log Wokwi dan Grafana serta konfirmasi pemilik mengenai restart. Seluruh penghambat tiket ini terpenuhi. Status tetap `ready-for-agent`; implementasi alarm tiket 03 belum dimulai.

Penyelesaian 10 November 2026: alarm lokal mandiri diimplementasikan dengan DOUT LOW dan suhu valid >=40 Celsius; LED merah GPIO 25/buzzer GPIO 26 mengikuti OR, dan kegagalan suhu tidak menghapus alarm sebelumnya. Pesan/parser menyimpan kedua boolean pada timestamp pengukuran yang sama. Grafana menambah stat empat keadaan berlabel teks dan tabel riwayat bersama suhu/ADC. Firmware lama tetap diterima tanpa status normal buatan; tidak ada dependensi atau layanan produksi baru.

Tes C++/loop firmware, build ESP32, 13 kasus parser Telegraf, serta stack MQTT/TLS terisolasi hingga enam kueri Grafana dan restart lulus. Demo langsung Wokwi → EMQX → layanan lokal juga berhasil: gas saja (25 Celsius/2177 ADC), normal (25/506), suhu saja (40/506), keduanya (40/2176), suhu saja saat gas pulih, lalu normal (25/506). Transisi terakhir tersimpan pada 19:50:13 WIB; label Grafana dan output lokal mengikuti keadaan normal. Kegagalan/pemulihan suhu diuji dengan loop host; suara tidak direkam secara akustik. Penghilangan jeda koneksi ulang dan penanda data terlambat tetap cakupan tiket 04. Seluruh acceptance criteria terpenuhi; status menjadi `done`, sehingga tiket 03 tidak lagi menghambat tiket 04.

Bukti, batas pengujian dan prosedur: [docs/verifikasi-tiket-03.md](../../../docs/verifikasi-tiket-03.md). Screenshot/log/CSV demo disimpan lokal di `evidence/local/ticket-03/` yang diabaikan Git.
