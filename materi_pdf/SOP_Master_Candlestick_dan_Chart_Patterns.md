# PANDUAN MASTER SOP CANDLESTICK & CHART PATTERNS (STANDAR ZERO-HALLUCINATION)

## 1. ATURAN KRITIS: PEMBEDAAN FORMASI 1-CANDLE VS 2-CANDLE (ANTI-SALAH IDENTIFIKASI)

### A. KESALAHAN UMUM ANALISIS: MEMBACA 1 CANDLE VS 2 CANDLE
Kesalahan paling sering terjadi adalah **salah mengenali Bullish Engulfing menjadi Inverted Hammer** (atau Bearish Engulfing menjadi Shooting Star).
- **Penyebab**: Analis atau algoritma hanya fokus pada bentuk candle tunggal (single candle) yang memiliki sumbu atas (upper shadow), tanpa memeriksa hubungan antara candle saat ini dengan candle sebelumnya (multi-candle relationship).
- **Aturan Mutlak**:
  1. **Inverted Hammer** adalah pola **SATU CANDLE (Single Candle Pattern)**:
     - Memiliki **body kecil di bagian dasar** ($body \le 35\%$ dari total range candle).
     - Sumbu atas panjang minimal $2\times$ panjang body.
     - Di bawah body **TIDAK BOLEH ADA GARIS / SHADOW** ($lower\_shadow \approx 0$).
     - **TIDAK MENELAN** body candle sebelumnya ($body\_size < prior\_body$ atau $close < prior\_open$).
  2. **Bullish Engulfing** adalah pola **DUA CANDLE (Two Candle Pattern)**:
     - Candle 1 (sebelumnya): Candle MERAH (bearish) pada tren turun.
     - Candle 2 (saat ini): Candle HIJAU (bullish) dengan **BODY SOLID/BESAR** ($body \ge 45\%$ dari range).
     - **SYARAT MENELAN (ENGULFING)**: Body candle 2 **WAJIB MENELAN SELURUH BODY** candle 1 ($close_2 \ge open_1$ dan $open_2 \le close_1$, serta $body_2 \ge 1.0 \times body_1$).
     - Meskipun candle 2 memiliki sumbu atas wajar akibat fluktuasi harga, selama body-nya menelan candle 1, pola tersebut **100% ADALAH BULLISH ENGULFING, BUKAN INVERTED HAMMER!**
     - DILARANG KERAS melabeli formasi dua candle yang menelan sebagai Inverted Hammer!

---

## 2. DETAIL ATURAN POLA CANDLESTICK GRADE-A (>70% AKURASI)

### [A] POLA PEMBALIKAN BULLISH (BULLISH REVERSAL - BUY)

1. **Bullish Engulfing (Pola 2-Candle)**:
   - **Konteks Tren**: Wajib muncul di akhir Downtrend (area support / lower band / oversold).
   - **Candle 1**: Bearish merah ($close_1 < open_1$).
   - **Candle 2**: Bullish hijau ($close_2 > open_2$).
   - **Syarat Body**: $open_2 \le close_1 + spread$, $close_2 \ge open_1 - spread$, dan $body_2 \ge body_1 \times 1.0$.
   - **Karakteristik**: Body candle 2 solid ($\ge 45\%$ rentang candle).
   - **Sinyal**: Sangat kuat untuk BUY.

2. **Inverted Hammer (Pola 1-Candle Pin Bar Reversal)**:
   - **Konteks Tren**: Wajib muncul di akhir Downtrend.
   - **Bentuk Fisik**: Sumbu atas panjang ($\ge 2\times$ body dan $\ge 50\%$ range candle).
   - **Ekor Bawah**: DI BAWAH BODY TIDAK BOLEH ADA GARIS ($lower\_shadow \le spread$ atau $\le 3\%$ range).
   - **Syarat Mutlak**: Body kecil ($\le 35\%$ range) dan BUKAN pola Bullish Engulfing.
   - **Sinyal**: BUY Reversal saat tren turun. DILARANG BUY jika muncul di tren naik (karena itu Shooting Star).

3. **Hammer (Pola 1-Candle Pin Bar Reversal)**:
   - **Konteks Tren**: Wajib muncul di akhir Downtrend dan area Support.
   - **Bentuk Fisik**: Sumbu bawah panjang minimal $2.0\times$ panjang body (dan $\ge 50\%$ range candle).
   - **Ekor Atas**: DI ATAS BODY TIDAK BOLEH ADA GARIS / SHADOW ($upper\_shadow \le spread$ atau $\le 3\%$ range candle).
   - **Syarat Mutlak**: Body kecil berada di puncak atas candle ($\le 35\%$ range candle), rentang candle signifikan ($\ge 3.5$ pips, bukan noise), dan BUKAN pola Bullish Engulfing.
   - **Sinyal**: BUY Reversal.

4. **Piercing Line (Pola 2-Candle)**:
   - **Konteks Tren**: Downtrend.
   - **Candle 1**: Bearish merah solid.
   - **Candle 2**: Bullish hijau yang dibuka lebih rendah dari close candle 1 ($open_2 \le close_1$), lalu ditutup di atas titik tengah body candle 1 ($close_2 \ge (open_1 + close_1) / 2$), namun BELUM menelan open candle 1 ($close_2 < open_1$).
   - **Sinyal**: BUY Reversal (~72% akurasi).

5. **Morning Star (Pola 3-Candle Reversal)**:
   - **Konteks Tren**: Downtrend.
   - **Candle 1**: Bearish merah besar.
   - **Candle 2**: Star / body kecil (bisa doji, hammer, atau spinning top) di area swing low ($body_2 \le 0.35 \times body_1$).
   - **Candle 3**: Bullish hijau besar yang ditutup menembus minimal 50% body candle 1 ($close_3 \ge (open_1 + close_1) / 2$).
   - **Sinyal**: BUY Reversal Grade-A (~75% akurasi).

6. **Tweezer Bottom (Pola 2-Candle)**:
   - **Konteks Tren**: Downtrend di area Support.
   - **Candle 1**: Bearish merah.
   - **Candle 2**: Bullish hijau.
   - **Syarat Mutlak**: Memiliki titik terendah (Low) yang hampir identik ($|low_2 - low_1| \le 15\%$ range), kedua candle memiliki rentang valid ($\ge 3.5$ pips), dan ukuran proporsional ($range_2 \ge 50\% \times range_1$).
   - **Sinyal**: BUY Reversal.

7. **Three White Soldiers (Pola 3-Candle)**:
   - **Konteks Tren**: Pembalikan awal dari Downtrend atau breakout support.
   - **Syarat**: 3 candle hijau berturut-turut ($close > open$), masing-masing membuat Higher High dan Higher Close, dengan sumbu atas yang pendek ($\le 20\%$ range).
   - **Sinyal**: BUY Strong Momentum.

8. **Bullish Kicker (Pola 2-Candle Eksplosif)**:
   - **Candle 1**: Bearish merah.
   - **Candle 2**: Gap up pembukaan di atas atau sejajar open candle 1, lalu melonjak naik tajam tanpa tumpang tindih body.
   - **Sinyal**: BUY Reversal Sangat Kuat (~78% akurasi).

9. **Three Inside Up (Pola 3-Candle - Confirmed Harami)**:
   - **Candle 1**: Bearish merah besar.
   - **Candle 2**: Bullish kecil di dalam tubuh candle 1 (Bullish Harami).
   - **Candle 3**: Bullish hijau konfirmasi yang ditutup di atas harga tertinggi candle 1 ($close_3 > open_1$).
   - **Sinyal**: BUY Reversal Terkonfirmasi.

10. **Bullish Abandoned Baby (Pola 3-Candle)**:
    - Candle 1 Bearish, Candle 2 Doji dengan gap ke bawah, Candle 3 Bullish dengan gap ke atas.
    - **Sinyal**: BUY Reversal (~78% akurasi).

11. **Rising Three Methods (Pola 5-Candle - Bullish Continuation)**:
    - Candle 1 Bullish besar, Candle 2-3-4 tiga candle koreksi kecil di dalam range candle 1, Candle 5 Bullish besar yang breakout di atas high candle 1.
    - **Sinyal**: BUY Kelanjutan Tren Naik.

---

### [B] POLA PEMBALIKAN BEARISH (BEARISH REVERSAL - SELL)

1. **Bearish Engulfing (Pola 2-Candle)**:
   - **Konteks Tren**: Wajib muncul di akhir Uptrend (area resistance / upper band / overbought).
   - **Candle 1**: Bullish hijau ($close_1 > open_1$).
   - **Candle 2**: Bearish merah ($close_2 < open_2$).
   - **Syarat Body**: $open_2 \ge close_1 - spread$, $close_2 \le open_1 + spread$, dan $body_2 \ge body_1 \times 1.0$.
   - **Karakteristik**: Body candle 2 solid ($\ge 45\%$ rentang candle).
   - **Pembeda dari Shooting Star**: Jika body menelan candle sebelumnya, pola tersebut adalah Bearish Engulfing, BUKAN Shooting Star!
   - **Sinyal**: Sangat kuat untuk SELL.

2. **Shooting Star (Pola 1-Candle Pin Bar Reversal)**:
   - **Konteks Tren**: Wajib muncul di akhir Uptrend.
   - **Bentuk Fisik**: Sumbu atas panjang ($\ge 2\times$ body dan $\ge 50\%$ range candle).
   - **Ekor Bawah**: DI BAWAH BODY TIDAK BOLEH ADA GARIS ($lower\_shadow \le spread$ atau $\le 3\%$ range).
   - **Syarat Mutlak**: Body kecil berada di dasar candle ($\le 35\%$ range) dan BUKAN pola Bearish Engulfing.
   - **Sinyal**: SELL Reversal saat tren naik. DILARANG SELL jika muncul di tren turun (karena itu Inverted Hammer).

3. **Hanging Man (Pola 1-Candle Pin Bar Reversal)**:
   - **Konteks Tren**: Wajib muncul di puncak Uptrend dan area Resistance.
   - **Bentuk Fisik**: Sumbu bawah panjang ($\ge 2.0\times$ body dan $\ge 50\%$ range candle).
   - **Ekor Atas**: DI ATAS BODY TIDAK BOLEH ADA GARIS / SHADOW ($upper\_shadow \le spread$ atau $\le 3\%$ range candle).
   - **Syarat Mutlak**: Body kecil berada di puncak atas candle ($\le 35\%$ range candle), rentang candle signifikan ($\ge 3.5$ pips), dan BUKAN pola Bearish Engulfing.
   - **Sinyal**: SELL Reversal (sinyal pelemahan momentum buyer).

4. **Dark Cloud Cover (Pola 2-Candle)**:
   - **Konteks Tren**: Uptrend.
   - **Candle 1**: Bullish hijau solid.
   - **Candle 2**: Bearish merah yang dibuka lebih tinggi dari close candle 1 ($open_2 \ge close_1$), lalu ditutup menembus minimal 50% body candle 1 ($close_2 \le (open_1 + close_1) / 2$), namun BELUM menelan open candle 1 ($close_2 > open_1$).
   - **Sinyal**: SELL Reversal (~72% akurasi).

5. **Evening Star (Pola 3-Candle Reversal)**:
   - **Konteks Tren**: Uptrend.
   - **Candle 1**: Bullish hijau besar.
   - **Candle 2**: Star / body kecil di area swing high ($body_2 \le 0.35 \times body_1$).
   - **Candle 3**: Bearish merah besar yang ditutup menembus minimal 50% body candle 1 ($close_3 \le (open_1 + close_1) / 2$).
   - **Sinyal**: SELL Reversal Grade-A (~75% akurasi).

6. **Tweezer Top (Pola 2-Candle)**:
   - **Konteks Tren**: Uptrend di area Resistance.
   - **Candle 1**: Bullish hijau.
   - **Candle 2**: Bearish merah.
   - **Syarat Mutlak**: Memiliki titik tertinggi (High) yang hampir identik ($|high_2 - high_1| \le 15\%$ range), kedua candle memiliki rentang valid ($\ge 3.5$ pips), dan ukuran proporsional ($range_2 \ge 50\% \times range_1$).
   - **Sinyal**: SELL Reversal.

7. **Three Black Crows (Pola 3-Candle)**:
   - **Konteks Tren**: Pembalikan awal dari Uptrend atau penolakan resistance.
   - **Syarat**: 3 candle merah berturut-turut ($close < open$), masing-masing membuat Lower Low dan Lower Close, dengan sumbu bawah yang pendek ($\le 20\%$ range).
   - **Sinyal**: SELL Strong Momentum.

8. **Bearish Kicker (Pola 2-Candle Eksplosif)**:
   - **Candle 1**: Bullish hijau.
   - **Candle 2**: Gap down pembukaan di bawah atau sejajar open candle 1, lalu meluncur turun tajam tanpa tumpang tindih body.
   - **Sinyal**: SELL Reversal Sangat Kuat (~78% akurasi).

9. **Three Inside Down (Pola 3-Candle - Confirmed Bearish Harami)**:
   - **Candle 1**: Bullish hijau besar.
   - **Candle 2**: Bearish kecil di dalam tubuh candle 1 (Bearish Harami).
   - **Candle 3**: Bearish merah konfirmasi yang ditutup di bawah harga terendah candle 1 ($close_3 < open_1$).
   - **Sinyal**: SELL Reversal Terkonfirmasi.

10. **Bearish Abandoned Baby (Pola 3-Candle)**:
    - Candle 1 Bullish, Candle 2 Doji gap up, Candle 3 Bearish gap down.
    - **Sinyal**: SELL Reversal (~78% akurasi).

11. **Falling Three Methods (Pola 5-Candle - Bearish Continuation)**:
    - Candle 1 Bearish besar, Candle 2-3-4 tiga candle koreksi naik kecil di dalam range candle 1, Candle 5 Bearish besar yang breakout di bawah low candle 1.
    - **Sinyal**: SELL Kelanjutan Tren Turun.

---

## 3. PANDUAN CHART PATTERNS KLASIK (STRUKTURAL MULTI-BAR)

1. **Double Bottom (Pola Huruf "W" - Bullish Reversal)**:
   - Terbentuk di akhir downtrend ketika harga menguji level support yang sama dua kali (Trough 1 dan Trough 2) dan gagal menembus ke bawah.
   - Konfirmasi: Penembusan (breakout) di atas garis leher (Neckline).
   - Aksi: BUY saat breakout atau retest neckline.

2. **Double Top (Pola Huruf "M" - Bearish Reversal)**:
   - Terbentuk di akhir uptrend ketika harga menguji level resistansi yang sama dua kali (Peak 1 dan Peak 2) dan gagal menembus ke atas.
   - Konfirmasi: Penembusan (breakdown) di bawah garis leher (Neckline).
   - Aksi: SELL saat breakdown atau retest neckline.

3. **Head and Shoulders (H&S - Bearish Reversal)**:
   - Terdiri dari Left Shoulder, Head (puncak tertinggi), dan Right Shoulder yang lebih rendah dari Head.
   - Konfirmasi: Penembusan garis leher (Neckline) ke bawah.
   - Aksi: SELL.

4. **Inverse Head and Shoulders (iH&S - Bullish Reversal)**:
   - Terdiri dari Left Shoulder bawah, Head (lembah terendah), dan Right Shoulder bawah yang lebih dangkal.
   - Konfirmasi: Penembusan garis leher (Neckline) ke atas.
   - Aksi: BUY.

5. **Bullish & Bearish Flag / Pennant (Continuation)**:
   - Flag: Pola tiang (flagpole) impulsif diikuti saluran koreksi sejajar berlawanan arah tren, lalu breakout melanjutkan arah tren utama.

---

## 4. ATURAN HIERARKI KEPUTUSAN AI (ZERO-HALLUCINATION DECISION TREE)

1. **Prioritaskan Multi-Candle di Atas Single-Candle**:
   - Jika sebuah candle memenuhi syarat Bullish Engulfing (menelan candle merah sebelumnya), AI **WAJIB MENETAPKAN SEBAGAI BULLISH ENGULFING**. Dilarang menurunkannya menjadi Inverted Hammer.
   - Jika sebuah candle memenuhi syarat Bearish Engulfing (menelan candle hijau sebelumnya), AI **WAJIB MENETAPKAN SEBAGAI BEARISH ENGULFING**. Dilarang menurunkannya menjadi Shooting Star.
2. **Evaluasi Rentang Waktu, Arah Swing, dan Zona Support/Resistance**:
   - **Sinyal Bullish Reversal (BUY)** HANYA diakui jika:
     a. Terjadi di **Zona Support** (Bollinger Band Lower zone atau menguji swing low 3-5 bar terakhir).
     b. Didahului oleh penurunan harga riil (swing drop / bearish progression).
     c. **DILARANG KERAS** melabeli Bullish Engulfing, Tweezer Bottom, Hammer, atau Inverted Hammer jika harga sedang berada di tengah **Rally / Minor Uptrend** (misalnya harga sudah naik 3 bar berturut-turut dengan higher lows dan higher closes mendekati EMA 20 / Middle Band). Candle hijau di puncak rally adalah kelanjutan atau bull trap, BUKAN pembalikan bottom!
   - **Sinyal Bearish Reversal (SELL)** HANYA diakui jika:
     a. Terjadi di **Zona Resistance** (Bollinger Band Upper zone atau menguji swing high 3-5 bar terakhir).
     b. Didahului oleh kenaikan harga riil (swing rally / bullish progression).
     c. **DILARANG KERAS** melabeli Bearish Engulfing, Tweezer Top, Shooting Star, atau Hanging Man jika harga sedang berada di tengah **Sell-off / Minor Downtrend** (misalnya harga sedang anjlok membuat lower highs dan lower closes). Candle merah di lembah penurunan adalah kelanjutan atau bear trap, BUKAN pembalikan top!

