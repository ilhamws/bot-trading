"""Advanced Quantitative Technical Engine.

Detects advanced chart patterns (Head & Shoulders, Bull/Bear Flag, Triangles),
RSI Divergence (Regular & Hidden), Fibonacci Golden Pocket (0.50-0.618),
ICT Institutional Killzones, and Bollinger Band Volatility Squeeze Breakouts.
"""

from datetime import datetime
from typing import Dict, Any, List, Optional, Tuple
import pandas as pd
import numpy as np

from config import logger


class AdvancedTechnicalsEngine:
    """Quantitative analyzer for 5 advanced institutional technical disciplines."""

    def analyze(
        self,
        df: pd.DataFrame,
        rsi_series: pd.Series,
        bb_upper: pd.Series,
        bb_lower: pd.Series,
        bb_basis: pd.Series,
        cur_idx: int = -1
    ) -> Dict[str, Any]:
        """Run all 5 advanced technical evaluations on OHLCV data."""
        if len(df) < 30:
            return {
                "bull_confluences": [],
                "bear_confluences": [],
                "details": [],
                "summary": "Data insufficient for advanced technicals",
            }

        bull_confluences: List[str] = []
        bear_confluences: List[str] = []
        details: List[str] = []

        # 1. DETEKSI DIVERGENSI RSI (REGULAR & HIDDEN)
        div_results = self.detect_rsi_divergence(df, rsi_series, cur_idx)
        for b_div in div_results.get("bull", []):
            bull_confluences.append(b_div)
        for be_div in div_results.get("bear", []):
            bear_confluences.append(be_div)
        if div_results.get("note"):
            details.append(div_results["note"])

        # 2. POLA GRAFIK GEOMETRIS KLASIK (H&S, FLAGS, TRIANGLES)
        pattern_res = self.detect_chart_patterns(df, cur_idx)
        for b_pat in pattern_res.get("bull", []):
            bull_confluences.append(b_pat)
        for be_pat in pattern_res.get("bear", []):
            bear_confluences.append(be_pat)
        if pattern_res.get("note"):
            details.append(pattern_res["note"])

        # 3. FIBONACCI GOLDEN POCKET (0.50 - 0.618 RETRACEMENT)
        fib_res = self.detect_fibonacci_golden_pocket(df, cur_idx)
        for b_fib in fib_res.get("bull", []):
            bull_confluences.append(b_fib)
        for be_fib in fib_res.get("bear", []):
            bear_confluences.append(be_fib)
        if fib_res.get("note"):
            details.append(fib_res["note"])

        # 4. WAKTU LIKUIDITAS INSTITUSIONAL (ICT KILLZONES)
        kz_res = self.evaluate_killzone(df.index[cur_idx])
        if kz_res.get("confluence"):
            if kz_res.get("is_active"):
                details.append(kz_res["confluence"])

        # 5. BOLLINGER BANDS SQUEEZE & EXPANSION
        sq_res = self.detect_bb_squeeze(df, bb_upper, bb_lower, bb_basis, cur_idx)
        for b_sq in sq_res.get("bull", []):
            bull_confluences.append(b_sq)
        for be_sq in sq_res.get("bear", []):
            bear_confluences.append(be_sq)
        if sq_res.get("note"):
            details.append(sq_res["note"])

        summary_text = " | ".join(details) if details else "Advanced Technicals Standby"

        return {
            "bull_confluences": bull_confluences,
            "bear_confluences": bear_confluences,
            "details": details,
            "summary": summary_text,
            "killzone_info": kz_res,
        }

    # =========================================================================
    # 1. DIVERGENSI RSI
    # =========================================================================
    def detect_rsi_divergence(
        self, df: pd.DataFrame, rsi_series: pd.Series, cur_idx: int = -1
    ) -> Dict[str, Any]:
        """Detect Regular & Hidden RSI divergence across recent swings."""
        bull: List[str] = []
        bear: List[str] = []
        note = None

        close = df["Close"] if "Close" in df.columns else df["close"]
        low = df["Low"] if "Low" in df.columns else df["low"]
        high = df["High"] if "High" in df.columns else df["high"]

        # Evaluasi swing dalam 15 bar terakhir
        window = 15
        sub_close = close.iloc[-window:]
        sub_rsi = rsi_series.iloc[-window:]
        sub_low = low.iloc[-window:]
        sub_high = high.iloc[-window:]

        c_low = float(sub_low.iloc[-1])
        c_high = float(sub_high.iloc[-1])
        c_rsi = float(sub_rsi.iloc[-1])

        # Cari titik swing low lokal sebelum bar saat ini
        prior_lows = sub_low.iloc[:-2]
        if not prior_lows.empty:
            min_idx = prior_lows.idxmin()
            prev_swing_low = float(prior_lows.loc[min_idx])
            prev_swing_rsi = float(sub_rsi.loc[min_idx])

            # Regular Bullish Divergence: Harga buat Lower Low, tapi RSI buat Higher Low
            if c_low < prev_swing_low and c_rsi > prev_swing_rsi and c_rsi < 45.0:
                bull.append("Regular Bullish RSI Divergence (Exhaustion Reversal)")
                note = f"Bullish RSI Divergence (Price: {c_low:.5f} < {prev_swing_low:.5f}, RSI: {c_rsi:.1f} > {prev_swing_rsi:.1f})"

            # Hidden Bullish Divergence: Harga buat Higher Low, tapi RSI buat Lower Low (Kontinuasi Tren)
            elif c_low > prev_swing_low and c_rsi < prev_swing_rsi and c_rsi < 50.0:
                bull.append("Hidden Bullish RSI Divergence (Trend Continuation)")
                note = f"Hidden Bullish Divergence (Price HL, RSI LL: {c_rsi:.1f})"

        # Cari titik swing high lokal sebelum bar saat ini
        prior_highs = sub_high.iloc[:-2]
        if not prior_highs.empty:
            max_idx = prior_highs.idxmax()
            prev_swing_high = float(prior_highs.loc[max_idx])
            prev_swing_rsi = float(sub_rsi.loc[max_idx])

            # Regular Bearish Divergence: Harga buat Higher High, tapi RSI buat Lower High
            if c_high > prev_swing_high and c_rsi < prev_swing_rsi and c_rsi > 55.0:
                bear.append("Regular Bearish RSI Divergence (Exhaustion Reversal)")
                note = f"Bearish RSI Divergence (Price: {c_high:.5f} > {prev_swing_high:.5f}, RSI: {c_rsi:.1f} < {prev_swing_rsi:.1f})"

            # Hidden Bearish Divergence: Harga buat Lower High, tapi RSI buat Higher High (Kontinuasi Tren)
            elif c_high < prev_swing_high and c_rsi > prev_swing_rsi and c_rsi > 50.0:
                bear.append("Hidden Bearish RSI Divergence (Trend Continuation)")
                note = f"Hidden Bearish Divergence (Price LH, RSI HH: {c_rsi:.1f})"

        return {"bull": bull, "bear": bear, "note": note}

    # =========================================================================
    # 2. POLA GRAFIK GEOMETRIS KLASIK
    # =========================================================================
    def detect_chart_patterns(self, df: pd.DataFrame, cur_idx: int = -1) -> Dict[str, Any]:
        """Detect Head and Shoulders, Bull/Bear Flags, and Triangles."""
        bull: List[str] = []
        bear: List[str] = []
        notes: List[str] = []

        close = df["Close"] if "Close" in df.columns else df["close"]
        high = df["High"] if "High" in df.columns else df["high"]
        low = df["Low"] if "Low" in df.columns else df["low"]
        open_p = df["Open"] if "Open" in df.columns else df["open"]

        c_close = float(close.iloc[cur_idx])
        c_open = float(open_p.iloc[cur_idx])
        c_high = float(high.iloc[cur_idx])
        c_low = float(low.iloc[cur_idx])

        # A. Head and Shoulders (H&S) & Inverse H&S (3 Swings over last 12-16 bars)
        if len(df) >= 16:
            p2_h = float(high.iloc[cur_idx - 2])
            p4_h = float(high.iloc[cur_idx - 4])
            p6_h = float(high.iloc[cur_idx - 6])

            # Head (p4_h) harus puncak tertinggi di atas bahu kiri (p6_h) dan bahu kanan (p2_h / c_high)
            is_hs = (p4_h > p6_h) and (p4_h > p2_h) and abs(p6_h - p2_h) <= (p4_h - p6_h) * 0.40 and (c_close < c_open)
            if is_hs:
                bear.append("Head and Shoulders Reversal")
                notes.append(f"Head and Shoulders (Head: {p4_h:.5f}, Shoulders: ~{p6_h:.5f})")

            p2_l = float(low.iloc[cur_idx - 2])
            p4_l = float(low.iloc[cur_idx - 4])
            p6_l = float(low.iloc[cur_idx - 6])

            # Inverse Head (p4_l) harus lembah terendah di bawah bahu kiri (p6_l) dan bahu kanan (p2_l / c_low)
            is_ihs = (p4_l < p6_l) and (p4_l < p2_l) and abs(p6_l - p2_l) <= (p6_l - p4_l) * 0.40 and (c_close > c_open)
            if is_ihs:
                bull.append("Inverse Head and Shoulders Reversal")
                notes.append(f"Inverse H&S (Head: {p4_l:.5f}, Shoulders: ~{p6_l:.5f})")

        # B. Bull Flag & Bear Flag (Impulse Pole + Corrective Channel Breakout)
        if len(df) >= 10:
            pole_start = float(close.iloc[cur_idx - 7])
            pole_end = float(close.iloc[cur_idx - 3])
            pole_move = pole_end - pole_start
            flag_lows = [float(low.iloc[cur_idx - i]) for i in (1, 2, 3)]
            flag_highs = [float(high.iloc[cur_idx - i]) for i in (1, 2, 3)]

            # Bull Flag: Kenaikan tajam (pole > 0), disusul koreksi dangkal menurun, lalu candle sekarang breakout hijau
            if pole_move > 0.0008 and min(flag_lows) >= pole_end - (pole_move * 0.45) and c_close > max(flag_highs) and c_close > c_open:
                bull.append("Bull Flag Breakout (High-Probability Continuation)")
                notes.append("Pola Bull Flag (Impulse + Konsolidasi Tipis)")

            # Bear Flag: Penurunan tajam (pole < 0), disusul koreksi dangkal menanjak, lalu candle sekarang breakdown merah
            elif pole_move < -0.0008 and max(flag_highs) <= pole_end - (pole_move * 0.45) and c_close < min(flag_lows) and c_close < c_open:
                bear.append("Bear Flag Breakdown (High-Probability Continuation)")
                notes.append("Pola Bear Flag (Drop Impulsif + Konsolidasi Tipis)")

        # C. Ascending & Descending Triangle
        if len(df) >= 12:
            highs_chunk = high.iloc[cur_idx - 8:cur_idx]
            lows_chunk = low.iloc[cur_idx - 8:cur_idx]
            max_h = float(highs_chunk.max())
            min_l = float(lows_chunk.min())

            # Ascending Triangle: Atap datar (selisih high tipis) dengan low meninggi
            is_flat_top = abs(float(highs_chunk.iloc[0]) - float(highs_chunk.iloc[-1])) <= 0.00015
            is_rising_lows = float(lows_chunk.iloc[-1]) > float(lows_chunk.iloc[0]) + 0.00020
            if is_flat_top and is_rising_lows and c_close >= max_h - 0.00010:
                bull.append("Ascending Triangle Pressure (Bullish Breakout Setup)")
                notes.append("Ascending Triangle Compression")

            # Descending Triangle: Lantai datar dengan high merendah
            is_flat_bottom = abs(float(lows_chunk.iloc[0]) - float(lows_chunk.iloc[-1])) <= 0.00015
            is_falling_highs = float(highs_chunk.iloc[-1]) < float(highs_chunk.iloc[0]) - 0.00020
            if is_flat_bottom and is_falling_highs and c_close <= min_l + 0.00010:
                bear.append("Descending Triangle Pressure (Bearish Breakdown Setup)")
                notes.append("Descending Triangle Compression")

        return {"bull": bull, "bear": bear, "note": " | ".join(notes) if notes else None}

    # =========================================================================
    # 3. FIBONACCI RETRACEMENT DINAMIS (GOLDEN POCKET 0.50 - 0.618)
    # =========================================================================
    def detect_fibonacci_golden_pocket(self, df: pd.DataFrame, cur_idx: int = -1) -> Dict[str, Any]:
        """Calculate dynamic Fibonacci retracement levels from the latest swing range."""
        bull: List[str] = []
        bear: List[str] = []
        note = None

        lookback = min(35, len(df))
        sub_df = df.iloc[-lookback:]
        high = sub_df["High"] if "High" in sub_df.columns else sub_df["high"]
        low = sub_df["Low"] if "Low" in sub_df.columns else sub_df["low"]
        close = df["Close"] if "Close" in df.columns else df["close"]

        swing_high = float(high.max())
        swing_low = float(low.min())
        curr_price = float(close.iloc[cur_idx])

        diff = swing_high - swing_low
        if diff < 0.0005:
            return {"bull": [], "bear": [], "note": None}

        # Level Retracement dari Swing Low ke Swing High (Bullish Retracement)
        fib_50 = swing_high - (0.50 * diff)
        fib_618 = swing_high - (0.618 * diff)
        # Golden Pocket Zone: antara fib_618 (bawah) dan fib_50 (atas)
        if fib_618 <= curr_price <= fib_50:
            bull.append("Fibonacci Golden Pocket 0.618 (Optimal Trade Entry)")
            note = f"Golden Pocket 0.50-0.618 Bullish ({fib_618:.5f} - {fib_50:.5f})"

        # Level Retracement dari Swing High ke Swing Low (Bearish Retracement / Rally in Downtrend)
        bear_fib_50 = swing_low + (0.50 * diff)
        bear_fib_618 = swing_low + (0.618 * diff)
        # Golden Pocket Zone untuk Sell: antara bear_fib_50 (bawah) dan bear_fib_618 (atas)
        if bear_fib_50 <= curr_price <= bear_fib_618:
            bear.append("Fibonacci Golden Pocket 0.618 (Optimal Bearish Rejection)")
            note = f"Golden Pocket 0.50-0.618 Bearish ({bear_fib_50:.5f} - {bear_fib_618:.5f})"

        return {"bull": bull, "bear": bear, "note": note}

    # =========================================================================
    # 4. WAKTU LIKUIDITAS INSTITUSIONAL (ICT KILLZONES)
    # =========================================================================
    def evaluate_killzone(self, timestamp: Any) -> Dict[str, Any]:
        """Evaluate whether current market time falls into high-liquidity ICT Killzones."""
        try:
            ts = pd.to_datetime(timestamp)
            # Konversi jam ke UTC
            utc_hour = ts.hour if getattr(ts, "tz", None) is None else ts.tz_convert("UTC").hour
            utc_minute = ts.minute
        except Exception:
            utc_hour = datetime.utcnow().hour
            utc_minute = datetime.utcnow().minute

        time_float = utc_hour + (utc_minute / 60.0)

        # 1. London Open Killzone: 07:00 - 10:00 UTC (14:00 - 17:00 WIB)
        if 7.0 <= time_float <= 10.0:
            return {
                "is_active": True,
                "session": "London Open Killzone",
                "confluence": "🏛️ Sesi Institusional: London Open Killzone (Likuiditas Tinggi)",
            }
        # 2. New York Open Killzone: 12.5 <= time <= 15.5 UTC (19:30 - 22:30 WIB)
        elif 12.5 <= time_float <= 15.5:
            return {
                "is_active": True,
                "session": "New York Open Killzone",
                "confluence": "🏛️ Sesi Institusional: New York Open Killzone (Volatilitas Puncak)",
            }
        # 3. Asian Session: 00:00 - 06:00 UTC (07:00 - 13:00 WIB)
        elif 0.0 <= time_float <= 6.0:
            return {
                "is_active": False,
                "session": "Asian Session",
                "confluence": "🌏 Sesi Asia (Konsolidasi & Akumulasi Likuiditas)",
            }
        else:
            return {
                "is_active": False,
                "session": "Normal Trading Hours",
                "confluence": "Sesi Perdagangan Reguler",
            }

    # =========================================================================
    # 5. BOLLINGER BANDS SQUEEZE & VOLATILITY EXPANSION
    # =========================================================================
    def detect_bb_squeeze(
        self,
        df: pd.DataFrame,
        bb_upper: pd.Series,
        bb_lower: pd.Series,
        bb_basis: pd.Series,
        cur_idx: int = -1
    ) -> Dict[str, Any]:
        """Detect Bollinger Band Squeeze (Energy Compression) and Breakout Expansion."""
        bull: List[str] = []
        bear: List[str] = []
        note = None

        close = df["Close"] if "Close" in df.columns else df["close"]
        bandwidth = (bb_upper - bb_lower) / (bb_basis + 1e-9)

        if len(bandwidth) < 20:
            return {"bull": [], "bear": [], "note": None}

        recent_bw = bandwidth.iloc[-20:]
        cur_bw = float(bandwidth.iloc[cur_idx])
        min_bw = float(recent_bw.min())

        is_squeeze = cur_bw <= (min_bw * 1.15)
        c_close = float(close.iloc[cur_idx])
        c_upper = float(bb_upper.iloc[cur_idx])
        c_lower = float(bb_lower.iloc[cur_idx])

        # Breakout setelah fase Squeeze
        prev_bw = float(bandwidth.iloc[cur_idx - 1])
        was_squeezed = prev_bw <= (min_bw * 1.20)

        if was_squeezed and c_close >= c_upper:
            bull.append("Bollinger Volatility Squeeze Breakout (Bullish Expansion)")
            note = f"BB Squeeze Breakout Bullish (BW: {cur_bw:.4f})"
        elif was_squeezed and c_close <= c_lower:
            bear.append("Bollinger Volatility Squeeze Breakdown (Bearish Expansion)")
            note = f"BB Squeeze Breakdown Bearish (BW: {cur_bw:.4f})"
        elif is_squeeze:
            note = f"Bollinger Squeeze Aktif (Kompresi Volatilitas: {cur_bw:.4f})"

        return {"bull": bull, "bear": bear, "note": note}


# Global singleton instance
advanced_technicals = AdvancedTechnicalsEngine()
