"""Smart Money Concepts (SMC) & ICT Quantitative Analysis Engine.

Detects institutional footprints: Fair Value Gaps (FVG), Order Blocks (OB),
Break of Structure (BOS), Change of Character (CHoCH), Liquidity Sweeps,
and calculates dynamic volatility metrics (ATR).
"""

from typing import Dict, Any, List, Optional, Tuple
import os
import json
import pandas as pd
import numpy as np

try:
    from smartmoneyconcepts import smc
    HAS_SMC_LIB = True
except ImportError:
    HAS_SMC_LIB = False


def calculate_atr(df: pd.DataFrame, period: int = 14) -> pd.Series:
    """Calculate Average True Range (ATR) with RMA/Wilder smoothing."""
    high = df["High"] if "High" in df.columns else df["high"]
    low = df["Low"] if "Low" in df.columns else df["low"]
    close = df["Close"] if "Close" in df.columns else df["close"]

    prev_close = close.shift(1)
    tr1 = high - low
    tr2 = (high - prev_close).abs()
    tr3 = (low - prev_close).abs()
    tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)

    atr = tr.ewm(alpha=1.0 / period, adjust=False).mean()
    return atr


def get_asset_min_sl_floor(symbol: str, curr_price: float = 0.0) -> float:
    """Calculate asset-specific minimum Stop Loss floor to prevent premature stop-outs.
    - XAUUSD / GOLD: min $3.50 (35.0 pips / 350 points)
    - GBPJPY ("The Beast"): min 0.120 (12.0 pips)
    - EURJPY & other JPY crosses: min 0.090 (9.0 pips)
    - USDJPY: min 0.075 (7.5 pips)
    - GBPUSD, EURGBP: min 0.00070 (7.0 pips)
    - Major forex (EURUSD, AUDUSD, USDCAD, USDCHF, NZDUSD): min 0.00060 (6.0 pips)
    - Crypto (BTC/ETH): min $250.0 / $15.0
    """
    sym = str(symbol or "").upper()
    if "XAU" in sym or "GOLD" in sym or (curr_price >= 1500.0 and curr_price <= 5000.0):
        return 3.50
    if "GBPJPY" in sym:
        return 0.120
    if "JPY" in sym:
        if "USDJPY" in sym:
            return 0.075
        return 0.090  # EURJPY, AUDJPY, CADJPY, etc.
    if "GBP" in sym:
        return 0.00070  # GBPUSD, EURGBP
    if "BTC" in sym:
        return 250.0
    if "ETH" in sym:
        return 15.0
    return 0.00060  # Default majors (EURUSD, USDCAD, AUDUSD, NZDUSD, USDCHF)


class SMCEngine:
    """Quantitative SMC detector integrating ICT institutional mechanics."""

    def __init__(self, swing_length: int = 5, manual_levels_file: Optional[str] = None) -> None:
        self.swing_length = swing_length
        self.manual_levels_file = manual_levels_file or os.path.join(
            os.path.dirname(os.path.abspath(__file__)), "manual_levels.json"
        )
        self.manual_levels: Dict[str, List[float]] = {}
        self._last_mtime: float = 0.0
        self.load_manual_levels()

    def load_manual_levels(self) -> None:
        """Load or refresh manual support/resistance levels from JSON."""
        if not os.path.exists(self.manual_levels_file):
            return
        try:
            mtime = os.path.getmtime(self.manual_levels_file)
            if mtime > self._last_mtime:
                with open(self.manual_levels_file, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    self.manual_levels = {str(k).upper(): [float(x) for x in v] for k, v in data.items()}
                self._last_mtime = mtime
        except Exception:
            pass

    def get_manual_levels(self, symbol: Optional[str] = None) -> List[float]:
        """Get manual levels for symbol (case-insensitive) plus general levels."""
        self.load_manual_levels()
        if not symbol:
            all_lvls: List[float] = []
            for lvls in self.manual_levels.values():
                all_lvls.extend(lvls)
            return sorted(list(set(all_lvls)))

        sym_clean = symbol.upper().replace("/", "").replace("_", "")
        for k, v in self.manual_levels.items():
            if k.upper().replace("/", "").replace("_", "") == sym_clean:
                return [float(x) for x in v]
        return []

    def _find_nearest_resistance(
        self,
        df_norm: pd.DataFrame,
        curr_price: float,
        unmit_bear_fvg: Optional[pd.DataFrame] = None,
        unmit_bear_ob: Optional[pd.DataFrame] = None,
        cur_idx: int = -1,
        symbol: Optional[str] = None,
    ) -> Optional[float]:
        """Find the nearest structural resistance level above curr_price."""
        levels: List[float] = []

        # 0. User Defined Manual Key Levels
        for lvl in self.get_manual_levels(symbol):
            if lvl > curr_price:
                levels.append(lvl)

        # 1. Fractal Swing Highs (3-bar fractal over last 40 bars)
        highs = df_norm["high"]
        n = len(df_norm)
        end_idx = n if cur_idx == -1 else (cur_idx if cur_idx >= 0 else n + cur_idx)
        start_idx = max(3, end_idx - 40)

        for i in range(start_idx, end_idx - 1):
            if (
                highs.iloc[i] > highs.iloc[i - 1]
                and highs.iloc[i] > highs.iloc[i - 2]
                and highs.iloc[i] > highs.iloc[i - 3]
                and highs.iloc[i] >= highs.iloc[i + 1]
            ):
                lvl = float(highs.iloc[i])
                if lvl > curr_price:
                    levels.append(lvl)

        # 2. Bearish FVG Bottoms (unmitigated)
        if unmit_bear_fvg is not None and not unmit_bear_fvg.empty:
            for _, row in unmit_bear_fvg.iterrows():
                b = float(row["Bottom"])
                if b > curr_price:
                    levels.append(b)

        # 3. Bearish Order Block Bottoms (unmitigated)
        if unmit_bear_ob is not None and not unmit_bear_ob.empty:
            for _, row in unmit_bear_ob.iterrows():
                b = float(row["Bottom"])
                if b > curr_price:
                    levels.append(b)

        return min(levels) if levels else None

    def _find_nearest_support(
        self,
        df_norm: pd.DataFrame,
        curr_price: float,
        unmit_bull_fvg: Optional[pd.DataFrame] = None,
        unmit_bull_ob: Optional[pd.DataFrame] = None,
        cur_idx: int = -1,
        symbol: Optional[str] = None,
    ) -> Optional[float]:
        """Find the nearest structural support level below curr_price."""
        levels: List[float] = []

        # 0. User Defined Manual Key Levels
        for lvl in self.get_manual_levels(symbol):
            if lvl < curr_price:
                levels.append(lvl)

        # 1. Fractal Swing Lows (3-bar fractal over last 40 bars)
        lows = df_norm["low"]
        n = len(df_norm)
        end_idx = n if cur_idx == -1 else (cur_idx if cur_idx >= 0 else n + cur_idx)
        start_idx = max(3, end_idx - 40)

        for i in range(start_idx, end_idx - 1):
            if (
                lows.iloc[i] < lows.iloc[i - 1]
                and lows.iloc[i] < lows.iloc[i - 2]
                and lows.iloc[i] < lows.iloc[i - 3]
                and lows.iloc[i] <= lows.iloc[i + 1]
            ):
                lvl = float(lows.iloc[i])
                if lvl < curr_price:
                    levels.append(lvl)

        # 2. Bullish FVG Tops (unmitigated)
        if unmit_bull_fvg is not None and not unmit_bull_fvg.empty:
            for _, row in unmit_bull_fvg.iterrows():
                t = float(row["Top"])
                if t < curr_price:
                    levels.append(t)

        # 3. Bullish Order Block Tops (unmitigated)
        if unmit_bull_ob is not None and not unmit_bull_ob.empty:
            for _, row in unmit_bull_ob.iterrows():
                t = float(row["Top"])
                if t < curr_price:
                    levels.append(t)

        return max(levels) if levels else None

    def analyze(self, df: pd.DataFrame, cur_idx: int = -1, symbol: Optional[str] = None) -> Dict[str, Any]:
        """Run comprehensive SMC and ATR analysis on OHLCV DataFrame."""
        if len(df) < 25:
            return {
                "has_smc": False,
                "atr": 0.0010,
                "atr_pips": 10.0,
                "bull_confluences": [],
                "bear_confluences": [],
                "summary": "Data insufficient for SMC",
            }

        # Normalize column names to lowercase required by smc library
        df_norm = df.copy()
        df_norm.columns = [col.lower() for col in df_norm.columns]
        if "volume" not in df_norm.columns:
            df_norm["volume"] = 100.0

        # 1. Dynamic ATR Calculation
        atr_series = calculate_atr(df_norm, period=14)
        atr_val = float(atr_series.iloc[cur_idx]) if not pd.isna(atr_series.iloc[cur_idx]) else 0.0010
        
        # Pips conversion (e.g. 0.0001 = 1 pip for standard forex, 0.01 for JPY, 0.10 for Gold)
        curr_price = float(df_norm["close"].iloc[cur_idx])
        is_jpy = curr_price > 50.0 and curr_price < 500.0
        is_gold = curr_price >= 1500.0 and curr_price <= 5000.0
        is_crypto = curr_price > 5000.0
        if is_gold:
            pip_unit = 0.10  # 1 pip emas = $0.10 ($1 = 10 pips)
        elif is_crypto:
            pip_unit = 1.00
        elif is_jpy:
            pip_unit = 0.01
        else:
            pip_unit = 0.0001
        atr_pips = round(atr_val / pip_unit, 1)

        bull_confluences: List[str] = []
        bear_confluences: List[str] = []
        smc_details: List[str] = []

        unmit_bull_fvg = None
        unmit_bear_fvg = None
        unmit_bull_ob = None
        unmit_bear_ob = None

        # 2. SMC Library Calculations
        if HAS_SMC_LIB:
            try:
                # A. Fair Value Gaps (FVG)
                fvg_res = smc.fvg(df_norm, join_consecutive=False)
                # Check recent unmitigated FVGs within last 15 bars
                recent_fvg = fvg_res.iloc[-15:]
                unmit_bull_fvg = recent_fvg[(recent_fvg["FVG"] == 1) & (recent_fvg["MitigatedIndex"] == 0)]
                unmit_bear_fvg = recent_fvg[(recent_fvg["FVG"] == -1) & (recent_fvg["MitigatedIndex"] == 0)]

                # Check if current price is testing/inside an unmitigated FVG
                c_low = float(df_norm["low"].iloc[cur_idx])
                c_high = float(df_norm["high"].iloc[cur_idx])

                for _, row in unmit_bull_fvg.iterrows():
                    top = row["Top"]
                    bottom = row["Bottom"]
                    if bottom <= c_low <= top or bottom <= curr_price <= top:
                        bull_confluences.append("Bullish FVG Retest (Unmitigated)")
                        smc_details.append(f"Bullish FVG Zone: {bottom:.5f}-{top:.5f}")
                        break

                for _, row in unmit_bear_fvg.iterrows():
                    top = row["Top"]
                    bottom = row["Bottom"]
                    if bottom <= c_high <= top or bottom <= curr_price <= top:
                        bear_confluences.append("Bearish FVG Retest (Unmitigated)")
                        smc_details.append(f"Bearish FVG Zone: {bottom:.5f}-{top:.5f}")
                        break

                # B. Swings, Order Blocks & BOS/CHoCH
                swings = smc.swing_highs_lows(df_norm, swing_length=self.swing_length)
                
                # Order Blocks
                ob_res = smc.ob(df_norm, swings)
                recent_ob = ob_res.iloc[-20:]
                unmit_bull_ob = recent_ob[(recent_ob["OB"] == 1) & (recent_ob["MitigatedIndex"] == 0)]
                unmit_bear_ob = recent_ob[(recent_ob["OB"] == -1) & (recent_ob["MitigatedIndex"] == 0)]

                for _, row in unmit_bull_ob.iterrows():
                    top = row["Top"]
                    bottom = row["Bottom"]
                    if bottom <= curr_price <= top or abs(curr_price - top) <= (atr_val * 0.3):
                        bull_confluences.append("Institutional Bullish Order Block")
                        smc_details.append(f"Bullish OB Zone: {bottom:.5f}-{top:.5f}")
                        break

                for _, row in unmit_bear_ob.iterrows():
                    top = row["Top"]
                    bottom = row["Bottom"]
                    if bottom <= curr_price <= top or abs(curr_price - bottom) <= (atr_val * 0.3):
                        bear_confluences.append("Institutional Bearish Order Block")
                        smc_details.append(f"Bearish OB Zone: {bottom:.5f}-{top:.5f}")
                        break

                # Breaker Blocks (Violated Order Blocks Flipped into Support / Resistance - ICT Failed Auction)
                breached_bear_ob = recent_ob[(recent_ob["OB"] == -1) & (recent_ob["MitigatedIndex"] != 0)]
                breached_bull_ob = recent_ob[(recent_ob["OB"] == 1) & (recent_ob["MitigatedIndex"] != 0)]

                for _, row in breached_bear_ob.iterrows():
                    top = row["Top"]
                    bottom = row["Bottom"]
                    # Former Bearish OB broken upwards -> now acts as Bullish Breaker Support
                    if (bottom <= curr_price <= top) or abs(curr_price - top) <= (atr_val * 0.35):
                        bull_confluences.append("Bullish Breaker Block Retest (Failed Supply Flip)")
                        smc_details.append(f"Bullish Breaker Zone: {bottom:.5f}-{top:.5f}")
                        break

                for _, row in breached_bull_ob.iterrows():
                    top = row["Top"]
                    bottom = row["Bottom"]
                    # Former Bullish OB broken downwards -> now acts as Bearish Breaker Resistance
                    if (bottom <= curr_price <= top) or abs(curr_price - bottom) <= (atr_val * 0.35):
                        bear_confluences.append("Bearish Breaker Block Retest (Failed Demand Flip)")
                        smc_details.append(f"Bearish Breaker Zone: {bottom:.5f}-{top:.5f}")
                        break

                # BOS & CHoCH Market Structure
                bc_res = smc.bos_choch(df_norm, swings)
                recent_bc = bc_res.iloc[-10:]
                last_choch = recent_bc[recent_bc["CHOCH"] != 0]
                if not last_choch.empty:
                    choch_val = last_choch.iloc[-1]["CHOCH"]
                    if choch_val == 1:
                        bull_confluences.append("Bullish CHoCH (Structure Shift)")
                    elif choch_val == -1:
                        bear_confluences.append("Bearish CHoCH (Structure Shift)")

                last_bos = recent_bc[recent_bc["BOS"] != 0]
                if not last_bos.empty:
                    bos_val = last_bos.iloc[-1]["BOS"]
                    if bos_val == 1:
                        bull_confluences.append("Bullish BOS (Trend Expansion)")
                    elif bos_val == -1:
                        bear_confluences.append("Bearish BOS (Trend Expansion)")

                # Liquidity Sweeps
                liq_res = smc.liquidity(df_norm, swings)
                recent_liq = liq_res.iloc[-10:]
                sweeps = recent_liq[recent_liq["Swept"] != 0]
                if not sweeps.empty:
                    sweep_val = sweeps.iloc[-1]["Liquidity"]
                    if sweep_val == 1:
                        bear_confluences.append("Buy-side Liquidity Sweep (BSL)")
                    elif sweep_val == -1:
                        bull_confluences.append("Sell-side Liquidity Sweep (SSL)")

            except Exception as e:
                smc_details.append(f"SMC calculation notice: {e}")

        # 3. Dynamic ATR & Adaptive S/R Target Calculations (Asset-Specific Minimum SL Floor)
        min_sl_floor = get_asset_min_sl_floor(symbol, curr_price)
        sl_distance = max(atr_val * 1.5, min_sl_floor)
        default_tp_dist = round(sl_distance * 1.5, 5)
        buffer = 1.0 * pip_unit  # 1.0 pip front-running buffer

        # A. BUY TP: Evaluasi Resistance Terdekat
        buy_sl = round(curr_price - sl_distance, 5)
        nearest_res = self._find_nearest_resistance(df_norm, curr_price, unmit_bear_fvg, unmit_bear_ob, cur_idx, symbol=symbol)
        buy_tp_mode = "Default 1.5x SL"
        if nearest_res is not None and nearest_res > curr_price + buffer:
            raw_res_dist = nearest_res - curr_price
            front_run_res_dist = raw_res_dist - buffer
            rr_res = front_run_res_dist / sl_distance
            is_manual_res = nearest_res in self.get_manual_levels(symbol)
            source_tag = " (Manual)" if is_manual_res else ""
            # Zona Ideal (R:R 1.25x - 1.85x): Geser TP ke Resistance
            if 1.25 <= rr_res <= 1.85:
                buy_tp = round(curr_price + front_run_res_dist, 5)
                buy_tp_mode = f"Adaptive Resistance{source_tag} ({nearest_res:.5f}, R:R 1:{rr_res:.2f})"
                smc_details.append(f"TP BUY dialihkan ke Resistance{source_tag}: {nearest_res:.5f} (R:R 1:{rr_res:.2f})")
            else:
                buy_tp = round(curr_price + default_tp_dist, 5)
                if rr_res < 1.25:
                    smc_details.append(f"Resistance terdekat{source_tag} terlalu dekat ({nearest_res:.5f}, R:R 1:{rr_res:.2f}) -> Kunci TP Default 1.5x")
        else:
            buy_tp = round(curr_price + default_tp_dist, 5)

        # B. SELL TP: Evaluasi Support Terdekat
        sell_sl = round(curr_price + sl_distance, 5)
        nearest_sup = self._find_nearest_support(df_norm, curr_price, unmit_bull_fvg, unmit_bull_ob, cur_idx, symbol=symbol)
        sell_tp_mode = "Default 1.5x SL"
        if nearest_sup is not None and nearest_sup < curr_price - buffer:
            raw_sup_dist = curr_price - nearest_sup
            front_run_sup_dist = raw_sup_dist - buffer
            rr_sup = front_run_sup_dist / sl_distance
            is_manual_sup = nearest_sup in self.get_manual_levels(symbol)
            source_tag = " (Manual)" if is_manual_sup else ""
            # Zona Ideal (R:R 1.25x - 1.85x): Geser TP ke Support
            if 1.25 <= rr_sup <= 1.85:
                sell_tp = round(curr_price - front_run_sup_dist, 5)
                sell_tp_mode = f"Adaptive Support{source_tag} ({nearest_sup:.5f}, R:R 1:{rr_sup:.2f})"
                smc_details.append(f"TP SELL dialihkan ke Support{source_tag}: {nearest_sup:.5f} (R:R 1:{rr_sup:.2f})")
            else:
                sell_tp = round(curr_price - default_tp_dist, 5)
                if rr_sup < 1.25:
                    smc_details.append(f"Support terdekat{source_tag} terlalu dekat ({nearest_sup:.5f}, R:R 1:{rr_sup:.2f}) -> Kunci TP Default 1.5x")
        else:
            sell_tp = round(curr_price - default_tp_dist, 5)

        summary_parts = []
        if bull_confluences:
            summary_parts.append(f"SMC Bull: {', '.join(bull_confluences)}")
        if bear_confluences:
            summary_parts.append(f"SMC Bear: {', '.join(bear_confluences)}")
        summary_parts.append(f"ATR(14): {atr_pips} pips ({atr_val:.5f})")

        return {
            "has_smc": True,
            "atr_val": atr_val,
            "atr_pips": atr_pips,
            "buy_sl": buy_sl,
            "buy_tp": buy_tp,
            "sell_sl": sell_sl,
            "sell_tp": sell_tp,
            "buy_tp_mode": buy_tp_mode,
            "sell_tp_mode": sell_tp_mode,
            "bull_confluences": bull_confluences,
            "bear_confluences": bear_confluences,
            "details": smc_details,
            "summary": " | ".join(summary_parts),
        }


# Global singleton instance
smc_engine = SMCEngine()
