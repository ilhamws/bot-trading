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

## 4. ATURAN TRAILING STOP & BREAKEVEN (BEP)
1. **Proteksi Breakeven:**
   - Ketika harga telah bergerak mencapai keuntungan sebesar $1.0 \times \text{Risk Distance}$ (R:R 1:1), Stop Loss **WAJIB DIGESER** ke titik Entry Price + 1 pip (Breakeven Point).
   - Menjamin bahwa trade yang sudah berjalan dengan benar tidak boleh berakhir menjadi kerugian modal.
2. **Trailing Stop Berbasis Struktur:**
   - Geser Stop Loss mengikuti pembentukan Higher Low baru (pada posisi BUY) atau Lower High baru (pada posisi SELL) setiap kali terjadi Break of Structure (BOS).
