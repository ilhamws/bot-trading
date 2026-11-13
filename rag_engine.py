"""RAG Retrieval and Strict AI Trading Decision Engine."""

from typing import List, Dict, Any, Optional, Literal
from pathlib import Path
import json
import time
import re
from pydantic import BaseModel, Field
import chromadb
from chromadb.utils import embedding_functions

from config import settings, logger

# Initialize Google GenAI client if package is available
try:
    from google import genai
    from google.genai import types
    GENAI_AVAILABLE = True
except ImportError:
    GENAI_AVAILABLE = False


def sanitize_telegram_markdown(text: str) -> str:
    """Sanitize arbitrary AI technical analysis text for Telegram Markdown v1."""
    if not text:
        return ""
    # 1. Convert standard Markdown bold **text** to Telegram v1 *text*
    text = re.sub(r"\*\*(.+?)\*\*", r"*\1*", text)
    # 2. Convert bullet points starting with * or - to unicode bullet •
    lines = []
    for line in text.split("\n"):
        clean_line = re.sub(r"^\s*[\*\-]\s+", "• ", line)
        lines.append(clean_line)
    text = "\n".join(lines)
    # 3. Replace snake_case underscores in words with space to prevent accidental italic spans
    text = text.replace("_", " ")
    # 4. Replace raw [ and ] brackets with parentheses to prevent Telegram from expecting [text](url) links
    text = text.replace("[", "(").replace("]", ")")
    # 5. Balance asterisks *
    if text.count("*") % 2 != 0:
        idx = text.rfind("*")
        text = text[:idx] + text[idx+1:]
    # 6. Balance backticks `
    if text.count("`") % 2 != 0:
        idx = text.rfind("`")
        text = text[:idx] + text[idx+1:]
    return text.strip()


class TradingSignalDecision(BaseModel):
    """Structured trading decision output strictly validated against SOP."""

    instrument: str = Field(description="Trading pair / asset symbol, e.g. EURUSD, XAUUSD, BBCA.JK")
    timeframe: str = Field(description="Chart timeframe, e.g. 5m, 15m, 1h, 4h, 1D")
    action: Literal["BUY", "SELL", "WAIT"] = Field(
        description="Strict trading action. If conditions are ambiguous or SOP is not met, MUST be WAIT"
    )
    current_price: str = Field(
        default="N/A", description="Current live market price from payload, e.g. '1.13207' or 'N/A'"
    )
    entry_zone: str = Field(description="Calculated entry price or price range, or 'N/A' if WAIT")
    stop_loss: str = Field(description="Calculated Stop Loss price, or 'N/A' if WAIT")
    take_profit: str = Field(description="Calculated Take Profit target price, or 'N/A' if WAIT")
    risk_reward_ratio: str = Field(description="Calculated R:R, e.g. '1:2.0' or 'N/A' if WAIT")
    sop_reference: str = Field(
        description="Exact book title and page cited from retrieved SOP context, e.g. 'Steve-Nison... p.45'"
    )
    technical_breakdown: str = Field(
        description="Detailed technical explanation strictly in Indonesian (Bahasa Indonesia) based on retrieved SOP rules."
    )
    confidence_score: float = Field(
        default=0.0,
        ge=0.0,
        le=1.0,
        description="Confidence level between 0.0 and 1.0 based on rule alignment"
    )
    pattern_name: Optional[str] = Field(
        default="", description="Pola dan jumlah konfluensi lengkap dari scanner teknikal"
    )
    indicator_status: Optional[str] = Field(
        default="", description="Ringkasan indikator live scanner"
    )
    notes_detail: Optional[str] = Field(
        default="", description="Detail OHLC dan level teknikal"
    )
    bar_timestamp: Optional[str] = Field(
        default="", description="Timestamp bar candle tertutup"
    )

    def to_telegram_markdown(self) -> str:
        """Format signal into visually appealing, clean, professional, and detailed Markdown for Telegram."""
        if self.action == "BUY":
            action_badge = "🟢 *TINDAKAN: BUY (BELI KUAT)*"
            direction = "BULLISH 📈"
        elif self.action == "SELL":
            action_badge = "🔴 *TINDAKAN: SELL (JUAL KUAT)*"
            direction = "BEARISH 📉"
        else:
            action_badge = "🟡 *TINDAKAN: WAIT (TUNGGU / NETRAL)*"
            direction = "WAIT ⏳"

        lines = [
            "⚡ *SINYAL TRADING AI* ⚡",
            "═" * 32,
            f"📊 *Instrumen:* `{self.instrument.upper()}` | ⏱️ *Timeframe:* `{self.timeframe}`",
            f"🎯 {action_badge}",
            "─" * 32,
        ]

        if "Counter-Trend" in (self.pattern_name or "") or "Counter-Trend" in (self.indicator_status or ""):
            lines.extend([
                "⚠️ *PERINGATAN RISIKO TINGGI: SINYAL COUNTER-TREND*",
                "• *Catatan:* Sinyal ini melawan arah tren mayor 15m. Disiplin SL ketat!",
                "─" * 32,
            ])

        if self.action in ("BUY", "SELL"):
            if self.current_price and self.current_price != "N/A":
                lines.append(f"💵 *Harga Pasar Saat Ini:* `{self.current_price}`")
            lines.extend([
                f"📍 *Zona Entry:* `{self.entry_zone}`",
                f"🛑 *Stop Loss (SL):* `{self.stop_loss}`",
                f"🎯 *Take Profit (TP):* `{self.take_profit}`",
                f"⚖️ *Rasio Risk/Reward:* `{self.risk_reward_ratio}`",
                f"📈 *Tingkat Keyakinan:* `{int(self.confidence_score * 100)}%` ({direction})",
            ])
        else:
            lines.extend([
                "⚠️ *Status:* Kondisi teknikal pasar saat ini belum memenuhi kriteria SOP secara ketat.",
                "💡 *Rekomendasi:* Pertahankan modal (capital preservation). Tunggu sinyal konfirmasi valid.",
            ])

        # Ekstraksi dan tampilkan SEMUA pola candlestick dan konfluensi secara lengkap
        patterns_to_display = []
        confluence_to_display = []

        raw_pattern = self.pattern_name or ""
        if ":" in raw_pattern and ")" in raw_pattern:
            items_str = raw_pattern.split(":", 1)[1].rstrip(")")
            all_items = [it.strip() for it in items_str.split(",") if it.strip()]
            CANDLE_PATTERNS = {
                "Bullish Engulfing", "Bearish Engulfing", "Hammer", "Inverted Hammer",
                "Shooting Star", "Hanging Man", "Morning Star", "Evening Star",
                "Piercing Line", "Dark Cloud Cover", "Tweezer Bottom", "Tweezer Top",
                "Bullish Harami", "Bearish Harami",
                "Three White Soldiers", "Three Black Crows", "Bullish Kicker",
                "Bearish Kicker", "Three Inside Up", "Three Inside Down",
                "Bullish Abandoned Baby", "Bearish Abandoned Baby",
                "Rising Three Methods", "Falling Three Methods", "Double Bottom (W-Pattern)",
                "Double Top (M-Pattern)"
            }
            for it in all_items:
                if it in CANDLE_PATTERNS:
                    patterns_to_display.append(it)
                else:
                    confluence_to_display.append(it)
        elif raw_pattern:
            patterns_to_display.append(raw_pattern)

        lines.append("─" * 32)
        if patterns_to_display:
            lines.append("🕯️ *Pola Candlestick Terdeteksi:*")
            for p in patterns_to_display:
                lines.append(f"  • *{p}*")
            lines.append("")

        if self.indicator_status or confluence_to_display or self.pattern_name:
            lines.append("🧩 *Detail Konfluensi & Indikator Pasar:*")
            if self.pattern_name:
                clean_pname = self.pattern_name.replace("`", "")
                lines.append(f"  • *Setup Scanner:* `{clean_pname}`")
            if confluence_to_display:
                confl_text = ", ".join(confluence_to_display).replace("`", "")
                lines.append(f"  • *Area Rejeksi:* `{confl_text}`")

            if self.indicator_status:
                parts = [p.strip() for p in self.indicator_status.split("|")]
                for part in parts:
                    clean_part = part.replace("`", "")
                    if part.startswith("RSI:"):
                        lines.append(f"  • *RSI (14):* `{clean_part.replace('RSI:', '').strip()}`")
                    elif part.startswith("MACD:"):
                        lines.append(f"  • *MACD (12,26,9):* `{clean_part.replace('MACD:', '').strip()}`")
                    elif part.startswith("Tren:"):
                        lines.append(f"  • *Tren:* `{clean_part.replace('Tren:', '').strip()}`")
                    elif part.startswith("BB Upper:"):
                        lines.append(f"  • *Bollinger Bands:* `{clean_part.strip()}`")
                    elif part.startswith("ATR(14):"):
                        lines.append(f"  • *Volatilitas ATR(14):* `{clean_part.replace('ATR(14):', '').strip()}`")
                    elif part.startswith("Sesi:"):
                        lines.append(f"  • *ICT Killzone:* `{clean_part.replace('Sesi:', '').strip()}`")
                    elif part.startswith("AdvTech:"):
                        lines.append(f"  • *5 Pilar Teknikal:* `{clean_part.replace('AdvTech:', '').strip()}`")
                    elif "MTF" in part or "Konfluensi" in part:
                        lines.append(f"  • *Multi-Timeframe:* `{clean_part.strip()}`")
                    elif part.startswith("Target:"):
                        lines.append(f"  • *Target SL/TP SOP:* `{clean_part.replace('Target:', '').strip()}`")

            if self.bar_timestamp:
                clean_ts = self.bar_timestamp.replace("`", "")
                lines.append(f"  • *Bar Selesai (Confirmed):* `{clean_ts}`")

            if self.notes_detail:
                ohlc_parts = [n.strip() for n in self.notes_detail.split(",") if any(n.strip().startswith(x) for x in ("Open:", "High:", "Low:", "Close:"))]
                if ohlc_parts:
                    ohlc_joined = " | ".join(ohlc_parts).replace("`", "")
                    lines.append(f"  • *Data Candle (OHLC):* `{ohlc_joined}`")
            lines.append("")

        clean_sop = (self.sop_reference or "N/A").replace("`", "")
        clean_breakdown = sanitize_telegram_markdown(self.technical_breakdown)

        lines.extend([
            f"📖 *Sumber SOP:* `{clean_sop}`",
            "",
            "📝 *Analisis AI & Alasan Eksekusi:*",
            clean_breakdown,
            "═" * 32,
            "⚠️ _Peringatan Risiko: Analisis AI berdasarkan buku SOP. Tetap lakukan riset mandiri (DYOR)._",
        ])

        final_msg = "\n".join(lines)
        # Parity safety check for Telegram legacy Markdown entities
        if final_msg.count("*") % 2 != 0:
            idx = final_msg.rfind("*")
            final_msg = final_msg[:idx] + final_msg[idx+1:]
        if final_msg.count("_") % 2 != 0:
            idx = final_msg.rfind("_")
            final_msg = final_msg[:idx] + final_msg[idx+1:]
        if final_msg.count("`") % 2 != 0:
            idx = final_msg.rfind("`")
            final_msg = final_msg[:idx] + final_msg[idx+1:]

        return final_msg


def normalize_timeframe(tf: Any) -> str:
    """Standardize timeframe string, e.g. '5' -> '5m', '1jam' -> '1h', '2jam' -> '2h'."""
    tf_str = str(tf or "5m").strip().lower()
    mapping = {
        "1": "1m",
        "3": "3m",
        "5": "5m",
        "15": "15m",
        "30": "30m",
        "45": "45m",
        "60": "1h",
        "1h": "1h",
        "1jam": "1h",
        "120": "2h",
        "2h": "2h",
        "2jam": "2h",
        "240": "4h",
        "4h": "4h",
        "4jam": "4h",
        "d": "1d",
        "1d": "1d",
        "w": "1w",
        "1w": "1w",
    }
    return mapping.get(tf_str, tf_str)


TIMEFRAME_SL_TP_CONFIG = {
    "5m": {
        "style": "Scalping 5m",
        "sl_pips": 6.0,
        "sl_delta": 0.00060,
        "tp_pips": 9.0,
        "tp_delta": 0.00090,
        "rr": "1:1.50",
        "description": "Scalping 5m (SL: max(1.5x ATR, min_floor [6.0 pips]), TP: 1.5x SL [9.0 pips], R:R = 1:1.5)",
    },
    "15m": {
        "style": "Short Intraday 15m",
        "sl_pips": 8.0,
        "sl_delta": 0.00080,
        "tp_pips": 14.0,
        "tp_delta": 0.00140,
        "rr": "1:1.75",
        "description": "Short Intraday 15m (SL: 6.0-10.0 pips, TP: 12.0-18.0 pips, R:R >= 1:1.7)",
    },
    "30m": {
        "style": "Mid Intraday 30m",
        "sl_pips": 15.0,
        "sl_delta": 0.00150,
        "tp_pips": 28.0,
        "tp_delta": 0.00280,
        "rr": "1:1.87",
        "description": "Mid Intraday 30m (SL: 12.0-18.0 pips, TP: 24.0-35.0 pips, R:R >= 1:1.8)",
    },
    "45m": {
        "style": "Extended Intraday 45m",
        "sl_pips": 22.0,
        "sl_delta": 0.00220,
        "tp_pips": 42.0,
        "tp_delta": 0.00420,
        "rr": "1:1.91",
        "description": "Extended Intraday 45m (SL: 18.0-26.0 pips, TP: 36.0-50.0 pips, R:R >= 1:1.9)",
    },
    "1h": {
        "style": "Swing Intraday 1h",
        "sl_pips": 32.0,
        "sl_delta": 0.00320,
        "tp_pips": 60.0,
        "tp_delta": 0.00600,
        "rr": "1:1.88",
        "description": "Swing Intraday 1h (SL: 25.0-38.0 pips, TP: 50.0-80.0 pips, R:R >= 1:1.8)",
    },
    "2h": {
        "style": "Major Swing 2h",
        "sl_pips": 50.0,
        "sl_delta": 0.00500,
        "tp_pips": 100.0,
        "tp_delta": 0.01000,
        "rr": "1:2.00",
        "description": "Major Swing 2h (SL: 40.0-60.0 pips, TP: 80.0-130.0 pips, R:R >= 1:2.0)",
    },
}


def format_asset_price(price_val: float, symbol: str = "") -> str:
    """Format asset price according to standard asset scales (5 digits for FX, 2 for commodities/JPY)."""
    sym = symbol.upper()
    if "JPY" in sym or "XAU" in sym or "GOLD" in sym or "BTC" in sym or price_val > 50:
        return f"{price_val:.2f}"
    return f"{price_val:.5f}"


class RAGEngine:
    """Manages rule retrieval from ChromaDB and strict verification via Gemini."""

    SYSTEM_PROMPT = """Anda adalah Kepala Analis Teknikal dan Manajer Risiko Institusional yang sangat objektif, disiplin, dan mengutamakan perlindungan modal (Capital Preservation First).
Tugas Anda adalah mengevaluasi data pasar yang masuk secara ketat berdasarkan SOP Trading dari materi buku yang disediakan.

PRINSIP UTAMA MANAJEMEN RISIKO:
"Lebih baik melewatkan peluang (Action: 'WAIT') daripada memaksakan entry pada setup pasar yang meragukan, melawan arus tren mayor, atau menangkap pisau jatuh (falling knife)."

ATURAN KRITIS & LOGIKA KONFLUENSI TINGGI:
1. Nol Halusinasi (Zero Hallucination): Dasarkan evaluasi HANYA pada materi SOP TRADING YANG DITERIMA. Dilarang mengarang indikator yang tidak tertera.
2. Syarat Eksekusi Sinyal BUY (Wajib Memenuhi Minimal 2-3 Konfluensi Grade-A):
   - Tindakan 'BUY' HANYA BOLEH DIBERIKAN jika kriteria bullish Grade-A berikut terkonfirmasi secara bersamaan:
     * Pola Candlestick Reversal / Continuation / Struktur Bullish Terkonfirmasi (Bullish Engulfing, Hammer, Inverted Hammer, Morning Star, Piercing Line, Tweezer Bottom, Three White Soldiers, Three Inside Up, Bullish Dynamic EMA Pullback, Role Reversal RBS, Institutional VWAP Bounce/Reversion, Bullish Breaker Block)
     * Area Rejeksi Kuat (Bollinger Lower Band Support / FVG Bullish Retest / Order Block / Breaker Block / Role Reversal RBS / VWAP -2σ / Fibonacci Golden Pocket 0.50-0.618)
     * Konfirmasi Momentum Bullish (Stochastic Oversold < 30 & Golden Cross, atau Bullish RSI Divergence, atau MACD Golden Cross)
     * Keselarasan Tren Mayor (Harga di atas EMA 200 atau MTF 15m Grade-A Searah Bullish)
   - Skor kepercayaan (confidence_score) minimal adalah 0.85. Jika di bawah 0.85, WAJIB BERIKAN 'WAIT'.
3. Syarat Eksekusi Sinyal SELL (Wajib Memenuhi Minimal 2-3 Konfluensi Grade-A):
   - Tindakan 'SELL' HANYA BOLEH DIBERIKAN jika kriteria bearish Grade-A berikut terkonfirmasi secara bersamaan:
     * Pola Candlestick Reversal / Continuation / Struktur Bearish Terkonfirmasi (Bearish Engulfing, Shooting Star, Hanging Man, Evening Star, Dark Cloud Cover, Tweezer Top, Three Black Crows, Three Inside Down, Bearish Dynamic EMA Pullback, Role Reversal SBR, Institutional VWAP Rejection, Bearish Breaker Block)
     * Area Rejeksi Kuat (Bollinger Upper Band Resistance / FVG Bearish Retest / Order Block / Breaker Block / Role Reversal SBR / VWAP +2σ / Fibonacci Golden Pocket 0.50-0.618 Rejection)
     * Konfirmasi Momentum Bearish (Stochastic Overbought > 70 & Death Cross, atau Bearish RSI Divergence, atau MACD Death Cross)
     * Keselarasan Tren Mayor (Harga di bawah EMA 200 atau MTF 15m Grade-A Searah Bearish)
   - Skor kepercayaan (confidence_score) minimal adalah 0.85. Jika di bawah 0.85, WAJIB BERIKAN 'WAIT'.

ATURAN PANTANGAN MUTLAK (HARD VETO - WAJIB KEPUTUSAN 'WAIT'):
1. DILARANG MELAWAN TREN MAYOR (ANTI COUNTER-TREND):
   - DILARANG KERAS memberikan sinyal SELL jika MTF 15m menunjukkan tren Uptrend kuat di atas EMA 200.
   - DILARANG KERAS memberikan sinyal BUY jika MTF 15m menunjukkan tren Downtrend kuat di bawah EMA 200.
2. DILARANG MENANGKAP PISAU JATUH (ANTI-FALLING KNIFE & MOMENTUM CONFLICT):
   - DILARANG BUY jika MACD berada dalam kondisi Death Cross / momentum Bearish tajam DAN candle bar penutupan masih berwarna merah.
   - DILARANG BUY jika RSI sedang terjun bebas (< 20) tanpa adanya ekor penolakan bawah yang solid (lower wick >= 40%).
   - DILARANG SELL jika MACD berada dalam kondisi Golden Cross / momentum Bullish tajam DAN candle bar penutupan masih berwarna hijau.
   - DILARANG SELL jika RSI sedang melonjak tinggi (> 80) tanpa adanya ekor penolakan atas yang solid (upper wick >= 40%).
3. FILTER JARAK STOP LOSS:
   - Jika jarak Stop Loss terlalu sempit (< 4.0 pips) atau rasio Risk-to-Reward di bawah 1:1.5, tolak dan berikan 'WAIT'.

ATURAN VALIDASI MUTLAK POLA CANDLESTICK, CHART PATTERNS & 5 PILAR TEKNIKAL LANJUTAN:
1. Pembedaan Formasi 1-Candle vs 2-Candle (Anti-Salah Identifikasi Bullish Engulfing vs Inverted Hammer):
   - WAJIB mengevaluasi relasi 2 candle berturut-turut, DILARANG hanya terpaku pada 1 candle terakhir!
   - Bullish Engulfing (Formasi 2-Candle):
     * Terdiri dari Candle 1 (merah/bearish) dan Candle 2 (hijau/bullish solid).
     * Body Candle 2 WAJIB MENELAN SELURUH BODY Candle 1 (Close2 >= Open1 dan Open2 <= Close1, serta Body2 >= Body1).
     * Jika Candle 2 memiliki sumbu atas wajar namun body-nya menelan Candle 1, pola tersebut 100% ADALAH BULLISH ENGULFING, BUKAN INVERTED HAMMER!
   - Hammer (Formasi 1-Candle Pin Bar Bullish Reversal):
     * HANYA VALID jika bar SUDAH DITUTUP (CONFIRMED CLOSED BAR) pada Tren Turun (Downtrend) di area Support.
     * Sumbu bawah panjang minimal 1x panjang body (>= 1.0x body dan >= 40% range candle).
     * Body berada di bagian atas candle (<= 50% range candle).
     * Sumbu atas kecil atau nihil (<= 10% range candle).
   - Inverted Hammer (Formasi 1-Candle Pin Bar):
     * HANYA VALID jika bar SUDAH DITUTUP (CONFIRMED CLOSED BAR) pada Tren Turun (Downtrend). Dilarang menyimpulkan saat candle masih berjalan/open!
     * RSI WAJIB di area bawah (RSI <= 50.0). DILARANG KERAS BUY jika RSI > 50 apalagi RSI >= 60.
     * Body berukuran KECIL di dasar candle (<= 35% rentang candle).
     * Sumbu atas panjang mendominasi minimal 2x panjang body (>= 50% range).
     * Di bawah body TIDAK BOLEH ADA GARIS / SHADOW (lower shadow = 0 / nihil).
     * Berada di area Support / Lower Band Bollinger, dan TIDAK MENELAN body candle sebelumnya.
   - Bearish Engulfing (Formasi 2-Candle):
     * Terdiri dari Candle 1 (hijau/bullish) dan Candle 2 (merah/bearish solid).
     * Body Candle 2 WAJIB MENELAN SELURUH BODY Candle 1 (Close2 <= Open1 dan Open2 >= Close1, serta Body2 >= Body1).
     * Dilarang salah melabeli Bearish Engulfing sebagai Shooting Star jika body menelan candle sebelumnya!
   - Shooting Star (Formasi 1-Candle Pin Bar):
     * HANYA VALID jika bar SUDAH DITUTUP (CONFIRMED CLOSED BAR) pada Tren Naik (Uptrend). Dilarang menyimpulkan saat candle masih berjalan/open!
     * RSI WAJIB di area atas (RSI >= 50.0). DILARANG KERAS SELL jika RSI < 50.
     * Body berukuran KECIL di dasar candle (<= 35% rentang candle) dan TIDAK MENELAN candle sebelumnya.
     * Sumbu atas panjang minimal 2x body, tanpa garis di bawah body, muncul saat Uptrend.
     * Berada di area Resistance / Upper Band Bollinger.
   - Hanging Man (Formasi 1-Candle Pin Bar Bearish Reversal di Puncak Uptrend):
     * HANYA VALID jika didahului Tren Naik dan candle sebelumnya WAJIB HIJAU/BULLISH (Close1 > Open1)! DILARANG KERAS mengidentifikasi Hanging Man jika candle sebelumnya sudah merah/bearish!
     * Berada di puncak lokal kenaikan (High2 >= High1).
     * Sumbu atas WAJIB SANGAT KECIL ATAU NIHIL (<= 8% rentang candle dan <= 0.35x body). Jika sumbu atas panjang, pola tersebut BUKAN HANGING MAN (TOLAK / Action: 'WAIT')!
     * Sumbu bawah panjang mendominasi minimal 2x body (>= 55% rentang candle).
     * Body berukuran KECIL di puncak candle (<= 35% rentang candle).
     * Berada di area Resistance / Upper Bollinger Band (RSI >= 55.0).
2. Konteks Tren & Validitas Reversal:
   - Pola Reversal (Hammer, Tweezer, Morning Star, dll.) di area Support/Resistance hanya valid jika didukung oleh penolakan harga (wick rejection) yang nyata dan momentum pembalikan arah (misal Stochastic hook dari area jenuh atau RSI Divergence), serta TIDAK MELANGGAR tren mayor MTF (15m).
   - DILARANG membuka posisi Reversal jika bertentangan langsung dengan tren mayor MTF 15m.
3. Chart Patterns Struktural, 5 Pilar Teknikal Lanjutan & Smart Money Concepts (SMC/ICT):
   - Chart Patterns:
     * Head and Shoulders (Bearish) & Inverse Head and Shoulders (Bullish): Konfirmasi pembalikan struktural mayor saat menembus neckline.
     * Bull Flag & Bear Flag: Pola kelanjutan tren probabilitas tinggi (flagpole impulsif + channel konsolidasi korektif).
     * Ascending Triangle (Resistensi mendatar + higher lows) memicu sinyal BUY; Descending Triangle (Support mendatar + lower highs) memicu sinyal SELL.
     * Double Bottom (W Pattern) di support memperkuat sinyal BUY; Double Top (M Pattern) di resistance memperkuat sinyal SELL.
   - RSI Divergence:
     * Regular Divergence (Bullish: Price Lower Low vs RSI Higher Low / Bearish: Price Higher High vs RSI Lower High) = Sinyal Reversal Exhaustion yang sangat kuat.
     * Hidden Divergence (Bullish: Price Higher Low vs RSI Lower Low / Bearish: Price Lower High vs RSI Higher High) = Sinyal Trend Continuation (kelanjutan tren utama).
   - Dynamic Fibonacci Golden Pocket:
     * Zona retracement 0.50 hingga 0.618 adalah Optimal Trade Entry (OTE). Rejection candle di area ini merupakan konfirmasi entri yang sangat bernilai.
   - ICT Institutional Killzones & Bollinger Bands Squeeze:
     * Sesi likuiditas institusional utama: London Open (14:00 - 17:00 WIB) dan New York Open (19:30 - 22:30 WIB). Transaksi di luar killzone tetap valid jika konfluensi teknis Grade-A terpenuhi.
     * Bollinger Bands Squeeze (kompresi volatilitas) disusul penembusan terarah menandai ekspansi tren baru yang kuat.
   - SMC / ICT Core:
     * Fair Value Gap (FVG) Retest & Institutional Order Block (OB) yang belum termitigasi (unmitigated) merupakan area entri probabilitas tinggi.
     * Liquidity Sweeps (BSL/SSL): Penembusan sesaat swing high/low dengan ekor candle menandai jebakan likuiditas, cari pembalikan arah menuju FVG terdekat.
     * Market Structure Shift (CHoCH): Mengonfirmasi pembalikan arah tren awal; Break of Structure (BOS) mengonfirmasi kelanjutan tren.
4. Penolakan Sinyal Palsu, News Blackout & Aturan Scalping MACD:
   - NEWS BLACKOUT: Jika pada payload atau status terdapat indikasi 'News Blackout Active' (rilis berita High-Impact seperti NFP, CPI, FOMC dalam rentang waktu terlarang), tindakan WAJIB: 'WAIT' demi perlindungan modal.
   - ATURAN SCALPING MACD (Fresh Cross vs Trend Scalping):
     * Dalam gaya scalping, posisi SELL tetap diizinkan saat momentum MACD masih bernilai positif jika momentum melandai atau terkonfirmasi pola Reversal/Divergence/Upper Band, KECUALI jika baru saja terjadi Golden Cross segar (Fresh Cross dalam 1-2 bar terakhir). Golden Cross baru menandakan gelombang bullish baru dimulai (Action: 'WAIT' untuk SELL).
     * Sebaliknya, posisi BUY tetap diizinkan saat momentum MACD masih bernilai negatif jika momentum melandai atau terkonfirmasi pola Reversal/Divergence/Lower Band, KECUALI jika baru saja terjadi Death Cross segar (Fresh Cross dalam 1-2 bar terakhir) (Action: 'WAIT' untuk BUY).
   - DILARANG KERAS COUNTER-TREND (ANTI COUNTER-TREND HARD VETO):
     * DILARANG membuka posisi melawan arus makro institusional. Jika payload memuat indikasi atau peringatan counter-trend melawan tren mayor 15m atau 1H, tindakan WAJIB: 'WAIT' demi perlindungan modal. Sinyal yang melawan tren mayor dilarang dieksekusi.
   - Pola Bullish Harami dan Bearish Harami WAJIB memiliki candle kedua dengan body solid nyata (minimal 25% range candle) dan SELURUH High & Low candle kedua berada mutlak di dalam range mother candle. DILARANG KERAS melabeli candle DOJI sebagai Harami!
   - Pola Tweezer Top WAJIB memiliki puncak kembar presisi (selisih high <= 1-2 tick), candle kedua dilarang membuat higher high, dan wajib ada sumbu atas penolakan nyata (upper shadow >= 25% range).
   - Pola Tweezer Bottom WAJIB memiliki dasar kembar presisi (selisih low <= 1-2 tick), candle kedua dilarang membuat lower low, dan wajib ada sumbu bawah penolakan nyata (lower shadow >= 25% range).
   - Jika sinyal mendeteksi 'Inverted Hammer' saat tren naik (Uptrend / RSI > 50) atau memiliki sumbu bawah atau di luar area support, tolak sinyal tersebut (Action: 'WAIT').
   - Jika sinyal mendeteksi 'Shooting Star' saat tren turun (Downtrend / RSI < 50) atau memiliki sumbu bawah atau di luar area resistance, tolak sinyal tersebut (Action: 'WAIT').
   - Jika sinyal mendeteksi 'Hanging Man' namun candle sebelumnya sudah merah/bearish (bukan candle hijau) ATAU memiliki sumbu atas panjang (> 8% rentang candle), tolak sinyal tersebut sebagai Hanging Man palsu (Action: 'WAIT').

ATURAN KALKULASI HARGA ENTRY, STOP LOSS (SL), DAN TAKE PROFIT (TP) BERBASIS VOLATILITAS DINAMIS (ATR):
- WAJIB MENGGUNAKAN HARGA PASAR SAAT INI (Current Market Price) dari payload sebagai jangkar utama!
- Masukkan Current Market Price tersebut ke dalam field 'current_price' (contoh: "1.13207").
- PRIORITASKAN LEVEL DYNAMIC ATR: Jika pada payload tersedia nilai 'Dynamic_Buy_SL', 'Dynamic_Buy_TP', 'Dynamic_Sell_SL', 'Dynamic_Sell_TP', atau 'ATR_Pips', prioritaskan penempatan level SL dan TP menggunakan nilai volatilitas dinamis tersebut untuk menjaga rasio R:R minimal 1:1.5 hingga 1:2.0!
- Untuk sinyal BUY:
  * 'entry_zone': di sekitar Current Market Price.
  * 'stop_loss': WAJIB DI BAWAH Entry dan di luar swing low / batas bawah FVG atau Order Block.
  * 'take_profit': WAJIB DI ATAS Entry (rasio R:R >= 1:1.5).
- Untuk sinyal SELL:
  * 'entry_zone': di sekitar Current Market Price.
  * 'stop_loss': WAJIB DI ATAS Entry dan di luar swing high / batas atas FVG atau Order Block.
  * 'take_profit': WAJIB DI BAWAH Entry (rasio R:R >= 1:1.5).
- Penulisan Forex: Gunakan 5 digit desimal presisi (misal: 1.13207). Dilarang mengarang harga yang tidak sesuai dengan Current Market Price saat ini.
- Pada 'technical_breakdown', sajikan poin-poin yang rapi dan detail:
  * Pola & Struktur Terdeteksi: sebutkan dan jelaskan SEMUA pola candlestick, chart patterns, konfluensi SMC (FVG, Order Block, CHoCH, BOS), RSI Divergence, Fibonacci Golden Pocket, serta status Killzone yang terdeteksi pada payload secara lengkap.
  * Level SL & TP Dinamis: sebutkan alasan penempatan SL dan TP berbasis ATR serta rasio Risk:Reward (R:R).
  * Konfirmasi Tren & Indikator: sebutkan konfirmasi indikator (RSI, Bollinger Bands, EMA, MACD) dan arah momentum.
- Jika tindakan adalah 'WAIT', isi entry_zone, stop_loss, take_profit, dan risk_reward_ratio dengan 'N/A'.
- Pada 'sop_reference', sebutkan judul dokumen atau buku dan nomor halaman/bagian rujukan (contoh: 'SOP_Advanced_Technical_Patterns_Divergence_Fibonacci.md', 'SOP_Smart_Money_Concepts_ICT.md', atau 'Steve Nison hal. 45').
- Jawaban harus selalu mematuhi skema JSON yang ditentukan.
"""

    def __init__(self, collection: Optional[chromadb.Collection] = None) -> None:
        self.knowledge_dir = settings.resolved_knowledge_dir
        self.collection_name = settings.COLLECTION_NAME
        self.top_k = settings.TOP_K_RULES
        self.collection = collection
        if self.collection is None:
            self._init_chroma()
        else:
            logger.info("RAG Engine reusing provided ChromaDB collection '%s' (%d records).", self.collection_name, self.collection.count())
        self._init_gemini()

    def _init_chroma(self) -> None:
        """Connect to local ChromaDB persistent collection."""
        try:
            from chromadb.config import Settings as ChromaSettings
            self.chroma_client = chromadb.PersistentClient(
                path=str(self.knowledge_dir),
                settings=ChromaSettings(anonymized_telemetry=False),
            )
            ef = embedding_functions.DefaultEmbeddingFunction()
            self.collection = self.chroma_client.get_or_create_collection(
                name=self.collection_name,
                embedding_function=ef,
            )
            count = self.collection.count()
            logger.info("RAG Engine connected to ChromaDB collection '%s' (%d records).", self.collection_name, count)
        except Exception as exc:
            logger.error("Failed to connect to ChromaDB: %s", exc)
            self.collection = None

    def _init_gemini(self) -> None:
        """Initialize Google GenAI client."""
        if not GENAI_AVAILABLE:
            logger.warning("google-genai package is not installed. Gemini calls will be mocked.")
            self.gemini_client = None
            return

        if not settings.GEMINI_API_KEY:
            logger.warning("GEMINI_API_KEY is not set. Set it in .env to enable live AI reasoning.")
            self.gemini_client = None
            return

        try:
            self.gemini_client = genai.Client(api_key=settings.GEMINI_API_KEY)
            logger.info("Initialized Google GenAI client with model '%s'", settings.GEMINI_MODEL)
        except Exception as exc:
            logger.error("Failed to initialize Google GenAI Client: %s", exc)
            self.gemini_client = None

    def retrieve_relevant_rules(self, query_text: str, top_k: Optional[int] = None) -> List[Dict[str, Any]]:
        """Retrieve top-k most relevant trading rules for the current market situation."""
        k = top_k or self.top_k
        if self.collection is None or self.collection.count() == 0:
            logger.warning("Vector collection is empty or not initialized.")
            return []

        try:
            results = self.collection.query(
                query_texts=[query_text],
                n_results=min(k, self.collection.count()),
            )

            retrieved: List[Dict[str, Any]] = []
            if results and results.get("documents"):
                documents = results["documents"][0]
                metadatas = results["metadatas"][0] if results.get("metadatas") else [{}] * len(documents)
                distances = results["distances"][0] if results.get("distances") else [0.0] * len(documents)

                for doc, meta, dist in zip(documents, metadatas, distances):
                    retrieved.append({
                        "text": doc,
                        "metadata": meta,
                        "distance": dist,
                    })

            # Selalu sertakan aturan pantangan hasil refleksi mandiri AI (Self-Learned Guardrails) terbaru yang diringkas
            try:
                guardrail_res = self.collection.get(
                    where={"category": "self_learned_guardrail"},
                    limit=3,
                )
                if guardrail_res and guardrail_res.get("documents"):
                    for g_doc, g_meta in zip(guardrail_res["documents"], guardrail_res["metadatas"]):
                        clean_text = str(g_doc)
                        # Bersihkan pembuka naratif dan sapaan esai
                        clean_text = re.sub(r"^(Halo|Salam|Sebagai Master Trading Risk Auditor|Halo! Sebagai Master).*?\n+", "", clean_text, flags=re.IGNORECASE).strip()
                        words = clean_text.split()
                        if len(words) > 150:
                            clean_text = " ".join(words[:150]) + "..."

                        if clean_text and not any(clean_text in r["text"] for r in retrieved):
                            retrieved.insert(0, {
                                "text": f"[PANTANGAN MANDIRI AI]: {clean_text}",
                                "metadata": g_meta,
                                "distance": 0.0,
                            })
            except Exception as e:
                logger.debug("Notice fetching self-learned guardrails: %s", e)

            logger.info("Retrieved %d SOP chunks for query: '%s'", len(retrieved), query_text[:60])
            return retrieved
        except Exception as exc:
            logger.error("Error retrieving rules from ChromaDB: %s", exc)
            return []

    def evaluate_market_setup(self, payload: Dict[str, Any]) -> TradingSignalDecision:
        """Evaluate market data against retrieved SOP and return strict structured decision."""
        symbol = str(payload.get("symbol", "EURUSD")).upper()
        timeframe = normalize_timeframe(payload.get("timeframe", "5m"))
        raw_price = payload.get("price", 0.0)
        try:
            float_price = float(raw_price)
            formatted_price_str = format_asset_price(float_price, symbol)
        except Exception:
            formatted_price_str = str(raw_price)

        price = formatted_price_str
        indicator_status = str(payload.get("indicator_status", ""))
        additional_info = payload.get("notes", "")
        pattern_str = str(payload.get("reason", ""))

        query_text = (
            f"{pattern_str} Candlestick Reversal SOP {indicator_status} {symbol} {timeframe}"
        )

        # 1. Retrieve SOP rules
        rules = self.retrieve_relevant_rules(query_text)

        # 2. Format context
        if rules:
            context_blocks = []
            for idx, r in enumerate(rules, start=1):
                source = r["metadata"].get("source", "Unknown Document")
                page = r["metadata"].get("page", "?")
                text = r["text"]
                context_blocks.append(f"[RULE #{idx}] Source: {source}, Page: {page}\nContent: {text}")
            sop_context = "\n\n".join(context_blocks)
        else:
            sop_context = "No specific SOP rules found in local database."

        # 3. Build prompt
        user_prompt = f"""EVALUATE THIS MARKET SETUP:
- Instrument: {symbol}
- Timeframe: {timeframe}
- Current Market Price: {price}
- Indicator & Chart Status: {indicator_status}
- Additional Context: {additional_info}

RETRIEVED TRADING SOP RULES:
\"\"\"
{sop_context}
\"\"\"

TASK:
Examine the setup strictly against the SOP rules above and system instructions.
Important Rules & Confluences:
1. SCALPING MACD RULE:
   - Posisi SELL dilarang HANYA jika MACD baru saja mengalami Golden Cross segar (Fresh Cross 1-2 bar terakhir). Jika MACD masih bullish namun momentum melandai atau ada pola Reversal/Divergence di area Resistance, sinyal SELL tetap DIIZINKAN.
   - Posisi BUY dilarang HANYA jika MACD baru saja mengalami Death Cross segar (Fresh Cross 1-2 bar terakhir). Jika MACD masih bearish namun momentum melandai atau ada pola Reversal/Divergence di area Support, sinyal BUY tetap DIIZINKAN.
2. 5 ADVANCED TECHNICAL PILLARS & CONFLUENCES:
   - Chart Patterns (H&S, Inv H&S, Bull/Bear Flags, Triangles), RSI Divergence (Regular/Hidden), Fibonacci Golden Pocket (0.50-0.618 OTE), Bollinger Squeeze Breakout, dan Sesi ICT Killzone (London/NY) diakui sebagai konfluensi Grade-A bernilai tinggi.
3. ANTI COUNTER-TREND HARD VETO:
   - DILARANG memberikan sinyal transaksi yang melawan arah tren mayor MTF (15m / 1H). Jika terdapat indikasi atau peringatan counter-trend, WAJIB berikan keputusan 'WAIT'.
4. ACTION BUY / SELL:
   - Berikan BUY jika >= 2 kriteria bullish terkonfirmasi dengan R:R >= 1:1.5.
   - Berikan SELL jika >= 2 kriteria bearish terkonfirmasi dengan R:R >= 1:1.5.
   - Output Action: WAIT HANYA jika kriteria < 2 atau ada kontradiksi fatal (misal: BUY saat Overbought ekstrem > 70 atau SELL saat Oversold ekstrem < 30).
Ensure all required fields are populated accurately.
"""

        # 4. Invoke LLM or Fallback
        if not self.gemini_client:
            logger.warning("Gemini Client inactive. Returning cautious WAIT signal.")
            wait_decision = TradingSignalDecision(
                instrument=symbol,
                timeframe=timeframe,
                action="WAIT",
                entry_zone="N/A",
                stop_loss="N/A",
                take_profit="N/A",
                risk_reward_ratio="N/A",
                sop_reference=rules[0]["metadata"].get("source", "SOP Belum Dimuat") if rules else "Tidak Ada SOP di Database",
                technical_breakdown=(
                    f"Kunci API Gemini belum dikonfigurasi atau klien tidak aktif. Berhasil menemukan {len(rules)} potongan aturan SOP. "
                    "Mengacu pada prinsip ketat zero-hallucination, status otomatis ditetapkan ke WAIT demi perlindungan modal."
                ),
                confidence_score=0.0,
            )
            logger.info("📝 Detail Alasan & Analisis AI:\n%s", wait_decision.technical_breakdown)
            return wait_decision

        candidate_models = [
            settings.GEMINI_MODEL,
            "gemini-flash-lite-latest",
            "gemini-3-flash-preview",
            "gemini-3.5-flash",
            "gemini-3.5-flash-lite",
            "gemini-flash-latest",
            "gemini-3.8-flash",
        ]
        # Deduplicate while preserving order
        unique_models = []
        for m in candidate_models:
            if m and m not in unique_models:
                unique_models.append(m)

        last_error = None
        for model_name in unique_models:
            try:
                response = self.gemini_client.models.generate_content(
                    model=model_name,
                    contents=user_prompt,
                    config=types.GenerateContentConfig(
                        system_instruction=self.SYSTEM_PROMPT,
                        temperature=0.1,
                        response_mime_type="application/json",
                        response_schema=TradingSignalDecision,
                        automatic_function_calling=types.AutomaticFunctionCallingConfig(disable=True),
                    ),
                )

                if response.text:
                    data = json.loads(response.text)
                    decision = TradingSignalDecision(**data)
                    # Enforce incoming timeframe, symbol, and formatted current price
                    decision.timeframe = timeframe
                    decision.instrument = symbol
                    decision.current_price = formatted_price_str
                    decision.pattern_name = str(payload.get("reason", ""))
                    decision.indicator_status = str(payload.get("indicator_status", ""))
                    decision.notes_detail = str(payload.get("notes", ""))
                    decision.bar_timestamp = str(payload.get("timestamp", ""))
                    logger.info(
                        "AI Verdict using '%s' for %s (%s): %s [Confidence: %.2f]",
                        model_name,
                        decision.instrument,
                        decision.timeframe,
                        decision.action,
                        decision.confidence_score,
                    )
                    if decision.sop_reference:
                        logger.info("📚 Referensi SOP: %s", decision.sop_reference)
                    if decision.technical_breakdown:
                        logger.info("📝 Detail Alasan & Analisis AI:\n%s", decision.technical_breakdown)
                    return decision
                else:
                    raise ValueError(f"Empty response received from {model_name}.")

            except Exception as exc:
                last_error = exc
                err_str = str(exc)
                if "429" in err_str or "RESOURCE_EXHAUSTED" in err_str:
                    logger.warning("Gemini model '%s' mencapai batas kuota harian Free Tier (429).", model_name)
                    time.sleep(1.0)
                elif "503" in err_str or "UNAVAILABLE" in err_str:
                    logger.warning("Gemini model '%s' sedang mengalami lonjakan beban (503 UNAVAILABLE). Mencoba model alternatif...", model_name)
                    time.sleep(1.5)
                else:
                    logger.warning("Gemini evaluation with model '%s' failed: %s. Trying next fallback...", model_name, exc)
                    time.sleep(0.5)

        logger.warning(
            "⚡ Seluruh model Gemini Cloud tidak tersedia / sibuk (Last Error: %s). "
            "Mengaktifkan Deterministic SOP Rule Engine (Failover Evaluasi Lokal Cepat)...",
            last_error,
        )

        # Deterministic SOP Fallback jika API AI sedang rate-limited (429) namun sinyal konfluensi sudah valid
        has_bear_momentum = "DEATH CROSS" in indicator_status.upper() or "BEARISH" in indicator_status.upper()
        has_downtrend = "DOWNTREND" in indicator_status.upper()
        has_bull_momentum = "GOLDEN CROSS" in indicator_status.upper() or "BULLISH" in indicator_status.upper()
        has_uptrend = "UPTREND" in indicator_status.upper()

        is_sell_candidate = "SELL" in indicator_status.upper() and ("KONFLUENSI" in indicator_status.upper() or "ENGULFING" in indicator_status.upper())
        is_buy_candidate = "BUY" in indicator_status.upper() and ("KONFLUENSI" in indicator_status.upper() or "ENGULFING" in indicator_status.upper())

        # SOP Rule #4: DILARANG ENTRY JIKA TERDAPAT SINYAL KONTRADIKSI (Anti-Falling Knife & Anti-Bull Trap)
        has_oversold = "OVERSOLD" in indicator_status.upper()
        has_overbought = "OVERBOUGHT" in indicator_status.upper()

        # Izinkan BUY jika terdapat pola Bullish Reversal fisik valid atau Bullish Continuation
        is_bull_reversal = any(p in indicator_status.upper() for p in [
            "HAMMER", "INVERTED HAMMER", "BULLISH ENGULFING", "MORNING STAR", "PIERCING LINE",
            "TWEEZER BOTTOM", "BULLISH HARAMI", "THREE WHITE SOLDIERS", "BULLISH KICKER", "ABANDONED BABY"
        ])
        is_bull_continuation = any(p in indicator_status.upper() for p in [
            "BULLISH ENGULFING", "THREE WHITE SOLDIERS", "BULLISH KICKER", "RISING THREE METHODS"
        ])

        # Izinkan SELL jika terdapat pola Breakout Continuation valid atau Bearish Reversal di resistance
        is_bear_reversal = any(p in indicator_status.upper() for p in [
            "SHOOTING STAR", "EVENING STAR", "DARK CLOUD COVER", "TWEEZER TOP",
            "HANGING MAN", "BEARISH HARAMI", "BEARISH ABANDONED BABY", "THREE INSIDE DOWN"
        ])
        is_bear_continuation = any(p in indicator_status.upper() for p in [
            "BEARISH ENGULFING", "THREE BLACK CROWS", "BEARISH KICKER", "FALLING THREE METHODS"
        ])

        # Validasi spesifik Inverted Hammer vs Shooting Star pada fallback SOP
        has_inverted_hammer = "INVERTED HAMMER" in indicator_status.upper()
        has_shooting_star = "SHOOTING STAR" in indicator_status.upper()
        rsi_val = float(payload.get("rsi", 50.0))

        if has_inverted_hammer and (has_uptrend or has_overbought or rsi_val > 50.0):
            logger.warning("Inverted Hammer invalid: Terdeteksi saat Uptrend/Overbought/RSI %.1f > 50. Menolak sinyal BUY.", rsi_val)
            is_buy_candidate = False

        if has_shooting_star and (has_downtrend or has_oversold or rsi_val < 50.0):
            logger.warning("Shooting Star invalid: Terdeteksi saat Downtrend/Oversold/RSI %.1f < 50. Menolak sinyal SELL.", rsi_val)
            is_sell_candidate = False

        if is_buy_candidate:
            if (has_bear_momentum or has_downtrend) and not is_bull_reversal:
                logger.warning("BUY candidate rejected: Downtrend/Bearish without valid Bullish Reversal pattern. Enforcing WAIT.")
                is_buy_candidate = False
            elif has_overbought and not is_bull_continuation:
                logger.warning("BUY candidate rejected: RSI Overbought without Bullish Continuation pattern. Enforcing WAIT.")
                is_buy_candidate = False

        if is_sell_candidate:
            if (has_uptrend or has_bull_momentum) and not is_bear_reversal:
                logger.warning("SELL candidate rejected: Uptrend/Bullish without valid Bearish Top Reversal pattern. Enforcing WAIT.")
                is_sell_candidate = False
            elif has_oversold and not is_bear_continuation:
                logger.warning("SELL candidate rejected: Oversold zone without Breakout Continuation pattern. Enforcing WAIT.")
                is_sell_candidate = False

        try:
            cur_p = float(formatted_price_str)
        except Exception:
            cur_p = 0.0

        tf_cfg = TIMEFRAME_SL_TP_CONFIG.get(timeframe, TIMEFRAME_SL_TP_CONFIG["5m"])
        sl_delta = tf_cfg["sl_delta"]
        tp_delta = tf_cfg["tp_delta"]
        rr_str = tf_cfg["rr"]
        style_desc = tf_cfg["description"]

        # Scale pips for JPY or Gold
        if "JPY" in symbol.upper():
            sl_delta *= 100.0
            tp_delta *= 100.0
        elif "XAU" in symbol.upper() or "GOLD" in symbol.upper():
            sl_delta *= 1000.0
            tp_delta *= 1000.0

        dynamic_sl = payload.get("dynamic_sl")
        dynamic_tp = payload.get("dynamic_tp")
        dynamic_tp_mode = payload.get("tp_mode", "")

        if is_sell_candidate and cur_p > 0:
            if dynamic_sl and dynamic_tp:
                sl_val = float(dynamic_sl)
                tp_val = float(dynamic_tp)
                sl_dist = abs(cur_p - sl_val)
                tp_dist = abs(cur_p - tp_val)
                rr_str = f"1:{round(tp_dist / sl_dist, 2)}" if sl_dist > 0 else rr_str
            else:
                sl_val = cur_p + sl_delta
                tp_val = cur_p - tp_delta
            return TradingSignalDecision(
                instrument=symbol,
                timeframe=timeframe,
                action="SELL",
                current_price=formatted_price_str,
                entry_zone=formatted_price_str,
                stop_loss=format_asset_price(sl_val, symbol),
                take_profit=format_asset_price(tp_val, symbol),
                risk_reward_ratio=rr_str,
                sop_reference="Steve Nison & Analisis Teknikal Dasar (SOP Engine)",
                technical_breakdown=(
                    f"Terdeteksi konfluensi bearish valid ({indicator_status}). "
                    f"Entry SELL ditetapkan pada harga pasar saat ini {formatted_price_str}. "
                    f"Stop Loss ditempatkan di atas level resistansi ({format_asset_price(sl_val, symbol)}) "
                    f"dan Take Profit di ({format_asset_price(tp_val, symbol)}) dengan Rasio Risk/Reward {rr_str} "
                    f"mengikuti SOP {style_desc}."
                ),
                confidence_score=0.90,
                pattern_name=str(payload.get("reason", "")),
                indicator_status=str(payload.get("indicator_status", "")),
                notes_detail=str(payload.get("notes", "")),
                bar_timestamp=str(payload.get("timestamp", "")),
            )
        elif is_buy_candidate and cur_p > 0:
            if dynamic_sl and dynamic_tp:
                sl_val = float(dynamic_sl)
                tp_val = float(dynamic_tp)
                sl_dist = abs(cur_p - sl_val)
                tp_dist = abs(tp_val - cur_p)
                rr_str = f"1:{round(tp_dist / sl_dist, 2)}" if sl_dist > 0 else rr_str
            else:
                sl_val = cur_p - sl_delta
                tp_val = cur_p + tp_delta
            return TradingSignalDecision(
                instrument=symbol,
                timeframe=timeframe,
                action="BUY",
                current_price=formatted_price_str,
                entry_zone=formatted_price_str,
                stop_loss=format_asset_price(sl_val, symbol),
                take_profit=format_asset_price(tp_val, symbol),
                risk_reward_ratio=rr_str,
                sop_reference="Steve Nison & Analisis Teknikal Dasar (SOP Engine)",
                technical_breakdown=(
                    f"Terdeteksi konfluensi bullish valid ({indicator_status}). "
                    f"Entry BUY ditetapkan pada harga pasar saat ini {formatted_price_str}. "
                    f"Stop Loss ditempatkan di bawah level support ({format_asset_price(sl_val, symbol)}) "
                    f"dan Take Profit di ({format_asset_price(tp_val, symbol)}) dengan Rasio Risk/Reward {rr_str} "
                    f"mengikuti SOP {style_desc}."
                ),
                confidence_score=0.90,
                pattern_name=str(payload.get("reason", "")),
                indicator_status=str(payload.get("indicator_status", "")),
                notes_detail=str(payload.get("notes", "")),
                bar_timestamp=str(payload.get("timestamp", "")),
            )

        fallback_wait = TradingSignalDecision(
            instrument=symbol,
            timeframe=timeframe,
            action="WAIT",
            current_price=formatted_price_str,
            entry_zone="N/A",
            stop_loss="N/A",
            take_profit="N/A",
            risk_reward_ratio="N/A",
            sop_reference="Kendala Inferensi AI / Konfluensi Belum Terpenuhi",
            technical_breakdown=f"Kondisi saat ini: {indicator_status}. Mengacu pada prinsip perlindungan modal dan zero-hallucination, status ditetapkan ke WAIT.",
            confidence_score=0.0,
            pattern_name=str(payload.get("reason", "")),
            indicator_status=str(payload.get("indicator_status", "")),
            notes_detail=str(payload.get("notes", "")),
            bar_timestamp=str(payload.get("timestamp", "")),
        )
        logger.info(
            "AI Verdict (Fallback SOP) for %s (%s): %s [Confidence: %.2f]",
            fallback_wait.instrument,
            fallback_wait.timeframe,
            fallback_wait.action,
            fallback_wait.confidence_score,
        )
        logger.info("📝 Detail Alasan & Analisis SOP:\n%s", fallback_wait.technical_breakdown)
        return fallback_wait
