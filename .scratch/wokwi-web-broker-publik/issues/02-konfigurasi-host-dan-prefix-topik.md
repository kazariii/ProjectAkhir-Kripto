# 02: Prefactor — host broker dan prefix topik dapat dikonfigurasi

**What to build:** Firmware sensor PQC dan receiver sesi membaca host broker dan prefix topik sesi dari konfigurasi, bukan konstanta. Nilai default tetap jalur Mosquitto privat sehingga perilaku deployment saat ini tidak berubah. Pengecekan kredensial menerima broker tanpa akun hanya bila konfigurasi menyatakannya secara eksplisit.

**Blocked by:** None (can start immediately)

**Status:** done

- [x] Firmware dan receiver memakai sumber konfigurasi yang sama untuk nama topik `up`/`down`
- [x] Build default dan konfigurasi privat menghasilkan topik dan host yang sama dengan sebelumnya
- [x] 113 pemeriksaan protokol, tes Python, dan loop sensor yang ada tetap lulus
- [x] Receiver privat di LXC di-restart dengan kode baru dan sesi native kontrol tetap lulus

## Comments

**Selesai, 25 November 2026.**

- Firmware: header bersama `pqc_broker.h` dipakai oleh firmware sensor PQC, sesi tiket 03, dan diagnostik. Defaultnya membaca akun privat dari `mqtt_diag_secrets.h`. Build yang mendefinisikan `PQC_BROKER_HOST` memakai broker publik tanpa akun. `PQC_TOPIC_PREFIX` menentukan topik sesi `<prefix>/up` dan `<prefix>/down`, dengan default `lab/kimia/pqc/session`.
- Receiver: topik diambil dari `topic_prefix` di JSON broker. Default `TOPIC_PREFIX` di `tools/session/native.py` disamakan dengan default firmware. Prefix yang kosong, berakhiran `/`, atau memuat wildcard `+`/`#` ditolak.
- Kredensial: tanpa akun hanya diterima bila JSON memuat `"public": true`, dan JSON publik tidak boleh memuat akun. Port tetap wajib 1883.
- Sumber konfigurasi firmware (makro build) dan receiver (JSON) berbeda artefak. Konsistensi prefix untuk jalur publik dijamin oleh provisioning di tiket 03.
- Env spike `mqtt-diagnostic-public` sekarang memakai `PQC_BROKER_HOST`. Flag `DIAG_PUBLIC`/`DIAG_PUBLIC_HOST` dihapus.

**Bukti:**

- String biner `pqc-telemetry` dan `pqc-session` sebelum dan sesudah perubahan identik: `10.34.211.141`, `diag-device`, `lab/kimia/pqc/session/up`, `lab/kimia/pqc/session/down`. Biner diagnostik publik tidak memuat IP privat atau akun.
- Di LXC: `make -C tools/session test` menghasilkan 113 checks lulus. 20 unit test lulus (`test_pqc_telemetry`, `test_telemetry_capture`, dan `test_broker_config` baru dengan 8 kasus). `check_pqc_sensor_cycle` lulus (2 PASS), dan `check_mqtt_capture.py` lulus (3 kasus).
- `lab-kimia-pqc-session.service` di-restart. Event `ready` menunjukkan `broker:10.34.211.141`, `topic_prefix:lab/kimia/pqc/session`, `public:false`. `tools.session.check_mqtt` lulus dengan `run_id` `fed278874f7d8934c8d2b726939775a2`, `encrypted_ack_verified:true`.
- `diag.json` spike ditambah `"public": true`. Responder publik di-restart dan kontrol native laptop lulus ulang (echo kecil dan 1519 byte).
- Backup berkas LXC sebelum sinkronisasi ada di `/opt/lab-kimia-mqtt/evidence/local/backup-wokwi-web-02/`.
