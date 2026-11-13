"""Standalone real-time market scanner with Bollinger Bands, MACD, and Candlestick detection.

Zero-cost alternative that scans live Forex & Stocks without needing a paid TradingView account.
"""

import argparse
import asyncio
from datetime import datetime
from typing import List, Dict, Any, Optional, Tuple
import io
import contextlib
import logging
from typing import List, Dict, Any, Optional
import requests
from requests.adapters import HTTPAdapter
import pandas as pd
import yfinance as yf

from config import settings, logger
from rag_engine import RAGEngine, normalize_timeframe, TIMEFRAME_SL_TP_CONFIG
from telegram_notifier import TelegramNotifier
from news_filter import news_filter
from smc_engine import smc_engine
from mtf_engine import mtf_engine
from signal_tracker import signal_tracker
from advanced_technicals import advanced_technicals
import mt5_executor

# Suppress noisy internal yfinance parser warnings
logging.getLogger("yfinance").setLevel(logging.CRITICAL)


class TimeoutHTTPAdapter(HTTPAdapter):
    """Ensure HTTP requests never hang indefinitely."""
    def __init__(self, timeout: int = 10, *args: Any, **kwargs: Any) -> None:
        self.timeout = timeout
        super().__init__(*args, **kwargs)

    def send(self, request: Any, **kwargs: Any) -> Any:
        kwargs.setdefault("timeout", self.timeout)
        return super().send(request, **kwargs)


# Standard symbol mappings for YFinance
YF_SYMBOL_MAP = {
    "EURUSD": "EURUSD=X",
    "GBPUSD": "GBPUSD=X",
    "USDJPY": "USDJPY=X",
    "AUDUSD": "AUDUSD=X",
    "USDCAD": "USDCAD=X",
    "USDCHF": "USDCHF=X",
    "NZDUSD": "NZDUSD=X",
    "EURGBP": "EURGBP=X",
    "EURJPY": "EURJPY=X",
    "GBPJPY": "GBPJPY=X",
    "AUDJPY": "AUDJPY=X",
    "CADJPY": "CADJPY=X",
    "CHFJPY": "CHFJPY=X",
    "EURCAD": "EURCAD=X",
    "GBPCAD": "GBPCAD=X",
    "EURAUD": "EURAUD=X",
    "GBPAUD": "GBPAUD=X",
    "EURCHF": "EURCHF=X",
    "AUDCAD": "AUDCAD=X",
    "XAUUSD": "GC=F",      # Gold Futures
    "BTCUSD": "BTC-USD",
    "BBCA": "BBCA.JK",
    "BBRI": "BBRI.JK",
}


def fetch_realtime_tradingview_price(symbol: str) -> Optional[float]:
    """Fetch 100% zero-delay live spot price directly from TradingView scanner API."""
    sym = symbol.upper()
    is_gold = "XAU" in sym or "GOLD" in sym
    is_crypto = "BTC" in sym or "ETH" in sym

    url = "https://scanner.tradingview.com/cfd/scan" if is_gold else "https://scanner.tradingview.com/forex/scan"

    if is_gold:
        tickers = ["OANDA:XAUUSD", "TVC:GOLD"]
    elif is_crypto:
        tickers = [f"BINANCE:{sym}T", f"COINBASE:{sym}"]
    else:
        tickers = [f"FX_IDC:{sym}", f"FX:{sym}", f"OANDA:{sym}"]

    try:
        payload = {"symbols": {"tickers": tickers}, "columns": ["close"]}
        resp = requests.post(url, json=payload, headers={"User-Agent": "Mozilla/5.0"}, timeout=3)
        if resp.status_code == 200:
            data = resp.json().get("data", [])
            for item in data:
                if item.get("d") and item["d"][0] is not None:
                    return float(item["d"][0])
    except Exception as exc:
        logger.debug("TradingView live tick fetch exception for %s: %s", symbol, exc)
    return None


def fetch_realtime_tradingview_bars(symbol: str, interval: str) -> Optional[Dict[str, float]]:
    """Fetch real-time active and previous confirmed candle OHLC directly from TradingView scanner API."""
    sym = symbol.upper()
    is_gold = "XAU" in sym or "GOLD" in sym
    is_crypto = "BTC" in sym or "ETH" in sym
    url = "https://scanner.tradingview.com/cfd/scan" if is_gold else (
        "https://scanner.tradingview.com/crypto/scan" if is_crypto else "https://scanner.tradingview.com/forex/scan"
    )

    tf_map = {"1m": "1", "3m": "3", "5m": "5", "15m": "15", "30m": "30", "45m": "45", "1h": "60", "2h": "120"}
    tv_tf = tf_map.get(interval, "5")

    if is_gold:
        tickers = ["OANDA:XAUUSD", "TVC:GOLD"]
    elif is_crypto:
        tickers = [f"BINANCE:{sym}USDT", f"COINBASE:{sym}USD"]
    else:
        tickers = [f"FX:{sym}", f"OANDA:{sym}", f"FX_IDC:{sym}"]

    cols = [
        f"open|{tv_tf}", f"high|{tv_tf}", f"low|{tv_tf}", f"close|{tv_tf}",
        f"open[1]|{tv_tf}", f"high[1]|{tv_tf}", f"low[1]|{tv_tf}", f"close[1]|{tv_tf}"
    ]

    try:
        resp = requests.post(
            url,
            json={"symbols": {"tickers": tickers}, "columns": cols},
            headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"},
            timeout=4
        )
        if resp.status_code == 200:
            for item in resp.json().get("data", []):
                vals = item.get("d")
                if vals and all(v is not None for v in vals):
                    return {
                        "curr_open": float(vals[0]),
                        "curr_high": float(vals[1]),
                        "curr_low": float(vals[2]),
                        "curr_close": float(vals[3]),
                        "prev_open": float(vals[4]),
                        "prev_high": float(vals[5]),
                        "prev_low": float(vals[6]),
                        "prev_close": float(vals[7]),
                    }
    except Exception as exc:
        logger.debug("Failed to fetch TradingView live bars for %s: %s", symbol, exc)
    return None


def is_choppy_session_hour(dt: Optional[datetime] = None) -> Tuple[bool, str]:
    """Check if current time falls into low-liquidity / choppy transition hours (WIB / UTC+7)."""
    now = dt or datetime.now()
    hour = now.hour
    minute = now.minute
    total_mins = hour * 60 + minute

    # 1. 11:30 - 13:00 WIB (Asian Session Lunch / Low Volume Consolidation)
    if (11 * 60 + 30) <= total_mins < (13 * 60):
        return True, "Fase Jeda Asia (11:30 - 13:00 WIB) - Likuiditas tipis & rawan false breakout"

    # 2. 17:30 - 19:00 WIB (London Lunch / Pre-New York Chop)
    if (17 * 60 + 30) <= total_mins < (19 * 60):
        return True, "Fase Pre-New York / London Lunch (17:30 - 19:00 WIB) - Pasar konsolidasi & rawan whipsaw"

    return False, ""


class LiveMarketScanner:
    """Continuously monitors real-time market data with Bollinger Bands and MACD."""

    def __init__(
        self,
        symbols: List[str],
        interval: str = "5m",
        check_interval_sec: int = 60,
        only_entry: bool = True,
        auto_trade: bool = True,
        lot_size: float = 0.01,
    ) -> None:
        self.symbols = symbols
        # Parse intervals: sinyal entry utama muncul pada timeframe ini (default 5m).
        # Timeframe lebih tinggi (15m) otomatis dianalisis di latar belakang sebagai kompas arah tren (MTF).
        raw_intervals = [normalize_timeframe(x.strip()) for x in interval.split(",") if x.strip()]
        self.entry_interval = raw_intervals[0] if raw_intervals else "5m"
        self.interval = self.entry_interval
        self.check_interval_sec = check_interval_sec
        self.only_entry = only_entry
        self.auto_trade = auto_trade
        self.lot_size = lot_size
        self.rag_engine = RAGEngine()
        self.notifier = TelegramNotifier()
        self.last_processed_timestamps: Dict[str, str] = {}
        self.cached_dfs: Dict[str, pd.DataFrame] = {}
        self.tv_connected: bool = True
        self.tv_alert_pending: Optional[str] = None

        # Inisialisasi TradingView Datafeed sebagai sumber data utama
        try:
            from tvDatafeed import TvDatafeed, Interval
            self.tv = TvDatafeed()
            self.TV_Interval = Interval
            logger.info("📡 TradingView Data Feed aktif sebagai penyedia data pasar UTAMA.")
        except Exception as e:
            self.tv = None
            self.TV_Interval = None
            self.tv_connected = False
            logger.warning("TvDatafeed tidak aktif, menggunakan fallback YFinance: %s", e)

        # Persistent HTTP session with desktop User-Agent to prevent Yahoo rate-limiting & hanging
        self.session = requests.Session()
        adapter = TimeoutHTTPAdapter(timeout=10)
        self.session.mount("https://", adapter)
        self.session.mount("http://", adapter)
        self.session.headers.update({
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
        })

    def _fetch_from_tradingview(self, symbol: str, interval: Optional[str] = None) -> Optional[pd.DataFrame]:
        """Fetch high-precision candles directly from TradingView."""
        if not self.tv or not self.TV_Interval:
            if self.tv_connected:
                self.tv_connected = False
                logger.error("❌ [KONEKSI TERPUTUS] WebSocket TradingView belum terinisialisasi! Mengalihkan ke backup Yahoo Finance.")
                self.tv_alert_pending = (
                    "⚠️ *PERINGATAN SISTEM BOT TRADING* ⚠️\n"
                    "════════════════════════════════\n"
                    "❌ *Koneksi WebSocket TradingView Terputus!*\n\n"
                    "• *Status:* Modul datafeed TradingView belum terinisialisasi.\n"
                    "• *Tindakan Otomatis:* Mengalihkan sumber data candle ke backup (*Yahoo Finance*).\n"
                    "• Bot akan otomatis mencoba menyambungkan kembali koneksi TradingView.\n"
                    "════════════════════════════════"
                )
            return None

        try:
            sym = symbol.upper().replace("=X", "")
            if "XAU" in sym or "GOLD" in sym:
                tv_sym, exchange = "XAUUSD", "OANDA"
            elif "BTC" in sym:
                tv_sym, exchange = "BTCUSDT", "BINANCE"
            elif "ETH" in sym:
                tv_sym, exchange = "ETHUSDT", "BINANCE"
            elif any(sym.endswith(c) for c in ["USD", "JPY", "GBP", "EUR", "AUD", "CAD", "CHF", "NZD"]):
                tv_sym, exchange = sym, "FX"
            elif ".JK" in sym:
                tv_sym, exchange = sym.replace(".JK", ""), "IDX"
            else:
                tv_sym, exchange = sym, "NASDAQ"

            tv_interval_map = {
                "1m": self.TV_Interval.in_1_minute,
                "3m": self.TV_Interval.in_3_minute,
                "5m": self.TV_Interval.in_5_minute,
                "15m": self.TV_Interval.in_15_minute,
                "30m": self.TV_Interval.in_30_minute,
                "45m": self.TV_Interval.in_45_minute,
                "1h": self.TV_Interval.in_1_hour,
                "2h": self.TV_Interval.in_2_hour,
                "4h": self.TV_Interval.in_4_hour,
                "1d": self.TV_Interval.in_daily,
            }
            tf_to_use = normalize_timeframe(interval or self.interval)
            tv_tf = tv_interval_map.get(tf_to_use, self.TV_Interval.in_5_minute)

            df = self.tv.get_hist(symbol=tv_sym, exchange=exchange, interval=tv_tf, n_bars=250)
            if df is not None and not df.empty and len(df) >= 20:
                df = df.rename(columns={
                    "open": "Open",
                    "high": "High",
                    "low": "Low",
                    "close": "Close",
                    "volume": "Volume"
                })
                df.index = pd.to_datetime(df.index)

                # Jika sebelumnya koneksi terputus, kirim notifikasi pemulihan (recovery)
                if not self.tv_connected:
                    self.tv_connected = True
                    logger.info("✅ [KONEKSI PULIH] WebSocket TradingView berhasil terhubung kembali untuk %s!", symbol)
                    self.tv_alert_pending = (
                        "✅ *SISTEM BOT TRADING PULIH* ✅\n"
                        "════════════════════════════════\n"
                        "🟢 *Koneksi WebSocket TradingView Berhasil Terhubung Kembali!*\n\n"
                        f"• *Simbol:* `{symbol.upper()}`\n"
                        "• *Status:* Feed data candle real-time TradingView telah normal kembali.\n"
                        "• Sumber data utama kembali disinkronkan ke TradingView.\n"
                        "════════════════════════════════"
                    )
                return df
            else:
                raise ConnectionError(f"Data kosong dari TradingView untuk {symbol}")

        except Exception as e:
            if self.tv_connected:
                self.tv_connected = False
                logger.error(
                    "❌ [KONEKSI TERPUTUS] WebSocket TradingView terputus pada simbol %s (%s). Mengalihkan ke backup Yahoo Finance.",
                    symbol,
                    e,
                )
                clean_err = str(e)[:80].replace("`", "'").replace("\n", " ")
                self.tv_alert_pending = (
                    "⚠️ *PERINGATAN SISTEM BOT TRADING* ⚠️\n"
                    "════════════════════════════════\n"
                    "❌ *Koneksi WebSocket TradingView Terputus!*\n\n"
                    f"• *Simbol Terdampak:* `{symbol.upper()}`\n"
                    f"• *Detail:* `{type(e).__name__}: {clean_err}`\n"
                    "• *Tindakan Otomatis:* Mengalihkan sementara ke sumber backup (*Yahoo Finance*).\n"
                    "• Bot akan otomatis mencoba rekoneksi (*auto-reconnect*) pada scan berikutnya.\n"
                    "════════════════════════════════"
                )
            else:
                logger.debug("TradingView get_hist still failing for %s: %s", symbol, e)

            # Coba reset instance TvDatafeed untuk rekoneksi otomatis
            try:
                from tvDatafeed import TvDatafeed
                self.tv = TvDatafeed()
            except Exception:
                pass

        return None

    def fetch_candle_data(self, symbol: str, interval: Optional[str] = None) -> Optional[pd.DataFrame]:
        """Fetch latest candle history from TradingView (Primary) with YFinance fallback."""
        target_tf = normalize_timeframe(interval or self.interval)
        cache_key = f"{symbol.upper()}_{target_tf}"

        # 1. Coba ambil data langsung dari TradingView (Akurasi 100% identik dengan chart TradingView)
        tv_df = self._fetch_from_tradingview(symbol, interval=target_tf)
        if tv_df is not None and len(tv_df) >= 20:
            self.cached_dfs[cache_key] = tv_df
            return tv_df

        # 2. Fallback ke YFinance jika TradingView terkendala
        ticker_symbol = YF_SYMBOL_MAP.get(symbol.upper(), symbol)
        try:
            suppressed_err = io.StringIO()
            with contextlib.redirect_stderr(suppressed_err):
                ticker = yf.Ticker(ticker_symbol, session=self.session)
                if target_tf == "45m":
                    # Resample from 15m candles
                    raw_df = ticker.history(period="25d", interval="15m")
                    if raw_df is not None and not raw_df.empty:
                        df = raw_df.resample("45min").agg({
                            "Open": "first", "High": "max", "Low": "min", "Close": "last", "Volume": "sum"
                        }).dropna()
                    else:
                        df = None
                elif target_tf == "2h":
                    # Resample from 1h candles
                    raw_df = ticker.history(period="60d", interval="1h")
                    if raw_df is not None and not raw_df.empty:
                        df = raw_df.resample("2h").agg({
                            "Open": "first", "High": "max", "Low": "min", "Close": "last", "Volume": "sum"
                        }).dropna()
                    else:
                        df = None
                elif target_tf == "1h":
                    df = ticker.history(period="30d", interval="1h")
                elif target_tf == "30m":
                    df = ticker.history(period="20d", interval="30m")
                elif target_tf == "15m":
                    df = ticker.history(period="10d", interval="15m")
                else:
                    # Default: 5m
                    df = ticker.history(period="5d", interval="5m")

            if df is None or df.empty or len(df) < 15:
                # If temporary network or Yahoo rate-limit occurs, fallback to cached candles
                if cache_key in self.cached_dfs:
                    return self.cached_dfs[cache_key]
                return None

            # Rekonsiliasi candle terkini dengan feed langsung dari TradingView Scanner API (100% Free & Sinkron)
            try:
                tv_bars = fetch_realtime_tradingview_bars(symbol, target_tf)
                if tv_bars is not None and len(df) >= 2:
                    tf_mins = {"1m": 1, "3m": 3, "5m": 5, "15m": 15, "30m": 30, "45m": 45, "1h": 60, "2h": 120}
                    bar_dur = pd.Timedelta(minutes=tf_mins.get(target_tf, 5))
                    last_ts = df.index[-1]
                    last_tz = getattr(last_ts, "tz", None)
                    now_time = pd.Timestamp.now(tz=last_tz) if last_tz else pd.Timestamp.now()
                    bar_close_time = last_ts + bar_dur

                    o_col = df.columns.get_loc("Open")
                    h_col = df.columns.get_loc("High")
                    l_col = df.columns.get_loc("Low")
                    c_col = df.columns.get_loc("Close")

                    if now_time < bar_close_time:
                        # df.iloc[-1] adalah bar yang sedang berjalan (forming)
                        df.iat[-1, o_col] = tv_bars["curr_open"]
                        df.iat[-1, h_col] = max(df.iloc[-1]["High"], tv_bars["curr_high"])
                        df.iat[-1, l_col] = min(df.iloc[-1]["Low"], tv_bars["curr_low"])
                        df.iat[-1, c_col] = tv_bars["curr_close"]

                        # df.iloc[-2] adalah bar terkonfirmasi yang baru selesai
                        df.iat[-2, o_col] = tv_bars["prev_open"]
                        df.iat[-2, h_col] = tv_bars["prev_high"]
                        df.iat[-2, l_col] = tv_bars["prev_low"]
                        df.iat[-2, c_col] = tv_bars["prev_close"]
                    else:
                        # Yahoo Finance belum merilis bar baru yang sedang berjalan
                        df.iat[-1, o_col] = tv_bars["prev_open"]
                        df.iat[-1, h_col] = tv_bars["prev_high"]
                        df.iat[-1, l_col] = tv_bars["prev_low"]
                        df.iat[-1, c_col] = tv_bars["prev_close"]

                        new_bar_time = last_ts + bar_dur
                        new_row = pd.DataFrame([{
                            "Open": tv_bars["curr_open"],
                            "High": tv_bars["curr_high"],
                            "Low": tv_bars["curr_low"],
                            "Close": tv_bars["curr_close"],
                            "Volume": 0
                        }], index=[new_bar_time])
                        df = pd.concat([df, new_row])
            except Exception as e:
                logger.debug("TradingView candle reconciliation skipped for %s: %s", symbol, e)

            # Simpan historical OHLC murni dari data penyedia untuk indikator dan pola closed-bar
            self.cached_dfs[cache_key] = df
            return df
        except Exception as exc:
            logger.debug("Fetch exception on %s: %s", symbol, exc)
            return self.cached_dfs.get(cache_key)

    def analyze_indicators_and_candles(self, symbol: str, df: pd.DataFrame) -> Optional[Dict[str, Any]]:
        """Calculate RSI, EMA 20/50/200, MACD, and detect candlestick patterns matching Pine Script."""
        close = df["Close"]
        high = df["High"]
        low = df["Low"]
        open_p = df["Open"]

        # 1. RSI (14)
        delta = close.diff()
        gain = delta.where(delta > 0, 0.0).rolling(14).mean()
        loss = (-delta.where(delta < 0, 0.0)).rolling(14).mean()
        rs = gain / (loss + 1e-9)
        rsi_series = 100.0 - (100.0 / (1.0 + rs))

        # 2. EMAs: 20, 50, 200
        ema20_series = close.ewm(span=20, adjust=False).mean()
        ema50_series = close.ewm(span=50, adjust=False).mean()
        ema200_series = close.ewm(span=200, adjust=False).mean()

        # 3. MACD (12, 26, 9)
        exp12 = close.ewm(span=12, adjust=False).mean()
        exp26 = close.ewm(span=26, adjust=False).mean()
        macd_line = exp12 - exp26
        signal_line = macd_line.ewm(span=9, adjust=False).mean()

        # 4. Bollinger Bands (20, 2)
        bb_basis = close.rolling(20).mean()
        bb_std = close.rolling(20).std()
        bb_upper = bb_basis + (2.0 * bb_std)
        bb_lower = bb_basis - (2.0 * bb_std)

        # 5. Stochastic Oscillator (8, 3, 3)
        low8 = low.rolling(8).min()
        high8 = high.rolling(8).max()
        stoch_k_raw = 100.0 * ((close - low8) / (high8 - low8 + 1e-9))
        stoch_k_series = stoch_k_raw.rolling(3).mean()  # %K Slowing = 3
        stoch_d_series = stoch_k_series.rolling(3).mean()  # %D Sinyal = 3

        # Pastikan analisis candlestick menggunakan CLOSED / CONFIRMED BAR untuk mencegah repainting
        tf_mins = {"1m": 1, "3m": 3, "5m": 5, "15m": 15, "30m": 30, "45m": 45, "1h": 60, "2h": 120}
        bar_dur = pd.Timedelta(minutes=tf_mins.get(self.interval, 5))
        last_ts = df.index[-1]
        last_tz = getattr(last_ts, "tz", None)
        now_time = pd.Timestamp.now(tz=last_tz) if last_tz else pd.Timestamp.now()

        # Sebuah bar dikatakan closed HANYA jika waktu sekarang >= waktu buka bar + durasi bar
        bar_close_time = last_ts + bar_dur
        if len(df) >= 35 and isinstance(df.index, pd.DatetimeIndex) and now_time < bar_close_time:
            # Bar terakhir (iloc[-1]) masih berjalan / belum ditutup (open/forming).
            # Bar terkonfirmasi (closed) terakhir yang sah dianalisis adalah iloc[-2]
            cur_idx = -2
        else:
            # Bar terakhir (iloc[-1]) sudah melewati durasi penutupan bar
            cur_idx = -1

        prev_idx = cur_idx - 1
        prev2_idx = cur_idx - 2
        prev3_idx = cur_idx - 3
        prev4_idx = cur_idx - 4

        c_open = float(open_p.iloc[cur_idx])
        c_high = float(high.iloc[cur_idx])
        c_low = float(low.iloc[cur_idx])
        c_close = float(close.iloc[cur_idx])
        c_time = str(df.index[cur_idx])

        # Live spot price untuk titik entri real-time
        live_spot_price = fetch_realtime_tradingview_price(symbol) or float(close.iloc[-1])

        # Check if already notified for this closed candle on this timeframe
        already_processed = (self.last_processed_timestamps.get(f"{symbol.upper()}_{self.interval}") == c_time)

        # 0. Filter Sesi Jam Rawan Chop / Low Liquidity (11:30 - 13:00 & 17:30 - 19:00 WIB)
        is_chop, chop_reason = is_choppy_session_hour()
        if is_chop and self.interval in ("1m", "3m", "5m"):
            return {
                "has_signal": False,
                "symbol": symbol.upper(),
                "timeframe": self.interval,
                "price": round(c_close, 5),
                "candle_close": round(c_close, 5),
                "live_spot_price": round(live_spot_price, 5),
                "trend": "Chop/Low Liquidity",
                "rsi": float(rsi_series.iloc[cur_idx]) if not pd.isna(rsi_series.iloc[cur_idx]) else 50.0,
                "macd": "Neutral",
                "reason": f"Sesi Dibatasi: {chop_reason}",
                "timestamp": c_time,
            }

        # Indicator values at current bar
        cur_rsi = float(rsi_series.iloc[cur_idx]) if not pd.isna(rsi_series.iloc[cur_idx]) else 50.0
        cur_ema20 = float(ema20_series.iloc[cur_idx])
        cur_ema50 = float(ema50_series.iloc[cur_idx])
        prev_ema20 = float(ema20_series.iloc[prev_idx])
        prev_ema50 = float(ema50_series.iloc[prev_idx])
        cur_ema200 = float(ema200_series.iloc[cur_idx]) if len(close) >= 200 else cur_ema50
        cur_macd = float(macd_line.iloc[cur_idx])
        cur_signal = float(signal_line.iloc[cur_idx])

        # Bollinger Bands values
        cur_bb_basis = float(bb_basis.iloc[cur_idx]) if not pd.isna(bb_basis.iloc[cur_idx]) else (c_high + c_low) / 2
        cur_bb_upper = float(bb_upper.iloc[cur_idx]) if not pd.isna(bb_upper.iloc[cur_idx]) else c_high
        cur_bb_lower = float(bb_lower.iloc[cur_idx]) if not pd.isna(bb_lower.iloc[cur_idx]) else c_low
        prev_bb_lower = float(bb_lower.iloc[prev_idx]) if not pd.isna(bb_lower.iloc[prev_idx]) else float(close.iloc[prev_idx])
        prev_bb_upper = float(bb_upper.iloc[prev_idx]) if not pd.isna(bb_upper.iloc[prev_idx]) else float(close.iloc[prev_idx])

        prev_macd = float(macd_line.iloc[prev_idx])
        prev_signal = float(signal_line.iloc[prev_idx])
        prev2_macd = float(macd_line.iloc[prev2_idx])
        prev2_signal = float(signal_line.iloc[prev2_idx])

        # Deteksi persilangan baru MACD (Fresh Cross dalam 1-2 bar terakhir)
        is_fresh_golden_cross = (
            (prev_macd <= prev_signal and cur_macd > cur_signal) or
            (prev2_macd <= prev2_signal and prev_macd > prev_signal)
        )
        is_fresh_death_cross = (
            (prev_macd >= prev_signal and cur_macd < cur_signal) or
            (prev2_macd >= prev2_signal and prev_macd < prev_signal)
        )

        # Stochastic (8, 3, 3) values & signals
        cur_stoch_k = float(stoch_k_series.iloc[cur_idx]) if not pd.isna(stoch_k_series.iloc[cur_idx]) else 50.0
        cur_stoch_d = float(stoch_d_series.iloc[cur_idx]) if not pd.isna(stoch_d_series.iloc[cur_idx]) else 50.0
        prev_stoch_k = float(stoch_k_series.iloc[prev_idx]) if not pd.isna(stoch_k_series.iloc[prev_idx]) else 50.0
        prev_stoch_d = float(stoch_d_series.iloc[prev_idx]) if not pd.isna(stoch_d_series.iloc[prev_idx]) else 50.0

        is_stoch_bullish_cross = (prev_stoch_k <= prev_stoch_d and cur_stoch_k > cur_stoch_d)
        is_stoch_bearish_cross = (prev_stoch_k >= prev_stoch_d and cur_stoch_k < cur_stoch_d)
        is_stoch_oversold = cur_stoch_k <= 25.0 or (cur_stoch_k <= 35.0 and is_stoch_bullish_cross)
        is_stoch_overbought = cur_stoch_k >= 75.0 or (cur_stoch_k >= 65.0 and is_stoch_bearish_cross)

        # Candle anatomy
        body_size = abs(c_close - c_open)
        c_range = c_high - c_low + 1e-9
        upper_shadow = c_high - max(c_open, c_close)
        lower_shadow = min(c_open, c_close) - c_low

        p_close = float(close.iloc[prev_idx])
        p_open = float(open_p.iloc[prev_idx])
        p_low = float(low.iloc[prev_idx])
        p_high = float(high.iloc[prev_idx])
        p2_close = float(close.iloc[prev2_idx])
        p2_open = float(open_p.iloc[prev2_idx])
        p_body = abs(p_close - p_open)
        p2_body = abs(p2_close - p2_open)
        p_upper_shadow = p_high - max(p_open, p_close)
        p_lower_shadow = min(p_open, p_close) - p_low

        # Previous candle metrics for multi-bar patterns
        p2_high = float(high.iloc[prev2_idx])
        p2_low = float(low.iloc[prev2_idx])
        p2_upper_shadow = p2_high - max(p2_open, p2_close)
        p2_lower_shadow = min(p2_open, p2_close) - p2_low
        p_range = p_high - p_low + 1e-9
        p2_range = p2_high - p2_low + 1e-9

        has_5_bars = len(close) >= abs(prev4_idx)
        p3_open = float(open_p.iloc[prev3_idx]) if has_5_bars else p2_open
        p3_close = float(close.iloc[prev3_idx]) if has_5_bars else p2_close
        p3_high = float(high.iloc[prev3_idx]) if has_5_bars else p2_high
        p3_low = float(low.iloc[prev3_idx]) if has_5_bars else p2_low

        p4_open = float(open_p.iloc[prev4_idx]) if has_5_bars else p3_open
        p4_close = float(close.iloc[prev4_idx]) if has_5_bars else p3_close
        p4_high = float(high.iloc[prev4_idx]) if has_5_bars else p3_high
        p4_low = float(low.iloc[prev4_idx]) if has_5_bars else p3_low

        # ==============================================================================
        # KONFIGURASI ALGORITMA DINAMIS BERDASARKAN TIMEFRAME & SESI PASAR
        # ==============================================================================
        if self.interval == "15m":
            spread_tol = 0.00010
            body_ratio = 1.00
            pin_ratio = 2.0
            star_ratio = 0.45
            tweezer_ratio = 0.12
            min_candle_range = 0.00028
            algo_name = "Algoritma Short Intraday 15m"
        elif self.interval == "30m":
            spread_tol = 0.00015
            body_ratio = 1.00
            pin_ratio = 2.0
            star_ratio = 0.40
            tweezer_ratio = 0.10
            min_candle_range = 0.00040
            algo_name = "Algoritma Mid Intraday 30m"
        elif self.interval == "45m":
            spread_tol = 0.00020
            body_ratio = 1.00
            pin_ratio = 2.0
            star_ratio = 0.35
            tweezer_ratio = 0.09
            min_candle_range = 0.00050
            algo_name = "Algoritma Extended Intraday 45m"
        elif self.interval == "1h":
            spread_tol = 0.00030
            body_ratio = 1.00
            pin_ratio = 2.2
            star_ratio = 0.35
            tweezer_ratio = 0.08
            min_candle_range = 0.00050
            algo_name = "Algoritma Swing Intraday 1h"
        elif self.interval == "2h":
            spread_tol = 0.00045
            body_ratio = 1.00
            pin_ratio = 2.5
            star_ratio = 0.30
            tweezer_ratio = 0.07
            min_candle_range = 0.00060
            algo_name = "Algoritma Major Swing 2h"
        else:
            # 5m Scalping Cepat (Optimal Sesi Asia & Low Volatility: 1.8 pips / 0.00018)
            spread_tol = 0.00005
            body_ratio = 1.00
            pin_ratio = 2.0
            star_ratio = 0.50
            tweezer_ratio = 0.15
            min_candle_range = 0.00018  # 1.8 pips untuk menangkap pembalikan pagi hari tanpa terlewat
            algo_name = "Algoritma Scalping 5m (Asia-Optimized)"

        # Normalisasi skala pips untuk multi-aset (Forex, JPY, Emas/Gold, Crypto)
        sym_upper = symbol.upper()
        if "JPY" in sym_upper:
            scale = 100.0
        elif "XAU" in sym_upper or "GOLD" in sym_upper:
            scale = 10000.0
        elif "BTC" in sym_upper:
            scale = 10000.0 * 100.0
        else:
            scale = 1.0

        spread_tol *= scale
        min_candle_range *= scale

        # Zone check for Reversal patterns:
        # Bullish Reversal Area (Support zone: lower half of Bollinger Bands or testing recent swing low)
        bb_lower_zone = (min(c_low, p_low) <= (cur_bb_basis + cur_bb_lower) / 2) or (min(c_low, p_low) <= cur_bb_lower + spread_tol)
        swing_low_test = (min(c_low, p_low) <= min(p2_low, p3_low) + spread_tol) if has_5_bars else bb_lower_zone
        is_support_zone = bb_lower_zone or swing_low_test

        # Bearish Reversal Area (Resistance zone: upper half of Bollinger Bands or testing recent swing high)
        bb_upper_zone = (max(c_high, p_high) >= (cur_bb_basis + cur_bb_upper) / 2) or (max(c_high, p_high) >= cur_bb_upper - spread_tol)
        swing_high_test = (max(c_high, p_high) >= max(p2_high, p3_high) - spread_tol) if has_5_bars else bb_upper_zone
        is_resistance_zone = bb_upper_zone or swing_high_test

        # Micro-trend direction checks over recent candles:
        # If market has been forming consecutive higher lows and higher closes over 3-4 bars, it is actively rising (rally)
        is_actively_rising = (
            has_5_bars and
            (c_low >= p2_low - spread_tol) and (p_low >= p3_low - spread_tol) and (p2_low >= p4_low - spread_tol) and
            (c_close > p3_close)
        )

        # If market has been forming consecutive lower highs and lower closes over 3-4 bars, it is actively falling (sell-off)
        is_actively_falling = (
            has_5_bars and
            (c_high <= p2_high + spread_tol) and (p_high <= p3_high + spread_tol) and (p2_high <= p4_high + spread_tol) and
            (c_close < p3_close)
        )

        # Konteks Pelemahan/Pullback untuk Pola Reversal Bullish:
        # Wajib: Ada pelemahan harga (minor drop), berada di area support/swing low, RSI <= 55.0,
        # dan BUKAN di tengah rally/uptrend aktif yang sudah berjalan!
        is_minor_downtrend = (p_close < p_open) or (p_close < p2_close) or (c_low < p_low) or (c_close < cur_ema20)
        is_downtrend_context = (
            (cur_rsi <= 55.0) and
            not is_actively_rising and
            is_support_zone and
            is_minor_downtrend
        )

        # Konteks Kenaikan/Pullback untuk Pola Reversal Bearish:
        # Wajib: Ada kenaikan harga (minor rally), berada di area resistance/swing high, RSI >= 42.0,
        # dan BUKAN di tengah sell-off/downtrend aktif yang sedang jatuh!
        is_minor_uptrend = (p_close > p_open) or (p_close > p2_close) or (c_high > p_high) or (c_close > cur_ema20)
        is_uptrend_context = (
            (cur_rsi >= 42.0) and
            not is_actively_falling and
            is_resistance_zone and
            is_minor_uptrend
        )

        # ==============================================================================
        # DAFTAR POLA BULLISH GRADE-A (>70% AKURASI):
        # ==============================================================================
        # 1. Bullish Engulfing (Formasi 2-Candle: Candle hijau solid menelan candle merah nyata sebelumnya di Support Downtrend - BUKAN Doji)
        is_bullish_engulfing = (
            is_downtrend_context and
            (p_close < p_open) and (c_close > c_open) and
            (p_body >= min_candle_range * 0.35) and
            (p_body >= 0.30 * p_range) and
            (p_body >= 0.25 * body_size) and
            (c_close >= p_open - spread_tol) and (c_open <= p_close + spread_tol) and
            (body_size >= p_body * 1.05) and
            (body_size >= 0.45 * c_range) and
            is_support_zone
        )

        # Ciri bentuk fisik identik Pin Bar Sumbu Atas (Inverted Hammer & Shooting Star):
        # 1. Sumbu atas panjang (minimal pin_ratio * body_size dan >= 50% range candle)
        # 2. Toleransi bayangan bawah sangat kecil (lower_shadow <= max(spread_tol * 2.0, 0.12 * c_range))
        # 3. Body berukuran kecil di bagian dasar (body_size <= 0.38 * c_range dan body_size > 0)
        # 4. Range candle valid / bukan noise (c_range >= min_candle_range)
        has_pin_top_shape = (
            (upper_shadow >= pin_ratio * body_size) and
            (upper_shadow >= 0.50 * c_range) and
            (lower_shadow <= max(spread_tol * 2.0, 0.12 * c_range)) and
            (body_size > 0) and
            (body_size <= 0.38 * c_range) and
            (c_range >= min_candle_range)
        )

        # Ciri bentuk fisik identik Pin Bar Sumbu Bawah (Hammer & Hanging Man):
        # 1. Sumbu bawah panjang (minimal pin_ratio * body_size dan >= 50% range candle)
        # 2. Toleransi bayangan atas sangat kecil (upper_shadow <= max(spread_tol * 2.0, 0.12 * c_range))
        # 3. Body berukuran kecil di bagian puncak atas (body_size <= 0.38 * c_range dan body_size > 0)
        # 4. Range candle valid / bukan noise (c_range >= min_candle_range)
        has_pin_bottom_shape = (
            (lower_shadow >= pin_ratio * body_size) and
            (lower_shadow >= 0.50 * c_range) and
            (upper_shadow <= max(spread_tol * 2.0, 0.12 * c_range)) and
            (body_size > 0) and
            (body_size <= 0.38 * c_range) and
            (c_range >= min_candle_range)
        )

        # 2. Hammer (Formasi 1-Candle Pin Bar Bullish Reversal):
        #    HANYA muncul pada Downtrend di area Support setelah candle merah penekan (p_close < p_open).
        #    Syarat Mutlak: Body kecil di puncak (<= 35% range), sumbu bawah panjang (>= 55% range dan >= 2x body),
        #    sumbu atas minimalis (<= 8% range dan <= 0.35x body), dan BUKAN Bullish Engulfing!
        is_hammer = (
            is_downtrend_context and
            (p_close < p_open) and # Wajib didahului candle penekan MERAH/BEARISH!
            (c_low <= p_low + spread_tol) and # Menguji batas low
            (lower_shadow >= 2.0 * body_size) and
            (lower_shadow >= 0.55 * c_range) and
            (upper_shadow <= 0.08 * c_range) and # Sumbu atas wajib sangat kecil
            (upper_shadow <= 0.35 * body_size) and
            (body_size > 0) and
            (body_size <= 0.35 * c_range) and
            (c_range >= min_candle_range) and
            (cur_rsi <= 50.0) and
            (c_low <= (cur_bb_basis + cur_bb_lower) / 2 or c_close <= cur_bb_basis) and
            not is_bullish_engulfing
        )

        # 3. Inverted Hammer (Formasi 1-Candle Pin Bar Reversal Bullish):
        # 3. Inverted Hammer (Formasi 1-Candle Pin Bar Reversal Bullish):
        #    HANYA muncul pada Downtrend di area Support setelah candle merah penekan (p_close < p_open).
        #    Syarat Mutlak: Body kecil di dasar (<= 35% range), sumbu atas panjang (>= 55% range dan >= 2x body),
        #    sumbu bawah minimalis (<= 8% range dan <= 0.35x body), dan BUKAN Bullish Engulfing!
        is_inverted_hammer = (
            is_downtrend_context and
            (p_close < p_open) and # Wajib didahului candle penekan MERAH/BEARISH!
            (c_low <= p_low + spread_tol) and
            (upper_shadow >= 2.0 * body_size) and
            (upper_shadow >= 0.55 * c_range) and
            (lower_shadow <= 0.08 * c_range) and # Sumbu bawah wajib sangat kecil / minimalis
            (lower_shadow <= 0.35 * body_size) and
            (body_size > 0) and
            (body_size <= 0.35 * c_range) and
            (max(c_open, c_close) - c_low <= 0.40 * c_range) and
            (c_range >= min_candle_range) and
            (cur_rsi <= 50.0) and
            (c_low <= (cur_bb_basis + cur_bb_lower) / 2 or c_close <= cur_bb_basis) and
            not is_bullish_engulfing
        )

        # 4. Morning Star Reversal (Formasi 3-Candle Reversal)
        #    Candle 1: Bearish solid panjang (p2_close < p2_open, body >= 35% range)
        #    Candle 2: Star candle kecil di dasar (p_body <= p2_body * star_ratio, p_low <= p2_low)
        #    Candle 3: Bullish solid yang menembus >= 50% body Candle 1 (c_close > c_open, c_close >= mid p2)
        is_morning_star = (
            is_downtrend_context and
            (p2_close < p2_open) and (p2_body >= min_candle_range * 0.35) and
            (p_body <= p2_body * star_ratio) and
            (p_low <= p2_low + spread_tol * 0.5) and
            (c_close > c_open) and (body_size >= min_candle_range * 0.30) and
            (c_close >= (p2_open + p2_close) / 2) and
            (c_close > p_close) and
            not is_bullish_engulfing
        )

        # 5. Tweezer Bottom (Formasi 2-Candle: Low kembar presisi di area Support / Dasar Downtrend - Steve Nison SOP)
        tw_b_diff = abs(c_low - p_low)
        tw_b_max = max(min(c_range, p_range) * 0.25, spread_tol * 2.2, 0.00011)
        is_tweezer_bottom = (
            is_downtrend_context and
            (max(c_range, p_range) >= min_candle_range) and
            (min(c_range, p_range) >= min_candle_range * 0.35) and
            (tw_b_diff <= tw_b_max) and
            (p_close < p_open or (p_close <= p_open and abs(p_close - p_open) <= spread_tol)) and
            (c_close > c_open) and
            (body_size >= min_candle_range * 0.30) and
            (c_close >= (p_open + p_close) / 2) and
            (lower_shadow >= 0.18 * c_range or (body_size >= 0.45 * c_range and c_close >= (p_open + p_close) / 2)) and
            (c_close > c_low) and
            (c_low <= (cur_bb_basis + cur_bb_lower) / 2 or is_support_zone) and
            not is_bullish_engulfing
        )

        # 6. Piercing Line (Formasi 2-Candle: Candle hijau menembus >= 50% body candle merah, namun BUKAN Tweezer Bottom)
        is_piercing_line = (
            is_downtrend_context and
            (p_close < p_open) and (p_body >= min_candle_range * 0.35) and
            (c_close > c_open) and (body_size >= min_candle_range * 0.30) and
            (c_low <= p_low + spread_tol * 0.5) and
            (c_open <= p_close + spread_tol) and
            (c_close >= (p_open + p_close) / 2) and (c_close < p_open) and
            not is_bullish_engulfing and
            not is_tweezer_bottom
        )

        # 7. Three White Soldiers (Formasi 3-Candle: Berakar dari support/tengah dan belum mentok di Upper Band)
        #    Syarat Steve Nison:
        #    - 3 candle berturut-turut HIJAU solid (p2, p, c)
        #    - Tiap candle membuat higher high & higher close
        #    - Masing-masing candle memiliki body solid nyata (>= 35% range), bukan doji/spinning top
        #    - Sumbu atas pendek pada tiap candle (upper_shadow <= 25% range)
        is_three_white_soldiers = (
            (p2_low <= cur_bb_basis or p2_close <= cur_ema20) and
            (c_close < cur_bb_upper) and
            (c_close > c_open) and (p_close > p_open) and (p2_close > p2_open) and
            (c_close > p_close) and (p_close > p2_close) and
            (c_high > p_high) and (p_high > p2_high) and
            (body_size >= 0.35 * c_range) and (p_body >= 0.35 * p_range) and (p2_body >= 0.35 * p2_range) and
            (upper_shadow <= 0.25 * c_range) and (p_upper_shadow <= 0.25 * p_range) and
            (c_open >= p_open - spread_tol) and (p_open >= p2_open - spread_tol) and
            (c_range >= min_candle_range * 0.70)
        )

        # 8. Bullish Kicker (Formasi 2-Candle Eksplosif: Wajib Gap Up di atas Open Candle 1 tanpa tumpang tindih body)
        is_bullish_kicker = (
            (p_close < p_open) and (c_close > c_open) and
            (p_body >= min_candle_range * 0.50) and
            (c_open >= p_open + spread_tol * 0.5) and
            (c_low >= p_open - spread_tol) and
            (body_size >= min_candle_range * 0.80) and
            (body_size >= p_body * 0.90) and
            (c_range >= min_candle_range)
        )

        # 9. Three Inside Up (Formasi 3-Candle - Confirmed Bullish Harami)
        #    Candle 1 (p2): Bearish solid mother candle
        #    Candle 2 (p): Bullish Harami solid SEPENUHNYA di dalam range mother candle
        #    Candle 3 (c): Candle konfirmasi HIJAU solid yang menembus ke atas (c_close > c_open, c_close > p_close, c_close > p2_open)
        is_three_inside_up = (
            (p2_close < p2_open) and (p_close > p_open) and
            (c_close > c_open) and # Candle 3 WAJIB HIJAU solid!
            (c_close > p_close) and
            (c_close > p2_open) and
            (body_size >= 0.35 * c_range) and # Wajib body solid nyata, BUKAN Pin Bar / Hammer!
            (p_high <= p2_high + spread_tol * 0.2) and
            (p_low >= p2_low - spread_tol * 0.2) and
            (p_open >= p2_close - spread_tol) and
            (p_close <= p2_open + spread_tol) and
            not is_hammer and
            not is_inverted_hammer
        )

        # 10. Bullish Abandoned Baby (Formasi 3-Candle: Doji dengan gap ke bawah dan candle 3 dengan gap ke atas)
        is_bullish_abandoned_baby = (
            is_downtrend_context and
            (p2_close < p2_open) and (p2_body >= min_candle_range * 0.35) and
            (p_body <= p_range * 0.20) and
            (p_range >= min_candle_range * 0.30) and
            (max(p_open, p_close) < p2_close - spread_tol * 0.5) and
            (c_close > c_open) and (body_size >= min_candle_range * 0.35) and
            (min(c_open, c_close) > max(p_open, p_close) + spread_tol * 0.5) and
            (c_close > (p2_open + p2_close) / 2)
        )

        # 11. Rising Three Methods (Formasi 5-Candle - Bullish Continuation)
        #    Candle 1 (p4): Bullish panjang solid
        #    Candle 2, 3, 4 (p3, p2, p): 3 candle kecil korektif di dalam rentang p4
        #    Candle 5 (c): Bullish panjang solid yang menembus di atas penutupan p4
        is_rising_three_methods = (
            has_5_bars and
            (p4_close > p4_open) and (abs(p4_close - p4_open) >= min_candle_range * 0.50) and
            (p_high <= p4_high + spread_tol and p_low >= p4_low - spread_tol) and
            (p2_high <= p4_high + spread_tol and p2_low >= p4_low - spread_tol) and
            (p3_high <= p4_high + spread_tol and p3_low >= p4_low - spread_tol) and
            (p_body <= abs(p4_close - p4_open) * 0.75) and
            (p2_body <= abs(p4_close - p4_open) * 0.75) and
            (c_close > c_open) and (body_size >= min_candle_range * 0.50) and
            (c_close > p4_close)
        )

        # 12. MACD Golden Cross
        is_macd_golden_cross = (
            (prev_macd <= prev_signal and cur_macd > cur_signal) or
            (cur_macd > cur_signal and cur_macd > prev_macd)
        )

        # 13. Chart Pattern: Double Bottom (Pola Huruf W di Area Support)
        is_double_bottom = (
            is_downtrend_context and (c_close > c_open) and (
                (has_5_bars and abs(min(c_low, p_low) - min(p3_low, p4_low)) <= (c_range * 0.20) and p2_high > max(c_low, p3_low) and (p2_high - min(c_low, p3_low)) >= min_candle_range * 0.5) or
                (abs(c_low - p2_low) <= (c_range * 0.18) and p_high > max(c_low, p2_low) and (p_high - min(c_low, p2_low)) >= min_candle_range * 0.5)
            )
        )

        # 14. Bullish Harami (Formasi 2-Candle Reversal: Candle hijau kecil solid SEPENUHNYA di dalam range mother candle merah sebelumnya)
        is_bullish_harami = (
            is_downtrend_context and
            (p_close < p_open) and (p_body >= min_candle_range * 0.35) and
            (c_close > c_open) and
            (c_low >= p_low - spread_tol * 0.2) and   # Low candle kedua TIDAK BOLEH lebih rendah dari mother candle!
            (c_high <= p_high + spread_tol * 0.2) and  # High candle kedua TIDAK BOLEH lebih tinggi dari mother candle!
            (c_open >= p_close - spread_tol * 0.5) and
            (c_close <= p_open + spread_tol * 0.5) and
            (body_size >= 0.25 * c_range) and
            (body_size <= p_body * 0.70) and
            (p_range >= min_candle_range * 0.70) and
            is_support_zone
        )

        # ==============================================================================
        # DAFTAR POLA BEARISH GRADE-A (>70% AKURASI):
        # ==============================================================================
        # 1. Bearish Engulfing (Formasi 2-Candle: Candle merah solid menelan candle hijau nyata sebelumnya di Resistance Uptrend - BUKAN Doji)
        is_bearish_engulfing = (
            is_uptrend_context and
            (p_close > p_open) and (c_close < c_open) and
            (p_body >= min_candle_range * 0.35) and
            (p_body >= 0.30 * p_range) and
            (p_body >= 0.25 * body_size) and
            (c_close <= p_open + spread_tol) and (c_open >= p_close - spread_tol) and
            (body_size >= p_body * 1.05) and
            (body_size >= 0.45 * c_range) and
            is_resistance_zone
        )

        # 2. Shooting Star (Formasi 1-Candle Pin Bar Reversal Bearish):
        #    HANYA muncul pada puncak Uptrend di area Resistance setelah candle hijau pendorong.
        #    Syarat Mutlak (Steve Nison SOP):
        #    1. Candle sebelumnya WAJIB HIJAU/BULLISH (p_close > p_open) yang mendorong ke puncak (c_high >= p_high - spread_tol).
        #    2. Sumbu atas panjang mendominasi (>= 55% range dan >= 2x body).
        #    3. Sumbu bawah WAJIB SANGAT KECIL ATAU NIHIL (<= 8% range dan <= 0.35x body).
        #    4. Body kecil di dasar (body_size <= 35% range dan max(c_open, c_close) - c_low <= 0.40 * c_range).
        is_shooting_star = (
            is_uptrend_context and
            (p_close > p_open) and # Wajib didahului candle BULLISH/HIJAU!
            (c_high >= p_high - spread_tol) and
            (upper_shadow >= 2.0 * body_size) and
            (upper_shadow >= 0.55 * c_range) and
            (lower_shadow <= 0.08 * c_range) and # Sumbu bawah wajib sangat kecil / minimalis
            (lower_shadow <= 0.35 * body_size) and
            (body_size > 0) and
            (body_size <= 0.35 * c_range) and
            (max(c_open, c_close) - c_low <= 0.40 * c_range) and
            (c_range >= min_candle_range) and
            (cur_rsi >= 50.0) and
            (c_high >= (cur_bb_basis + cur_bb_upper) / 2 or c_close >= cur_bb_basis) and
            not is_bearish_engulfing
        )

        # 3. Hanging Man (Formasi 1-Candle Pin Bar Reversal Bearish):
        #    HANYA muncul pada puncak Uptrend di area Resistance setelah candle hijau pendorong.
        #    Syarat Mutlak (Steve Nison SOP):
        #    1. Candle sebelumnya WAJIB HIJAU/BULLISH (p_close > p_open). DILARANG jika candle sebelumnya sudah merah!
        #    2. Berada di puncak tren naik (c_high >= p_high - spread_tol).
        #    3. Sumbu atas WAJIB SANGAT KECIL ATAU NIHIL (<= 8% c_range dan <= 0.35x body). Jika sumbu atas panjang, BUKAN Hanging Man!
        #    4. Sumbu bawah panjang minimal 2x body (>= 55% c_range).
        #    5. Body kecil berada di puncak (body_size <= 35% range dan min(c_open, c_close) - c_low >= 0.55 * c_range).
        is_hanging_man = (
            is_uptrend_context and
            (p_close > p_open) and # Wajib didahului candle BULLISH/HIJAU!
            (c_high >= p_high - spread_tol) and # Berada di puncak lokal
            (lower_shadow >= 2.0 * body_size) and
            (lower_shadow >= 0.55 * c_range) and
            (upper_shadow <= 0.08 * c_range) and # Sumbu atas WAJIB sangat kecil / minimalis
            (upper_shadow <= 0.35 * body_size) and
            (body_size > 0) and
            (body_size <= 0.35 * c_range) and
            (min(c_open, c_close) - c_low >= 0.55 * c_range) and
            (c_range >= min_candle_range) and
            (cur_rsi >= 55.0) and
            (c_high >= (cur_bb_basis + cur_bb_upper) / 2 or c_close >= cur_bb_basis) and
            not is_bearish_engulfing
        )

        # 4. Evening Star Reversal (Formasi 3-Candle Reversal)
        #    Candle 1: Bullish solid panjang (p2_close > p2_open, body >= 35% range)
        #    Candle 2: Star candle kecil di puncak (p_body <= p2_body * star_ratio, p_high di puncak)
        #    Candle 3: Bearish solid yang menembus <= 50% body Candle 1 (c_close < c_open, c_close <= mid p2)
        is_evening_star = (
            is_uptrend_context and
            (p2_close > p2_open) and (p2_body >= min_candle_range * 0.35) and
            (p_body <= p2_body * star_ratio) and
            (p_high >= p2_high - spread_tol * 0.5) and
            (c_close < c_open) and (body_size >= min_candle_range * 0.30) and
            (c_close <= (p2_open + p2_close) / 2) and
            (c_close < p_close) and
            not is_bearish_engulfing
        )

        # 5. Tweezer Top (Formasi 2-Candle: High kembar presisi di area Resistance / Puncak Uptrend - Steve Nison SOP)
        tw_t_diff = abs(c_high - p_high)
        tw_t_max = max(min(c_range, p_range) * 0.25, spread_tol * 2.2, 0.00011)
        is_tweezer_top = (
            is_uptrend_context and
            (max(c_range, p_range) >= min_candle_range) and
            (min(c_range, p_range) >= min_candle_range * 0.35) and
            (tw_t_diff <= tw_t_max) and
            (p_close > p_open or (p_close >= p_open and abs(p_close - p_open) <= spread_tol)) and
            (c_close < c_open) and
            (body_size >= min_candle_range * 0.30) and
            (c_close <= (p_open + p_close) / 2) and
            (upper_shadow >= 0.18 * c_range or (body_size >= 0.45 * c_range and c_close <= (p_open + p_close) / 2)) and
            (c_close < c_high) and
            (c_high >= (cur_bb_basis + cur_bb_upper) / 2 or is_resistance_zone) and
            not is_bearish_engulfing
        )

        # 6. Dark Cloud Cover (Formasi 2-Candle: Candle merah menembus >= 50% body candle hijau, namun BUKAN Tweezer Top)
        is_dark_cloud_cover = (
            is_uptrend_context and
            (p_close > p_open) and (p_body >= min_candle_range * 0.35) and
            (c_close < c_open) and (body_size >= min_candle_range * 0.30) and
            (c_high >= p_high - spread_tol * 0.5) and  # Wajib menguji ke atas / setara high candle 1
            (c_open >= p_close - spread_tol) and
            (c_close <= (p_open + p_close) / 2) and (c_close > p_open) and
            not is_bearish_engulfing and
            not is_tweezer_top
        )

        # 7. Three Black Crows (Formasi 3-Candle: Berakar dari resistance/tengah dan belum mentok di Lower Band)
        #    Syarat Steve Nison:
        #    - 3 candle berturut-turut MERAH solid (p2, p, c)
        #    - Tiap candle membuat lower low & lower close
        #    - Masing-masing candle memiliki body solid nyata (>= 35% range), bukan doji/spinning top
        #    - Sumbu bawah pendek pada tiap candle (lower_shadow <= 25% range)
        is_three_black_crows = (
            (p2_high >= cur_bb_basis or p2_close >= cur_ema20) and
            (c_close > cur_bb_lower) and
            (c_close < c_open) and (p_close < p_open) and (p2_close < p2_open) and
            (c_close < p_close) and (p_close < p2_close) and
            (c_low < p_low) and (p_low < p2_low) and
            (body_size >= 0.35 * c_range) and (p_body >= 0.35 * p_range) and (p2_body >= 0.35 * p2_range) and
            (lower_shadow <= 0.25 * c_range) and (p_lower_shadow <= 0.25 * p_range) and
            (c_open <= p_open + spread_tol) and (p_open <= p2_open + spread_tol) and
            (c_range >= min_candle_range * 0.70)
        )

        # 8. Bearish Kicker (Formasi 2-Candle Eksplosif: Wajib Gap Down di bawah Open Candle 1 tanpa tumpang tindih body)
        is_bearish_kicker = (
            (p_close > p_open) and (c_close < c_open) and
            (p_body >= min_candle_range * 0.50) and
            (c_open <= p_open - spread_tol * 0.5) and
            (c_high <= p_open + spread_tol) and
            (body_size >= min_candle_range * 0.80) and
            (body_size >= p_body * 0.90) and
            (c_range >= min_candle_range)
        )

        # 9. Three Inside Down (Formasi 3-Candle - Confirmed Bearish Harami)
        #    Candle 1 (p2): Bullish solid mother candle
        #    Candle 2 (p): Bearish Harami solid SEPENUHNYA di dalam range mother candle
        #    Candle 3 (c): Candle konfirmasi MERAH solid yang menembus ke bawah (c_close < c_open, c_close < p_close, c_close < p2_open)
        is_three_inside_down = (
            (p2_close > p2_open) and (p_close < p_open) and
            (c_close < c_open) and # Candle 3 WAJIB MERAH solid!
            (c_close < p_close) and
            (c_close < p2_open) and
            (body_size >= 0.35 * c_range) and # Wajib body solid nyata, BUKAN Pin Bar / Hanging Man!
            (p_high <= p2_high + spread_tol * 0.2) and
            (p_low >= p2_low - spread_tol * 0.2) and
            (p_open <= p2_close + spread_tol) and
            (p_close >= p2_open - spread_tol) and
            not is_hanging_man and
            not is_shooting_star
        )

        # 10. Bearish Abandoned Baby (Formasi 3-Candle: Doji dengan gap ke atas dan candle 3 dengan gap ke bawah)
        is_bearish_abandoned_baby = (
            is_uptrend_context and
            (p2_close > p2_open) and (p2_body >= min_candle_range * 0.35) and
            (p_body <= p_range * 0.20) and
            (p_range >= min_candle_range * 0.30) and
            (min(p_open, p_close) > p2_close + spread_tol * 0.5) and
            (c_close < c_open) and (body_size >= min_candle_range * 0.35) and
            (max(c_open, c_close) < min(p_open, p_close) - spread_tol * 0.5) and
            (c_close < (p2_open + p2_close) / 2)
        )

        # 11. Falling Three Methods (Formasi 5-Candle - Bearish Continuation)
        #    Candle 1 (p4): Bearish panjang solid
        #    Candle 2, 3, 4 (p3, p2, p): 3 candle kecil korektif di dalam rentang p4
        #    Candle 5 (c): Bearish panjang solid yang menembus di bawah penutupan p4
        is_falling_three_methods = (
            has_5_bars and
            (p4_close < p4_open) and (abs(p4_close - p4_open) >= min_candle_range * 0.50) and
            (p_high <= p4_high + spread_tol and p_low >= p4_low - spread_tol) and
            (p2_high <= p4_high + spread_tol and p2_low >= p4_low - spread_tol) and
            (p3_high <= p4_high + spread_tol and p3_low >= p4_low - spread_tol) and
            (p_body <= abs(p4_close - p4_open) * 0.75) and
            (p2_body <= abs(p4_close - p4_open) * 0.75) and
            (c_close < c_open) and (body_size >= min_candle_range * 0.50) and
            (c_close < p4_close)
        )

        # 12. MACD Death Cross
        is_macd_death_cross = (
            (prev_macd >= prev_signal and cur_macd < cur_signal) or
            (cur_macd < cur_signal and cur_macd < prev_macd)
        )

        # 13. Chart Pattern: Double Top (Pola Huruf M di Area Resistance)
        is_double_top = (
            is_uptrend_context and (c_close < c_open) and (
                (has_5_bars and abs(max(c_high, p_high) - max(p3_high, p4_high)) <= (c_range * 0.20) and p2_low < min(c_high, p3_high) and (max(c_high, p3_high) - p2_low) >= min_candle_range * 0.5) or
                (abs(c_high - p2_high) <= (c_range * 0.18) and p_low < min(c_high, p2_high) and (max(c_high, p2_high) - p_low) >= min_candle_range * 0.5)
            )
        )

        # 14. Bearish Harami (Formasi 2-Candle Reversal: Candle merah kecil solid SEPENUHNYA di dalam range mother candle hijau sebelumnya)
        is_bearish_harami = (
            is_uptrend_context and
            (p_close > p_open) and (p_body >= min_candle_range * 0.35) and
            (c_close < c_open) and
            (c_high <= p_high + spread_tol * 0.2) and  # High candle kedua TIDAK BOLEH lebih tinggi dari mother candle!
            (c_low >= p_low - spread_tol * 0.2) and   # Low candle kedua TIDAK BOLEH lebih rendah dari mother candle!
            (c_open <= p_close + spread_tol * 0.5) and
            (c_close >= p_open - spread_tol * 0.5) and
            (body_size >= 0.25 * c_range) and
            (body_size <= p_body * 0.70) and
            (p_range >= min_candle_range * 0.70) and
            is_resistance_zone and
            not is_dark_cloud_cover
        )

        # Evaluasi Konfluensi Bullish
        bull_matches = []
        if is_bullish_engulfing:
            bull_matches.append("Bullish Engulfing")
        if is_hammer:
            bull_matches.append("Hammer")
        if is_inverted_hammer:
            bull_matches.append("Inverted Hammer")
        if is_morning_star:
            bull_matches.append("Morning Star")
        if is_tweezer_bottom:
            bull_matches.append("Tweezer Bottom")
        if is_piercing_line:
            bull_matches.append("Piercing Line")
        if is_bullish_harami:
            bull_matches.append("Bullish Harami")
        if is_three_white_soldiers:
            bull_matches.append("Three White Soldiers")
        if is_bullish_kicker:
            bull_matches.append("Bullish Kicker")
        if is_three_inside_up:
            bull_matches.append("Three Inside Up")
        if is_bullish_abandoned_baby:
            bull_matches.append("Bullish Abandoned Baby")
        if is_rising_three_methods:
            bull_matches.append("Rising Three Methods")
        if is_macd_golden_cross:
            bull_matches.append("MACD Golden Cross")
        if is_double_bottom:
            bull_matches.append("Double Bottom (W-Pattern)")

        # Konfluensi Teknis Bullish (Harga berada di Support / Lower Band kuartil bawah)
        bb_bull_zone = (c_close <= cur_bb_basis) and (c_low <= cur_bb_lower or p_low <= prev_bb_lower or c_low <= (cur_bb_basis + cur_bb_lower) / 2)
        if bb_bull_zone:
            bull_matches.append("Bollinger Support Zone")
        if cur_macd > cur_signal:
            bull_matches.append("MACD Bullish Momentum")
        if self.interval in ("1h", "2h"):
            if c_close > cur_ema200 or cur_rsi < 35:
                bull_matches.append("Major EMA200 Support / Uptrend")
        # Konfluensi Stochastic Oscillator (8, 3, 3)
        if is_stoch_oversold or (is_stoch_bullish_cross and cur_stoch_k <= 45.0):
            bull_matches.append("Stochastic (8,3,3) Oversold / Bullish Cross")

        # Konfluensi Institusional Smart Money Concepts (SMC) & ICT
        smc_data = smc_engine.analyze(df, cur_idx=cur_idx, symbol=symbol)
        for b_conf in smc_data.get("bull_confluences", []):
            bull_matches.append(b_conf)

        # 8 Pilar Teknikal Lanjutan (Chart Patterns, RSI Divergence, Fibonacci, Killzones, BB Squeeze, EMA Pullback, RBS/SBR, VWAP)
        adv_tech = advanced_technicals.analyze(
            df=df,
            rsi_series=rsi_series,
            bb_upper=bb_upper,
            bb_lower=bb_lower,
            bb_basis=bb_basis,
            ema20_series=ema20_series,
            ema50_series=ema50_series,
            cur_ema200=cur_ema200,
            cur_idx=cur_idx,
        )
        for b_conf in adv_tech.get("bull_confluences", []):
            bull_matches.append(b_conf)

        # Evaluasi Konfluensi Multi-Timeframe (1H Macro Compass + 15m Intermediate Setup)
        df_15m = self.fetch_candle_data(symbol, interval="15m") if self.interval != "15m" else df
        df_1h = self.fetch_candle_data(symbol, interval="1h") if self.interval in ("1m", "3m", "5m", "15m") else None
        mtf_eval_bull = mtf_engine.evaluate_mtf_confluence(df_15m, df_1h=df_1h, candidate_action="BUY")
        mtf_eval_bear = mtf_engine.evaluate_mtf_confluence(df_15m, df_1h=df_1h, candidate_action="SELL")

        for m_conf in mtf_eval_bull.get("confluences", []):
            bull_matches.append(m_conf)

        # Evaluasi Konfluensi Bearish
        bear_matches = []
        for be_conf in smc_data.get("bear_confluences", []):
            bear_matches.append(be_conf)
        for be_conf in adv_tech.get("bear_confluences", []):
            bear_matches.append(be_conf)
        for m_conf in mtf_eval_bear.get("confluences", []):
            bear_matches.append(m_conf)

        if is_bearish_engulfing:
            bear_matches.append("Bearish Engulfing")
        if is_shooting_star:
            bear_matches.append("Shooting Star")
        if is_hanging_man:
            bear_matches.append("Hanging Man")
        if is_evening_star:
            bear_matches.append("Evening Star")
        if is_tweezer_top:
            bear_matches.append("Tweezer Top")
        if is_dark_cloud_cover:
            bear_matches.append("Dark Cloud Cover")
        if is_bearish_harami:
            bear_matches.append("Bearish Harami")
        if is_three_black_crows:
            bear_matches.append("Three Black Crows")
        if is_bearish_kicker:
            bear_matches.append("Bearish Kicker")
        if is_three_inside_down:
            bear_matches.append("Three Inside Down")
        if is_bearish_abandoned_baby:
            bear_matches.append("Bearish Abandoned Baby")
        if is_falling_three_methods:
            bear_matches.append("Falling Three Methods")
        if is_macd_death_cross:
            bear_matches.append("MACD Death Cross")
        if is_double_top:
            bear_matches.append("Double Top (M-Pattern)")

        # Konfluensi Teknis Bearish (Harga berada di Resistance / Upper Band kuartil atas)
        bb_bear_zone = (c_close >= cur_bb_basis) and (c_high >= cur_bb_upper or p_high >= prev_bb_upper or c_high >= (cur_bb_basis + cur_bb_upper) / 2)
        if bb_bear_zone:
            bear_matches.append("Bollinger Resistance Zone")
        if cur_macd < cur_signal:
            bear_matches.append("MACD Bearish Momentum")
        if self.interval in ("1h", "2h"):
            if c_close < cur_ema200 or cur_rsi > 65:
                bear_matches.append("Major EMA200 Resistance / Downtrend")
        # Konfluensi Stochastic Oscillator (8, 3, 3)
        if is_stoch_overbought or (is_stoch_bearish_cross and cur_stoch_k >= 55.0):
            bear_matches.append("Stochastic (8,3,3) Overbought / Bearish Cross")

        trend_status = "Uptrend (di atas EMA 200)" if c_close > cur_ema200 else "Downtrend (di bawah EMA 200)"
        macd_status = "MACD Golden Cross / Bullish" if cur_macd > cur_signal else "MACD Death Cross / Bearish"

        NON_CANDLE_INDICATORS = {
            "Bollinger Support Zone", "Bollinger Resistance Zone",
            "MACD Bullish Momentum", "MACD Bearish Momentum",
            "MACD Golden Cross", "MACD Death Cross",
            "Stochastic (8,3,3) Oversold / Bullish Cross",
            "Stochastic (8,3,3) Overbought / Bearish Cross",
            "Major EMA200 Support / Uptrend", "Major EMA200 Resistance / Downtrend",
            "Konfluensi MTF Grade-A (15m Searah Bullish)",
            "Konfluensi MTF Grade-A (15m Searah Bearish)",
            "Konfluensi MTF Grade-A (15m & 30m Searah Bullish)",
            "Konfluensi MTF Grade-A (15m & 30m Searah Bearish)",
            "Konfluensi MTF (15m/30m Bullish)",
            "Konfluensi MTF (15m/30m Bearish)",
            "⚠️ Peringatan: Counter-Trend (Melawan Tren Mayor 15m)",
            "Regular Bullish RSI Divergence (Exhaustion Reversal)",
            "Hidden Bullish RSI Divergence (Trend Continuation)",
            "Regular Bearish RSI Divergence (Exhaustion Reversal)",
            "Hidden Bearish RSI Divergence (Trend Continuation)",
            "Fibonacci Golden Pocket 0.618 (Optimal Trade Entry)",
            "Fibonacci Golden Pocket 0.618 (Optimal Bearish Rejection)",
            "Bollinger Volatility Squeeze Breakout (Bullish Expansion)",
            "Bollinger Volatility Squeeze Breakdown (Bearish Expansion)",
            "Ascending Triangle Pressure (Bullish Breakout Setup)",
            "Descending Triangle Pressure (Bearish Breakdown Setup)",
            # 4 Teknik Institusional Sebagai Area Nilai / Lokasi (Bukan Pemicu Entri Mandiri):
            "Bullish Dynamic EMA Pullback (EMA 20/50 Trend Bounce)",
            "Bearish Dynamic EMA Pullback (EMA 20/50 Trend Bounce)",
            "Role Reversal RBS (Resistance Became Support Retest)",
            "Role Reversal SBR (Support Became Resistance Retest)",
            "Institutional VWAP Baseline Trend Bounce (Bullish)",
            "Institutional VWAP Baseline Trend Bounce (Bearish)",
            "Institutional VWAP -2σ Mean Reversion (Oversold Bounce)",
            "Institutional VWAP +2σ Mean Reversion (Overbought Rejection)",
            "Bullish Breaker Block Retest (Failed Supply Flip)",
            "Bearish Breaker Block Retest (Failed Demand Flip)",
            # Struktur SMC / Likuiditas (Konteks Lokasi):
            "Bullish FVG Retest (Unmitigated)",
            "Bearish FVG Retest (Unmitigated)",
            "Institutional Bullish Order Block",
            "Institutional Bearish Order Block",
            "Bullish CHoCH (Structure Shift)",
            "Bearish CHoCH (Structure Shift)",
            "Bullish BOS (Trend Expansion)",
            "Bearish BOS (Trend Expansion)",
            "Sell-side Liquidity Sweep (SSL)",
            "Buy-side Liquidity Sweep (BSL)",
        }
        # Pola Candlestick & SMC Pembalikan Bullish (Reversal BUY)
        BULLISH_REVERSAL_PATTERNS = {
            "Bullish Engulfing", "Hammer", "Inverted Hammer", "Morning Star",
            "Piercing Line", "Tweezer Bottom", "Bullish Harami", "Bullish Abandoned Baby",
            "Three Inside Up", "Three White Soldiers", "Bullish Kicker",
            "Double Bottom (W-Pattern)", "Inverse Head and Shoulders Reversal",
            "Bullish FVG Retest (Unmitigated)", "Institutional Bullish Order Block",
            "Bullish CHoCH (Structure Shift)", "Sell-side Liquidity Sweep (SSL)",
            "Role Reversal RBS (Resistance Became Support Retest)",
            "Bullish Breaker Block Retest (Failed Supply Flip)",
            "Institutional VWAP -2σ Mean Reversion (Oversold Bounce)"
        }
        # Pola Candlestick & SMC Kelanjutan Tren Bullish (Breakout Continuation BUY)
        BULLISH_CONTINUATION_PATTERNS = {
            "Bullish Engulfing", "Three White Soldiers", "Bullish Kicker", "Rising Three Methods",
            "Bull Flag Breakout (High-Probability Continuation)",
            "Bullish BOS (Trend Expansion)",
            "Bullish Dynamic EMA Pullback (EMA 20/50 Trend Bounce)",
            "Role Reversal RBS (Resistance Became Support Retest)",
            "Institutional VWAP Baseline Trend Bounce (Bullish)",
            "Bullish Breaker Block Retest (Failed Supply Flip)"
        }
        # Pola Candlestick & SMC Kelanjutan Tren Bearish (Breakout Continuation SELL)
        BEARISH_CONTINUATION_PATTERNS = {
            "Bearish Engulfing", "Three Black Crows", "Bearish Kicker", "Falling Three Methods",
            "Bear Flag Breakdown (High-Probability Continuation)",
            "Bearish BOS (Trend Expansion)",
            "Bearish Dynamic EMA Pullback (EMA 20/50 Trend Bounce)",
            "Role Reversal SBR (Support Became Resistance Retest)",
            "Institutional VWAP Baseline Trend Bounce (Bearish)",
            "Bearish Breaker Block Retest (Failed Demand Flip)"
        }
        # Pola Candlestick & SMC Pembalikan Puncak Bearish (Top Reversal SELL)
        BEARISH_REVERSAL_PATTERNS = {
            "Bearish Engulfing", "Shooting Star", "Hanging Man", "Evening Star", "Dark Cloud Cover",
            "Tweezer Top", "Bearish Harami", "Bearish Abandoned Baby", "Three Inside Down",
            "Double Top (M-Pattern)", "Head and Shoulders Reversal",
            "Bearish FVG Retest (Unmitigated)", "Institutional Bearish Order Block",
            "Bearish CHoCH (Structure Shift)", "Buy-side Liquidity Sweep (BSL)",
            "Role Reversal SBR (Support Became Resistance Retest)",
            "Bearish Breaker Block Retest (Failed Demand Flip)",
            "Institutional VWAP +2σ Mean Reversion (Overbought Rejection)"
        }

        # SOP STEVE NISON: Pemicu Entri Fisik Wajib Berupa Pola Candlestick Murni atau Chart Pattern Terkonfirmasi
        PURE_CANDLESTICK_TRIGGERS_BULL = {
            "Hammer", "Inverted Hammer", "Bullish Engulfing", "Piercing Line",
            "Tweezer Bottom", "Morning Star", "Three White Soldiers",
            "Bullish Kicker", "Three Inside Up", "Bullish Harami",
            "Bullish Abandoned Baby", "Rising Three Methods",
            "Double Bottom (W-Pattern)", "Inverse Head and Shoulders Reversal",
            "Bull Flag Breakout (High-Probability Continuation)"
        }
        PURE_CANDLESTICK_TRIGGERS_BEAR = {
            "Shooting Star", "Hanging Man", "Bearish Engulfing", "Dark Cloud Cover",
            "Tweezer Top", "Evening Star", "Three Black Crows",
            "Bearish Kicker", "Three Inside Down", "Bearish Harami",
            "Bearish Abandoned Baby", "Falling Three Methods",
            "Double Top (M-Pattern)", "Head and Shoulders Reversal",
            "Bear Flag Breakdown (High-Probability Continuation)"
        }

        has_pure_bull_candle = any(m in PURE_CANDLESTICK_TRIGGERS_BULL for m in bull_matches)
        has_pure_bear_candle = any(m in PURE_CANDLESTICK_TRIGGERS_BEAR for m in bear_matches)
        has_bull_reversal = any(m in BULLISH_REVERSAL_PATTERNS for m in bull_matches)
        has_bull_continuation = any(m in BULLISH_CONTINUATION_PATTERNS for m in bull_matches)
        has_bear_continuation = any(m in BEARISH_CONTINUATION_PATTERNS for m in bear_matches)
        has_bear_reversal = any(m in BEARISH_REVERSAL_PATTERNS for m in bear_matches)

        # ==============================================================================
        # STRATEGI PASCA-BERITA (POST-NEWS TREND CONTINUATION STRATEGY)
        # ==============================================================================
        post_news_ctx = news_filter.get_post_news_context(symbol, max_drift_min=120)
        is_post_news = post_news_ctx.get("is_post_news", False)

        if is_post_news:
            ev_title = post_news_ctx.get("event_title", "High-Impact News")
            mins_ago = post_news_ctx.get("minutes_since_event", 0)

            # Hitung arah pergerakan impuls sejak rilis berita
            bars_ago = max(3, min(int(mins_ago / 5), len(df) - 1)) if self.interval == "5m" else 6
            price_pre = float(df['Open'].iloc[-bars_ago])
            delta_pips = (c_close - price_pre) * 10000

            # Konfirmasi arah impuls pasca berita: pergerakan pips atau alignment MTF
            if delta_pips <= -6.0 or (c_close < cur_ema50 and not mtf_eval_bull.get("is_allowed")):
                post_news_bias = "BEARISH"
            elif delta_pips >= 6.0 or (c_close > cur_ema50 and not mtf_eval_bear.get("is_allowed")):
                post_news_bias = "BULLISH"
            else:
                post_news_bias = "NEUTRAL"

            # 1. ATURAN PANTANGAN MUTLAK (ANTI-COUNTER TREND SAAT DRIFT BERITA)
            if post_news_bias == "BEARISH":
                # DILARANG KERAS BUY saat pasar berada dalam fase terjun bebas / impuls bearish berita
                if bull_matches:
                    logger.info("🚫 [POST-NEWS GUARD] BUY dibatalkan karena fase Bearish Drift pasca '%s' (%s, %.1f pips)", ev_title, symbol, delta_pips)
                    bull_matches = []

                # 2. KONFLUENSI KELANJUTAN TREN PASCA-BERITA (PULLBACK / RETEST SELL)
                # Entri SELL diizinkan saat harga melakukan retest ke EMA 20/50, FVG, atau Stochastic hook down
                is_bear_retest = (
                    (c_high >= cur_ema20 - spread_tol or c_high >= cur_ema50 - spread_tol) or
                    (cur_stoch_k >= 35.0 and is_stoch_bearish_cross) or
                    has_bear_continuation or has_bear_reversal
                )
                if is_bear_retest and c_close <= cur_bb_basis + spread_tol:
                    bear_matches.append(f"Post-News Trend Continuation (Retest Bearish pasca '{ev_title}')")

            elif post_news_bias == "BULLISH":
                # DILARANG KERAS SELL saat pasar berada dalam fase lonjakan impuls bullish berita
                if bear_matches:
                    logger.info("🚫 [POST-NEWS GUARD] SELL dibatalkan karena fase Bullish Drift pasca '%s' (%s, +%.1f pips)", ev_title, symbol, delta_pips)
                    bear_matches = []

                # 2. KONFLUENSI KELANJUTAN TREN PASCA-BERITA (PULLBACK / RETEST BUY)
                is_bull_retest = (
                    (c_low <= cur_ema20 + spread_tol or c_low <= cur_ema50 + spread_tol) or
                    (cur_stoch_k <= 65.0 and is_stoch_bullish_cross) or
                    has_bull_continuation or has_bull_reversal
                )
                if is_bull_retest and c_close >= cur_bb_basis - spread_tol:
                    bull_matches.append(f"Post-News Trend Continuation (Retest Bullish pasca '{ev_title}')")

        # ==============================================================================
        # SOP RULE #4 & ATURAN SIMETRIS REVERSAL / BREAKOUT CONTINUATION (UPTREND & DOWNTREND)
        # ==============================================================================
        
        # 1. ATURAN FILTER SELL:
        # A. Hard Veto Kontradiksi Multi-Timeframe (MTF: 15m) - Larangan Mutlak Counter-Trend & Counter-Momentum
        if not mtf_eval_bear.get("is_allowed") and self.interval in ("1m", "3m", "5m"):
            reason_bear = mtf_eval_bear.get("contradiction_reason", "Melawan tren mayor / momentum 15m")
            logger.info("🚫 [MTF VETO] Sinyal SELL dibatalkan: %s.", reason_bear)
            bear_matches = []

        # B. Anti-Steep EMA Uptrend Veto: Dilarang SELL jika EMA20 & EMA50 keduanya menanjak tajam
        elif (cur_ema20 > prev_ema20 and cur_ema50 > prev_ema50 and c_close > cur_ema50) and self.interval in ("1m", "3m", "5m"):
            logger.info("🚫 [EMA SLOPE VETO] Sinyal SELL dibatalkan karena tren EMA20 & EMA50 menanjak tajam ke atas (Bullish Slope).")
            bear_matches = []

        # C. Reversal Confirmation Veto: Pola pembalikan wajib memiliki bar konfirmasi merah solid
        elif has_bear_reversal and (c_close > c_open or c_close > (p_open + p_close) / 2):
            logger.info("🚫 [REVERSAL VETO] Sinyal SELL dibatalkan karena bar penutupan tidak mengonfirmasi rejeksi bearish solid.")
            bear_matches = []

        # D. Anti-Rocket & Momentum Collision Veto:
        # Dilarang SELL jika MACD sedang Golden Cross aktif (Bullish Momentum), KECUALI jika ada konfirmasi pola candlestick reversal murni solid yang ditutup merah dengan sumbu penolakan atas nyata, bearish engulfing, atau dorongan momentum bearish solid
        elif cur_macd > cur_signal:
            is_valid_bear_rejection = (
                has_pure_bear_candle and c_close < c_open and (
                    upper_shadow >= 0.18 * c_range or
                    is_bearish_engulfing or
                    body_size >= 0.40 * c_range
                )
            )
            if not is_valid_bear_rejection:
                logger.info("🚫 [MOMENTUM VETO] Sinyal SELL dibatalkan karena bertabrakan dengan MACD Bullish Golden Cross tanpa konfirmasi candlestick reversal murni solid.")
                bear_matches = []
        elif cur_rsi > 78.0 and upper_shadow < 0.35 * c_range:
            bear_matches = []

        # D2. Micro-trend EMA Alignment Veto: Dilarang SELL jika harga ditutup di atas EMA20 dan EMA20 sedang menanjak (kecuali ada pola pembalikan puncak)
        elif c_close > cur_ema20 and cur_ema20 > prev_ema20 and not (has_bear_reversal or is_shooting_star):
            logger.info("🚫 [EMA ALIGNMENT VETO] Sinyal SELL dibatalkan karena harga di atas EMA20 yang sedang menanjak (Micro-Bullish Rebound).")
            bear_matches = []

        # E. Pola Breakout Continuation & F. Pola Bearish Top Reversal & G. Larangan Mutlak SELL:
        elif c_close > c_open and not is_shooting_star:
            bear_matches = []
        elif is_fresh_golden_cross and cur_rsi < 70.0:
            # DILARANG SELL tepat setelah Golden Cross terjadi (1-2 bar terakhir), karena momentum kenaikan baru saja dimulai
            bear_matches = []
        elif has_bear_continuation:
            if cur_rsi < 28 or c_close <= cur_bb_lower + spread_tol or c_low <= cur_bb_lower:
                bear_matches = []
        elif has_bear_reversal:
            if cur_rsi < 35.0 or c_close <= cur_bb_lower:
                bear_matches = []
        else:
            if cur_rsi < 32 or c_close <= cur_bb_lower:
                bear_matches = []

        # 2. ATURAN FILTER BUY:
        # A. Hard Veto Kontradiksi Multi-Timeframe (MTF: 15m) - Larangan Mutlak Counter-Trend
        if not mtf_eval_bull.get("is_allowed") and self.interval in ("1m", "3m", "5m"):
            reason_bull = mtf_eval_bull.get("contradiction_reason", "Melawan tren mayor 15m")
            logger.info("🚫 [MTF VETO] Sinyal BUY dibatalkan: %s.", reason_bull)
            bull_matches = []

        # B. Anti-Steep EMA Downtrend Veto: Dilarang BUY jika EMA20 & EMA50 keduanya menukik tajam
        elif (cur_ema20 < prev_ema20 and cur_ema50 < prev_ema50 and c_close < cur_ema50) and self.interval in ("1m", "3m", "5m"):
            logger.info("🚫 [EMA SLOPE VETO] Sinyal BUY dibatalkan karena tren EMA20 & EMA50 menukik tajam ke bawah (Bearish Slope).")
            bull_matches = []

        # C. Reversal Confirmation Veto: Pola pembalikan wajib memiliki bar konfirmasi hijau solid
        elif has_bull_reversal and (c_close < c_open or c_close < (p_open + p_close) / 2):
            logger.info("🚫 [REVERSAL VETO] Sinyal BUY dibatalkan karena bar penutupan tidak mengonfirmasi rejeksi bullish solid.")
            bull_matches = []

        # D. Anti-Falling Knife & Momentum Collapse Veto:
        # Dilarang BUY jika MACD sedang Death Cross aktif (Bearish Momentum), KECUALI jika ada konfirmasi pola candlestick reversal murni solid yang ditutup hijau dengan sumbu pantulan nyata, bullish engulfing, atau dorongan momentum bullish solid
        elif cur_macd < cur_signal:
            is_valid_bull_rejection = (
                has_pure_bull_candle and c_close > c_open and (
                    lower_shadow >= 0.18 * c_range or
                    is_bullish_engulfing or
                    body_size >= 0.40 * c_range
                )
            )
            if not is_valid_bull_rejection:
                logger.info("🚫 [MOMENTUM VETO] Sinyal BUY dibatalkan karena bertabrakan dengan MACD Bearish Death Cross tanpa konfirmasi candlestick reversal murni solid.")
                bull_matches = []
        elif cur_rsi < 22.0 and lower_shadow < 0.35 * c_range:
            bull_matches = []

        # D2. Micro-trend EMA Alignment Veto: Dilarang BUY jika harga ditutup di bawah EMA20 dan EMA20 sedang menukik turun (kecuali ada pola pembalikan dasar)
        elif c_close < cur_ema20 and cur_ema20 < prev_ema20 and not (has_bull_reversal or is_hammer):
            logger.info("🚫 [EMA ALIGNMENT VETO] Sinyal BUY dibatalkan karena harga di bawah EMA20 yang sedang menukik (Micro-Bearish Plunge).")
            bull_matches = []

        # C. Pola Breakout Continuation & D. Pola Bullish Reversal & E. Larangan Mutlak BUY:
        elif c_close < c_open and lower_shadow < 1.5 * body_size and not is_inverted_hammer:
            bull_matches = []
        elif is_fresh_death_cross and cur_rsi > 30.0:
            # DILARANG BUY tepat setelah Death Cross terjadi (1-2 bar terakhir), karena momentum penurunan baru saja dimulai
            bull_matches = []
        elif has_bull_continuation:
            if cur_rsi > 72 or c_close >= cur_bb_upper - spread_tol or c_high >= cur_bb_upper:
                bull_matches = []
        elif has_bull_reversal:
            if cur_rsi > 68.0 or c_close >= cur_bb_upper:
                bull_matches = []
        else:
            if cur_rsi > 68 or c_close >= cur_bb_upper:
                bull_matches = []

        # Anti-Overbought Exhaustion Veto: Dilarang keras BUY di pucuk jika Stochastic > 82 atau RSI > 70 atau harga menembus BB Upper KECUALI jika didukung breakout/reversal terkonfirmasi
        if (cur_stoch_k > 82.0 or cur_rsi > 70.0 or c_close >= cur_bb_upper) and not (has_bull_continuation or has_bull_reversal):
            logger.info("🚫 [OVERBOUGHT VETO] Sinyal BUY dibatalkan karena pasar overextended di area pucuk/jenuh beli (Stoch: %.1f, RSI: %.1f, BB Upper: %.4f).", cur_stoch_k, cur_rsi, cur_bb_upper)
            bull_matches = []

        # Anti-Oversold Exhaustion Veto: Dilarang keras SELL di dasar jika Stochastic < 18 atau RSI < 30 atau harga menembus BB Lower KECUALI jika didukung breakdown/reversal terkonfirmasi
        if (cur_stoch_k < 18.0 or cur_rsi < 30.0 or c_close <= cur_bb_lower) and not (has_bear_continuation or has_bear_reversal):
            logger.info("🚫 [OVERSOLD VETO] Sinyal SELL dibatalkan karena pasar overextended di area lembah/jenuh jual (Stoch: %.1f, RSI: %.1f, BB Lower: %.4f).", cur_stoch_k, cur_rsi, cur_bb_lower)
            bear_matches = []

        # Anti-Divergence Collision Hard Veto: Dilarang keras bertransaksi melawan arah divergensi RSI aktif
        has_bull_div = any("Bullish" in b and "Divergence" in b for b in adv_tech.get("bull_confluences", []))
        if has_bull_div and bear_matches:
            logger.info("🚫 [DIVERGENCE VETO] Sinyal SELL dibatalkan karena terdeteksi Bullish RSI Divergence (indikasi kuat dorongan/pantulan naik).")
            bear_matches = []

        has_bear_div = any("Bearish" in b and "Divergence" in b for b in adv_tech.get("bear_confluences", []))
        if has_bear_div and bull_matches:
            logger.info("🚫 [DIVERGENCE VETO] Sinyal BUY dibatalkan karena terdeteksi Bearish RSI Divergence (indikasi kuat tekanan/penurunan tajam).")
            bull_matches = []

        # Anti-Opposing Order Block Veto: Dilarang BUY jika tepat menabrak Bearish Order Block; Dilarang SELL jika tepat menabrak Bullish Order Block
        has_opposing_bear_ob = "Institutional Bearish Order Block" in smc_data.get("bear_confluences", [])
        if has_opposing_bear_ob and bull_matches:
            logger.info("🚫 [ORDER BLOCK VETO] Sinyal BUY dibatalkan karena harga tepat menabrak Institutional Bearish Order Block institusional.")
            bull_matches = []

        has_opposing_bull_ob = "Institutional Bullish Order Block" in smc_data.get("bull_confluences", [])
        if has_opposing_bull_ob and bear_matches:
            logger.info("🚫 [ORDER BLOCK VETO] Sinyal SELL dibatalkan karena harga tepat menabrak Institutional Bullish Order Block institusional.")
            bear_matches = []

        # Anti-Opposing Golden Pocket Veto: Dilarang BUY jika tepat menabrak Bearish Golden Pocket; Dilarang SELL jika di Bullish Golden Pocket
        has_opposing_bear_gp = "Fibonacci Golden Pocket 0.618 (Optimal Bearish Rejection)" in adv_tech.get("bear_confluences", [])
        if has_opposing_bear_gp and bull_matches and not has_bull_continuation:
            logger.info("🚫 [GOLDEN POCKET VETO] Sinyal BUY dibatalkan karena harga berada di dalam zona penolakan Fibonacci Bearish Golden Pocket (0.58-0.65).")
            bull_matches = []

        has_opposing_bull_gp = "Fibonacci Golden Pocket 0.618 (Optimal Trade Entry)" in adv_tech.get("bull_confluences", [])
        if has_opposing_bull_gp and bear_matches and not has_bear_continuation:
            logger.info("🚫 [GOLDEN POCKET VETO] Sinyal SELL dibatalkan karena harga berada di dalam zona pantulan Fibonacci Bullish Golden Pocket (0.58-0.65).")
            bear_matches = []

        # Anti-Proximity Veto (Anti-Buying into Resistance & Anti-Selling into Support):
        # Mencegah entry terjepit langsung di bawah Resistance kuat atau tepat di atas Support kuat tanpa ruang (headroom) yang cukup menuju TP
        sl_dist = smc_data.get("sl_distance", max(smc_data.get("atr_val", 0.001) * 1.5, 0.00060))
        is_jpy = "JPY" in sym_upper
        is_gold = "XAU" in sym_upper or "GOLD" in sym_upper
        is_crypto = "BTC" in sym_upper
        is_eth = "ETH" in sym_upper
        if is_gold:
            pip_unit = 0.10
        elif is_crypto:
            pip_unit = 1.00
        elif is_eth:
            pip_unit = 0.10
        elif is_jpy:
            pip_unit = 0.01
        else:
            pip_unit = 0.0001

        min_headroom = max(sl_dist * 0.40, 2.0 * pip_unit)
        vwap_upper_2 = adv_tech.get("vwap_upper_2")
        vwap_lower_2 = adv_tech.get("vwap_lower_2")
        nearest_res = smc_data.get("nearest_res")
        nearest_sup = smc_data.get("nearest_sup")

        # 1. EVALUASI HEADROOM UNTUK BUY (CEK ATAP RESISTANCE)
        if bull_matches:
            # Veto jika harga telah mencapai atau berada di atas batas VWAP +2σ (Statistical Premium Overextension) KECUALI jika didukung kelanjutan tren terkonfirmasi
            if vwap_upper_2 is not None and c_close >= vwap_upper_2 - (0.5 * pip_unit) and not has_bull_continuation:
                logger.info(
                    "🚫 [RESISTANCE PROXIMITY VETO] Sinyal BUY dibatalkan karena harga telah menyentuh/melampaui zona atap VWAP +2σ (Close: %.5f >= VWAP +2σ: %.5f).",
                    c_close, vwap_upper_2
                )
                bull_matches = []
            else:
                overhead_res_candidates = []
                if vwap_upper_2 is not None and vwap_upper_2 > c_close:
                    overhead_res_candidates.append(("VWAP +2σ", vwap_upper_2))
                if nearest_res is not None and nearest_res > c_close:
                    overhead_res_candidates.append(("SMC Resistance", nearest_res))

                if overhead_res_candidates and not has_bull_continuation:
                    res_name, res_lvl = min(overhead_res_candidates, key=lambda x: x[1])
                    headroom = res_lvl - c_close
                    if headroom < min_headroom:
                        headroom_pips = headroom / pip_unit
                        min_headroom_pips = min_headroom / pip_unit
                        logger.info(
                            "🚫 [RESISTANCE PROXIMITY VETO] Sinyal BUY dibatalkan karena jarak ke Resistance terdekat terlalu sempit (%s: %.5f, Headroom: %.1f pips < Minimal: %.1f pips).",
                            res_name, res_lvl, headroom_pips, min_headroom_pips
                        )
                        bull_matches = []

        # 2. EVALUASI HEADROOM UNTUK SELL (CEK LANTAI SUPPORT)
        if bear_matches:
            # Veto jika harga telah mencapai atau berada di bawah batas VWAP -2σ (Statistical Discount Overextension) KECUALI jika didukung kelanjutan tren terkonfirmasi
            if vwap_lower_2 is not None and c_close <= vwap_lower_2 + (0.5 * pip_unit) and not has_bear_continuation:
                logger.info(
                    "🚫 [SUPPORT PROXIMITY VETO] Sinyal SELL dibatalkan karena harga telah menyentuh/melampaui zona lantai VWAP -2σ (Close: %.5f <= VWAP -2σ: %.5f).",
                    c_close, vwap_lower_2
                )
                bear_matches = []
            else:
                floor_sup_candidates = []
                if vwap_lower_2 is not None and vwap_lower_2 < c_close:
                    floor_sup_candidates.append(("VWAP -2σ", vwap_lower_2))
                if nearest_sup is not None and nearest_sup < c_close:
                    floor_sup_candidates.append(("SMC Support", nearest_sup))

                if floor_sup_candidates and not has_bear_continuation:
                    sup_name, sup_lvl = max(floor_sup_candidates, key=lambda x: x[1])
                    headroom = c_close - sup_lvl
                    if headroom < min_headroom:
                        headroom_pips = headroom / pip_unit
                        min_headroom_pips = min_headroom / pip_unit
                        logger.info(
                            "🚫 [SUPPORT PROXIMITY VETO] Sinyal SELL dibatalkan karena jarak ke Support terdekat terlalu sempit (%s: %.5f, Headroom: %.1f pips < Minimal: %.1f pips).",
                            sup_name, sup_lvl, headroom_pips, min_headroom_pips
                        )
                        bear_matches = []

        # Anti-Dead Market & Volatility Compression Veto:
        # Dilarang membuka posisi pada pasar mati / kompresi ekstrem di mana ATR terlalu kecil DAN lebar BB terlalu sempit secara bersamaan
        if (bull_matches or bear_matches) and self.interval in ("1m", "3m", "5m"):
            atr_pips = smc_data.get("atr_pips", 0.0)
            bb_width_pips = (cur_bb_upper - cur_bb_lower) / pip_unit
            tf_factor = 0.6 if self.interval == "1m" else (0.8 if self.interval == "3m" else 1.0)

            if is_gold:
                min_atr_thresh = 4.0 * tf_factor
                min_bb_width_thresh = 18.0 * tf_factor
            elif is_jpy:
                min_atr_thresh = 2.5 * tf_factor
                min_bb_width_thresh = 10.0 * tf_factor
            elif is_crypto:
                min_atr_thresh = 20.0 * tf_factor
                min_bb_width_thresh = 80.0 * tf_factor
            elif is_eth:
                min_atr_thresh = 2.0 * tf_factor
                min_bb_width_thresh = 8.0 * tf_factor
            else:
                min_atr_thresh = 1.8 * tf_factor
                min_bb_width_thresh = 8.0 * tf_factor

            if atr_pips < min_atr_thresh and bb_width_pips < min_bb_width_thresh:
                logger.info(
                    "🚫 [LOW VOLATILITY VETO] Sinyal %s dibatalkan karena pasar mati / kompresi sempit "
                    "(ATR: %.1f < Min: %.1f pips DAN BB Width: %.1f < Min: %.1f pips).",
                    symbol, atr_pips, min_atr_thresh, bb_width_pips, min_bb_width_thresh
                )
                bull_matches = []
                bear_matches = []

        # ==============================================================================
        # SISTEM VALIDASI 4 PILAR INDEPENDEN (REGIME GATE & VALUE-TRIGGER HARMONY)
        # ==============================================================================
        # Pilar 1: Struktur & Tren Makro (MTF 1H & 15m searah / ADX >= 20 / EMA Stacking)
        # Pilar 2: Lokasi / Area Nilai (FVG, Order Block, RBS/SBR, Dynamic EMA, Fib OTE, BB Zone)
        # Pilar 3: Pemicu Candlestick Fisik Steve Nison Terkonfirmasi pada Closed Bar
        # Pilar 4: Harmoni Momentum (Stochastic Rebound/Cross, MACD Momentum, RSI Divergence)
        
        p1_bull = bool(mtf_eval_bull.get("confluences")) or (mtf_eval_bull.get("bias_15m") == "Bullish") or (c_close > cur_ema200)
        p2_bull = bb_bull_zone or bool(smc_data.get("bull_confluences")) or bool(adv_tech.get("bull_confluences"))
        p3_bull = has_pure_bull_candle
        p4_bull = is_stoch_oversold or is_stoch_bullish_cross or (cur_macd > cur_signal) or any("Divergence" in b for b in adv_tech.get("bull_confluences", []))

        # Filter Netral Bias: Jika bias 15m Netral (pasar choppy), tolak TF 5m KECUALI pantulan ekstrem VWAP -2σ + Liquidity Sweep
        is_vwap_extreme_bull = any("VWAP -2σ" in b for b in adv_tech.get("bull_confluences", [])) and any("Liquidity Sweep" in b for b in smc_data.get("bull_confluences", []))
        if mtf_eval_bull.get("is_neutral_bias") and not is_vwap_extreme_bull:
            p1_bull = False

        bull_all_pillars = p1_bull and p2_bull and p3_bull and p4_bull

        p1_bear = bool(mtf_eval_bear.get("confluences")) or (mtf_eval_bear.get("bias_15m") == "Bearish") or (c_close < cur_ema200)
        p2_bear = bb_bear_zone or bool(smc_data.get("bear_confluences")) or bool(adv_tech.get("bear_confluences"))
        p3_bear = has_pure_bear_candle
        p4_bear = is_stoch_overbought or is_stoch_bearish_cross or (cur_macd < cur_signal) or any("Divergence" in b for b in adv_tech.get("bear_confluences", []))

        # Filter Netral Bias: Jika bias 15m Netral (pasar choppy), tolak TF 5m KECUALI penolakan ekstrem VWAP +2σ + Liquidity Sweep
        is_vwap_extreme_bear = any("VWAP +2σ" in b for b in adv_tech.get("bear_confluences", [])) and any("Liquidity Sweep" in b for b in smc_data.get("bear_confluences", []))
        if mtf_eval_bear.get("is_neutral_bias") and not is_vwap_extreme_bear:
            p1_bear = False

        bear_all_pillars = p1_bear and p2_bear and p3_bear and p4_bear

        pattern_name = None
        if bull_matches and bull_all_pillars:
            pattern_name = f"BUY (4 Pilar Terkonfirmasi: {', '.join(bull_matches)})"
        elif bear_matches and bear_all_pillars:
            pattern_name = f"SELL (4 Pilar Terkonfirmasi: {', '.join(bear_matches)})"
        else:
            if bull_matches and not bull_all_pillars:
                missing = []
                if not p1_bull: missing.append("Pilar 1 (Tren MTF 1H/15m / ADX)")
                if not p2_bull: missing.append("Pilar 2 (Lokasi Nilai SMC/EMA/Fib)")
                if not p3_bull: missing.append("Pilar 3 (Pemicu Candlestick Steve Nison)")
                if not p4_bull: missing.append("Pilar 4 (Harmoni Momentum Stoch/MACD)")
                logger.debug("⏳ [%s] %s | Sinyal BUY ditolak karena belum lulus 4 Pilar: Kurang %s", self.interval, symbol, " & ".join(missing))
            elif bear_matches and not bear_all_pillars:
                missing = []
                if not p1_bear: missing.append("Pilar 1 (Tren MTF 1H/15m / ADX)")
                if not p2_bear: missing.append("Pilar 2 (Lokasi Nilai SMC/EMA/Fib)")
                if not p3_bear: missing.append("Pilar 3 (Pemicu Candlestick Steve Nison)")
                if not p4_bear: missing.append("Pilar 4 (Harmoni Momentum Stoch/MACD)")
                logger.debug("⏳ [%s] %s | Sinyal SELL ditolak karena belum lulus 4 Pilar: Kurang %s", self.interval, symbol, " & ".join(missing))

        rsi_status = "RSI Oversold" if cur_rsi < 30 else ("RSI Overbought" if cur_rsi > 70 else "RSI Netral")
        bb_status = f"BB Upper: {cur_bb_upper:.4f}, BB Lower: {cur_bb_lower:.4f}"
        tf_info = TIMEFRAME_SL_TP_CONFIG.get(self.interval, TIMEFRAME_SL_TP_CONFIG["5m"])
        mtf_summary = mtf_eval_bull.get("summary", "")

        if already_processed:
            return {
                "has_signal": False,
                "symbol": symbol.upper(),
                "timeframe": self.interval,
                "price": round(c_close, 5),
                "candle_close": round(c_close, 5),
                "live_spot_price": round(live_spot_price, 5),
                "trend": trend_status,
                "rsi": cur_rsi,
                "macd": macd_status,
                "reason": f"Sinyal bar {c_time} sudah dikirim (Standby)",
                "timestamp": c_time,
                "mtf_summary": mtf_summary,
            }

        # Tidak memunculkan sinyal jika konfluensi kurang dari 2 atau terdapat kontradiksi fatal
        if not pattern_name:
            reason = "Menunggu konfluensi pola Grade-A"
            if bull_matches:
                reason = f"Bullish belum cukup konfluensi ({', '.join(bull_matches)})"
            elif bear_matches:
                reason = f"Bearish belum cukup konfluensi ({', '.join(bear_matches)})"
            elif cur_rsi < 35:
                reason = f"RSI Oversold ({cur_rsi:.1f}) di area Support (Dilarang SELL)"
            elif cur_rsi > 65:
                reason = f"RSI Overbought ({cur_rsi:.1f}) di area Resistance (Dilarang BUY)"
            return {
                "has_signal": False,
                "symbol": symbol.upper(),
                "timeframe": self.interval,
                "price": round(c_close, 5),
                "candle_close": round(c_close, 5),
                "live_spot_price": round(live_spot_price, 5),
                "trend": trend_status,
                "rsi": cur_rsi,
                "macd": macd_status,
                "reason": reason,
                "timestamp": c_time,
                "atr_pips": smc_data.get("atr_pips", 0.0),
                "smc_summary": smc_data.get("summary", ""),
                "mtf_summary": mtf_summary,
            }

        self.last_processed_timestamps[f"{symbol.upper()}_{self.interval}"] = c_time

        kz_info = adv_tech.get("killzone_info", {})
        kz_badge = f" | {kz_info.get('confluence')}" if kz_info.get("is_active") else ""
        adv_summary = f" | AdvTech: {adv_tech.get('summary')}" if adv_tech.get("summary") else ""

        stoch_status = f"Stoch(8,3,3): {cur_stoch_k:.1f}/{cur_stoch_d:.1f}"
        if is_stoch_oversold:
            stoch_status += " (Oversold)"
        elif is_stoch_overbought:
            stoch_status += " (Overbought)"

        indicator_summary = (
            f"{algo_name} | Pola: {pattern_name} | RSI: {cur_rsi:.1f} ({rsi_status}) | "
            f"MACD: {macd_status} | {stoch_status} | Tren: {trend_status} | {bb_status} | "
            f"ATR(14): {smc_data.get('atr_pips', 0.0)} pips | {mtf_summary}{kz_badge}{adv_summary} | Target: {tf_info['description']}"
        )
        chosen_tp_mode = smc_data.get("buy_tp_mode") if "BUY" in pattern_name else smc_data.get("sell_tp_mode", "Default 1.5x SL")
        notes_detail = (
            f"Open: {c_open:.5f}, High: {c_high:.5f}, Low: {c_low:.5f}, Close: {c_close:.5f}, "
            f"Stoch_K: {cur_stoch_k:.1f}, Stoch_D: {cur_stoch_d:.1f}, "
            f"EMA20: {cur_ema20:.4f}, EMA50: {cur_ema50:.4f}, BB_Lower: {cur_bb_lower:.4f}, BB_Upper: {cur_bb_upper:.4f}, "
            f"ATR_Pips: {smc_data.get('atr_pips', 0.0)}, Dynamic_Buy_SL: {smc_data.get('buy_sl')}, Dynamic_Buy_TP: {smc_data.get('buy_tp')}, "
            f"Dynamic_Sell_SL: {smc_data.get('sell_sl')}, Dynamic_Sell_TP: {smc_data.get('sell_tp')}, "
            f"TP_Mode: {chosen_tp_mode}, "
            f"SMC_Summary: {smc_data.get('summary', '-')}, "
            f"AdvTech_Summary: {adv_tech.get('summary', '-')}, "
            f"Killzone_Session: {kz_info.get('session', 'Normal')}, "
            f"MTF_15m_Bias: {mtf_eval_bull.get('bias_15m')}, "
            f"SOP_Timeframe: {self.interval}, Target_SL_TP: {tf_info['description']}"
        )

        return {
            "has_signal": True,
            "symbol": symbol.upper(),
            "timeframe": self.interval,
            "price": round(c_close, 5),
            "candle_close": round(c_close, 5),
            "live_spot_price": round(live_spot_price, 5),
            "trend": trend_status,
            "rsi": cur_rsi,
            "macd": macd_status,
            "reason": pattern_name,
            "indicator_status": indicator_summary,
            "notes": notes_detail,
            "timestamp": c_time,
            "atr_pips": smc_data.get("atr_pips", 0.0),
            "dynamic_sl": smc_data.get("buy_sl") if "BUY" in pattern_name else smc_data.get("sell_sl"),
            "dynamic_tp": smc_data.get("buy_tp") if "BUY" in pattern_name else smc_data.get("sell_tp"),
            "tp_mode": chosen_tp_mode,
            "smc_summary": smc_data.get("summary", ""),
            "adv_tech_summary": adv_tech.get("summary", ""),
            "killzone_session": kz_info.get("session", "Normal"),
            "mtf_summary": mtf_summary,
            "mtf_15m_bias": mtf_eval_bull.get("bias_15m"),
        }

    async def scan_loop(self, once: bool = False) -> None:
        """Run continuous real-time market scan loop."""
        logger.info(
            "Starting Live Market Scanner for: %s (Entry Timeframe: %s [Trend Filter: 15m], Interval: %ds)",
            ", ".join(self.symbols),
            self.entry_interval,
            self.check_interval_sec,
        )

        while True:
            for symbol in self.symbols:
                # 1. Filter News Blackout sebelum memproses candle
                is_blackout, blackout_reason = news_filter.is_news_blackout(symbol)
                if is_blackout:
                    logger.warning("🚫 %s | NEWS BLACKOUT AKTIF: %s. Melewati simbol ini demi keamanan modal.", symbol, blackout_reason)
                    continue

                self.interval = self.entry_interval
                try:
                    df = self.fetch_candle_data(symbol, interval=self.entry_interval)

                    # Kirim notifikasi status koneksi WebSocket TradingView ke Telegram jika terjadi gangguan/pemulihan
                    if self.tv_alert_pending:
                        alert_to_send = self.tv_alert_pending
                        self.tv_alert_pending = None
                        await self.notifier.send_message(alert_to_send)

                    if df is not None:
                        # 0. Sinkronkan harga riil eksekusi MT5 ke DB (Anti-desinkronisasi SL/TP)
                        signal_tracker.sync_executed_orders()

                        # Evaluasi outcome yang dilaporkan langsung dari MT5 Bridge Windows
                        external_outcomes = signal_tracker.process_external_outcomes()

                        # Evaluasi otomatis sinyal terbuka via riwayat candle terkini (6 bar / 30m) agar tidak ada spike SL terlewat
                        recent_df = df.tail(6) if len(df) >= 6 else df
                        curr_h = float(recent_df["High"].max())
                        curr_l = float(recent_df["Low"].min())
                        curr_c = float(df["Close"].iloc[-1])
                        candle_outcomes = signal_tracker.check_signals_outcome(
                            symbol=symbol,
                            current_high=curr_h,
                            current_low=curr_l,
                            current_close=curr_c,
                            bar_time=str(df.index[-1]),
                        )

                        all_outcomes = external_outcomes + candle_outcomes
                        for outcome in all_outcomes:
                            loss_diag = None
                            if outcome.get("status") == "LOSS":
                                # 1. AI seketika menganalisis penyebab 1 trade loss ini
                                loss_diag = signal_tracker.diagnose_single_loss(self.rag_engine, outcome)

                            outcome_msg = signal_tracker.format_telegram_outcome_alert(outcome, loss_diagnosis=loss_diag)
                            await self.notifier.send_message(outcome_msg)

                            # 2. Trigger evaluasi mandiri AI jika mencapai batas akumulasi 2 LOSS (min_losses=2)
                            if outcome.get("status") == "LOSS":
                                reflection = signal_tracker.reflect_and_self_optimize(self.rag_engine, min_losses=2)
                                if reflection:
                                    logger.info("🧠 [SELF-LEARNED] AI menyelesaikan refleksi kegagalan dan memperbarui SOP.")
                                    ref_alert = (
                                        "🧠 *LAPORAN EVALUASI MANDIRI AI (SELF-REFLECTION)* 🧠\n"
                                        "═" * 32 + "\n"
                                        "⚠️ *Terdeteksi akumulasi 2 trade LOSS.* AI telah mengaudit penyebab kegagalan dan menyuntikkan aturan pantangan baru ke ChromaDB:\n\n"
                                        f"{reflection}\n"
                                        "═" * 32 + "\n"
                                        "✅ *SOP lokal dan Guardrails telah diperbarui otomatis!*"
                                    )
                                    await self.notifier.send_message(ref_alert)

                            # 3. Trigger evaluasi mandiri AI jika mencapai batas akumulasi 3 BREAKEVEN (min_breakevens=3)
                            if outcome.get("status") == "BREAKEVEN":
                                be_reflection = signal_tracker.reflect_and_self_optimize_breakeven(self.rag_engine, min_breakevens=3)
                                if be_reflection:
                                    logger.info("🛡️ [BREAKEVEN-AUDIT] AI menyelesaikan audit akumulasi 3x Breakeven dan memperbarui SOP.")
                                    be_alert = (
                                        "🛡️ *LAPORAN ANALISIS AKUMULASI BREAKEVEN (3x BE HIT)* 🛡️\n"
                                        "═" * 32 + "\n"
                                        "⚠️ *Terdeteksi akumulasi 3 trade menyentuh Stop Loss Breakeven.* AI telah mengaudit penyebab reli harga tertahan sebelum Take Profit dan menyuntikkan aturan optimasi ke ChromaDB:\n\n"
                                        f"{be_reflection}\n"
                                        "═" * 32 + "\n"
                                        "✅ *SOP lokal dan Guardrails optimasi Exit telah diperbarui otomatis!*"
                                    )
                                    await self.notifier.send_message(be_alert)
                        # 0a. Proteksi Posisi Aktif & Correlation Shield:
                        # Dilarang membuka posisi baru jika simbol ini atau kluster mata uang ini masih memiliki trade berjalan
                        is_cluster_blocked, c_name, conf_sym = signal_tracker.has_cluster_conflict(symbol)
                        if is_cluster_blocked:
                            logger.info("🛡️ [%s] %s | CORRELATION SHIELD: Kluster '%s' sudah memiliki posisi berjalan (%s). Melewati scanning.", self.interval, symbol, c_name, conf_sym)
                            continue

                        # 0b. Cooldown pasca Loss: Jika trade sebelumnya pada simbol ini terkena SL dalam 15 menit terakhir, jeda sejenak untuk mencegah overtrading
                        is_cooldown, cooldown_reason = signal_tracker.is_loss_cooldown(symbol, cooldown_minutes=15)
                        if is_cooldown:
                            logger.info("⏳ [%s] %s | LOSS COOLDOWN AKTIF: %s. Melewati scanning demi proteksi modal.", self.interval, symbol, cooldown_reason)
                            continue

                        setup = self.analyze_indicators_and_candles(symbol, df)
                        if setup and setup.get("has_signal"):
                            logger.info("🎯 [%s] SETUP VALID DITEMUKAN pada %s [Bar Selesai: %s]: %s", self.interval, symbol, setup.get("timestamp", "-"), setup["indicator_status"])
                            decision = self.rag_engine.evaluate_market_setup(setup)
                            if self.only_entry and decision.action == "WAIT":
                                logger.info("Keputusan AI adalah WAIT (Setup belum memenuhi SOP). Pesan Telegram disaring (hanya mengirim BUY/SELL).")
                            else:
                                await self.notifier.send_signal_decision(decision)

                                # 1. Eksekusi order otomatis ke MetaTrader 5 (Auto-Entry LANGSUNG ke Antrean MT5)
                                order_ticket = None
                                if self.auto_trade and decision.action in ("BUY", "SELL"):
                                    order_res = mt5_executor.dispatch_signal_order(
                                        decision=decision,
                                        setup=setup,
                                        lot_size=self.lot_size,
                                    )
                                    if order_res.get("success"):
                                        order_ticket = order_res.get("ticket")
                                        logger.info(
                                            "🚀 [MT5 AUTO-ORDER] Order %s %s didispatch ke antrean MT5 (Lot: %.2f, OrderID: %s)!",
                                            decision.action, symbol, self.lot_size, order_res.get("order_id", "-")
                                        )
                                    else:
                                        logger.error("❌ [MT5 AUTO-ORDER FAILED] Gagal mendispatch order %s %s: %s",
                                                     decision.action, symbol, order_res.get("error", "Unknown error"))

                                # 2. Catat sinyal ke dalam database untuk dilacak hasilnya (Outcome Tracker)
                                signal_tracker.record_signal(decision, setup, ticket=order_ticket)
                        elif setup:
                            logger.info(
                                "⏳ [%s] %s [Bar Selesai: %s] | Live Price: %.5f | RSI: %.1f | Tren: %s | MACD: %s | Status: %s | %s",
                                self.interval,
                                symbol,
                                setup.get("timestamp", "-"),
                                setup.get("price", 0.0),
                                setup.get("rsi", 50.0),
                                setup.get("trend", "-"),
                                setup.get("macd", "-"),
                                setup.get("reason", "Standby"),
                                setup.get("mtf_summary", ""),
                            )
                        else:
                            logger.info("⏳ [%s] %s | Menunggu candle berikutnya...", self.interval, symbol)
                    else:
                        logger.warning("⚠️ [%s] %s | Gagal mengambil data candle pasar.", self.interval, symbol)
                except Exception as exc:
                    logger.error("Scan error on %s [%s]: %s", symbol, self.interval, exc)

            if once:
                break
            await asyncio.sleep(self.check_interval_sec)


def main() -> None:
    """CLI Entrypoint for Live Market Scanner."""
    parser = argparse.ArgumentParser(description="Live Bollinger Bands & MACD Market Scanner")
    parser.add_argument(
        "--symbols",
        type=str,
        default="EURUSD,XAUUSD,GBPUSD",
        help="Comma-separated symbols to monitor (e.g. EURUSD,XAUUSD,USDJPY)",
    )
    parser.add_argument(
        "--interval",
        type=str,
        default="5m",
        help="Candle entry timeframe (default: 5m). 15m is automatically analyzed in background for trend bias.",
    )
    parser.add_argument("--poll-sec", type=int, default=60, help="Check interval in seconds")
    parser.add_argument(
        "--include-wait",
        action="store_true",
        help="Also send Telegram alert if decision is WAIT (default: False, only sends BUY and SELL)",
    )
    parser.add_argument(
        "--once",
        action="store_true",
        help="Run scan once and exit (useful for testing and instant signal generation)",
    )
    parser.add_argument(
        "--stats",
        action="store_true",
        help="Tampilkan laporan performa trading (Win Rate, Net Pips, Profit Factor) dari SQLite lalu keluar",
    )
    parser.add_argument(
        "--reflect",
        action="store_true",
        help="Jalankan refleksi mandiri AI (Self-Reflection) pada riwayat trade yang rugi dan suntikkan guardrail ke ChromaDB",
    )
    parser.add_argument(
        "--auto-trade",
        action="store_true",
        default=True,
        help="Aktifkan auto-entry ke MetaTrader 5 (default: True)",
    )
    parser.add_argument(
        "--no-auto-trade",
        action="store_false",
        dest="auto_trade",
        help="Nonaktifkan auto-entry ke MetaTrader 5 (hanya scanner & Telegram)",
    )
    parser.add_argument(
        "--lot",
        type=float,
        default=0.01,
        help="Ukuran volume/lot untuk auto-entry MT5 (default: 0.01)",
    )

    args = parser.parse_args()

    if args.stats:
        stats = signal_tracker.get_performance_report()
        print("\n" + "═" * 45)
        print("📊 LAPORAN PERFORMA TRADING (OUTCOME TRACKER)")
        print("═" * 45)
        print(f"• Total Sinyal        : {stats['total_signals']}")
        print(f"• Sinyal Terbuka      : {stats['open']}")
        print(f"• Sinyal Selesai      : {stats['completed']}")
        print(f"• Menang (Take Profit): {stats['wins']}")
        print(f"• Kalah (Stop Loss)   : {stats['losses']}")
        print(f"• Win Rate            : {stats['win_rate_pct']}%")
        print(f"• Net Pips            : {stats['net_pips']} pips")
        print(f"• Profit Factor       : {stats['profit_factor']}")
        print("═" * 45 + "\n")
        return

    if args.reflect:
        from rag_engine import RAGEngine
        engine = RAGEngine()
        print("\n🧠 Menjalankan Evaluasi & Optimasi Mandiri AI (Self-Reflection)...")
        res = signal_tracker.reflect_and_self_optimize(engine, min_losses=1)
        if res:
            print("\n✅ Refleksi LOSS selesai! Aturan pantangan baru disuntikkan ke ChromaDB:\n")
            print(res)
        be_res = signal_tracker.reflect_and_self_optimize_breakeven(engine, min_breakevens=1)
        if be_res:
            print("\n🛡️ Audit BREAKEVEN selesai! Aturan optimasi exit baru disuntikkan ke ChromaDB:\n")
            print(be_res)
        if not res and not be_res:
            print("\nℹ️ Belum ada riwayat LOSS atau BREAKEVEN baru yang perlu dievaluasi.")
        return

    raw_symbols = args.symbols.strip().upper()
    if raw_symbols in ("ALL", "ALL_MARKETS"):
        # Semua pasar Forex + Gold + Kripto (kecuali saham lokal IDX)
        symbols_list = [s for s in YF_SYMBOL_MAP.keys() if s not in ("BBCA", "BBRI")]
    elif raw_symbols in ("FOREX", "ALL_FOREX"):
        # Seluruh pasangan mata uang Forex
        symbols_list = [s for s in YF_SYMBOL_MAP.keys() if s not in ("BBCA", "BBRI", "XAUUSD", "BTCUSD")]
    else:
        symbols_list = [s.strip().upper() for s in args.symbols.split(",") if s.strip()]

    scanner = LiveMarketScanner(
        symbols=symbols_list,
        interval=args.interval,
        check_interval_sec=args.poll_sec,
        only_entry=not args.include_wait,
        auto_trade=args.auto_trade,
        lot_size=args.lot,
    )

    asyncio.run(scanner.scan_loop(once=args.once))


if __name__ == "__main__":
    main()
