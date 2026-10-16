# SOP KALENDER EKONOMI & PERLINDUNGAN HIGH-IMPACT NEWS (NEWS BLACKOUT)

## 1. PENDAHULUAN
Rilis data makroekonomi berkategori High-Impact (Bintang 3 / Red Folder) memicu pelebaran spread drastis (spread spike), likuiditas semu, slippage ekstrem, dan pergerakan harga tanpa arah teknikal (whipsaw). Sistem trading kuantitatif wajib menerapkan filter pembekuan sinyal (*News Blackout*) demi menjaga modal.

---

## 2. KLASIFIKASI BERITA BERDAMPAK TINGGI (HIGH-IMPACT NEWS)
1. **Amerika Serikat (USD):**
   - Non-Farm Payrolls (NFP) & Tingkat Pengangguran (Unemployment Rate).
   - Consumer Price Index (CPI) & Core CPI (Data Inflasi).
   - FOMC Statement, Fed Funds Interest Rate Decision, & FOMC Press Conference.
   - Gross Domestic Product (GDP) Advance / QoQ.
   - Producer Price Index (PPI) & Retail Sales.
2. **Zona Euro (EUR):**
   - ECB Interest Rate Decision & Monetary Policy Statement.
   - Eurozone Flash CPI Inflation Estimate.
   - German Flash Manufacturing PMI & German Ifo Business Climate.
3. **Inggris (GBP):**
   - Bank of England (BoE) Official Bank Rate & Monetary Policy Report.
   - UK CPI Inflation YoY.
   - UK GDP MoM / QoQ.
4. **Jepang (JPY):**
   - Bank of Japan (BoJ) Policy Rate & Outlook Report.
   - National Core CPI YoY.
5. **Emas / Gold (XAUUSD):**
   - Sangat sensitif terhadap seluruh berita berdampak tinggi USD, yield obligasi US Treasury 10-Tahun, dan ketegangan geopolitik mendadak.

---

## 3. ATURAN OPERASIONAL NEWS BLACKOUT
1. **Jendela Waktu Pembekuan (Blackout Window):**
   - **Pra-Berita (Pre-News):** 30 menit sebelum jadwal resmi rilis berita. Seluruh sinyal baru DIBEKUKAN (Action: WAIT).
   - **Pasca-Berita (Post-News):** 15 menit setelah rilis berita. Menunggu penutupan minimal 3 candle M5 agar spread kembali normal dan arah tren sejati terbentuk.
2. **Pengecualian / Larangan Mutlak:**
   - Dilarang keras membuka posisi baru (BUY maupun SELL) di dalam jendela waktu blackout, meskipun muncul pola candlestick Grade-A atau sinyal teknikal sempurna.
   - Jika sinyal muncul saat jendela blackout, sistem WAJIB menghasilkan status **WAIT** dengan alasan: `"News Blackout Active: High-Impact event [Nama Berita] dirilis dalam rentang waktu terlarang."`
3. **Penyaringan Simbol Terkait:**
   - Berita USD memblokir pasangan: EURUSD, GBPUSD, USDJPY, AUDUSD, USDCAD, USDCHF, XAUUSD.
   - Berita EUR memblokir: EURUSD, EURGBP, EURJPY.
   - Berita GBP memblokir: GBPUSD, EURGBP, GBPJPY.
