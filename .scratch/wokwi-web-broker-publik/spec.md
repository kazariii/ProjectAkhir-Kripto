# Wokwi web melalui broker MQTT publik

Keputusan pengguna (25 November 2026): simulasi ESP32 harus bisa dijalankan dari wokwi.com agar mudah didemokan ke dosen. Wokwi web tidak menjangkau Mosquitto privat di LXC (`10.34.211.141`), jadi transport dipindah ke broker publik `broker.emqx.io:1883` tanpa TLS. Aturan tugas melarang TLS; perlindungan tetap dari ML-KEM-512, ChaCha20-Poly1305, dan prospective FN-DSA-512 di lapisan aplikasi.

Receiver, InfluxDB, dan Grafana tetap di LXC. Receiver tersambung keluar ke broker publik.

## Prinsip migrasi

- Expand-contract: jalur Mosquitto privat tetap hidup sampai jalur publik terbukti. Rollback berarti kembali ke konfigurasi privat, tanpa rebuild infrastruktur. Mosquitto tidak dimatikan.
- Risiko terbesar (Wokwi web menerima firmware, chip MQ2, ukuran frame, jalur keluar LXC) dibuktikan di tiket 01 sebelum kode produksi diubah.
- Firmware yang dibagikan memakai identitas FN-DSA khusus demo; identitas lab tidak ikut tersebar.
- Broker publik tidak memberi login/ACL. Siapa pun dapat publish/subscribe pada topik. Kerahasiaan dan integritas tetap dijamin protokol sesi; ketersediaan (banjir handshake) tidak.
- Jaringan kampus terbukti memblokir Wi-Fi Wokwi web (tiket 01), sedangkan hotspot HP berhasil. Panduan demo harus menyebut syarat jaringan ini.
- Topik memakai prefix unik untuk menghindari tabrakan; prefix bukan rahasia dan bukan kontrol akses.

## Urutan

01 spike dan 02 prefactor (independen); 03 telemetri end-to-end (01, 02); 04 ketahanan (03); 05 cutover dan dokumentasi (03, 04); 06 akses Grafana (independen, butuh keputusan pengguna).
