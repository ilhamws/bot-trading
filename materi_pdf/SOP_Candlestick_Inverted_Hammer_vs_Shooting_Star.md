# SOP STANDAR CANDLESTICK: INVERTED HAMMER VS SHOOTING STAR

## 1. PENGERTIAN & FILOSOFI PSIKOLOGI PASAR

Pola **Inverted Hammer** dan **Shooting Star** adalah dua pola candlestick berkepala sumbu atas (upper shadow) yang memiliki bentuk fisik identik namun berada di posisi tren yang **180 derajat berlawanan**.

### A. INVERTED HAMMER (Pola Bullish Reversal)
1. **Definisi**: Pola candlestick pembalikan arah dari tren turun (bearish) menjadi tren naik (bullish).
2. **Prasyarat Mutlak Tren**:
   - **HANYA BOLEH MUNCUL PADA TREN TURUN (DOWNTREND)**, baik tren turun mayor (di bawah EMA 200/50) maupun tren turun minor (pullback korektif / swing low).
   - Menandakan bahwa setelah tekanan jual (bearish), pembeli (buyers) mulai masuk secara agresif mencoba mendorong harga naik. Meskipun seller sempat menekan kembali di akhir sesi, dominasi seller telah habis dan pembeli bersiap mengambil alih arah tren.
3. **Ciri Anatomi Fisik Mutlak**:
   - **Sumbu Panjang di Atas Body (Upper Shadow)**: Panjang sumbu atas minimal 2x panjang body candle (upper_shadow >= 1.5 - 2.5 * body_size).
   - **DI BAWAH BODY TIDAK BOLEH ADA GARIS / SHADOW (Lower Shadow = 0)**: Syarat mutlak Inverted Hammer adalah tidak memiliki ekor bawah (atau sangat kecil / negligible <= spread tolerance). Jika terdapat ekor/garis di bawah body, pola tersebut BUKAN Inverted Hammer.
   - **Posisi Body**: Body kecil berada di bagian paling dasar / bawah rentang candle. Body dapat berwarna hijau (bullish close) ataupun merah (bearish close), namun body hijau memberikan konfirmasi kekuatan buyer yang lebih superior.
4. **Keputusan Trading**:
   - Menjadi basis sinyal **BUY**.
   - DILARANG KERAS mengambil keputusan BUY dengan alasan Inverted Hammer jika pasar sedang dalam tren naik (Uptrend), karena bentuk candle tersebut pada tren naik adalah Shooting Star (sinyal SELL).
   - Konfluensi pendukung: Berada di area Support / Lower Bollinger Band, RSI Oversold / Netral Bawah (< 50), atau MACD Golden Cross.

---

### B. SHOOTING STAR (Pola Bearish Reversal)
1. **Definisi**: Pola candlestick pembalikan arah dari tren naik (bullish) menjadi tren turun (bearish).
2. **Prasyarat Mutlak Tren**:
   - **HANYA BOLEH MUNCUL PADA TREN NAIK (UPTREND)**, baik tren naik mayor (di atas EMA 200/50) maupun tren naik minor (rally / swing high).
   - Menandakan perlawanan arah menjadi downtrend akibat penolakan keras harga atas (strong high price rejection). Seller menekan harga turun secara masif dari titik tertingginya hingga menutup candle mendekati harga terendah.
3. **Ciri Anatomi Fisik Mutlak**:
   - **Sumbu Panjang di Atas Body (Upper Shadow)**: Panjang sumbu atas minimal 2x panjang body candle (upper_shadow >= 1.5 - 2.5 * body_size).
   - **DI BAWAH BODY TIDAK BOLEH ADA GARIS / SHADOW (Lower Shadow = 0)**: Syarat mutlak Shooting Star adalah tidak memiliki ekor bawah (atau sangat kecil / negligible <= spread tolerance). Jika terdapat ekor/garis di bawah body, pola tersebut BUKAN Shooting Star.
   - **Posisi Body**: Body kecil berada di bagian paling dasar / bawah rentang candle. Body berwarna merah (bearish close) memberikan konfirmasi tekanan seller yang paling dominan.
4. **Keputusan Trading**:
   - Menjadi basis sinyal **SELL**.
   - DILARANG KERAS menganggapnya sebagai Inverted Hammer jika muncul saat tren naik.
   - Konfluensi pendukung: Berada di area Resistance / Upper Bollinger Band, RSI Overbought / Netral Atas (> 50), atau MACD Death Cross.

---

## 2. ATURAN INTEGRITAS DAN VALIDASI SISTEM AI (ANTI-SALAH KEPUTUSAN)

1. **Uji Keberadaan Ekor Bawah (No Lower Wick Rule)**:
   - Jika sebuah candle memiliki bayangan/garis bawah yang nyata (lower shadow > 5% dari range candle), maka pola tersebut dinyatakan **TIDAK VALID** sebagai Inverted Hammer maupun Shooting Star.
2. **Uji Konteks Tren (Trend Direction Filter)**:
   - Candle sumbu atas tanpa ekor bawah pada **Downtrend** = **Inverted Hammer** (Peluang BUY Reversal).
   - Candle sumbu atas tanpa ekor bawah pada **Uptrend** = **Shooting Star** (Peluang SELL Reversal).
3. **Penyaringan False Signal pada Terminal**:
   - Jika terminal atau scanner mendeteksi 'Inverted Hammer' namun tren minor/mayor sedang naik atau RSI berada di atas 55.0 (kondisi dorongan naik), Model AI WAJIB menolak sinyal tersebut dan menetapkan keputusan **WAIT**, dengan catatan teknis: "Pola Inverted Hammer tidak valid karena muncul pada tren naik / terdapat garis di bawah body (bentuk ini terindikasi Shooting Star atau penolakan harga atas, dilarang BUY)".
