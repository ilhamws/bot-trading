"""Multi-Timeframe (MTF) Alignment and Confirmation Engine.

Provides intermediate timeframe analysis on 15m
to confirm entries, eliminate low-probability noise, and ensure trading
in harmony with intermediate timeframe order flow.
"""

from typing import Dict, Any, List, Optional, Tuple
import pandas as pd
import numpy as np


class MultiTimeframeEngine:
    """Evaluates 15m intermediate timeframe market context."""

    def analyze_single_tf(self, df: pd.DataFrame, tf_name: str) -> Dict[str, Any]:
        """Calculate trend, momentum, and key levels for a specific timeframe."""
        if df is None or len(df) < 25:
            return {
                "tf": tf_name,
                "valid": False,
                "bias": "Neutral",
                "trend": "Unknown",
                "rsi": 50.0,
                "macd_status": "Neutral",
                "summary": f"{tf_name}: Data tidak cukup",
            }

        close = df["Close"] if "Close" in df.columns else df["close"]
        high = df["High"] if "High" in df.columns else df["high"]
        low = df["Low"] if "Low" in df.columns else df["low"]

        # 1. EMAs: 20, 50, 200
        ema20 = float(close.ewm(span=20, adjust=False).mean().iloc[-1])
        ema50 = float(close.ewm(span=50, adjust=False).mean().iloc[-1])
        ema200 = float(close.ewm(span=200, adjust=False).mean().iloc[-1]) if len(close) >= 200 else ema50

        curr_close = float(close.iloc[-1])

        # 2. RSI (14)
        delta = close.diff()
        gain = delta.where(delta > 0, 0.0).rolling(14).mean()
        loss = (-delta.where(delta < 0, 0.0)).rolling(14).mean()
        rs = gain / (loss + 1e-9)
        rsi_series = 100.0 - (100.0 / (1.0 + rs))
        cur_rsi = float(rsi_series.iloc[-1]) if not pd.isna(rsi_series.iloc[-1]) else 50.0

        # 3. MACD (12, 26, 9)
        exp12 = close.ewm(span=12, adjust=False).mean()
        exp26 = close.ewm(span=26, adjust=False).mean()
        macd_line = exp12 - exp26
        signal_line = macd_line.ewm(span=9, adjust=False).mean()
        cur_macd = float(macd_line.iloc[-1])
        cur_signal = float(signal_line.iloc[-1])

        # Bias determination
        is_above_ema200 = curr_close > ema200
        is_above_ema50 = curr_close > ema50
        macd_bull = cur_macd > cur_signal

        bull_score = 0
        bear_score = 0

        if is_above_ema200:
            bull_score += 2
        else:
            bear_score += 2

        if is_above_ema50:
            bull_score += 1
        else:
            bear_score += 1

        if macd_bull:
            bull_score += 1
        else:
            bear_score += 1

        if cur_rsi >= 50.0:
            bull_score += 1
        else:
            bear_score += 1

        if bull_score >= 4:
            bias = "Bullish"
        elif bear_score >= 4:
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
            "rsi": round(cur_rsi, 1),
            "macd_status": macd_desc,
            "close": curr_close,
            "ema200": ema200,
            "ema50": ema50,
            "summary": f"{tf_name}: {bias} ({trend_desc}, {macd_desc}, RSI {cur_rsi:.1f})",
        }

    def evaluate_mtf_confluence(
        self,
        df_15m: Optional[pd.DataFrame],
        df_30m: Optional[pd.DataFrame] = None,
        candidate_action: str = "BUY",
    ) -> Dict[str, Any]:
        """Evaluate intermediate trend alignment using exclusively the 15m timeframe."""
        res_15m = self.analyze_single_tf(df_15m, "15m") if df_15m is not None else {"valid": False, "bias": "Neutral"}
        bias_15 = res_15m.get("bias", "Neutral")

        mtf_confluences: List[str] = []
        is_allowed = True
        contradiction_reason = None

        if "BUY" in candidate_action.upper():
            if bias_15 == "Bearish":
                is_allowed = False
                contradiction_reason = "Kontradiksi MTF: Timeframe 15m Bearish kuat di bawah EMA 200 (Dilarang BUY melawan tren mayor 15m)"
            elif bias_15 == "Bullish":
                mtf_confluences.append("Konfluensi MTF Grade-A (15m Searah Bullish)")

        elif "SELL" in candidate_action.upper():
            if bias_15 == "Bullish":
                is_allowed = False
                contradiction_reason = "Kontradiksi MTF: Timeframe 15m Bullish kuat di atas EMA 200 (Dilarang SELL melawan tren mayor 15m)"
            elif bias_15 == "Bearish":
                mtf_confluences.append("Konfluensi MTF Grade-A (15m Searah Bearish)")

        summary_text = f"MTF Matrix -> [{res_15m.get('summary', '15m: N/A')}]"

        return {
            "is_allowed": is_allowed,
            "contradiction_reason": contradiction_reason,
            "confluences": mtf_confluences,
            "bias_15m": bias_15,
            "details_15m": res_15m,
            "summary": summary_text,
        }


# Global singleton instance
mtf_engine = MultiTimeframeEngine()
