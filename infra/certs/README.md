# CA EMQX lokal

Unduh **CA Certificate** dari halaman deployment EMQX Cloud Serverless milik pemilik proyek. Simpan di direktori ini sebagai `emqx-ca.pem`. Berkas `.pem` lokal diabaikan Git.

Salin isi PEM yang sama ke konstanta `MQTT_ROOT_CA` pada `firmware/include/secrets.h`. Sertifikat CA ini merupakan trust anchor publik, bukan private key. Jangan memakai sertifikat dari deployment/hostname lain atau menonaktifkan verifikasi untuk mengatasi kegagalan koneksi.
