# JURNAL & RIWAYAT LENGKAP PENGEMBANGAN BOT TRADING AI (PROJECT CONTEXT)
*Dokumen ini diperbarui secara berkala sebagai catatan persisten seluruh topik percakapan, konfigurasi, solusi bug, dan parameter teknikal.*

---

## 📌 Topik 1: Pengaturan Izin MetaTrader 5 (MT5 Desktop)
* **Permasalahan:** Pilihan opsi Algo Trading dan API eksternal di pengaturan MT5.
* **Solusi & Rekomendasi:**
  * Wajib Centang: **"Izinkan perdagangan algoritmik"** (tombol Algo Trading di toolbar harus berwarna HIJAU).
  * Wajib Centang: **"Izinkan impor DLL"** (untuk library native bridge eksternal).
  * Nonaktifkan pembatasan yang mematikan EA saat ganti akun/profil/simbol jika ingin bot tetap berjalan kontinu.
  * Pastikan **TIDAK** mencentang "Nonaktifkan perdagangan algoritmik melalui API Python eksternal" agar Python dapat mengirim order.

---

## 📌 Topik 2: Integrasi Auto-Trade MT5 (Fixed Lot 0.01)
* **Permasalahan:** Pengguna ingin order yang dihasilkan AI langsung otomatis dieksekusi di akun MT5 Demo (`10013117729` pada server `MetaQuotes-Demo`), dan dipantau dari aplikasi HP (Mobile MT5).
* **Solusi & Arsitektur:**
  * Membangun arsitektur decoupled antrean file:
    * `live_market_scanner.py` (WSL Ubuntu) menulis sinyal order ke `orders_queue/pending/`.
    * `mt5_bridge.py` (Windows Native PowerShell) membaca file pending, menghubungkan ke terminal MT5, dan mengeksekusi order instan dengan volume fixed `0.01` lot.
    * Setelah sukses, payload dipindahkan ke `orders_queue/executed/`.
  * Menangani Retcode 10031 (*absence of network connection*) dengan reconnect retry loop otomatis.
  * Menangani mode filling broker (`FOK`, `IOC`, `RETURN`) dan wildcard symbol matching (`*EURUSD*`).

---

## 📌 Topik 3: Detail Sumber Candle pada Notifikasi Telegram
* **Permasalahan:** Pengguna meminta agar setiap notifikasi hasil (TP tercapai atau SL tersentuh) mencantumkan sumber informasi detail, seperti candle menit berapa posisi tersebut dibuka.
* **Solusi:**
  * Memperbarui `signal_tracker.py` agar menyertakan:
    * `Sumber Candle Sinyal: Candle 5m Bar [Timestamp/Menit]`
    * `Waktu Sinyal Masuk: [Waktu Riil WIB]`
    * `Waktu Tercapai Exit: [Waktu Riil WIB]`
    * Catatan eksplisit: *"Posisi ini berasal dari sinyal candle 5m yang ditutup pada pukul [Timestamp] WIB"*.

---

## 📌 Topik 4: Penyelarasan Rasio Stop Loss (SL) & Take Profit (TP)
* **Permasalahan Awal:** Pada tiket lama `#152757702345`, SL terpasang lebih besar daripada TP akibat pergeseran harga eksekusi (*slippage*).
* **Solusi & Standar Baru yang Ditetapkan:**
  * **Stop Loss (SL):** **$1.2\times$ nilai ATR(14)** dari harga entry.
  * **Take Profit (TP):** **$1.5\times$ dari jarak SL** (Rasio Risk to Reward **1 : 1.5**).
  * **Dynamic Anchoring:** Di dalam `mt5_bridge.py`, jarak SL dan TP diikat langsung ke harga live saat order dieksekusi (`Ask` untuk BUY, `Bid` untuk SELL) sehingga rasio TP minimal $1.5\times$ dari jarak SL selalu dijamin 100%.

---

## 📌 Topik 5: Audit & Higienitas Pola Candlestick (Steve Nison Standards)
* **Permasalahan:** Muncul false signal Hanging Man saat candle sebelumnya berwarna merah dan memiliki sumbu atas yang terlalu panjang.
* **Solusi di [`live_market_scanner.py`](file:///mnt/c/bot%20trading/live_market_scanner.py) & [`rag_engine.py`](file:///mnt/c/bot%20trading/rag_engine.py):**
  * **Hanging Man:** Wajib didahului candle hijau (`Close1 > Open1`), di puncak lokal, sumbu atas $\le 8\%$ rentang candle & $\le 0.35\times$ body, sumbu bawah $\ge 55\%$ rentang candle.
  * **Shooting Star:** Wajib didahului candle hijau, di puncak lokal, sumbu bawah $\le 8\%$.
  * **Hammer & Inverted Hammer:** Wajib didahului candle merah (`Close1 < Open1`), di support, sumbu lawan $\le 8\%$.
  * **Three White Soldiers & Three Black Crows:** Wajib 3 candle solid berturut-turut ($\ge 35\%$ rentang), sumbu lawan pendek ($\le 25\%$), dilarang memicu pada doji.
  * **Pemisahan Logika MTF:** Peringatan counter-trend MTF tidak lagi membatalkan filter arah penutupan candle.

---

## 📌 Topik 6: Diagnosa Instan Tiap 1 SL & Pembelajaran Mandiri (Self-Learning)
* **Permasalahan:** Pengguna meminta agar:
  1. Setiap kali ada 1 trade kena SL, AI seketika menganalisis penyebabnya dan mengirim pesan ke Telegram dengan detail candle.
  2. Menerapkan **Pilihan 2 (Cepat - 2 Loss)**: AI mengevaluasi diri dan mengupdate SOP saat mencapai 2 loss berturut-turut (`min_losses=2`).
* **Solusi yang Telah Diterapkan:**
  * Menambahkan `diagnose_single_loss()` di `signal_tracker.py` menggunakan Google Gemini untuk menganalisis root-cause kekalahan teknikal (2-3 kalimat) dan mencantumkannya langsung di pesan Telegram Stop Loss.
  * Mengubah ambang batas `min_losses = 2` pada `reflect_and_self_optimize()`.
  * Begitu 2 loss terjadi: AI merumuskan 3 aturan pantangan baru (*Self-Learned Guardrails*), menyimpannya ke SQLite (`signals.db`), menyuntikkannya ke ChromaDB (`knowledge_db/`), dan mengirimkan laporan lengkap ke Telegram.
  * Di `rag_engine.py`, aturan pantangan mandiri tersebut otomatis diposisikan sebagai **prioritas teratas (*Rule #1 & #2*)** pada setiap kali evaluasi peluang entri baru.

---

## 📌 Topik 7: Presisi Pola Tweezer Top vs Dark Cloud Cover & Auto-Reconnect MT5 Bridge
* **Permasalahan (20:41):**
  1. MT5 Bridge gagal mengeksekusi order otomatis karena transient timeout IPC (`Simbol 'EURUSD' tidak ditemukan`).
  2. Scanner salah mengenali formasi candle 20:30–20:35 sebagai *Dark Cloud Cover*, padahal merupakan *Tweezer Top* dengan High kembar (selisih hanya 0.3 pips).
* **Solusi:**
  * **Tweezer Top vs Dark Cloud Cover (Steve Nison SOP):**
    * Tweezer Top: 2 candle menguji resistance dengan High kembar presisi ($\le 0.5$ pips), candle 1 hijau, candle 2 merah berbalik arah. Sumbu atas tidak dipaksakan $\ge 25\%$ di kedua candle.
    * Dark Cloud Cover: Diberi guard `not is_tweezer_top` agar tidak mendahului Tweezer Top saat High kembar terbentuk.
    * Hal simetris diterapkan pada Tweezer Bottom vs Piercing Line.
  * **Auto-Reconnect MT5 Bridge:**
    * Menambahkan fungsi `ensure_mt5_connected()` dan 3x retry loop di `resolve_symbol()` serta `execute_order()`.
    * Jika terminal MT5 sempat offline atau transient error, bridge otomatis re-inisialisasi tanpa membuang order ke `failed/`.

---

## 📌 Topik 8: Monitoring Posisi Riil MT5 (Position Watcher) & Desinkronisasi SL
* **Permasalahan (21:12 - Tiket #152758756811):**
  * Posisi BUY di MT5 tersentuh Stop Loss pada 21:15 (SL 1.11880), namun notifikasi Telegram sempat tidak langsung terkirim karena scanner WSL hanya mengandalkan candle TradingView dan nilai SL teoritis di database (`1.11867`).
* **Solusi Terintegrasi:**
  * **Notifikasi SL & Diagnosa AI Sukses Dikirim:** Analisis forensik Gemini untuk Tiket #152758756811 telah berhasil diproses dan dikirimkan ke Telegram.
  * **Sinkronisasi Harga Riil (`sync_executed_orders`):** Database `signals.db` kini otomatis diselaraskan dengan harga eksekusi riil, SL, dan TP aktual dari MT5.
  * **Native MT5 Position Watcher di [`mt5_bridge.py`](file:///mnt/c/bot%20trading/mt5_bridge.py):** Menambahkan `check_closed_positions()` yang memantau tiket aktif secara native via `mt5.positions_get()` dan `mt5.history_deals_get()`. Begitu posisi ditutup oleh SL/TP di MT5, bridge langsung mengirim notifikasi seketika dan menulis payload ke `orders_queue/outcomes/` untuk diagnosa kilat AI.
  * **MT5 Ticket Single Source of Truth:** Kolom `ticket` ditambahkan ke `signals.db`. Simulasi candle TradingView (`check_signals_outcome`) kini dibatasi hanya untuk sinyal paper-trading (`ticket IS NULL`). Setiap transaksi yang memiliki nomor tiket MT5 wajib 100% diputus statusnya (WIN/LOSS, exit price, profit) oleh konfirmasi deal riil terminal MT5.

## 🚀 Panduan Menjalankan Sistem
1. **Di Windows PowerShell:**
   ```powershell
   cd "C:\bot trading"
   python mt5_bridge.py
   ```
2. **Di Terminal WSL Ubuntu:**
   ```bash
   cd "/mnt/c/bot trading"
   ./.venv/bin/python live_market_scanner.py --symbols EURUSD --interval 5m
   ```
