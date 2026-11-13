# SOP STANDAR INSTITUSIONAL: SMART MONEY CONCEPTS (SMC) & ICT

## 1. PENDAHULUAN & PRINSIP DASAR
Pendekatan Smart Money Concepts (SMC) dan Inner Circle Trader (ICT) berfokus pada pelacakan jejak likuiditas pelaku pasar institusional (bank sentral, dana lindung nilai, dan liquidity providers). Berbeda dari analisis retail konvensional yang mengandalkan garis indikator statis, SMC menganalisis struktur pasar murni, area ketidakseimbangan harga (*imbalance*), dan penyerapan likuiditas (*liquidity sweeps*).

---

## 2. STRUKTUR PASAR (MARKET STRUCTURE)
1. **Swing Highs & Swing Lows:**
   - Swing High: Titik tertinggi lokal di mana candle sebelumnya dan candle sesudahnya memiliki High lebih rendah.
   - Swing Low: Titik terendah lokal di mana candle sebelumnya dan candle sesudahnya memiliki Low lebih tinggi.
2. **Break of Structure (BOS):**
   - Penembusan valid pada level Swing High (pada tren naik) atau Swing Low (pada tren turun) oleh body candle penutup (*closed candle*).
   - Menandakan **kelanjutan tren (trend continuation)** institusional.
3. **Change of Character (CHoCH):**
   - Pembalikan struktur pertama di mana harga menembus Swing Low terakhir dalam kondisi uptrend, atau menembus Swing High terakhir dalam kondisi downtrend.
   - Merupakan sinyal peringatan awal terjadinya **pembalikan arah tren (trend reversal)**.

---

## 3. FAIR VALUE GAP (FVG / IMBALANCE)
1. **Definisi Anatomi FVG:**
   - FVG adalah ketidakseimbangan harga 3-candle berturut-turut yang terjadi akibat lonjakan volume agresif satu arah (ekspansi cepat).
   - **Bullish FVG:** Terjadi celah antara Low Candle 3 dan High Candle 1. (Low[3] > High[1]).
   - **Bearish FVG:** Terjadi celah antara High Candle 3 dan Low Candle 1. (High[3] < Low[1]).
2. **Mitigasi FVG (Mitigation Rule):**
   - Celah FVG bertindak sebagai magnet likuiditas di masa depan.
   - Status **Unmitigated (Fresh):** FVG yang belum pernah disentuh atau ditembus oleh ekor/body candle setelahnya. Ini adalah area entri dengan probabilitas tertinggi.
   - Status **Mitigated:** FVG yang sudah terisi oleh pergerakan harga subsequent. Kekuatan pantulannya berkurang drastis dan tidak lagi menjadi level entri utama.
3. **Aturan Eksekusi FVG:**
   - Entri BUY: Diuji ketika harga pullback turun ke area Bullish FVG unmitigated saat tren mayor naik.
   - Entri SELL: Diuji ketika harga pullback naik ke area Bearish FVG unmitigated saat tren mayor turun.

---

## 4. INSTITUTIONAL ORDER BLOCK (OB)
1. **Definisi Order Block:**
   - **Bullish Order Block:** Candle penurunan terakhir (biasanya candle merah) sebelum terjadinya pergerakan kenaikan impulsif yang memecahkan struktur harga (BOS/CHoCH) dan meninggalkan FVG.
   - **Bearish Order Block:** Candle kenaikan terakhir (biasanya candle hijau) sebelum pergerakan penurunan impulsif yang memecahkan struktur harga dan meninggalkan FVG.
2. **Validitas Order Block Grade-A:**
   - Wajib memicu pergerakan impulsif yang menghasilkan BOS atau CHoCH.
   - Wajib meninggalkan setidaknya 1 Fair Value Gap (FVG) di depannya.
   - Belum termitigasi (unmitigated/fresh). Jika harga sudah masuk ke dalam 50% equilibrium body Order Block tersebut sebelumnya, validitasnya gugur.

---

## 5. LIKUIDITAS & JEBAKAN PASAR (LIQUIDITY POOLS & SWEEPS)
1. **Buy-side Liquidity (BSL):**
   - Kumpulan order Buy Stop (stop loss para penjual dan breakout buy retail) yang berkumpul di atas level *Equal Highs* atau *Double Top*.
2. **Sell-side Liquidity (SSL):**
   - Kumpulan order Sell Stop (stop loss para pembeli dan breakout sell retail) yang berkumpul di bawah level *Equal Lows* atau *Double Bottom*.
3. **Liquidity Sweep (Stop Hunt):**
   - Manuver di mana harga menembus sesaat level BSL/SSL hanya dengan ekor candle (*wick only*) lalu langsung berbalik arah dan ditutup kembali di dalam rentang harga sebelumnya.
   - Tindakan: Dilarang melakukan breakout trade saat terjadi liquidity sweep. Cari peluang entri pembalikan arah menuju FVG yang berlawanan.

---

## 6. MULTI-TIMEFRAME CONFLUENCE MATRIX
* **Timeframe Tinggi (H4 / H1):** Menentukan arah tren institusional, letak Order Block mayor, dan FVG mayor.
* **Timeframe Menengah (M15):** Menentukan struktur pasar lokal (BOS / CHoCH).
* **Timeframe Pemicu (M5 / M1):** Menentukan titik entri presisi saat harga menyentuh FVG M15/H1 yang terkonfirmasi pola pembalikan Grade-A.

---

## 7. INSTITUTIONAL BREAKER BLOCK (FAILED SUPPLY/DEMAND FLIP)
1. **Definisi Breaker Block:**
   - Breaker Block adalah Order Block yang gagal menahan harga dan ditembus secara impulsif, lalu bertukar fungsi (*flip*) menjadi area pertahanan arah yang baru.
2. **Bullish Breaker Block (BUY):**
   - Order Block Bearish yang tertembus ke atas saat terjadi pergerakan impulsif (BOS).
   - Ketika harga retrace kembali menguji atap Breaker Block tersebut, area ini berubah menjadi support kuat untuk BUY.
3. **Bearish Breaker Block (SELL):**
   - Order Block Bullish yang tertembus ke bawah saat pergerakan drop impulsif.
   - Ketika harga pullback naik menguji lantai Breaker Block tersebut, area ini berubah menjadi resistance kuat untuk SELL.

---

## 8. STRATEGI PASCA-BERITA (POST-NEWS TREND CONTINUATION DRIFT 15 - 120 MENIT)
1. **Fase Blackout (0 - 15 Menit):**
   - Dilarang keras membuka posisi baru saat rilis berita High-Impact untuk menghindari slippage eksekusi dan pelebaran spread broker.
2. **Fase Post-News Drift (15 - 120 Menit):**
   - Arah pasar didikte oleh dorongan volume fundamental besar (*institutional news drift*).
   - **Aturan Pantangan Mutlak:** Dilarang keras membuka posisi berlawanan arah dengan impuls berita (*anti-falling knife*).
   - **Syarat Entri Pullback / Retest:**
     - Entri searah impuls berita hanya diizinkan saat harga melakukan koreksi sehat (*pullback*) ke EMA-20/50, Fair Value Gap (FVG), atau Breaker Block.
     - Wajib disertai konfirmasi candlestick rejection Steve Nison dan rasio Risk-to-Reward minimal 1 : 1.5.
