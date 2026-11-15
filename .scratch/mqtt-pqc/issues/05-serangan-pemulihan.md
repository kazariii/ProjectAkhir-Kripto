# 05 — Serangan dan pemulihan sesi PQC

**What to build:** Buktikan kerahasiaan payload, penolakan penyamaran, modifikasi dan replay pada MQTT TCP/1883. Lengkapi pemulihan handshake yang kehilangan pesan, pembaruan sesi ketika clock Wokwi tertinggal, serta pemulihan gangguan layanan tanpa mengirim ulang sampel lama.

**Blocked by:** 04 — Telemetri ke Grafana (`done`).

**Status:** done

## Acceptance criteria

- [x] Tes protokol menolak pin/kunci palsu, perubahan handshake/data, replay/counter lama, dan sesi kedaluwarsa.
- [x] Kehilangan respons handshake pulih dengan retry byte identik; duplikasi tidak mereset counter atau memperpanjang umur kunci.
- [x] Pembaruan sesi terautentikasi memakai clock LXC dan tetap memerlukan handshake baru, signature dan konfirmasi kunci.
- [x] Serangan pada broker aktual tidak menghasilkan ACK penyimpanan atau titik Influx baru; kontrol valid sebelum/sesudah berhasil.
- [x] Gangguan receiver, broker dan penulisan Influx pulih; tidak ada fallback plaintext atau pengiriman backlog.
- [x] Firmware ESP32 dibangun dan pemulihan Wokwi dibuktikan dengan serial, journal LXC dan titik Influx/Grafana; sensor/alarm tetap berjalan selama gangguan.
- [x] Bukti publik disanitasi, batas klaim keamanan dicatat, monitoring lama dan histori dipertahankan.

## Comments

Tiket ini tidak mengklaim audit kriptografi, perlindungan metadata MQTT, ketahanan DoS, atau kepatuhan FN-DSA final. Migrasi default dan penghentian ingress lama tetap tiket 06.

15 November 2026: 113 pemeriksaan protokol, 12 tes parser/ACK/capture, regresi loop sensor PQC dan legacy, build ESP32, serta 21 kasus kontrol native pada broker LXC lulus. Delapan titik kontrol cocok dengan Influx/Grafana; subscriber MQTT terpisah mengamati byte frame yang sama. Mutasi, replay, plaintext dan secret identitas palsu tidak mendapat balasan atau titik baru pada jendela uji.

Run Wokwi `8f337e9c0273ef3c232b05be37524edc`: 136 ACK dari 148 SENT, lima sesi, empat keadaan alarm, gap sampel lokal maksimum 2000ms. Receiver, broker dan Influx masing-masing dimatikan 20 detik lalu pulih otomatis. Enam write Influx tidak terkonfirmasi tidak mendapat ACK. LXC meminta renewal pada umur 180,219 detik dan ESP32 mengonfirmasi sesi baru ketika pertambahan jam virtualnya baru 174 detik. Dua belas frame tanpa ACK tidak diklaim tersimpan; tidak ada retry/backlog telemetri. Bukti native dan Wokwi dipisahkan.

[Verifikasi](../../../docs/verifikasi-pqc-tiket-05.md), [ringkasan](../../../docs/evidence/pqc-ticket-05/summary.json). Perubahan tersedia lokal dan receiver/image uji telah diperbarui di LXC/laptop; belum di-commit/dipush. Tiket 06 tidak lagi terhambat oleh tiket 05.
