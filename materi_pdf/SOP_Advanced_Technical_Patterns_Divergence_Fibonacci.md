# SOP STRATEGI TEKNIKAL LANJUTAN: CHART PATTERNS, DIVERGENSI RSI, FIBONACCI GOLDEN POCKET, ICT KILLZONES, DAN VOLATILITAS SQUEEZE

Dokumen ini merupakan panduan standar operasional (SOP) tingkat lanjut untuk sistem trading kuantitatif institusional dan AI decision engine.

---

## 1. POLA GRAFIK GEOMETRIS KLASIK (ADVANCED CHART PATTERNS)

### A. Head and Shoulders (H&S) & Inverse Head and Shoulders (iH&S)
1. **Head and Shoulders (Bearish Reversal):**
   - **Struktur:** Terdiri dari 3 puncak: Puncak kiri (Left Shoulder), Puncak tertinggi tengah (Head), dan Puncak kanan yang lebih rendah (Right Shoulder).
   - **Garis Leher (Neckline):** Garis support yang menghubungkan lembah antara kedua bahu.
   - **Aturan Eksekusi:** SELL terpicu saat harga gagal membuat higher high pada Right Shoulder dan menolak area resistance neckline dengan konfirmasi candle bearish.
2. **Inverse Head and Shoulders (Bullish Reversal):**
   - **Struktur:** Terdiri dari 3 lembah: Lembah kiri, Lembah terendah tengah (Head), dan Lembah kanan yang lebih tinggi (Right Shoulder).
   - **Aturan Eksekusi:** BUY terpicu saat Right Shoulder membentuk higher low di atas support neckline dengan konfirmasi candle bullish.

### B. Bull Flag & Bear Flag (Pola Bendera Kontinuasi Tren Kuat)
1. **Bull Flag (Bullish Continuation):**
   - **Tiang Bendera (Flagpole):** Kenaikan harga tajam dan impulsif didukung volume tinggi.
   - **Bendera (Flag):** Saluran konsolidasi korektif menurun tipis (koreksi tidak boleh lebih dalam dari 50% flagpole).
   - **Aturan Eksekusi:** BUY saat harga menembus batas atas bendera ke arah uptrend mayor.
2. **Bear Flag (Bearish Continuation):**
   - **Tiang Bendera (Flagpole):** Penurunan harga tajam dan impulsif didukung volume tinggi.
   - **Bendera (Flag):** Saluran konsolidasi korektif naik tipis (koreksi dangkal).
   - **Aturan Eksekusi:** SELL saat harga menembus batas bawah bendera ke arah downtrend mayor.

### C. Ascending & Descending Triangle (Pola Kompresi Volatilitas)
1. **Ascending Triangle (Bullish Bias):**
   - Puncak horizontal datar (resistance) berulang kali diuji oleh lembah yang semakin meninggi (*Higher Lows*).
   - Mengindikasikan pembeli terus agresif menekan resistance hingga terjadi ledakan breakout ke atas.
2. **Descending Triangle (Bearish Bias):**
   - Dasar horizontal datar (support) berulang kali diuji oleh puncak yang semakin merendah (*Lower Highs*).
   - Mengindikasikan penjual terus agresif menekan support hingga terjadi breakdown ke bawah.

---

## 2. DETEKSI DIVERGENSI RSI (RSI MOMENTUM DIVERGENCE)

Divergensi terjadi ketika pergerakan grafik harga bertolak belakang dengan pergerakan osilator momentum RSI (14).

1. **Regular Bullish Divergence (Pembalikan Naik Kuat):**
   - **Kondisi:** Grafik harga mencetak titik terendah baru yang lebih rendah (*Lower Low*), namun indikator RSI mencetak titik terendah yang lebih tinggi (*Higher Low*).
   - **Makna:** Tekanan jual telah melemah drastis (*exhaustion*). Sinyal pembalikan arah BUY probabilitas tinggi.
2. **Regular Bearish Divergence (Pembalikan Turun Kuat):**
   - **Kondisi:** Grafik harga mencetak titik tertinggi baru yang lebih tinggi (*Higher High*), namun indikator RSI mencetak titik tertinggi yang lebih rendah (*Lower High*).
   - **Makna:** Tekanan beli telah jenuh (*exhaustion*). Sinyal pembalikan arah SELL probabilitas tinggi.
3. **Hidden Divergence (Kelanjutan Tren / Trend Continuation):**
   - **Hidden Bullish:** Harga mencetak *Higher Low* saat pullback, namun RSI mencetak *Lower Low* $\rightarrow$ Sinyal BUY kelanjutan uptrend.
   - **Hidden Bearish:** Harga mencetak *Lower High* saat retrace, namun RSI mencetak *Higher High* $\rightarrow$ Sinyal SELL kelanjutan downtrend.

---

## 3. FIBONACCI RETRACEMENT DINAMIS (GOLDEN POCKET 0.50 - 0.65)

1. **Konsep Golden Pocket:**
   - Berdasarkan swing impulsif terkini (High ke Low atau Low ke High), area antara rasio Fibonacci 50.0% (0.500) dan 65.0% (0.650) merupakan area keseimbangan harga institusional paling dicari (*Optimal Trade Entry / OTE*).
2. **Kronologi Swing (Urutan Waktu Wajib):**
   - **Bullish Retracement (BUY):** Swing Low terjadi LEBIH DULU daripada Swing High (`pos_low < pos_high`), lalu harga pullback turun mencari diskon di area 0.50 - 0.65.
   - **Bearish Retracement (SELL):** Swing High terjadi LEBIH DULU daripada Swing Low (`pos_high < pos_low`), lalu harga koreksi naik mencari premium di area 0.50 - 0.65.
3. **Konfluensi Entry:**
   - BUY Setup: Ketika harga retrace ke Golden Pocket (0.50 - 0.65) dan bersinggungan dengan Bullish Order Block, FVG, atau Support EMA/Bollinger.
   - SELL Setup: Ketika harga rally ke Golden Pocket (0.50 - 0.65) dan bersinggungan dengan Bearish Order Block, FVG, atau Resistance EMA/Bollinger.

---

## 4. WAKTU LIKUIDITAS INSTITUSIONAL (ICT KILLZONES)

Forex dan Komoditas bergerak dengan probabilitas tren tertinggi saat sesi likuiditas perbankan aktif:

1. **London Open Killzone (14:00 - 17:00 WIB / 07:00 - 10:00 UTC):**
   - Volume perdagangan Eropa masuk. Titik High/Low harian sering kali terbentuk pada sesi ini.
2. **New York Open Killzone (19:30 - 22:30 WIB / 12:30 - 15:30 UTC):**
   - Likuiditas gabungan London-New York paling masif di dunia. Tren terkuat dan pergerakan impulsif terjadi pada sesi ini.
3. **Asian Session / Dead Zone (05:00 - 13:00 WIB):**
   - Karakteristik pasar berkisar sideways (*consolidation*). Hati-hati terhadap jebakan breakout palsu (*Asian Range Fakeout*).

---

## 5. BOLLINGER BANDS SQUEEZE & VOLATILITY EXPANSION

1. **BandWidth Squeeze (Kompresi Volatilitas Ekstrem):**
   - Formula: `BandWidth = (Upper Band - Lower Band) / Middle Basis`.
   - Ketika BandWidth berada di level terendah dalam 20 bar terakhir, pasar sedang mengumpulkan energi kinetik besar.
2. **Breakout Expansion:**
   - Candle penembusan pertama yang ditutup di luar pita Bollinger setelah fase squeeze menandakan awal ledakan tren baru (*volatility expansion*).
   - Diikuti oleh pembukaan pita atas dan pita bawah secara serentak ke arah berlawanan (*opening the jaws*).

---

## 6. DYNAMIC EMA 20/50 PULLBACK & TREND BOUNCE (ZONA NILAI KELANJUTAN TREN)

1. **Definisi & Fungsi:**
   - EMA 20 dan EMA 50 berfungsi sebagai *Dynamic Support* pada tren naik dan *Dynamic Resistance* pada tren turun.
   - Bertindak sebagai **Area Nilai / Lokasi (Where)**, bukan pemicu entri mandiri tanpa konfirmasi candle.
2. **Bullish Dynamic EMA Pullback (BUY):**
   - Terjadi saat tren 15m/1H Bullish dan harga melakukan koreksi sehat menyentuh EMA 20 atau EMA 50.
   - Syarat Entri: Wajib disertai formasi candlestick rejection (Hammer, Bullish Engulfing, Tweezer Bottom) yang ditutup hijau di atas garis EMA.
3. **Bearish Dynamic EMA Pullback (SELL):**
   - Terjadi saat tren 15m/1H Bearish dan harga melakukan koreksi naik menyentuh EMA 20 atau EMA 50.
   - Syarat Entri: Wajib disertai formasi candlestick rejection (Shooting Star, Bearish Engulfing, Tweezer Top) yang ditutup merah di bawah garis EMA.

---

## 7. ROLE REVERSAL (RBS / SBR RETEST)

1. **Resistance Became Support (RBS - BUY):**
   - Area resistance horizontal yang berhasil ditembus (*breakout*) oleh impulsive candle beralih fungsi menjadi support baru.
   - Entri BUY dieksekusi saat harga melakukan retest ke level breakout tersebut dengan konfirmasi rejection candle.
2. **Support Became Resistance (SBR - SELL):**
   - Area support horizontal yang berhasil ditembus (*breakdown*) beralih fungsi menjadi resistance baru.
   - Entri SELL dieksekusi saat harga melakukan retest ke level breakdown tersebut dengan konfirmasi rejection candle.

---

## 8. INSTITUTIONAL VWAP & STANDARD DEVIATION BANDS (±2 SIGMA)

1. **Session-Anchored VWAP Baseline:**
   - Volume-Weighted Average Price dihitung sejak awal hari perdagangan (reset harian sesi Asia).
   - Berfungsi sebagai garis ekuilibrium institusional (*fair value baseline*).
2. **Trend Continuation Bounce:**
   - Memantul di garis VWAP Baseline searah tren mayor adalah setup continuasi dengan rasio R:R sangat tinggi.
3. **Statistical Mean Reversion (±2σ Bands):**
   - **VWAP -2σ (Oversold Extreme):** Pantulan di pita -2σ yang disertai Liquidity Sweep sah untuk BUY Mean-Reversion.
   - **VWAP +2σ (Overbought Extreme):** Penolakan di pita +2σ yang disertai Liquidity Sweep sah untuk SELL Mean-Reversion.

---

## 9. HARMONI MOMENTUM HISTOGRAM MACD (PULLBACK CONTINUATION RULE)

1. **Karakteristik Lagging MACD saat Pullback:**
   - Saat harga melakukan koreksi 3-4 bar dalam tren naik 15m yang kuat, garis MACD wajar berada di bawah Signal line (*Death Cross sementara*).
2. **Harmoni Histogram Menanjak (`cur_hist > prev_hist`):**
   - Jika MACD Histogram mulai memendek atau menanjak naik ke atas, ini mengindikasikan tekanan jual korektif telah habis (*seller exhaustion*).
   - **Aturan Eksekusi:** Entri BUY diperbolehkan meskipun garis MACD masih di bawah Signal line, asalkan didukung:
     - Tren 15m/1H searah Bullish.
     - Candlestick rejection Steve Nison terkonfirmasi pada closed bar.
     - Histogram MACD menanjak naik (`cur_hist > prev_hist`).
