# 02: Level gas tampil bersama suhu

**What to build:** Tambahkan MQ2 pada ESP32 yang sama agar indikasi gas di meja praktikum lab kimia dapat dipantau bersama suhu. Nilai relatif gas melewati jalur MQTT/TLS, Telegraf, InfluxDB, dan Grafana yang sudah berjalan, sehingga pengunjung dashboard dapat membandingkan kedua pengukuran dari waktu ke waktu.

**Blocked by:** 01: Suhu dari Wokwi tersimpan dan tampil di Grafana — selesai; tidak lagi menghambat.

**Status:** done

- [x] Komponen MQ2 Wokwi terpasang pada ESP32 yang sama dengan DS18B20. Pemilihan pin dan penyesuaian level tegangan mempertimbangkan batas masukan ESP32.
- [x] ESP32 membaca keluaran analog MQ2 sebagai `gas_raw` dan keluaran digitalnya sebagai indikasi ambang gas. Keluaran digital aktif LOW ditafsirkan dengan benar.
- [x] `gas_raw` ditambahkan sebagai angka pada pesan perangkat yang sama, dengan identitas dan timestamp penyimpanan yang konsisten dengan pengukuran suhu.
- [x] Pembacaan gas tampil sebagai ADC/level relatif. Dashboard dan penjelasan tidak menyebutnya sebagai konsentrasi LPG terkalibrasi atau ppm hasil pengukuran nyata.
- [x] Grafana memiliki nilai gas terkini dan grafik historis gas terpisah dari grafik suhu, dengan nama serta satuan yang jelas.
- [x] Perubahan gas di Wokwi terlihat pada data tersimpan dan dashboard tanpa menghentikan pembaruan suhu setiap 2 detik saat terhubung.
- [x] Pengujian mencakup gas yang meningkat dengan suhu tetap dan suhu yang meningkat dengan gas tetap; riwayat kedua sensor tetap tersedia setelah layanan dimulai ulang.

## Comments

10 November 2026: implementasi lokal pada branch `codex/ticket-02-monitoring-gas`. Diagram menambahkan MQ2 pada ESP32 yang sama, AOUT ke ADC1 GPIO 34 dan DOUT ke GPIO 27 melalui model penurun level. Model diperlukan karena Wokwi tidak mensimulasikan pembagi resistor analog biasa; untuk perangkat fisik, panduan menjelaskan pembagi 10 kΩ/15 kΩ pada masing-masing keluaran 5 V. Firmware membaca ADC 12-bit dan menafsirkan DOUT LOW sebagai ambang terlampaui, mencetak indikasi pada serial. Telemetry menambahkan `gas_raw` numerik pada siklus suhu 2 detik yang sama. Alarm LED/buzzer/field boolean tetap di luar cakupan tiket ini.

Build ESP32, tes C++ telemetry, sembilan kasus parser Telegraf, kompilasi dan pengujian binary model, serta lint diagram lulus. Pengujian dengan broker TLS Mosquitto lokal dan konfigurasi layanan produksi berhasil membuktikan perubahan sensor mandiri, timestamp bersama di InfluxDB, empat kueri panel Grafana, persistensi setelah seluruh layanan restart, dan masuknya titik baru sesudah pemulihan. Broker lokal hanya fixture tes, bukan pengganti EMQX pada jalur demo.

Kriteria yang dicentang telah dibuktikan pada batas lokal tersebut. Rangkaian/pembacaan di mesin Wokwi, DOUT pada simulator, interval aktual 2 detik, dan perubahan stimulus Wokwi sampai EMQX/Grafana belum diamati; kriteria terkait tetap terbuka. Kredensial/CA EMQX serta token simulator tidak tersedia. Status `ready-for-human` berarti pemilik perlu mengisi konfigurasi dan menjalankan demo nyata; tiket 01 masih menjadi penghambat yang belum selesai dan penghambat tiket 03 belum dibuka.

Panduan: [docs/jalur-suhu.md](../../../docs/jalur-suhu.md). Bukti aktual dan skenario verifikasi tersisa: [docs/verifikasi-tiket-02.md](../../../docs/verifikasi-tiket-02.md).

Pembaruan 10 November 2026: tiket 01 telah selesai setelah pemilik mengonfirmasi uji restart/persistensi dan kegagalan/pemulihan sensor. Penghambat tiket 02 sudah terpenuhi. Status tiket 02 tetap `ready-for-human` karena implementasi tersedia dan yang tersisa adalah verifikasi MQ2 di Wokwi: perubahan gas dengan suhu tetap, perubahan suhu dengan gas tetap, serta kedua keadaan DOUT. Ketersediaan akun, CA, dan layanan demo kini telah dibuktikan pada tiket 01; pernyataan keterbatasan sebelumnya di atas merupakan riwayat pemeriksaan awal. Tiket 03 tetap menunggu penyelesaian tiket 02.

Penyelesaian 10 November 2026: pemilik memberikan tiga screenshot Wokwi/Grafana dan log serial. Rangkaian ESP32, DS18B20, MQ2, serta `mq2-level` terlihat berjalan. Log memperlihatkan suhu tetap 25,00 Celsius saat `gas_raw` naik dari 2177 hingga 2425; Grafana menampilkan 25,00 Celsius dan 2425 ADC serta riwayat gas yang berubah. Screenshot serial menunjukkan `2190 ADC / terlampaui (DOUT=LOW)` lalu `2162 ADC / belum terlampaui (DOUT=HIGH)` pada suhu 23,62 Celsius. Screenshot riwayat kedua sensor memperlihatkan perubahan suhu dengan segmen gas tetap. Setelah koneksi stabil, contoh pengiriman `ms=44046`, `46046`, `48046` berjarak 2.000 ms. Ada putus-sambung MQTT/TLS, termasuk satu `status=-2; TLS=-1 ERROR - Generic error`, yang diikuti koneksi dan pengiriman berhasil; bukti ini tidak diklaim sebagai koneksi tanpa gangguan.

Pemilik juga mengonfirmasi restart berhasil dan keadaan tetap baik setelahnya. Bukti restart berasal dari konfirmasi pemilik, bukan pengulangan agen atau screenshot khusus sebelum/sesudah. Bukti mentah disimpan lokal pada `evidence/local/ticket-02/` yang diabaikan Git; ringkasan tersedia di dokumen verifikasi. Seluruh tujuh acceptance criteria terpenuhi berdasarkan pengujian lokal, screenshot/log demo, dan konfirmasi pemilik. Status menjadi `done`; tiket 02 tidak lagi menghambat tiket 03. Catatan keterbatasan sebelumnya merupakan riwayat.
