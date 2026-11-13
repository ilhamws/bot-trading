# SOP ENSIKLOPEDIA DAN STANDAR OPERASIONAL CANDLESTICK STEVE NISON
> **Dokumen Otoritatif Inti:** Diadopsi langsung dari karya fundamental Steve Nison (*"Japanese Candlestick Charting Techniques"*).
> **Kategori Knowledge Base:** `candlestick_sop`

---

## 1. Prinsip Fundamental Candlestick Jepang (The Steve Nison Axioms)
1. **Prioritas Real Body:** Real body mencerminkan pertempuran sesungguhnya antara pembeli (*bulls*) dan penjual (*bears*). Body hijau/putih panjang menandakan dominasi mutlak pembeli; body merah/hitam panjang menandakan kepanikan dan dominasi penjual.
2. **Fungsi Bayangan (Shadows/Wicks):** Bayangan atas (*upper shadow*) mencerminkan penolakan harga tertinggi (*rejection of high prices*). Bayangan bawah (*lower shadow*) mencerminkan penolakan harga terendah (*rejection of low prices / buying pressure*).
3. **Syarat Mutlak Prior Trend:** Seluruh pola pembalikan arah (*reversal*) WAJIB didahului oleh tren nyata yang terdefinisi. Pola *Bullish Reversal* hanya sah jika terjadi setelah tren turun (*downtrend*); pola *Bearish Reversal* hanya sah jika terjadi setelah tren naik (*uptrend*). Pola yang muncul di tengah konsolidasi datar (*flat sideways*) dianggap tidak valid (*noise*).
4. **Prinsip Konfirmasi Closed Bar:** Dilarang mengambil keputusan trading sebelum batang lilin ditutup sempurna (*confirmed closed bar*).

---

## 2. Katalog Standar Pola 1-Candle (Single-Candle Lines)

### A. Hammer (Palu Bullish Reversal)
* **Konteks:** Wajib muncul di dasar tren turun (*downtrend*) atau area support utama.
* **Ciri Fisik Presisi:**
  - Real body kecil berada di sepertiga teratas dari rentang candle ($\le 35\%$ dari total range).
  - Sumbu bawah panjang minimal $2\times$ panjang real body ($\ge 55\%$ dari total range candle).
  - Sumbu atas sangat pendek atau tidak ada sama sekali ($\le 8\%$ range).
  - Warna body: Lebih diutamakan hijau/bullish, namun jika merah tetap valid asalkan candle berikutnya mengonfirmasi penutupan di atas midpoint candle penekan sebelumnya.

### B. Hanging Man (Gantung Diri - Bearish Reversal)
* **Konteks:** Wajib muncul di puncak tren naik (*uptrend*) atau area resistance utama.
* **Ciri Fisik Presisi:**
  - Candle sebelumnya WAJIB HIJAU SOLID yang mendorong ke puncak (`High2 >= High1`).
  - Real body kecil di bagian atas candle.
  - Sumbu bawah panjang ($\ge 2\times$ body dan $\ge 55\%$ total range).
  - Sumbu atas hampir nihil ($\le 8\%$ range).
  - **Konfirmasi Kritis:** Wajib dikonfirmasi oleh penutupan candle berikutnya yang berwarna merah di bawah real body Hanging Man.

### C. Shooting Star (Bintang Jatuh - Bearish Reversal)
* **Konteks:** Puncak uptrend atau penolakan batas resistensi / Upper Bollinger Band.
* **Ciri Fisik Presisi:**
  - Real body kecil berada di sepertiga terbawah candle ($\le 35\%$ range).
  - Sumbu atas panjang menjulang minimal $2\times$ panjang real body ($\ge 55\%$ total range).
  - Sumbu bawah sangat pendek atau nihil ($\le 8\%$ range).
  - Menandakan pembeli sempat mendorong harga tinggi namun dipukul jatuh oleh gelombang jual institusional hingga tutup dekat titik terendah.

### D. Inverted Hammer (Palu Terbalik - Bullish Reversal)
* **Konteks:** Dasar downtrend atau area support kuat / Lower Bollinger Band.
* **Ciri Fisik Presisi:**
  - Real body kecil berada di sepertiga terbawah candle.
  - Sumbu atas panjang minimal $2\times$ body ($\ge 50\%$ range).
  - Sumbu bawah nihil atau sangat kecil ($\le 5\%$).
  - **Konfirmasi Steve Nison:** Wajib menunggu candle berikutnya ditutup hijau solid menembus di atas body Inverted Hammer.

---

## 3. Katalog Standar Pola 2-Candle (Dual-Candle Lines)

### A. Bullish Engulfing (Menelan Bullish)
* **Struktur:**
  - Candle 1: Candle merah (*bearish*) yang mencerminkan sisa tren turun.
  - Candle 2: Candle hijau (*bullish*) dengan body solid besar yang menelan seluruh real body Candle 1 (`Close2 >= Open1` dan `Open2 <= Close1`).
  - Rasio Body: Panjang body Candle 2 minimal $1.05\times$ hingga $1.5\times$ dari body Candle 1.
* **Area Validasi:** Support struktural, FVG demand, atau Lower Bollinger Band.

### B. Bearish Engulfing (Menelan Bearish)
* **Struktur:**
  - Candle 1: Candle hijau (*bullish*) di puncak pergerakan.
  - Candle 2: Candle merah (*bearish*) dengan body solid besar yang menelan seluruh real body Candle 1 (`Close2 <= Open1` dan `Open2 >= Close1`).
  - Rasio Body: Panjang body Candle 2 minimal $1.05\times$ dari Candle 1.
* **Area Validasi:** Resistance struktural, FVG supply, atau Upper Bollinger Band.

### C. Piercing Line (Jarum Penusuk Bullish)
* **Struktur:**
  - Candle 1: Merah solid panjang pada downtrend.
  - Candle 2: Dibuka gap down di bawah Low Candle 1, kemudian rally kuat hingga ditutup HIJAU MENEMBUS DI ATAS 50% (*midpoint*) body Candle 1.
  - Dilarang menutup di bawah midpoint; jika tutup di bawah 50%, diklasifikasikan sebagai *Incomplete Piercing* / *Counter-Attack Line*.

### D. Dark Cloud Cover (Awan Gelap Bearish)
* **Struktur:**
  - Candle 1: Hijau solid panjang pada uptrend.
  - Candle 2: Dibuka gap up di atas High Candle 1, kemudian terjual deras hingga ditutup MERAH MENEMBUS DI BAWAH 50% (*midpoint*) body Candle 1.
  - Menandakan pembeli gagal mempertahankan momentum dan awan gelap pasokan institusional mulai menenggelamkan harga.

### E. Tweezer Top & Tweezer Bottom (Jepitan Puncak & Jepitan Dasar)
* **Tweezer Top:** Dua candle berturut-turut menguji level resistance dengan titik puncak High yang identik (selisih $\le 1.0$ pip). Candle 1 hijau, candle 2 merah berbalik turun dengan penolakan sumbu atas nyata ($\ge 18\%$) atau momentum merah solid.
* **Tweezer Bottom:** Dua candle berturut-turut menguji level support dengan titik dasar Low yang identik (selisih $\le 1.0$ pip). Candle 1 merah, candle 2 hijau memantul naik dengan penolakan sumbu bawah nyata ($\ge 18\%$) atau momentum hijau solid.

---

## 4. Katalog Standar Pola Multi-Candle & Pola Kelanjutan Tren (Continuation)

### A. Morning Star & Evening Star (Bintang Fajar & Bintang Senja)
* **Morning Star (3-Candle Bullish Reversal):**
  - Bar 1: Candle merah panjang.
  - Bar 2: Candle berbadan kecil (bisa hijau/merah/doji) yang membentuk gap atau menguji titik rendah.
  - Bar 3: Candle hijau solid panjang yang ditutup menembus minimal 50% hingga 70% dari body Bar 1.
* **Evening Star (3-Candle Bearish Reversal):**
  - Bar 1: Candle hijau panjang.
  - Bar 2: Candle berbadan kecil di puncak.
  - Bar 3: Candle merah solid panjang yang ditutup menembus minimal 50% hingga 70% dari body Bar 1.

### B. Three White Soldiers & Three Black Crows
* **Three White Soldiers (Tiga Prajurit Putih):** Tiga candle hijau solid berturut-turut dengan Higher Close, Higher High, dan sumbu atas pendek ($\le 25\%$). Menandakan pergeseran kontrol mutlak ke pembeli.
* **Three Black Crows (Tiga Gagak Hitam):** Tiga candle merah solid berturut-turut dengan Lower Close, Lower Low, dan sumbu bawah pendek ($\le 25\%$). Menandakan kontrol mutlak penjual.

### C. Rising Three Methods & Falling Three Methods (Continuation)
* **Rising Three Methods (Bullish Continuation):**
  - Satu candle hijau panjang, diikuti oleh 2–3 candle kecil korektif yang bertahan di dalam rentang candle hijau pertama, lalu disusul oleh candle hijau besar penutup yang menembus ke level High baru.
* **Falling Three Methods (Bearish Continuation):**
  - Satu candle merah panjang, diikuti oleh 2–3 candle kecil korektif yang bertahan di dalam rentang candle merah pertama, lalu disusul oleh candle merah besar penutup yang menembus ke level Low baru.

---

## 5. Kaidah Penggabungan Candlestick dengan Analisis Teknikal Barat (Western Confluence)
* **Steve Nison Rule of Harmony:** Candlestick Jepang tidak boleh digunakan sendirian tanpa konfirmasi level harga Barat:
  1. Jangan entry BUY hanya karena ada Hammer jika berada di tengah ruang hampa (*no-man's land*); Hammer wajib berpijak di Support, Dynamic EMA 20/50, atau Bullish FVG.
  2. Jangan entry SELL hanya karena ada Shooting Star di tengah tren naik kuat tanpa adanya benturan level Resistance institusional atau Fibonacci Golden Pocket.
  3. Stop Loss logis wajib diletakkan di bawah titik ekstrim Low pola bullish (plus buffer ATR) atau di atas titik ekstrim High pola bearish (plus buffer ATR).
