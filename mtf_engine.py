"""Multi-Timeframe (MTF) Alignment and Confirmation Engine.

Provides top-down multi-timeframe analysis (1H Macro Compass and 15m Intermediate Setup)
to confirm entries, eliminate low-probability noise, and ensure trading
in harmony with institutional order flow, ADX trend strength, and EMA stacking.
"""

from typing import Dict, Any, List, Optional, Tuple
import pandas as pd
import numpy as np


def calculate_adx(df: pd.DataFrame, period: int = 14) -> Tuple[float, float, float]:
    """Calculate Average Directional Index (ADX), +DI, and -DI using Wilder's smoothing.
    Returns: (adx_val, plus_di, minus_di)
    """
    if df is None or len(df) < period + 5:
        return 0.0, 0.0, 0.0

    high = df["High"] if "High" in df.columns else df["high"]
    low = df["Low"] if "Low" in df.columns else df["low"]
    close = df["Close"] if "Close" in df.columns else df["close"]

    tr1 = high - low
    tr2 = (high - close.shift(1)).abs()
    tr3 = (low - close.shift(1)).abs()
    tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)

    up_move = high - high.shift(1)
    down_move = low.shift(1) - low

    pos_dm = pd.Series(np.where((up_move > down_move) & (up_move > 0), up_move, 0.0), index=df.index)
    neg_dm = pd.Series(np.where((down_move > up_move) & (down_move > 0), down_move, 0.0), index=df.index)

    # Wilder's smoothing with alpha = 1 / period
    atr_series = tr.ewm(alpha=1.0 / period, adjust=False).mean()
    pos_di_series = 100.0 * (pos_dm.ewm(alpha=1.0 / period, adjust=False).mean() / (atr_series + 1e-9))
    neg_di_series = 100.0 * (neg_dm.ewm(alpha=1.0 / period, adjust=False).mean() / (atr_series + 1e-9))

    dx_series = 100.0 * ((pos_di_series - neg_di_series).abs() / ((pos_di_series + neg_di_series) + 1e-9))
    adx_series = dx_series.ewm(alpha=1.0 / period, adjust=False).mean()

    adx_val = float(adx_series.iloc[-1]) if not pd.isna(adx_series.iloc[-1]) else 0.0
    pos_di = float(pos_di_series.iloc[-1]) if not pd.isna(pos_di_series.iloc[-1]) else 0.0
    neg_di = float(neg_di_series.iloc[-1]) if not pd.isna(neg_di_series.iloc[-1]) else 0.0

    return round(adx_val, 2), round(pos_di, 2), round(neg_di, 2)


def calculate_normalized_slope(series: pd.Series, atr_val: float, bars: int = 5) -> float:
    """Calculate normalized slope of an indicator over the last N bars relative to ATR."""
    if len(series) < bars + 1 or atr_val <= 0:
        return 0.0
    delta = float(series.iloc[-1] - series.iloc[-bars - 1])
    return round(delta / (atr_val + 1e-9), 3)


class MultiTimeframeEngine:
    """Evaluates 1H and 15m timeframe market context with ADX and EMA Stacking."""

    def analyze_single_tf(self, df: pd.DataFrame, tf_name: str) -> Dict[str, Any]:
        """Calculate trend, momentum, ADX strength, and EMA stacking for a specific timeframe."""
        if df is None or len(df) < 25:
            return {
                "tf": tf_name,
                "valid": False,
                "bias": "Neutral",
                "trend": "Unknown",
                "adx": 0.0,
                "adx_regime": "No Data",
                "ema_stack": "Unknown",
                "slope_50": 0.0,
                "rsi": 50.0,
                "macd_status": "Neutral",
                "summary": f"{tf_name}: Data tidak cukup",
            }

        close = df["Close"] if "Close" in df.columns else df["close"]
        high = df["High"] if "High" in df.columns else df["high"]
        low = df["Low"] if "Low" in df.columns else df["low"]

        # 1. EMAs: 20, 50, 200
        ema20_s = close.ewm(span=20, adjust=False).mean()
        ema50_s = close.ewm(span=50, adjust=False).mean()
        ema200_s = close.ewm(span=200, adjust=False).mean() if len(close) >= 200 else ema50_s

        ema20 = float(ema20_s.iloc[-1])
        ema50 = float(ema50_s.iloc[-1])
        ema200 = float(ema200_s.iloc[-1])
        curr_close = float(close.iloc[-1])

        # 2. ATR (14) & Normalized Slope EMA 50
        tr1 = high - low
        tr2 = (high - close.shift(1)).abs()
        tr3 = (low - close.shift(1)).abs()
        tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
        atr_val = float(tr.rolling(14).mean().iloc[-1]) if len(df) >= 14 else 0.0010
        slope_50 = calculate_normalized_slope(ema50_s, atr_val, bars=5)

        # 3. ADX (14) Trend Strength
        adx_val, plus_di, minus_di = calculate_adx(df, period=14)
        is_trending = adx_val >= 20.0
        adx_desc = f"Trending (ADX {adx_val:.1f})" if is_trending else f"Choppy/Sideways (ADX {adx_val:.1f} < 20)"

        # 4. EMA Stacking
        is_bullish_stack = (ema20 > ema50) and (ema50 > ema200)
        is_bearish_stack = (ema20 < ema50) and (ema50 < ema200)
        if is_bullish_stack:
            stack_desc = "Bullish Stack (20 > 50 > 200)"
        elif is_bearish_stack:
            stack_desc = "Bearish Stack (20 < 50 < 200)"
        else:
            stack_desc = "Mixed/Entangled EMA"

        # 5. RSI (14)
        delta = close.diff()
        gain = delta.where(delta > 0, 0.0).rolling(14).mean()
        loss = (-delta.where(delta < 0, 0.0)).rolling(14).mean()
        rs = gain / (loss + 1e-9)
        rsi_series = 100.0 - (100.0 / (1.0 + rs))
        cur_rsi = float(rsi_series.iloc[-1]) if not pd.isna(rsi_series.iloc[-1]) else 50.0

        # 6. MACD (12, 26, 9)
        exp12 = close.ewm(span=12, adjust=False).mean()
        exp26 = close.ewm(span=26, adjust=False).mean()
        macd_line = exp12 - exp26
        signal_line = macd_line.ewm(span=9, adjust=False).mean()
        cur_macd = float(macd_line.iloc[-1])
        cur_signal = float(signal_line.iloc[-1])
        macd_bull = cur_macd > cur_signal

        # 7. Rigorous 3-Pillar Regime Determination
        # Bullish requires: Close > EMA200, (EMA Stacking or Slope >= +0.10), ADX >= 20, RSI >= 48, MACD Bullish
        is_above_ema200 = curr_close > ema200
        is_above_ema50 = curr_close > ema50

        if is_above_ema200 and (is_bullish_stack or slope_50 >= 0.10) and is_trending and cur_rsi >= 48.0 and macd_bull:
            bias = "Bullish"
        elif (not is_above_ema200) and (is_bearish_stack or slope_50 <= -0.10) and is_trending and cur_rsi <= 52.0 and (not macd_bull):
            bias = "Bearish"
        else:
            bias = "Neutral"

        trend_desc = "Uptrend (di atas EMA 200)" if is_above_ema200 else "Downtrend (di bawah EMA 200)"
        macd_desc = "MACD Bullish" if macd_bull else "MACD Bearish"

        return {
            "tf": tf_name,
            "valid": True,
            "bias": bias,
            "trend": trend_desc,
            "adx": adx_val,
            "plus_di": plus_di,
            "minus_di": minus_di,
            "adx_regime": adx_desc,
            "is_trending": is_trending,
            "is_bullish_stack": is_bullish_stack,
            "is_bearish_stack": is_bearish_stack,
            "ema_stack": stack_desc,
            "slope_50": slope_50,
            "rsi": round(cur_rsi, 1),
            "macd_status": macd_desc,
            "macd_bull": macd_bull,
            "is_above_ema200": is_above_ema200,
            "close": curr_close,
            "ema20": ema20,
            "ema50": ema50,
            "ema200": ema200,
            "summary": f"{tf_name}: {bias} ({stack_desc}, {adx_desc}, Slope: {slope_50:+.2f}, RSI {cur_rsi:.1f})",
        }

    def evaluate_mtf_confluence(
        self,
        df_15m: Optional[pd.DataFrame],
        df_1h: Optional[pd.DataFrame] = None,
        candidate_action: str = "BUY",
    ) -> Dict[str, Any]:
        """Evaluate top-down trend & momentum alignment using 1H Macro Compass and 15m Intermediate Setup."""
        res_15m = self.analyze_single_tf(df_15m, "15m") if df_15m is not None else {"valid": False, "bias": "Neutral"}
        res_1h = self.analyze_single_tf(df_1h, "1h") if df_1h is not None else {"valid": False, "bias": "Neutral"}

        if not res_15m.get("valid", False):
            return {
                "is_allowed": True,
                "contradiction_reason": None,
                "confluences": [],
                "bias_15m": "Neutral",
                "bias_1h": res_1h.get("bias", "Neutral"),
                "details_15m": res_15m,
                "details_1h": res_1h,
                "summary": "MTF Matrix -> [15m: Standby]",
            }

        bias_15 = res_15m.get("bias", "Neutral")
        bias_1h = res_1h.get("bias", "Neutral") if res_1h.get("valid", False) else "Neutral"
        macd_bull_15 = res_15m.get("macd_bull", False)
        rsi_15 = res_15m.get("rsi", 50.0)
        is_trending_15 = res_15m.get("is_trending", False)

        mtf_confluences: List[str] = []
        is_allowed = True
        is_neutral_bias = (bias_15 == "Neutral")
        contradiction_reason = None

        act_upper = candidate_action.upper()

        if "BUY" in act_upper:
            # 1. Hard Veto Tren 15m Bearish
            if bias_15 == "Bearish":
                is_allowed = False
                contradiction_reason = "Kontradiksi MTF: Timeframe 15m Bearish di bawah EMA 200 (Dilarang BUY melawan tren mayor 15m)"
            # 1b. Hard Veto Macro 1H Bearish jika data 1H valid
            elif res_1h.get("valid", False) and bias_1h == "Bearish":
                is_allowed = False
                contradiction_reason = "Kontradiksi MTF: Timeframe 1H Macro Bearish (Dilarang BUY melawan arus makro 1H)"
            # 1c. Hard Veto MTF Overbought Ekstrem: RSI 15m >= 78.0
            elif rsi_15 >= 78.0:
                is_allowed = False
                contradiction_reason = f"Kontradiksi MTF: RSI 15m Overbought Ekstrem ({rsi_15:.1f} >= 78.0, Dilarang BUY di area pucuk 15m)"
            # 2. Konfluensi Grade-A Bullish
            elif bias_15 == "Bullish" and macd_bull_15:
                mtf_confluences.append("Konfluensi MTF Grade-A (15m Bullish Stacking + ADX Trend)")
                if res_1h.get("valid", False) and bias_1h == "Bullish":
                    mtf_confluences.append("Konfluensi Makro 1H Searah Bullish")

        elif "SELL" in act_upper:
            # 1. Hard Veto Tren 15m Bullish
            if bias_15 == "Bullish":
                is_allowed = False
                contradiction_reason = "Kontradiksi MTF: Timeframe 15m Bullish di atas EMA 200 (Dilarang SELL melawan tren mayor 15m)"
            # 1b. Hard Veto Macro 1H Bullish jika data 1H valid
            elif res_1h.get("valid", False) and bias_1h == "Bullish":
                is_allowed = False
                contradiction_reason = "Kontradiksi MTF: Timeframe 1H Macro Bullish (Dilarang SELL melawan arus makro 1H)"
            # 1c. Hard Veto MTF Oversold Ekstrem: RSI 15m <= 22.0
            elif rsi_15 <= 22.0:
                is_allowed = False
                contradiction_reason = f"Kontradiksi MTF: RSI 15m Oversold Ekstrem ({rsi_15:.1f} <= 22.0, Dilarang SELL di area dasar 15m)"
            # 2. Konfluensi Grade-A Bearish
            elif bias_15 == "Bearish" and not macd_bull_15:
                mtf_confluences.append("Konfluensi MTF Grade-A (15m Bearish Stacking + ADX Trend)")
                if res_1h.get("valid", False) and bias_1h == "Bearish":
                    mtf_confluences.append("Konfluensi Makro 1H Searah Bearish")

        summary_parts = [f"15m: {bias_15}"]
        if res_1h.get("valid", False):
            summary_parts.append(f"1H: {bias_1h}")
        summary_text = f"MTF Matrix -> [{', '.join(summary_parts)} | ADX 15m: {res_15m.get('adx', 0.0)}]"

        return {
            "is_allowed": is_allowed,
            "is_neutral_bias": is_neutral_bias,
            "contradiction_reason": contradiction_reason,
            "confluences": mtf_confluences,
            "bias_15m": bias_15,
            "bias_1h": bias_1h,
            "details_15m": res_15m,
            "details_1h": res_1h,
            "summary": summary_text,
        }


# Global singleton instance
mtf_engine = MultiTimeframeEngine()
