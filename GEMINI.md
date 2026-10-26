# ATURAN & MEMORI PERSISTEN SISTEM TRADING AI
> **PENTING UNTUK ASISTEN AI (ANTIGRAVITY):**
> File ini adalah memori inti dan konteks permanen proyek. Setiap kali pengguna menjalankan perintah `/clear` atau memulai sesi baru, Anda WAJIB langsung membaca dan menerapkan seluruh konteks, aturan, parameter, dan status terakhir di bawah ini tanpa meminta pengguna mengulang penjelasannya!

---

## 1. Identitas Akun & Profil Pengguna
* **Platform:** MetaTrader 5 (MT5 Desktop Windows & MT5 Mobile App Smartphone).
* **Akun Demo:** `10013117729`
* **Nama Server:** `MetaQuotes-Demo`
* **Pemilik:** Ilham Saputro
* **Instrumen Utama:** `EURUSD` (Forex)
* **Timeframe Utama:** `5m` (Scalping Cepat Sesi Asia & London/New York)
* **Fixed Lot Volume:** `0.01` lot (Wajib fix, tanpa compounding).

---

## 2. Arsitektur Komunikasi Dua Sisi (WSL <-> Windows)
* **Sisi Analisis (WSL Ubuntu):**
  * Script: `live_market_scanner.py`
  * Perintah Jalan: `./.venv/bin/python live_market_scanner.py --symbols EURUSD --interval 5m`
  * Komponen: TradingView Real-time Data Feed, ChromaDB Vector RAG (`knowledge_db/`), Google Gemini AI (`gemini-flash-lite-latest`), Stochastic Oscillator (8, 3, 3), SmartMoneyConcepts Engine (`smc_engine.py`), Multi-Timeframe Evaluator (`mtf_engine.py`), News Filter, dan Telegram Notifier (`telegram_notifier.py`).
  * Antrean Order: Menulis payload order JSON ke `orders_queue/pending/`.
* **Sisi Eksekusi (Windows 11 Native):**
  * Script: `mt5_bridge.py`
  * Perintah Jalan di PowerShell: `cd "C:\bot trading" && python mt5_bridge.py`
  * Komponen: Membaca `orders_queue/pending/`, auto-detect filling mode (`FOK`, `IOC`, `RETURN`), auto-reconnect retry loop (3x percobaan dengan `ensure_mt5_connected` & Retcode 10031), eksekusi instan di terminal MT5, dan memindahkan status ke `orders_queue/executed/`.

---

## 3. Parameter Risiko, SL, TP, dan Rasio (R:R)
* **Jarak Stop Loss (SL):** **$1.5\times$ nilai ATR(14)** dari harga entry dengan batas lantai minimal (**floor min 4.5 pips**).
  * Formula: `SL Distance = max(ATR * 1.5, 0.00045)` (mencegah SL tersambar premature oleh spread/noise broker).
* **Jarak Take Profit (TP) & Algoritma Adaptif S/R:**
  * **Target Default:** $1.5\times$ dari jarak SL (Rasio Risk to Reward **1 : 1.5**, minimal 6.8 pips).
  * **Algoritma Geser Resistance/Support Terdekat (`smc_engine.py`):**
    * Sebelum mengunci TP, bot memindai Resistance (BUY) atau Support (SELL) terdekat dari Swing High/Low fraktal, FVG, Order Block, serta **Level Kunci Manual (`manual_levels.json`)**.
    * **Level Kunci Manual Terdaftar (EURUSD):** `1.12685` (Resistance Mayor), `1.12608` (Resistance Minor/Flip), `1.12488` (Support Kunci RBS), `1.12406` (Support Mayor/Base Demand).
    * **Zona Ideal ($1.25\times - 1.85\times$ SL):** TP dialihkan ke level struktural/manual tersebut dengan buffer front-running 1.0 pip.
    * **Level Terlalu Dekat ($< 1.25\times$ SL):** Tetap entry dengan **mengunci TP default di $1.5\times$ SL** (mengantisipasi breakout tanpa memotong R:R).
    * **Level Jauh ($> 1.85\times$ SL) / Tidak Ada Level:** Tetap mengunci TP default di **$1.5\times$ SL**.
* **Anti-Slippage Dynamic Anchoring (`mt5_bridge.py`):**
  * Jarak SL dan TP dihitung ulang berdasarkan harga riil eksekusi (`Ask` untuk BUY, `Bid` untuk SELL) dengan batas minimum SL terkunci $\ge 4.5$ pips dan TP adaptif diizinkan pada rentang $\ge 1.25\times$ hingga $1.85\times$ SL (fallback default $1.5\times$).
* **Filter Mutlak Institusional & Proteksi Modal:**
  * **Ambang Batas Konfluensi:** Wajib minimal **2 Konfluensi Grade-A** (dengan kewajiban memuat minimal 1 pola candlestick valid + 1 konfluensi indikator/MTF) untuk memastikan efisiensi entry tanpa mengorbankan kualitas.
  * **Hard Veto MTF (Anti Counter-Trend):** Dilarang keras SELL jika MTF 15m Bullish di atas EMA 200, dilarang BUY jika MTF 15m Bearish di bawah EMA 200.
  * **Filter Jam Sesi Rawan Chop (*Session Filter*):** Dilarang membuka posisi baru pada jam likuiditas tipis & rawan false breakout: **11:30 – 13:00 WIB** (Jeda Siang Asia) dan **17:30 – 19:00 WIB** (London Lunch / Pre-NY).
  * **Dynamic Breakeven & Stepped Trailing Profit Lock (`mt5_bridge.py`):**
    * **Tier 1 (Breakeven):** Floating profit $\ge +5.0$ pips $\rightarrow$ SL otomatis digeser ke Entry $+0.5$ pip untuk mengunci posisi bebas risiko (*risk-free trade*).
    * **Tier 2 (Stepped Profit Lock):** Floating profit $\ge +8.0$ pips $\rightarrow$ SL otomatis digeser ke Entry $+4.5$ pips untuk mengunci keuntungan solid dan mencegah profit tergerus saat harga berbalik sebelum TP.
    * **Tier 3 (Runner Profit Lock):** Floating profit $\ge +12.0$ pips $\rightarrow$ SL otomatis digeser ke Entry $+8.5$ pips pada tren ekspansi panjang.
  * **Anti-Recovery Rally & Momentum Collision Veto:** Dilarang keras SELL jika MACD sedang Golden Cross aktif (`cur_macd > cur_signal`), KECUALI jika RSI Overbought parah $\ge 70.0$ dengan sumbu penolakan atas $\ge 30\%$. Dilarang keras BUY jika MACD Death Cross aktif (`cur_macd < cur_signal`), KECUALI jika RSI Oversold parah $\le 30.0$ dengan sumbu pantulan bawah $\ge 30\%$.
  * **Micro-Trend EMA Alignment Veto:** Dilarang SELL jika harga penutupan berada di atas EMA 20 dan EMA 20 sedang menanjak naik; dilarang BUY jika harga di bawah EMA 20 dan EMA 20 menukik turun.
  * **Anti-Steep EMA Slope Veto:** Dilarang BUY jika EMA-20 & EMA-50 menukik tajam ke bawah; dilarang SELL jika EMA-20 & EMA-50 menanjak tajam ke atas.
  * **Anti-Falling Knife:** Dilarang BUY saat MACD Death Cross tajam & candle penutupan merah; dilarang BUY jika RSI $< 22$ tanpa wick rejection $\ge 40\%$.
  * **Post-Loss Cooldown:** Wajib jeda **15 menit (3 bar candle)** pasca trade loss sebelum membuka order baru di simbol yang sama.

---

## 4. Standar Higienitas Candlestick (Steve Nison SOP)
* **Wajib Konfirmasi Bar Reversal:**
  * Seluruh pola pembalikan arah (Reversal) WAJIB ditutup dengan candle searah (Hijau untuk BUY, Merah untuk SELL) yang menembus batas separuh (*midpoint*) candle penekan sebelumnya.
* **Hanging Man (Bearish Reversal):**
  * Candle sebelumnya WAJIB HIJAU/BULLISH (`Close1 > Open1`) yang mendorong ke puncak (`High2 >= High1`). DILARANG jika candle sebelumnya sudah merah!
  * Sumbu atas WAJIB SANGAT PENDEK ($\le 8\%$ rentang candle & $\le 0.35\times$ body).
  * Sumbu bawah panjang mendominasi ($\ge 55\%$ rentang candle & $\ge 2\times$ body).
* **Shooting Star (Bearish Reversal):**
  * Candle sebelumnya WAJIB HIJAU di area Resistance, sumbu bawah $\le 8\%$ rentang candle.
* **Hammer & Inverted Hammer (Bullish Reversal):**
  * Candle sebelumnya WAJIB MERAH/BEARISH di area Support, sumbu lawan $\le 8\%$.
* **Three White Soldiers & Three Black Crows:**
  * 3 candle berturut-turut dengan body solid ($\ge 35\%$ rentang) dan sumbu lawan pendek ($\le 25\%$), dilarang memicu pada doji.
* **Filter Pemisahan MTF:**
  * Peringatan Counter-trend MTF (15m) tidak membatalkan eksekusi filter larangan penutupan candle berlawanan.
* **Tweezer Top (Bearish Reversal):**
  * Dua candle berturut-turut menguji level resistance dengan High kembar presisi (selisih $\le 1.1$ pips / $25\%$ range).
  * Candle 1 Bullish (`Close1 > Open1`), Candle 2 Bearish (`Close2 < Open2`) yang berbalik turun dari puncak High yang sama.
  * Candle 2 WAJIB body merah solid ($\ge 30\%$ range), menembus $\le 50\%$ body candle 1, dan memiliki sumbu atas penolakan nyata ($\ge 18\%$ range) atau dorongan momentum bearish solid ($\ge 45\%$ range).
  * Mengambil prioritas mutlak di atas Dark Cloud Cover; jika High kembar terpenuhi, diklasifikasikan sebagai Tweezer Top.
* **Tweezer Bottom (Bullish Reversal):**
  * Dua candle berturut-turut menguji level support dengan Low kembar presisi (selisih $\le 1.1$ pips / $25\%$ range).
  * Candle 1 Bearish (`Close1 < Open1`), Candle 2 Bullish (`Close2 > Open2`) yang memantul naik dari dasar Low yang sama.
  * Candle 2 WAJIB body hijau solid ($\ge 30\%$ range), menembus $\ge 50\%$ body candle 1, dan memiliki sumbu bawah penolakan nyata ($\ge 18\%$ range) atau dorongan momentum bullish solid ($\ge 45\%$ range).
  * Mengambil prioritas mutlak di atas Piercing Line.
* **Dark Cloud Cover & Piercing Line Guard:**
  * Dark Cloud Cover WAJIB mengecualikan Tweezer Top (`not is_tweezer_top`).
  * Piercing Line WAJIB mengecualikan Tweezer Bottom (`not is_tweezer_bottom`).
* **Engulfing & Pullback Calibration:**
  * Rasio body Engulfing diatur $\ge 1.05\times$ body candle lawan (menghilangkan dead zone).
  * Konteks RSI untuk pola reversal / retest: Bearish diizinkan pada RSI $\ge 42.0$ (pullback dalam tren turun) dan Bullish pada RSI $\le 55.0$ (pullback dalam tren naik).

---

## 5. Fitur Diagnosa Instan & Pembelajaran Mandiri AI (Self-Learning)
* **Diagnosa Seketika Tiap 1 Trade Kena SL:**
  * Setiap kali ada 1 posisi tersentuh Stop Loss, Gemini seketika melakukan audit forensik kilat (2–3 kalimat) mengenai penyebab teknikal SL.
  * Pesan notifikasi Telegram langsung dikirim memuat: Sumber Candle Bar (menit berapa), Waktu Masuk, Waktu Exit, Pips Rugi, dan Analisis AI Penyebab Kena SL.
* **Ambang Batas Evaluasi Mandiri (Pilihan 2: `min_losses = 2`):**
  * Begitu terjadi akumulasi **2 trade LOSS**:
    1. AI mengaudit benang merah sistemik dari kegagalan tersebut.
    2. Merumuskan 3 aturan pantangan baru (*Self-Learned Guardrails*).
    3. Menyimpan permanen ke SQLite (`signals.db` tabel `ai_reflections`).
    4. Menginjeksi aturan ke ChromaDB (`knowledge_db/`) dengan kategori `self_learned_guardrail`.
    5. Mengirim Laporan Evaluasi Mandiri lengkap ke Telegram.
    6. **Injeksi Prioritas RAG:** Aturan pantangan mandiri ini otomatis disuntikkan di urutan teratas (*Rule #1 & #2*) pada setiap query analisa pasar berikutnya.
* **Audit Akumulasi Breakeven (Ambang Batas: `min_breakevens = 3`):**
  * Jika terjadi akumulasi **3 trade menyentuh Stop Loss Breakeven** (walaupun tidak berturut-turut):
    1. AI mengaudit mengapa harga gagal mencapai Take Profit penuh setelah sempat menguntungkan $\ge +5.0$ pips.
    2. Merumuskan 2–3 aturan optimasi target TP / proteksi exit baru.
    3. Menyimpan permanen ke SQLite (`signals.db` tabel `ai_reflections`).
    4. Menginjeksi aturan ke ChromaDB (`knowledge_db/`) dengan kategori `self_learned_guardrail`.
    5. Mengirim Laporan Analisis Akumulasi Breakeven lengkap ke Telegram.

---

## 6. Riwayat Tiket & Status Terkini
* **Tiket Eksekusi Terakhir:** Tiket `#152811995297` (BUY USDJPY 0.01 lot @ 157.129, Exit 157.134, Status: WIN +0.5 pip via Breakeven) & `#152811924451` (BUY USDJPY 0.01 lot @ 157.101, Exit 157.106, Status: WIN +0.5 pip via Breakeven).
* **Tiket Loss Riil Terakhir:** Tiket `#152811747254` (BUY EURUSD 0.01 lot @ 1.12186, Exit 1.12141, Status: LOSS -4.5 pips).
* **Refleksi Tersimpan:** Refleksi ID #1 s/d #13 aktif di ChromaDB & SQLite (termasuk pantangan mutlak BUY saat Stochastic Overbought > 80 & menabrak BB Upper di 5m).
* **Fitur Terkini:** Multi-simbol scanning live feed (`EURUSD`, `GBPUSD`, `USDJPY`, `XAUUSD`), Native MT5 Position Watcher & Dynamic Breakeven, pemisahan klasifikasi Breakeven SL (`profit >= 0` $\rightarrow$ WIN / no false reflection) di `mt5_bridge.py`.

---

## 7. Strategi Pasca-Berita (Post-News Trend Continuation SOP)
* **Fase Blackout (0 - 15 Menit):**
  * Tetap menahan diri (DILARANG BUKA POSISI) saat rilis berita High-Impact (CPI, NFP, FOMC, Interest Rate) untuk menghindari slippage eksekusi dan pelebaran spread broker (5–10 pips).
* **Fase Post-News Drift (15 - 120 Menit):**
  * AI mendeteksi arah impuls berita fundamental di `news_filter.py` dan `live_market_scanner.py`.
  * **Aturan Pantangan Mutlak:** Dilarang keras membuka posisi berlawanan arah dengan impuls berita (*anti-falling knife*). Jika rilis berita memicu penurunan tajam (seperti CPI tinggi), sinyal BUY otomatis dibatalkan.
  * **Syarat Entri Pullback / Retest:** Entri searah hanya diizinkan saat harga melakukan koreksi sehat (*pullback*) ke EMA-20/50, Fair Value Gap (FVG), atau Stochastic hook di area diskon dengan konfirmasi candlestick pattern dan rasio Risk-to-Reward minimal 1 : 1.5.
