# Issue tracker: Local Markdown

- Satu fitur berada di .scratch/<feature-slug>/.
- Spesifikasi berada di .scratch/<feature-slug>/spec.md.
- Setiap tiket memiliki satu berkas:
  .scratch/<feature-slug>/issues/<NN>-<slug>.md.
- Nomor dimulai dari 01, dengan tiket penghambat lebih dahulu.
- Setiap tiket mencantumkan What to build, Blocked by,
  Status, dan daftar acceptance criteria.
- Blocked by mencantumkan nomor dan judul tiket penghambat.
- Tiket dapat dikerjakan setelah seluruh penghambatnya selesai.
- Status mengikuti triage-labels.md.
- Komentar tambahan ditulis di bagian Comments.

Saat diminta menerbitkan tiket, buat berkas lokal sesuai
aturan di atas. Saat diminta membaca atau memperbarui tiket,
gunakan berkas tiket yang dirujuk.
