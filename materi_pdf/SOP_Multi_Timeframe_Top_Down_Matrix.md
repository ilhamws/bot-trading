# SOP MATRIKS MULTI-TIMEFRAME TOP-DOWN (1H -> 15M -> 5M)
> **Dokumen Otoritatif Inti:** Aturan Evaluasi Multi-Timeframe Berjenjang.
> **Kategori Knowledge Base:** `trend_regime`

---

## 1. Filosofi Analisis Top-Down Institusional
Analisis teknikal multi-timeframe membagi pasar menjadi 3 lapisan fungsi yang saling terikat secara hierarkis:
1. **Timeframe 1 Jam (1H) — Kompas Tren Makro (Where the Tide Flows):**
   - Berfungsi menentukan arah arus uang besar (*institutional bias*).
   - Menghilangkan jebakan kebisingan (*noise filtering*).
   - Syarat Bullish 1H: Harga berada di atas EMA 50 1H atau EMA 200 1H.
   - Syarat Bearish 1H: Harga berada di bawah EMA 50 1H atau EMA 200 1H.
2. **Timeframe 15 Menit (15m) — Struktur Pasar & Rezim Tren (The Setup Roadmap):**
   - Berfungsi memetakan zona nilai utama, struktur fraktal BOS/CHOCH, penataan EMA (*EMA Stacking*), dan kekuatan tren ADX.
   - Menguji apakah pasar sedang dalam tren sehat (`ADX >= 20.0` dan `EMA20 > EMA50 > EMA200`) atau sedang konsolidasi netral (`bias == Neutral`).
3. **Timeframe 5 Menit (5m) — Pemicu Eksekusi Mikro & Lokasi Diskon (The Precision Trigger):**
   - Berfungsi mencari titik masuk dengan risiko sekecil mungkin (*tight risk entry*).
   - Menunggu harga melakukan koreksi (*pullback*) ke area diskon (di antara EMA 20–50, FVG, atau Order Block), lalu dieksekusi saat muncul konfirmasi candlestick Steve Nison yang ditutup searah.

---

## 2. Matriks Keputusan Berjenjang (The Decision Matrix)

| Bias Makro 1H | Rezim 15m (ADX & EMA) | Sinyal TF 5m | Keputusan Sistem | Alasan & Manajemen Risiko |
| :--- | :--- | :--- | :--- | :--- |
| **Bullish** | **Bullish (ADX $\ge$ 20)** | **Bullish Pullback + Candle Trigger** | **APPROVED BUY** | Keselarasan mutlak 3 timeframe (Grade-A Setup). |
| **Bullish** | **Bullish (ADX $\ge$ 20)** | **Bearish Reversal** | **HARD VETO (WAIT)** | Dilarang counter-trend melawan arah arus uang institusional. |
| **Bearish** | **Bearish (ADX $\ge$ 20)** | **Bearish Pullback + Candle Trigger** | **APPROVED SELL** | Keselarasan mutlak 3 timeframe (Grade-A Setup). |
| **Bearish** | **Bearish (ADX $\ge$ 20)** | **Bullish Reversal** | **HARD VETO (WAIT)** | Dilarang counter-trend / menangkap pisau jatuh (*falling knife*). |
| **Netral / Chop** | **Neutral (ADX < 20)** | **Sinyal Tren (EMA Bounce / Soldiers)** | **HARD VETO (WAIT)** | Pasar choppy tanpa likuiditas terarah; rawan false breakout. |
| **Netral / Chop** | **Neutral** | **Mean Reversion di Batas VWAP $\pm 2\sigma$ + Sweep** | **SELECTIVE PERMIT** | Hanya diizinkan jika memantul tepat di batas deviasi statistik ekstrem. |

---

## 3. Aturan Pelarangan Mutlak (Hard Veto Summary)
1. **Dilarang BUY saat 15m Bearish di bawah EMA 200.**
2. **Dilarang SELL saat 15m Bullish di atas EMA 200.**
3. **Dilarang mengambil posisi tren saat ADX 15m < 20.0.**
4. **Dilarang membuka posisi saat RSI 15m Overbought Ekstrem ($\ge 78.0$) untuk BUY atau Oversold Ekstrem ($\le 22.0$) untuk SELL.**
