# Monitoring di LXC

Deployment dilakukan pada 11 November 2026 di `root@10.34.211.141`, hostname `TA-Bu-Ari`, Ubuntu 26.04.1 LTS, RAM 2 GB, disk 10 GB. Direktori aplikasi: `/opt/lab-kimia-suhu`.

## Akses

- [Grafana](http://10.34.211.141:3000), [dashboard meja 01](http://10.34.211.141:3000/d/suhu-meja01): akses lewat jaringan privat/VPN yang bisa menjangkau LXC.
- Login Grafana memakai `GRAFANA_USERNAME` dan `GRAFANA_PASSWORD` pada `.env` proyek yang sudah ada. Kredensial yang sama disalin secara terenkripsi ke `.env` server, dengan permission `600` di direktori `700`.
- InfluxDB hanya dipublikasikan pada `127.0.0.1:8086` di server. Jika perlu membuka UI dari laptop, jalankan `ssh -N -L 18086:127.0.0.1:8086 root@10.34.211.141`, lalu buka `http://127.0.0.1:18086`. Login memakai `INFLUX_USERNAME` / `INFLUX_PASSWORD` pada `.env`.
- Grafana menggunakan HTTP pada jaringan privat. Untuk akses Grafana melalui SSH terenkripsi, jalankan `ssh -N -L 13000:10.34.211.141:3000 root@10.34.211.141`, lalu buka `http://127.0.0.1:13000`.

ESP32/Wokwi tetap mengirim ke EMQX Cloud melalui MQTT/TLS port 8883. Telegraf di LXC berlangganan ke broker yang sama dengan verifikasi CA dan hostname. Firmware tidak perlu diubah. Docker di laptop tidak perlu dijalankan untuk monitoring; simulator tetap perlu dinyalakan agar ada data sensor baru.

## Konfigurasi dan operasi

Docker Engine 29.9.3 dan Compose 5.7.0 dipasang dari [repository resmi Docker untuk Ubuntu](https://docs.docker.com/engine/install/ubuntu/). Image aplikasi menggunakan versi dan digest dalam `compose.yaml`: InfluxDB 2.9.1, Telegraf 1.40.3, Grafana 13.3.0. Dashboard dan datasource diprovisikan dari `infra/grafana`.

Server memakai `GRAFANA_BIND_ADDRESS=10.34.211.141` pada `.env`. Compose memakai `127.0.0.1` bila variabel tidak diisi; `.env.example` mendokumentasikan pengaturan ini. Pembaruan dari laptop harus mempertahankan nilai IP server tersebut dan kredensial yang sudah menginisialisasi volume.

Jalankan perintah berikut **di server**:

```sh
ssh root@10.34.211.141
cd /opt/lab-kimia-suhu
docker compose config --quiet
docker compose ps
docker compose logs --tail 50 telegraf
```

Memulai atau menerapkan pembaruan konfigurasi:

```sh
docker compose up -d --wait --wait-timeout 180
```

Memulai ulang atau menghentikan sementara:

```sh
docker compose restart
# Atau hentikan sementara; nyalakan lagi dengan compose up di atas.
docker compose stop
```

Docker diaktifkan saat boot dan ketiga layanan memakai `restart: unless-stopped`. Autostart setelah reboot LXC belum diuji dengan reboot aktual. Container yang sengaja dihentikan tetap berhenti sampai dinyalakan kembali.

Data berada dalam volume `lab-kimia-suhu_influx-data`, `lab-kimia-suhu_influx-config`, dan `lab-kimia-suhu_grafana-data`. Jangan menjalankan `docker compose down -v`, menghapus volume, atau mereset bucket untuk mengganti konfigurasi. Riwayat laptop **belum dimigrasikan** karena Docker Desktop tidak aktif saat deployment; data lokal tidak dihapus. Server mulai menerima data baru dari deployment ini.

Jangan menjalankan Telegraf laptop bersamaan dengan Telegraf LXC: konfigurasi keduanya memakai client ID MQTT `telegraf-meja01` sehingga dapat saling memutus sesi. Untuk kembali memakai stack lokal, hentikan Telegraf server terlebih dahulu.

Log Docker memakai driver `local`, maksimum tiga berkas masing-masing 10 MB per container. Retensi InfluxDB tetap tanpa batas sesuai proyek; pantau kapasitas dengan `df -h /`. Seusai deployment disk terpakai sekitar 3,1 GB dari 10 GB. Backup eksternal belum disiapkan.

## Hasil verifikasi

- Tiga container berjalan, InfluxDB healthy; API kesehatan Grafana dan datasource InfluxDB berhasil.
- Akses `http://10.34.211.141:3000/api/health` dari laptop berhasil.
- Dashboard UID `suhu-meja01` tersedia dengan tujuh panel.
- Satu sampel sintetis dengan device ID terpisah `lxc-deploy-b340ea33addc` diterbitkan memakai akun ESP32 melalui EMQX/TLS: suhu 26,25 Celsius, ADC 321, kedua alarm false. Sampel diterima Telegraf, tersimpan pada satu timestamp, dan terbaca melalui API kueri datasource Grafana. Panel utama tetap memfilter `esp32-meja01`.
- Setelah `docker compose restart`, sampel dengan timestamp asli `2026-11-11T02:47:08.441141381Z` tetap ada dan kembali terbaca melalui Grafana.
- Sampel asli `esp32-meja01` belum diterima selama verifikasi. Jalankan Wokwi dan periksa waktu penerimaan terbaru di dashboard untuk membuktikan alur sensor asli. Sampel sintetis tidak membuktikan simulator sedang aktif.

Skrip pemeriksaan satu kali dan hasil lokal disimpan di `evidence/local/lxc/` yang diabaikan Git. Bukti ini tidak mencakup pemindahan riwayat laptop atau reboot host Proxmox/LXC.
