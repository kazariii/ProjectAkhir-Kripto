# 03: Peringatan gas dan suhu bekerja secara mandiri

**What to build:** Sistem memberi peringatan lokal melalui LED merah dan buzzer serta memperlihatkan status yang sama di Grafana. Alarm gas tidak bergantung pada kenaikan suhu, dan alarm suhu tidak bergantung pada gas. Riwayat pengukuran memuat kondisi alarm agar kejadian sebelumnya dapat ditinjau.

**Blocked by:** 02: Level gas tampil bersama suhu.

**Status:** ready-for-agent

- [ ] Alarm gas aktif saat keluaran digital MQ2 menunjukkan ambang terlampaui; status LOW dari pin sensor berarti alarm gas aktif.
- [ ] Alarm suhu aktif pada pembacaan valid DS18B20 yang mencapai atau melebihi 40 derajat Celsius dan kembali tidak aktif saat pembacaan valid berada di bawah ambang tersebut.
- [ ] LED merah dan buzzer aktif jika salah satu alarm aktif. Keputusan alarm dibuat di ESP32 berdasarkan pembacaan lokal.
- [ ] Pesan dan penyimpanan menambahkan `gas_alarm` serta `temperature_alarm` sebagai status boolean; nilai kedua status dapat ditampilkan bersama pengukuran yang bersangkutan.
- [ ] Grafana membedakan empat keadaan: normal, peringatan gas, peringatan suhu, dan kedua peringatan aktif. Label atau teks tetap menjelaskan keadaan tanpa bergantung pada warna saja.
- [ ] Keempat keadaan berhasil didemonstrasikan dari Wokwi sampai dashboard, termasuk gas tinggi dengan suhu normal dan suhu tinggi dengan gas normal.
- [ ] Setelah kedua pembacaan valid kembali di bawah ambang, LED, buzzer, dan status dashboard mengikuti keadaan normal; pembacaan suhu gagal tidak dianggap bukti bahwa suhu kembali aman.
- [ ] Ambang 40 derajat Celsius dan ambang MQ2 dinyatakan sebagai pengaturan demonstrasi simulasi, bukan standar keselamatan atau pembuktian deteksi kebakaran.
- [ ] Pekerjaan dibatasi pada dashboard, LED, dan buzzer. Kendali katup gas, kipas jarak jauh, serta notifikasi eksternal berada di luar cakupan.
