# SOP FILTER REZIM PASAR, KEKUATAN TREN (ADX), DAN KEMIRINGAN EMA
> **Dokumen Otoritatif Inti:** Aturan Penyaringan Rezim Pasar dan Kekuatan Tren.
> **Kategori Knowledge Base:** `trend_regime`

---

## 1. Definisi Tiga Rezim Pasar (Market Regimes)
1. **Strong Trending Regime (Pasar Tren Kuat):**
   - Karakteristik: Pergerakan terarah dengan momentum konsisten, membuat urutan Higher High / Higher Low (Uptrend) atau Lower High / Lower Low (Downtrend).
   - Indikator: `ADX(14) >= 20.0` (dan optimal jika `ADX >= 25.0`), kemiringan EMA terpolarisasi tajam, dan struktur EMA tertumpuk rapi (*EMA Stacking*).
   - Strategi Sah: **Trend-Pullback Continuation** (membeli di diskon saat koreksi menyentuh EMA 20/50 atau FVG).
2. **Choppy / Ranging / Sideways Regime (Pasar Rawan Jebakan):**
   - Karakteristik: Harga bergerak bolak-balik tanpa arah di dalam rentang sempit, memotong bolak-balik garis EMA.
   - Indikator: `ADX(14) < 20.0`, kemiringan EMA 50 mendekati nol (*flat* / $|Slope| < 0.10$), dan Bollinger Bands mengalami pemampatan sempit (*Bollinger Squeeze*).
   - **Aturan Pantangan Mutlak:** DILARANG KERAS menjalankan strategi *trend-following* (seperti EMA Bounce, Three White Soldiers, Breakout Continuation). Semua sinyal tren otomatis diveto saat ADX < 20.0!
3. **High Volatility Expansion / News Regime:**
   - Karakteristik: Lonjakan rentang candle ekstrem akibat rilis data ekonomi atau likuiditas mendadak.
   - Penanganan: Patuhi SOP News Blackout (tahan diri 15 menit pasca-rilis berita).

---

## 2. Standar Tiga Syarat Sah Tren (The 3 Pillar Trend Definition)
Dilarang menyatakan pasar sedang dalam tren naik (*Uptrend*) hanya karena harga sesaat berada di atas EMA 200. Sebuah tren dinyatakan valid HANYA JIKA memenuhi 3 kriteria kuantitatif berikut:

### A. EMA Alignment & Stacking (Penataan EMA Berjenjang)
* **Kriteria Bullish Trend:**
  - `EMA 20 > EMA 50` DAN `EMA 50 > EMA 200` pada timeframe 15m.
  - Urutan ini membuktikan kecepatan momentum jangka pendek memimpin di atas jangkar jangka menengah dan panjang.
* **Kriteria Bearish Trend:**
  - `EMA 20 < EMA 50` DAN `EMA 50 < EMA 200` pada timeframe 15m.

### B. Normalized EMA Slope (Kemiringan EMA 50 Dinormalisasi ATR)
* **Formula Kuantitatif:**
  $$\text{Slope} = \frac{\text{EMA50}_{\text{current}} - \text{EMA50}_{\text{bar}-5}}{\text{ATR}(14)}$$
* **Ambang Batas (Thresholds):**
  - **Bullish Expansion:** $\text{Slope} \ge +0.10$ (menandakan sudut menanjak sehat).
  - **Bearish Expansion:** $\text{Slope} \le -0.10$ (menandakan sudut menukik tajam).
  - **Flat / Sideways Neutral:** $-0.10 < \text{Slope} < +0.10$. Menandakan garis EMA mendatar; peluang false breakout sangat tinggi.

### C. ADX (Average Directional Index) Periode 14
* **Kekuatan Tren:**
  - `ADX < 20.0`: Pasar mati / tanpa tren (*Non-Trending*). Semua posisi trend-following dibatalkan.
  - `20.0 <= ADX < 35.0`: Tren sehat berkembang (*Developing Trend*). Area emas untuk entry pullback.
  - `ADX >= 35.0`: Tren sangat kuat (*Strong Trend*). Menandakan dorongan institusional agresif.
