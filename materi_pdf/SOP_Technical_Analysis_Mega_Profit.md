# SOP STRATEGI ANALISIS TEKNIKAL MEGA PROFIT (SMC, SWING, & PROBABILITY)
> **Dokumen Otoritatif Inti:** Diadopsi dari kurikulum komprehensif *"Technical Analysis for Mega Profit"*.
> **Kategori Knowledge Base:** `smc_ict`

---

## 1. Arsitektur Struktur Pasar & Aliran Likuiditas (Market Structure)
1. **Swing Highs & Swing Lows Fraktal:**
   - Swing High: Titik harga di mana high diapit oleh minimal 2 candle di kiri dan kanan dengan high yang lebih rendah.
   - Swing Low: Titik harga di mana low diapit oleh minimal 2 candle di kiri dan kanan dengan low yang lebih tinggi.
2. **Break of Structure (BOS):**
   - Bullish BOS: Penutupan candle (*Close*) menembus ke atas Swing High sebelumnya dalam arah tren naik.
   - Bearish BOS: Penutupan candle menembus ke bawah Swing Low sebelumnya dalam arah tren turun.
3. **Change of Character (CHOCH):**
   - Sinyal awal transisi tren ketika harga menembus level struktur minor berlawanan arah sebelum tren utama berputar.

---

## 2. Fibonacci Retracement Kronologis & Optimal Trade Entry (OTE)
1. **Aturan Kronologis Wajib:**
   - Evaluasi ayunan harga WAJIB memperhatikan urutan waktu terjadinya titik ekstrim.
   - **Ayunan Naik (Upward Swing):** Titik `Swing Low` terjadi lebih dulu daripada `Swing High`. Harga saat ini sedang mengalami koreksi turun (*retrace down*).
     - Hitung: `Diskon = Swing High - (Rasio * (Swing High - Swing Low))`.
     - Rasio OTE Emas: **0.50 s/d 0.65** (Golden Pocket).
     - **Tindakan:** HANYA evaluasi peluang BUY di area diskon ini. Dilarang mencari sinyal SELL.
   - **Ayunan Turun (Downward Swing):** Titik `Swing High` terjadi lebih dulu daripada `Swing Low`. Harga saat ini sedang mengalami koreksi naik (*retrace up*).
     - Hitung: `Premium = Swing Low + (Rasio * (Swing High - Swing Low))`.
     - Rasio OTE Emas: **0.50 s/d 0.65** (Golden Pocket).
     - **Tindakan:** HANYA evaluasi peluang SELL di area premium ini. Dilarang mencari sinyal BUY.

---

## 3. Fair Value Gap (FVG) & Order Block (OB) Institutional Footprint
1. **Fair Value Gap (FVG):**
   - Ketidakseimbangan harga 3-candle di mana candle tengah mengalami impuls volume agresif, meninggalkan celah antara High candle-1 dan Low candle-3 (Bullish FVG) atau antara Low candle-1 dan High candle-3 (Bearish FVG).
   - Zona FVG yang belum tersentuh (*Unmitigated*) berfungsi sebagai magnet likuiditas dan area pantulan bernilai tinggi.
2. **Institutional Order Block (OB):**
   - Candle penekan terakhir sebelum terjadinya pergerakan impulsif yang merusak struktur pasar (BOS).
   - Menandakan jejak akumulasi atau distribusi institusi perbankan.

---

## 4. Konsep Role Reversal (RBS & SBR)
1. **Resistance Becomes Support (RBS):**
   - Level resistance mayor yang berhasil ditembus (*breakout*) oleh impuls volume kuat, kemudian saat harga melakukan pengujian ulang (*retest/pullback*), level tersebut berubah fungsi menjadi lantai pijakan support baru.
2. **Support Becomes Resistance (SBR):**
   - Level support mayor yang berhasil ditembus ke bawah (*breakdown*), kemudian saat harga memantul kembali (*pullback*), level tersebut berubah fungsi menjadi atap resistensi baru.

---

## 5. Manajemen Risiko & Ekspektansi Matematika Mega Profit
1. **Kekuatan Rasio Risk-to-Reward (R:R):**
   - Jangan pernah membuka posisi dengan R:R di bawah $1 : 1.5$.
   - Pada Win Rate 50%, sistem dengan R:R 1:1.5 menghasilkan ekspektansi matematis positif (+0.25R per trade).
   - Pada Win Rate 60%, sistem menghasilkan profit akumulatif sangat masif (+0.50R per trade).
2. **Dynamic Volatility Buffer (ATR):**
   - Jarak Stop Loss WAJIB berbasis volatilitas aktual pasar: `SL = max(1.5 * ATR, Min Floor Asset)`.
   - Mengeliminasi risiko tersenggol oleh spread acak broker (*anti-suffocation*).
