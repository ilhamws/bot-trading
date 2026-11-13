# SOP MANAJEMEN RISIKO KUANTITATIF & VOLATILITAS DINAMIS (ATR)

## 1. PENDAHULUAN & FILOSOFI RISIKO
Pasar keuangan bergerak dengan volatilitas dinamis yang berubah setiap saat. Menggunakan nilai Stop Loss (SL) dan Take Profit (TP) dengan pips statis/kaku adalah penyebab utama kekalahan akun trading (sering terkena stop-out prematur saat volatilitas tinggi atau target tidak tercapai saat pasar sepi). Manajemen risiko profesional wajib menggunakan **Average True Range (ATR)**.

---

## 2. FORMULA STOP LOSS & TAKE PROFIT BERBASIS ATR (14)
1. **Perhitungan ATR:**
   - Gunakan indikator ATR dengan periode standar 14 pada timeframe trading aktif.
   - True Range (TR) = $\max(\text{High} - \text{Low}, |\text{High} - \text{Close}_{\text{prev}}|, |\text{Low} - \text{Close}_{\text{prev}}|)$
   - $\text{ATR}_{14} = \text{SMA}(TR, 14)$ atau $\text{EMA}(TR, 14)$.
2. **Kalkulasi Stop Loss Dinamis:**
   - **Posisi BUY:** $\text{SL} = \text{Entry Price} - (1.5 \times \text{ATR}_{14})$ (diletakkan di bawah Swing Low / batas bawah zona FVG).
   - **Posisi SELL:** $\text{SL} = \text{Entry Price} + (1.5 \times \text{ATR}_{14})$ (diletakkan di atas Swing High / batas atas zona FVG).
3. **Kalkulasi Take Profit Dinamis (Rasio Risk:Reward):**
   - Syarat mutlak rasio Risk-to-Reward (R:R) adalah minimal **1 : 1.5** hingga **1 : 2.5**.
   - **TP 1 (Target Konservatif / Amankan Profit Sebagian):** $1.5 \times \text{Risk Distance}$ (R:R 1:1.5).
   - **TP 2 (Target Likuiditas Utama):** $2.0 \times \text{Risk Distance}$ (R:R 1:2.0) atau level Swing High/Low berseberangan berikutnya.

---

## 3. ATURAN TOLERANSI SPREAD & BIAYA TRANSAKSI
1. **Rasio Spread terhadap Volatilitas:**
   - Broker spread wajib diukur secara real-time sebelum order dikirim.
   - Batas Maksimum: $\text{Spread} \le 0.25 \times \text{ATR}_{14}$.
   - Jika spread melebar melebihi 25% dari nilai ATR (misalnya saat pergantian sesi pasar / rollover jam 05:00 WIB), sistem **DILARANG ENTRY** (Action: WAIT).

---

## 4. ATURAN STEPPED TRAILING STOP & BREAKEVEN BERBASIS R-MULTIPLE

Untuk mencegah Stop Loss tersenggol terlalu cepat oleh noise pasar namun tetap mengamankan profit mengembang secara sistematis, proteksi Stop Loss dijalankan melalui **Stepped Trailing Stop Berbasis R-Multiple** ($1\text{R} = |\text{Entry Price} - \text{Initial SL}|$):

1. **Tier 1 — Proteksi Breakeven (+0.85R Floating):**
   - Ketika *floating profit* mencapai $\ge +0.85\text{R}$ (misal +5.1 pips pada SL 6.0 pips di EURUSD, atau +29.8 pips di Gold):
   - Stop Loss otomatis digeser ke **Entry $+0.15\text{R}$**.
   - Posisi resmi bebas risiko (*risk-free*) dan biaya spread/komisi terkunci aman.
2. **Tier 2 — Kunci Profit Menengah (+1.15R Floating):**
   - Ketika *floating profit* mencapai $\ge +1.15\text{R}$:
   - Stop Loss otomatis digeser ke **Entry $+0.60\text{R}$**.
   - Mengunci lebih dari separuh target keuntungan saat harga mendekati TP penuh.
3. **Tier 3 — Kunci Runner Ekspansi Tren (+1.35R Floating):**
   - Ketika *floating profit* mencapai $\ge +1.35\text{R}$:
   - Stop Loss otomatis digeser ke **Entry $+1.00\text{R}$**.
   - Menjamin perolehan profit minimal 1R penuh saat harga bersiap menyentuh Take Profit akhir 1.5R.
