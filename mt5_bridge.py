"""
MetaTrader 5 Windows Bridge for AI Trading Bot.
Run this script on Windows (via Windows PowerShell / CMD):
    python mt5_bridge.py
or to test connection:
    python mt5_bridge.py --test

Features:
- Connects directly to active MetaTrader 5 Desktop terminal
- Automatic broker symbol detection (handles EURUSD, EURUSDm, EURUSD.pro, etc.)
- Auto-detects supported filling mode (FOK, IOC, RETURN)
- Enforces fixed lot size (default 0.01)
- Executes dynamic ATR SL & TP from AI scanner signals
- Sends Telegram notification upon successful order execution
"""

import os
import sys
import time
from datetime import datetime, timedelta
import json
import shutil
import logging
import argparse
from pathlib import Path
from typing import Optional, Dict, Any

try:
    import MetaTrader5 as mt5
except ImportError:
    print("=" * 60)
    print("ERROR: Package MetaTrader5 belum terinstall di Python Windows!")
    print("Silakan buka CMD / PowerShell Windows dan jalankan:")
    print("    pip install MetaTrader5 requests python-dotenv")
    print("=" * 60)
    sys.exit(1)

try:
    import requests
except ImportError:
    requests = None

# Configure Logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-7s | %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger("MT5Bridge")

BASE_DIR = Path(__file__).resolve().parent
PENDING_DIR = BASE_DIR / "orders_queue" / "pending"
EXECUTED_DIR = BASE_DIR / "orders_queue" / "executed"
FAILED_DIR = BASE_DIR / "orders_queue" / "failed"
OUTCOMES_DIR = BASE_DIR / "orders_queue" / "outcomes"
QUEUE_DIR = BASE_DIR / "orders_queue"
LIVE_POSITIONS_FILE = QUEUE_DIR / "live_positions.json"

PENDING_DIR.mkdir(parents=True, exist_ok=True)
EXECUTED_DIR.mkdir(parents=True, exist_ok=True)
FAILED_DIR.mkdir(parents=True, exist_ok=True)
OUTCOMES_DIR.mkdir(parents=True, exist_ok=True)

# Active position tracking dictionary {ticket: order_data}
active_positions: Dict[int, Dict[str, Any]] = {}


def sync_live_mt5_positions_file() -> None:
    """Sync real-time active positions from MT5 terminal into orders_queue/live_positions.json for WSL scanner."""
    try:
        positions = mt5.positions_get()
        pos_list = []
        if positions:
            for p in positions:
                pos_list.append({
                    "ticket": int(p.ticket),
                    "symbol": str(p.symbol),
                    "action": "BUY" if p.type == mt5.ORDER_TYPE_BUY else "SELL",
                    "volume": float(p.volume),
                    "price_open": float(p.price_open),
                    "sl": float(p.sl),
                    "tp": float(p.tp),
                    "profit": float(p.profit),
                    "time": int(p.time)
                })

        payload = {
            "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
            "count": len(pos_list),
            "positions": pos_list
        }

        temp_file = QUEUE_DIR / "temp_live_positions.json"
        with open(temp_file, "w", encoding="utf-8") as f:
            json.dump(payload, f, indent=2)
        temp_file.replace(LIVE_POSITIONS_FILE)
    except Exception as e:
        logger.debug("Error syncing live positions file: %s", e)

# Load configuration from .env if available
TELEGRAM_BOT_TOKEN = None
TELEGRAM_CHAT_ID = None
DEFAULT_LOT_SIZE = 0.01

env_path = BASE_DIR / ".env"
if env_path.exists():
    try:
        with open(env_path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line.startswith("#") or "=" not in line:
                    continue
                k, v = line.split("=", 1)
                k = k.strip()
                v = v.strip().strip('"').strip("'")
                if k == "TELEGRAM_BOT_TOKEN":
                    TELEGRAM_BOT_TOKEN = v
                elif k == "TELEGRAM_CHAT_ID":
                    TELEGRAM_CHAT_ID = v
                elif k == "MT5_LOT_SIZE":
                    try:
                        DEFAULT_LOT_SIZE = float(v)
                    except ValueError:
                        pass
    except Exception as e:
        logger.warning("Gagal membaca .env: %s", e)


def send_telegram_alert(message: str) -> None:
    """Send trade execution alert to Telegram if configured."""
    if not (TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID and requests):
        return
    try:
        url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
        payload = {
            "chat_id": TELEGRAM_CHAT_ID,
            "text": message,
            "parse_mode": "Markdown",
            "disable_web_page_preview": True,
        }
        requests.post(url, json=payload, timeout=5)
    except Exception as ex:
        logger.warning("Gagal mengirim notifikasi Telegram: %s", ex)


def init_mt5() -> bool:
    """Initialize connection to MetaTrader 5 terminal."""
    if not mt5.initialize():
        logger.error("Inisialisasi MT5 gagal. Error code: %s", mt5.last_error())
        logger.error("Pastikan aplikasi MetaTrader 5 Desktop di Windows SUDAH DIBUKA dan login ke akun demo.")
        return False

    acc = mt5.account_info()
    if acc is None:
        logger.error("Gagal mendapatkan info akun MT5. Pastikan Anda sudah login ke akun demo.")
        return False

    logger.info("=" * 60)
    logger.info("✅ TERHUBUNG KE METATRADER 5 BERHASIL!")
    logger.info("• Akun Login  : %d (%s)", acc.login, "DEMO" if acc.trade_mode == 0 else "REAL")
    logger.info("• Nama Server : %s", acc.server)
    logger.info("• Nama Pemilik: %s", acc.name)
    logger.info("• Saldo/Equity: $%.2f / $%.2f %s", acc.balance, acc.equity, acc.currency)
    logger.info("• Leverage    : 1:%d", acc.leverage)
    logger.info("• Fixed Lot   : %.2f", DEFAULT_LOT_SIZE)
    # Pastikan simbol utama langsung aktif di Market Watch
    if mt5.symbol_select("EURUSD", True):
        logger.info("• Simbol Utama: EURUSD (Aktif di Market Watch)")
    else:
        logger.warning("• Simbol Utama: EURUSD belum aktif di Market Watch (error: %s)", mt5.last_error())
    logger.info("=" * 60)
    return True


def ensure_mt5_connected(max_wait_sec: int = 5) -> bool:
    """Ensure MetaTrader 5 terminal is initialized, IPC is healthy, and connected to broker."""
    start_time = time.time()
    while time.time() - start_time < max_wait_sec:
        try:
            t_info = mt5.terminal_info()
            acc = mt5.account_info()
            if t_info is not None and getattr(t_info, "connected", False) and acc is not None:
                return True
            logger.warning("⚠️ Terminal MT5 terputus/offline (connected=%s, last_error=%s). Merestart koneksi...", 
                           getattr(t_info, "connected", False) if t_info else "None", mt5.last_error())
            mt5.shutdown()
            time.sleep(0.5)
            if mt5.initialize():
                time.sleep(1.0)
                t_info = mt5.terminal_info()
                acc = mt5.account_info()
                if t_info is not None and getattr(t_info, "connected", False) and acc is not None:
                    logger.info("✅ Terminal MT5 & Akun #%s berhasil tersambung kembali!", acc.login)
                    mt5.symbol_select("EURUSD", True)
                    return True
        except Exception as e:
            logger.error("Error saat memeriksa koneksi MT5: %s", e)
        time.sleep(1.0)
    return False


def resolve_symbol(raw_symbol: str, retries: int = 3) -> Optional[str]:
    """Find the exact matching symbol name in the active broker with retry and auto-reconnect."""
    raw = raw_symbol.upper().replace("/", "").replace("_", "")

    for attempt in range(1, retries + 1):
        if not ensure_mt5_connected(max_wait_sec=3):
            logger.warning("Percobaan %d/%d: Terminal MT5 belum terhubung ke broker...", attempt, retries)
            time.sleep(1.0)
            continue

        # 1. Cek langsung info simbol di broker (terlepas dari apakah sudah ada di Market Watch)
        info = mt5.symbol_info(raw)
        if info is not None:
            mt5.symbol_select(raw, True)
            return raw

        # 2. Coba aktifkan langsung via symbol_select
        if mt5.symbol_select(raw, True):
            return raw

        # 3. Cari dengan filter wildcard group (misal *EURUSD*) - sangat cepat & anti-timeout
        candidates = mt5.symbols_get(group=f"*{raw}*")
        if candidates:
            for s in candidates:
                # Utamakan simbol yang aktif ditradingkan
                if s.trade_mode != mt5.SYMBOL_TRADE_MODE_DISABLED:
                    if mt5.symbol_select(s.name, True):
                        logger.info("Simbol '%s' berhasil dipetakan ke '%s' (broker)", raw, s.name)
                        return s.name
            # Fallback ke candidate pertama
            first_name = candidates[0].name
            if mt5.symbol_select(first_name, True):
                logger.info("Simbol '%s' dipetakan ke '%s'", raw, first_name)
                return first_name

        # 4. Cari dengan grup mata uang dasar (misal *EUR*)
        eur_candidates = mt5.symbols_get(group="*EUR*") or ()
        for s in eur_candidates:
            name_clean = s.name.upper().replace("/", "").replace("_", "").replace(".", "")
            if raw in name_clean or name_clean in raw:
                if mt5.symbol_select(s.name, True):
                    logger.info("Simbol '%s' ditemukan di grup Forex: '%s'", raw, s.name)
                    return s.name

        # 5. Cari di seluruh daftar simbol broker (jika tersedia)
        all_syms = mt5.symbols_get() or ()
        for s in all_syms:
            name_clean = s.name.upper().replace("/", "").replace("_", "").replace(".", "")
            if raw in name_clean:
                if mt5.symbol_select(s.name, True):
                    logger.info("Simbol '%s' ditemukan di daftar lengkap broker: '%s'", raw, s.name)
                    return s.name

        if attempt < retries:
            logger.warning("Simbol '%s' belum ditemukan di percobaan %d/%d (last_error: %s), merestart koneksi terminal...", 
                           raw, attempt, retries, mt5.last_error())
            mt5.shutdown()
            time.sleep(0.5)
            mt5.initialize()
            time.sleep(1.0)

    # 6. Diagnostik: Tampilkan simbol yang saat ini ada di Market Watch
    all_syms = mt5.symbols_get() or ()
    visible_syms = [s.name for s in all_syms if getattr(s, "visible", False)]
    t_info = mt5.terminal_info()
    logger.error(
        "❌ Simbol '%s' tidak ditemukan di broker MT5 ini!\n"
        "• Status Terminal MT5: %s (Error code: %s)\n"
        "• Total Simbol di Broker: %d\n"
        "• Simbol aktif di Market Watch Anda: %s\n"
        "• SOLUSI CEPAT: Buka MT5 di laptop -> Klik kanan di daftar 'Market Watch' (Pengawasan Pasar) -> Pilih 'Show All' (Tampilkan Semua).",
        raw,
        "Connected" if (t_info and getattr(t_info, "connected", False)) else "Disconnected/Offline",
        mt5.last_error(),
        len(all_syms),
        ", ".join(visible_syms[:20]) if visible_syms else "KOSONG"
    )
    return None


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
    return 0.00060  # Default majors


def get_filling_type(symbol_info) -> int:
    """Determine the supported filling mode for the symbol."""
    filling_mode = getattr(symbol_info, "filling_mode", 0)
    if filling_mode & 1:  # FOK
        return mt5.ORDER_FILLING_FOK
    elif filling_mode & 2:  # IOC
        return mt5.ORDER_FILLING_IOC
    else:
        return mt5.ORDER_FILLING_RETURN


def execute_order(order_data: Dict[str, Any]) -> Dict[str, Any]:
    """Execute a BUY or SELL order in MetaTrader 5 with exact SL & TP."""
    raw_symbol = order_data.get("symbol", "EURUSD")
    action_str = str(order_data.get("action", "")).upper()
    lot = float(order_data.get("lot", DEFAULT_LOT_SIZE))
    sl_raw = order_data.get("sl")
    tp_raw = order_data.get("tp")
    setup_reason = order_data.get("reason", "AI Signal")

    ensure_mt5_connected(max_wait_sec=3)
    symbol = resolve_symbol(raw_symbol)
    if not symbol:
        err = f"Simbol '{raw_symbol}' tidak ditemukan pada broker MT5 ini."
        logger.error(err)
        return {"success": False, "error": err}

    # 0. CORRELATION SHIELD (MAX 2 PER CLUSTER, MAX 1 PER EXACT SYMBOL)
    try:
        from currency_clusters import get_cluster_conflicts
        open_positions = mt5.positions_get()
        if open_positions:
            active_syms = [p.symbol for p in open_positions]
            is_blocked, cluster_name, conflicting_sym = get_cluster_conflicts(symbol, active_syms, max_per_cluster=2)
            if is_blocked:
                err = (
                    f"🛡️ [CORRELATION SHIELD VETO] Order {action_str} {symbol} ditolak: "
                    f"Batas aktif kluster '{cluster_name}' tercapai ({conflicting_sym}). "
                    f"Maksimal 2 posisi aktif per kluster (dan 1 posisi per simbol) demi proteksi modal!"
                )
                logger.warning(err)
                return {"success": False, "error": err}
    except Exception as cs_err:
        logger.error("Error saat mengevaluasi Correlation Shield di bridge: %s", cs_err)

    symbol_info = mt5.symbol_info(symbol)
    if symbol_info is None:
        ensure_mt5_connected(max_wait_sec=3)
        symbol_info = mt5.symbol_info(symbol)
    if symbol_info is None:
        err = f"Gagal mendapatkan info simbol {symbol}."
        logger.error(err)
        return {"success": False, "error": err}

    # 1. Pastikan simbol aktif di Market Watch dan tunggu tick valid (Bid & Ask > 0)
    mt5.symbol_select(symbol, True)
    
    tick = None
    for _ in range(10):
        t = mt5.symbol_info_tick(symbol)
        if t is not None and t.ask > 0.0 and t.bid > 0.0:
            tick = t
            break
        time.sleep(0.2)

    digits = symbol_info.digits
    point = symbol_info.point

    # 2. Tentukan harga eksekusi awal (Prioritas: tick live, fallback: planned_price)
    planned_price = float(order_data.get("price", 0.0))
    if tick and tick.ask > 0.0 and tick.bid > 0.0:
        price = tick.ask if action_str == "BUY" else tick.bid
    else:
        price = planned_price
        logger.warning("⚠️ Tick live untuk %s belum mengalir dari broker, menggunakan planned price: %.5f", symbol, price)

    if price <= 0.0:
        err = f"Harga eksekusi tidak valid (0.0) untuk {symbol}. Order dibatalkan demi keamanan!"
        logger.error(err)
        return {"success": False, "error": err}

    if action_str == "BUY":
        order_type = mt5.ORDER_TYPE_BUY
    elif action_str == "SELL":
        order_type = mt5.ORDER_TYPE_SELL
    else:
        err = f"Tindakan order tidak valid: {action_str} (Hanya BUY atau SELL)."
        logger.error(err)
        return {"success": False, "error": err}

    # 3. Hitung SL & TP dinamis dengan proteksi multi-lapis (Anti-Zero & Anti-Negative Stops)
    sl_val = 0.0
    tp_val = 0.0

    try:
        raw_sl_f = float(sl_raw) if sl_raw and str(sl_raw) != "N/A" else 0.0
        raw_tp_f = float(tp_raw) if tp_raw and str(tp_raw) != "N/A" else 0.0
    except (ValueError, TypeError):
        raw_sl_f = 0.0
        raw_tp_f = 0.0

    min_floor = get_asset_min_sl_floor(symbol, price)
    tp_mode = str(order_data.get("tp_mode", ""))
    ref_candle_close = float(order_data.get("candle_close", 0.0) or 0.0)

    if raw_sl_f > 0.0:
        # Gunakan ref_candle_close jika tersedia, fallback planned_price, fallback execution price
        ref_p = ref_candle_close if ref_candle_close > 0.0 else (planned_price if planned_price > 0.0 else price)
        sl_dist = abs(raw_sl_f - ref_p)
        if sl_dist < min_floor:
            sl_dist = min_floor

        tp_dist = abs(raw_tp_f - ref_p) if raw_tp_f > 0.0 else round(sl_dist * 1.5, digits)
        min_adaptive_tp = round(sl_dist * 1.25, digits)

        is_adaptive = "Adaptive" in tp_mode
        if not is_adaptive and tp_dist < min_adaptive_tp:
            tp_dist = round(sl_dist * 1.5, digits)
        elif is_adaptive and tp_dist < (min_floor * 0.5):
            tp_dist = round(sl_dist * 1.5, digits)

        if action_str == "BUY":
            sl_val = round(price - sl_dist, digits)
            # Jika Adaptive Resistance dan raw_tp_f masih berada di atas harga riil eksekusi dengan jarak aman:
            if is_adaptive and raw_tp_f > price + (min_floor * 0.5):
                tp_val = raw_tp_f
            else:
                tp_val = round(price + tp_dist, digits)
        else:
            sl_val = round(price + sl_dist, digits)
            # Jika Adaptive Support dan raw_tp_f masih berada di bawah harga riil eksekusi dengan jarak aman:
            if is_adaptive and 0.0 < raw_tp_f < price - (min_floor * 0.5):
                tp_val = raw_tp_f
            else:
                tp_val = round(price - tp_dist, digits)
    else:
        sl_dist = min_floor
        tp_dist = round(min_floor * 1.5, digits)
        if action_str == "BUY":
            sl_val = round(price - sl_dist, digits)
            tp_val = round(price + tp_dist, digits)
        else:
            sl_val = round(price + sl_dist, digits)
            tp_val = round(price - tp_dist, digits)

    # 4. VALIDASI MUTLAK / FAIL-SAFE INTEGRITAS STOP LOSS & TAKE PROFIT:
    is_valid_stops = False
    if sl_val > 0.0 and tp_val > 0.0:
        if action_str == "BUY" and sl_val < price and tp_val > price:
            is_valid_stops = True
        elif action_str == "SELL" and sl_val > price and tp_val < price:
            is_valid_stops = True

    if not is_valid_stops:
        logger.warning("⚠️ Kalkulasi SL/TP berjangkar tidak valid (SL: %s, TP: %s vs Price: %s). Mengaktifkan fallback presisi...",
                       sl_val, tp_val, price)
        # Fallback 1: Gunakan raw_sl_f dan raw_tp_f jika berada di sisi yang benar
        if raw_sl_f > 0.0 and raw_tp_f > 0.0:
            if action_str == "BUY" and raw_sl_f < price and raw_tp_f > price:
                sl_val = round(raw_sl_f, digits)
                tp_val = round(raw_tp_f, digits)
                is_valid_stops = True
            elif action_str == "SELL" and raw_sl_f > price and raw_tp_f < price:
                sl_val = round(raw_sl_f, digits)
                tp_val = round(raw_tp_f, digits)
                is_valid_stops = True

        # Fallback 2: Hitung langsung dari min_floor aset
        if not is_valid_stops:
            if action_str == "BUY":
                sl_val = round(price - min_floor, digits)
                tp_val = round(price + (min_floor * 1.5), digits)
            else:
                sl_val = round(price + min_floor, digits)
                tp_val = round(price - (min_floor * 1.5), digits)
            is_valid_stops = True

    # Pengecekan Terakhir: DILARANG KERAS mengirim order tanpa SL/TP yang sah!
    if sl_val <= 0.0 or tp_val <= 0.0 or (action_str == "BUY" and sl_val >= price) or (action_str == "SELL" and sl_val <= price):
        err = f"🛑 FATAL: Gagal menentukan SL/TP valid untuk {symbol} (SL: {sl_val}, TP: {tp_val}, Price: {price}). Order DIBATALKAN demi proteksi modal!"
        logger.critical(err)
        return {"success": False, "error": err}

    # Ensure min volume
    min_volume = symbol_info.volume_min
    max_volume = symbol_info.volume_max
    step_volume = symbol_info.volume_step
    lot = max(min_volume, min(lot, max_volume))
    lot = round(lot / step_volume) * step_volume
    lot = round(lot, 2)

    filling_type = get_filling_type(symbol_info)

    request = {
        "action": mt5.TRADE_ACTION_DEAL,
        "symbol": symbol,
        "volume": lot,
        "type": order_type,
        "price": price,
        "sl": sl_val,
        "tp": tp_val,
        "deviation": 25,
        "magic": 778899,
        "comment": f"AI 5m {action_str}"[:31],
        "type_time": mt5.ORDER_TIME_GTC,
        "type_filling": filling_type,
    }

    # Kirim order dengan auto-retry jika koneksi broker sempat terputus (Retcode 10031)
    max_retries = 3
    result = None
    for attempt in range(1, max_retries + 1):
        if attempt > 1:
            time.sleep(1.5)
            tick = mt5.symbol_info_tick(symbol)
            if tick and tick.ask > 0.0 and tick.bid > 0.0:
                price = tick.ask if action_str == "BUY" else tick.bid
                request["price"] = price
                if action_str == "BUY":
                    request["sl"] = round(price - sl_dist, digits)
                    request["tp"] = round(price + tp_dist, digits)
                else:
                    request["sl"] = round(price + sl_dist, digits)
                    request["tp"] = round(price - tp_dist, digits)

        logger.info(
            "Mengirim Order ke MT5 (Percobaan %d/%d): %s %s %.2f lot @ %.5f (SL: %.5f, TP: %.5f)...",
            attempt, max_retries, action_str, symbol, lot, request["price"], request["sl"], request["tp"]
        )
        result = mt5.order_send(request)

        if result is None:
            time.sleep(1.0)
            continue

        if result.retcode == 10031:  # Absence of network connection
            logger.warning("⚠️ Koneksi terminal MT5 ke server broker terputus (Retcode 10031). Mencoba menyambungkan ulang...")
            mt5.initialize()
            continue

        break

    if result is None:
        err = f"Gagal mengirim order setelah {max_retries} percobaan. Error: {mt5.last_error()}"
        logger.error(err)
        return {"success": False, "error": err}

    if result.retcode != mt5.TRADE_RETCODE_DONE:
        # Fallback untuk broker ECN / Market Execution yang mewajibkan SL/TP dipasang terpisah
        if result.retcode in (10016, 10015):
            logger.warning("Broker menolak SL/TP awal (Retcode %s). Mencoba open posisi terlebih dahulu lalu memasang SL/TP...", result.retcode)
            request_no_sltp = dict(request)
            request_no_sltp["sl"] = 0.0
            request_no_sltp["tp"] = 0.0
            result = mt5.order_send(request_no_sltp)
            if result and result.retcode == mt5.TRADE_RETCODE_DONE:
                ticket = result.order
                time.sleep(0.2)
                # Dapatkan harga riil buka untuk memasang SL/TP presisi
                pos_list = mt5.positions_get(ticket=ticket)
                real_open = pos_list[0].price_open if (pos_list and len(pos_list) > 0) else price
                
                if action_str == "BUY":
                    mod_sl = round(real_open - sl_dist, digits)
                    mod_tp = round(real_open + tp_dist, digits)
                else:
                    mod_sl = round(real_open + sl_dist, digits)
                    mod_tp = round(real_open - tp_dist, digits)

                modify_req = {
                    "action": mt5.TRADE_ACTION_SLTP,
                    "position": ticket,
                    "symbol": symbol,
                    "sl": mod_sl,
                    "tp": mod_tp,
                }
                mod_res = None
                for mod_attempt in range(3):
                    mod_res = mt5.order_send(modify_req)
                    if mod_res and mod_res.retcode == mt5.TRADE_RETCODE_DONE:
                        logger.info("✅ SL/TP berhasil dipasang ke Ticket #%d! (SL: %.*f, TP: %.*f)", ticket, digits, mod_sl, digits, mod_tp)
                        sl_val = mod_sl
                        tp_val = mod_tp
                        break
                    time.sleep(0.5)

                if not mod_res or mod_res.retcode != mt5.TRADE_RETCODE_DONE:
                    # EMERGENCY CLOSE: Dilarang membiarkan posisi terbuka tanpa SL!
                    logger.critical("🚨 BAHAYA: Gagal memasang SL/TP ke Ticket #%d (%s)! Menutup posisi seketika demi keamanan!",
                                    ticket, mod_res.comment if mod_res else mt5.last_error())
                    t_curr = mt5.symbol_info_tick(symbol)
                    c_price = (t_curr.bid if action_str == "BUY" else t_curr.ask) if t_curr else price
                    emergency_close = {
                        "action": mt5.TRADE_ACTION_DEAL,
                        "position": ticket,
                        "symbol": symbol,
                        "volume": lot,
                        "type": mt5.ORDER_TYPE_SELL if action_str == "BUY" else mt5.ORDER_TYPE_BUY,
                        "price": c_price,
                        "deviation": 25,
                        "magic": 778899,
                        "comment": "Emergency Close No SL",
                        "type_filling": filling_type,
                    }
                    mt5.order_send(emergency_close)
                    return {"success": False, "error": "Order dibatalkan & ditutup darurat karena broker menolak pemasangan SL/TP!"}
            else:
                err = f"Order ditolak oleh broker! Retcode: {result.retcode if result else 'N/A'} ({result.comment if result else mt5.last_error()})"
                logger.error(err)
                return {"success": False, "error": err, "retcode": result.retcode if result else -1}
        else:
            err = f"Order ditolak oleh broker! Retcode: {result.retcode} ({result.comment})"
            logger.error(err)
            return {"success": False, "error": err, "retcode": result.retcode}
            return {"success": False, "error": err, "retcode": result.retcode}

    ticket = result.order
    exec_price = result.price
    logger.info("=" * 60)
    logger.info("🎉 AUTO-ORDER BERHASIL DIEKSEKUSI DI MT5!")
    logger.info("• Ticket      : #%d", ticket)
    logger.info("• Simbol      : %s", symbol)
    logger.info("• Tipe Order  : %s", action_str)
    logger.info("• Lot Size    : %.2f", lot)
    logger.info("• Harga Buka  : %.*f", digits, exec_price)
    logger.info("• Stop Loss   : %.*f", digits, sl_val)
    logger.info("• Take Profit : %.*f", digits, tp_val)
    logger.info("• Setup AI    : %s", setup_reason)
    logger.info("=" * 60)

    # Telegram notification
    action_emoji = "🟢 *BUY*" if action_str == "BUY" else "🔴 *SELL*"
    candle_time = order_data.get("candle_time") or order_data.get("created_at", "-")
    tf_str = order_data.get("timeframe", "5m")
    tg_msg = (
        f"🤖 *AUTO-ENTRY MT5 DIEKSEKUSI* 🚀\n"
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"🎟️ *Ticket ID:* `#{ticket}`\n"
        f"📊 *Instrumen:* `{symbol}` | ⏱️ *TF:* `{tf_str}`\n"
        f"🎯 *Posisi:* {action_emoji} `(Lot: {lot:.2f})`\n"
        f"💵 *Harga Open:* `{exec_price:.{digits}f}`\n"
        f"🛑 *Stop Loss:* `{sl_val:.{digits}f}`\n"
        f"🎯 *Take Profit:* `{tp_val:.{digits}f}`\n"
        f"🧠 *Pola Konfirmasi:* `{setup_reason}`\n"
        f"🕒 *Sumber Candle:* `Candle Bar {candle_time}`\n"
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"📱 _Posisi aktif di MT5 HP. Berasal dari candle {tf_str} tertutup pukul {candle_time}._"
    )
    send_telegram_alert(tg_msg)

    return {
        "success": True,
        "ticket": ticket,
        "symbol": symbol,
        "action": action_str,
        "lot": lot,
        "open_price": exec_price,
        "sl": sl_val,
        "tp": tp_val,
        "retcode": result.retcode,
    }


def load_active_positions(close_if_breached: bool = False) -> None:
    """Load previously executed orders that are still open in MT5."""
    for f in EXECUTED_DIR.glob("*.json"):
        try:
            with open(f, "r", encoding="utf-8") as jf:
                data = json.load(jf)
            exec_res = data.get("execution_result", {})
            ticket = exec_res.get("ticket")
            if ticket:
                pos = mt5.positions_get(ticket=ticket)
                if pos and len(pos) > 0:
                    active_positions[ticket] = data
                    logger.info("📍 Memantau posisi terbuka MT5: Ticket #%d (%s %s)", ticket, data.get("symbol"), data.get("action"))
        except Exception:
            pass
    # Periksa dan pasang SL/TP darurat jika ada posisi aktif tanpa proteksi
    fix_unprotected_positions(close_if_breached=close_if_breached)
    sync_live_mt5_positions_file()


def fix_unprotected_positions(close_if_breached: bool = False) -> None:
    """Scan all active MT5 positions and immediately attach emergency SL/TP if missing (sl <= 0 or tp <= 0).
    Ensures SL and TP are strictly compliant with current live market price and broker stops level to eliminate 'Invalid stops'.
    """
    positions = mt5.positions_get()
    if not positions:
        return

    for pos in positions:
        ticket = pos.ticket
        sym = pos.symbol
        # Jika SL dan TP sudah terpasang valid (> 0), lewati
        if pos.sl > 0.0 and pos.tp > 0.0:
            continue

        sym_info = mt5.symbol_info(sym)
        if not sym_info:
            continue
        digits = sym_info.digits
        point = sym_info.point
        price_open = pos.price_open
        is_buy = pos.type == mt5.ORDER_TYPE_BUY
        min_floor = get_asset_min_sl_floor(sym, price_open)

        order_data = active_positions.get(ticket, {})
        raw_sl = float(order_data.get("sl") or 0.0)
        raw_tp = float(order_data.get("tp") or 0.0)
        plan_p = float(order_data.get("price") or price_open)

        if raw_sl > 0.0 and raw_tp > 0.0:
            sl_dist = abs(raw_sl - plan_p)
            tp_dist = abs(raw_tp - plan_p)
            sl_dist = max(sl_dist, min_floor)
            tp_dist = max(tp_dist, sl_dist * 1.5)
        else:
            sl_dist = min_floor
            tp_dist = round(min_floor * 1.5, digits)

        intended_sl = round(price_open - sl_dist if is_buy else price_open + sl_dist, digits)
        intended_tp = round(price_open + tp_dist if is_buy else price_open - tp_dist, digits)

        # 1. Dapatkan tick live terkini untuk memastikan SL/TP valid di sisi harga pasar sekarang
        mt5.symbol_select(sym, True)
        tick = mt5.symbol_info_tick(sym)
        if not tick or tick.bid <= 0.0 or tick.ask <= 0.0:
            time.sleep(0.3)
            tick = mt5.symbol_info_tick(sym)

        cur_bid = tick.bid if tick else price_open
        cur_ask = tick.ask if tick else price_open
        stops_level = sym_info.trade_stops_level * point
        spread_dist = sym_info.spread * point
        min_stop_distance = max(stops_level, spread_dist, 10 * point)

        # Cek apakah harga pasar sudah melampaui intended SL saat posisi berjalan telanjang
        is_already_breached = False
        if is_buy and cur_bid <= intended_sl:
            is_already_breached = True
        elif not is_buy and cur_ask >= intended_sl:
            is_already_breached = True

        if is_already_breached and close_if_breached:
            logger.warning(
                "🚨 [EMERGENCY CLOSE] Posisi Ticket #%d (%s) telah menembus intended SL (%.5f vs CurPrice: %.5f). Menutup posisi di harga pasar...",
                ticket, sym, intended_sl, cur_bid if is_buy else cur_ask
            )
            close_req = {
                "action": mt5.TRADE_ACTION_DEAL,
                "position": ticket,
                "symbol": sym,
                "volume": pos.volume,
                "type": mt5.ORDER_TYPE_SELL if is_buy else mt5.ORDER_TYPE_BUY,
                "price": cur_bid if is_buy else cur_ask,
                "deviation": 25,
                "magic": 778899,
                "comment": "SL Breached Auto-Close",
                "type_filling": get_filling_type(sym_info),
            }
            c_res = mt5.order_send(close_req)
            if c_res and c_res.retcode == mt5.TRADE_RETCODE_DONE:
                logger.info("✅ Sukses menutup darurat posisi breached Ticket #%d (%s)!", ticket, sym)
                continue

        # Hitung SL/TP legal yang PASTI diterima broker (tidak akan pernah memicu 'Invalid stops')
        if is_buy:
            max_legal_sl = round(cur_bid - min_stop_distance, digits)
            min_legal_tp = round(cur_ask + min_stop_distance, digits)
            # Jika harga sudah turun melampaui intended_sl, pasang SL tepat di bawah harga pasar saat ini agar valid
            fix_sl = min(intended_sl, max_legal_sl)
            fix_tp = max(intended_tp, min_legal_tp)
        else:
            min_legal_sl = round(cur_ask + min_stop_distance, digits)
            max_legal_tp = round(cur_bid - min_stop_distance, digits)
            # Jika harga sudah naik melampaui intended_sl, pasang SL tepat di atas harga pasar saat ini agar valid
            fix_sl = max(intended_sl, min_legal_sl)
            fix_tp = min(intended_tp, max_legal_tp)

        logger.warning(
            "🔧 [AUTO-REPAIR SL/TP] Mendeteksi posisi terbuka Ticket #%d (%s) TANPA PROTEKSI (Open: %.5f, CurPrice: %.5f)! Memasang SL: %.5f, TP: %.5f...",
            ticket, sym, price_open, cur_bid if is_buy else cur_ask, fix_sl, fix_tp
        )
        req = {
            "action": mt5.TRADE_ACTION_SLTP,
            "position": ticket,
            "symbol": sym,
            "sl": fix_sl,
            "tp": fix_tp,
        }
        res = mt5.order_send(req)
        if res and res.retcode == mt5.TRADE_RETCODE_DONE:
            logger.info("✅ [AUTO-REPAIR SL/TP] SUKSES! SL/TP darurat berhasil dipasang ke Ticket #%d (SL: %.*f, TP: %.*f)!",
                        ticket, digits, fix_sl, digits, fix_tp)
            send_telegram_alert(
                f"🛡️ *SL/TP DARURAT BERHASIL DIPASANG!* 🛡️\n"
                f"━━━━━━━━━━━━━━━━━━━━\n"
                f"🎟️ *Ticket ID:* `#{ticket}`\n"
                f"📊 *Instrumen:* `{sym}`\n"
                f"💵 *Harga Open:* `{price_open:.{digits}f}`\n"
                f"📈 *Harga Saat Ini:* `{(cur_bid if is_buy else cur_ask):.{digits}f}`\n"
                f"🛑 *Stop Loss Baru:* `{fix_sl:.{digits}f}`\n"
                f"🎯 *Take Profit Baru:* `{fix_tp:.{digits}f}`\n"
                f"━━━━━━━━━━━━━━━━━━━━\n"
                f"✅ _Posisi kini 100% terlindungi dari risiko kerugian tanpa batas._"
            )
        else:
            logger.critical("❌ [AUTO-REPAIR SL/TP] Gagal memasang SL/TP darurat ke Ticket #%d: %s (Req: SL=%.5f, TP=%.5f, CurBid=%.5f, CurAsk=%.5f)",
                            ticket, res.comment if res else mt5.last_error(), fix_sl, fix_tp, cur_bid, cur_ask)


def check_breakeven_protection() -> None:
    """Auto-move Stop Loss using Stepped Trailing Stop (Multi-Tier Profit Lock):
    - Tier 1: Floating >= +5.0 pips -> Lock +0.5 pip (Breakeven / Risk-Free)
    - Tier 2: Floating >= +8.0 pips -> Lock +4.5 pips (Profit Protection)
    - Tier 3: Floating >= +12.0 pips -> Lock +8.5 pips (Runner Lock)
    """
    if not active_positions:
        return

    for ticket, order_data in list(active_positions.items()):
        pos_list = mt5.positions_get(ticket=ticket)
        if not pos_list or len(pos_list) == 0:
            continue
        pos = pos_list[0]
        sym = pos.symbol
        pip_scale = 0.01 if "JPY" in sym else (0.10 if "XAU" in sym or "GOLD" in sym else 0.0001)

        info = mt5.symbol_info_tick(sym)
        if not info:
            continue

        sym_info = mt5.symbol_info(sym)
        digits = sym_info.digits if sym_info else 5

        cur_bid = info.bid
        cur_ask = info.ask
        is_buy = pos.type == mt5.ORDER_TYPE_BUY

        # Hitung floating profit dalam satuan pips
        floating_pips = (cur_bid - pos.price_open) / pip_scale if is_buy else (pos.price_open - cur_ask) / pip_scale

        # Evaluasi Jenjang Trailing Bertingkat (Stepped Trailing Tiers)
        target_pips = 0.0
        tier_label = ""
        icon = "🛡️"

        if floating_pips >= 12.0:
            target_pips = 8.5
            tier_label = "TIER 3: RUNNER LOCK (+8.5 PIPS)"
            icon = "💎"
        elif floating_pips >= 8.0:
            target_pips = 4.5
            tier_label = "TIER 2: PROFIT LOCK (+4.5 PIPS)"
            icon = "💰"
        elif floating_pips >= 5.0:
            target_pips = 0.5
            tier_label = "TIER 1: BREAKEVEN (+0.5 PIP)"
            icon = "🛡️"

        if target_pips > 0.0:
            new_sl = round(
                pos.price_open + (target_pips * pip_scale) if is_buy
                else pos.price_open - (target_pips * pip_scale),
                digits
            )
            # Pastikan SL baru hanya maju searah keuntungan (tidak pernah mundur)
            should_move = (pos.sl < new_sl) if is_buy else (pos.sl > new_sl or pos.sl <= 0)
            if should_move:
                req = {
                    "action": mt5.TRADE_ACTION_SLTP,
                    "position": ticket,
                    "symbol": sym,
                    "sl": new_sl,
                    "tp": pos.tp,
                }
                res = mt5.order_send(req)
                if res and res.retcode == mt5.TRADE_RETCODE_DONE:
                    logger.info("%s [%s] SL Tiket #%d dimajukan ke %.5f (+%.1f pips, Floating: +%.1f pips)",
                                icon, tier_label, ticket, new_sl, target_pips, floating_pips)
                    be_msg = (
                        f"{icon} *{tier_label} AKTIF!* {icon}\n"
                        f"━━━━━━━━━━━━━━━━━━━━\n"
                        f"🎟️ *Ticket ID:* `#{ticket}`\n"
                        f"📊 *Instrumen:* `{sym}`\n"
                        f"📈 *Floating Profit:* `+{floating_pips:.1f} pips`\n"
                        f"🔒 *Stop Loss Baru:* `{new_sl}` (Terkunci +{target_pips:.1f} pips)\n"
                        f"━━━━━━━━━━━━━━━━━━━━\n"
                        f"✅ _Keuntungan aman terkunci jika pasar berbalik arah!_"
                    )
                    send_telegram_alert(be_msg)


def check_closed_positions() -> None:
    """Monitor active positions and immediately detect SL or TP hits in MT5."""
    if not active_positions:
        return

    closed_tickets = []
    for ticket, order_data in list(active_positions.items()):
        pos = mt5.positions_get(ticket=ticket)
        if pos is None or len(pos) == 0:
            closed_tickets.append(ticket)
            
            # 1. Cari history deals untuk posisi unik ini
            deals = mt5.history_deals_get(position=ticket)
            if not deals or len(deals) == 0:
                now_dt = datetime.now()
                from_dt = now_dt - timedelta(days=3)
                all_deals = mt5.history_deals_get(from_dt, now_dt + timedelta(days=1))
                if all_deals:
                    deals = [d for d in all_deals if getattr(d, "position_id", None) == ticket]

            exit_price = None
            profit = 0.0
            reason_str = "TUTUP POSISI"
            close_time = time.strftime("%Y-%m-%d %H:%M:%S")

            if deals:
                for d in reversed(deals):
                    if d.entry == mt5.DEAL_ENTRY_OUT:
                        exit_price = d.price
                        profit = d.profit
                        close_time = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(d.time))
                        if d.reason == mt5.DEAL_REASON_SL:
                            reason_str = "🛑 STOP LOSS TERSENTUH"
                        elif d.reason == mt5.DEAL_REASON_TP:
                            reason_str = "🎯 TAKE PROFIT TERCAPAI"
                        elif d.reason == mt5.DEAL_REASON_CLIENT:
                            reason_str = "✋ DITUTUP MANUAL"
                        break

            sym = order_data.get("symbol", "EURUSD")
            action = order_data.get("action", "")
            sl_val = float(order_data.get("sl") or 0.0)
            tp_val = float(order_data.get("tp") or 0.0)
            open_p = float(order_data.get("price") or order_data.get("open_price") or 0.0)

            # Fallback jika deal history MT5 belum sinkron
            if exit_price is None:
                info = mt5.symbol_info_tick(sym)
                cur_price = info.bid if action == "BUY" else info.ask if info else 0.0
                if action == "BUY":
                    if sl_val > 0 and (cur_price <= sl_val or (open_p > 0 and cur_price < open_p)):
                        exit_price = sl_val
                        reason_str = "🛑 STOP LOSS TERSENTUH"
                        profit = -abs(exit_price - open_p) * 100000 * float(order_data.get("lot", 0.01))
                    elif tp_val > 0 and cur_price >= tp_val:
                        exit_price = tp_val
                        reason_str = "🎯 TAKE PROFIT TERCAPAI"
                        profit = abs(exit_price - open_p) * 100000 * float(order_data.get("lot", 0.01))
                    else:
                        exit_price = sl_val
                        reason_str = "🛑 STOP LOSS TERSENTUH"
                        profit = -abs(exit_price - open_p) * 100000 * float(order_data.get("lot", 0.01))
                else:  # SELL
                    if sl_val > 0 and (cur_price >= sl_val or (open_p > 0 and cur_price > open_p)):
                        exit_price = sl_val
                        reason_str = "🛑 STOP LOSS TERSENTUH"
                        profit = -abs(exit_price - open_p) * 100000 * float(order_data.get("lot", 0.01))
                    elif tp_val > 0 and cur_price <= tp_val:
                        exit_price = tp_val
                        reason_str = "🎯 TAKE PROFIT TERCAPAI"
                        profit = abs(exit_price - open_p) * 100000 * float(order_data.get("lot", 0.01))
                    else:
                        exit_price = sl_val
                        reason_str = "🛑 STOP LOSS TERSENTUH"
                        profit = -abs(exit_price - open_p) * 100000 * float(order_data.get("lot", 0.01))

            if profit > 0 and "STOP LOSS" not in reason_str:
                status_word = "WIN"
            elif profit >= 0 and "STOP LOSS" in reason_str:
                pip_scale = 0.01 if "JPY" in sym else (0.10 if "XAU" in sym or "GOLD" in sym else 0.0001)
                planned_price = float(order_data.get("price") or open_p or exit_price or 0.0)
                pips_gain = round(abs(exit_price - planned_price) / pip_scale, 1) if (exit_price and planned_price) else 0.5
                if pips_gain >= 2.0:
                    reason_str = f"💰 TRAILING PROFIT LOCK TERSENTUH (+{pips_gain:.1f} pips)"
                    status_word = "WIN"
                else:
                    reason_str = "🛡️ BREAKEVEN TERSENTUH (+PROFIT)"
                    status_word = "BREAKEVEN"
            else:
                status_word = "LOSS"

            logger.info("=" * 60)
            logger.info("📢 POSISI TIKET #%d TELAH SELESAI DI MT5!", ticket)
            logger.info("• Status      : %s (%s)", reason_str, status_word)
            logger.info("• Harga Exit  : %s", exit_price)
            logger.info("• Profit/Rugi : $%.2f", profit)
            logger.info("=" * 60)

            tg_msg = (
                f"{reason_str} DI METATRADER 5! 🔔\n"
                f"━━━━━━━━━━━━━━━━━━━━\n"
                f"🎟️ *Ticket ID:* `#{ticket}`\n"
                f"📊 *Instrumen:* `{sym}` | *Aksi:* `{action}`\n"
                f"🏁 *Harga Exit:* `{exit_price}`\n"
                f"💵 *P&L Bersih:* `${profit:+.2f}`\n"
                f"🕒 *Waktu Selesai:* `{close_time}`\n"
                f"━━━━━━━━━━━━━━━━━━━━\n"
                f"📱 _Posisi telah selesai di terminal MT5._"
            )
            send_telegram_alert(tg_msg)

            # Tulis ke orders_queue/outcomes agar AI di WSL langsung membuat diagnosa
            outcome_payload = {
                "ticket": ticket,
                "symbol": sym,
                "action": action,
                "status": status_word,
                "exit_price": exit_price,
                "profit": profit,
                "close_time": close_time,
                "order_data": order_data
            }
            out_file = OUTCOMES_DIR / f"OUTCOME_{ticket}.json"
            try:
                with open(out_file, "w", encoding="utf-8") as of:
                    json.dump(outcome_payload, of, indent=2)
            except Exception as e:
                logger.error("Gagal menulis outcome file: %s", e)

    for t in closed_tickets:
        active_positions.pop(t, None)


def process_queue() -> None:
    """Continuously monitor pending order queue and execute."""
    logger.info("Menunggu sinyal order masuk dari AI Scanner di folder 'orders_queue/pending/'...")
    logger.info("Tekan Ctrl+C untuk menghentikan bridge.")
    load_active_positions()
    
    while True:
        try:
            # 0. Sinkronisasi Ground Truth posisi aktif MT5 ke live_positions.json untuk WSL Scanner
            sync_live_mt5_positions_file()

            # 0b. Periksa & pasang SL/TP darurat otomatis jika ada posisi yang terbuka tanpa proteksi
            fix_unprotected_positions()

            # 1. Periksa posisi yang ditutup oleh SL / TP di MT5
            check_closed_positions()

            # 1b. Periksa perlindungan Breakeven (BE) otomatis
            check_breakeven_protection()

            # 2. Proses antrean order pending
            pending_files = list(PENDING_DIR.glob("*.json"))
            for order_file in pending_files:
                try:
                    with open(order_file, "r", encoding="utf-8") as f:
                        order_data = json.load(f)

                    order_id = order_data.get("order_id", order_file.stem)
                    logger.info("Memproses sinyal order ID: %s...", order_id)

                    exec_res = execute_order(order_data)

                    # Jika gagal karena verifikasi simbol atau koneksi, lakukan re-koneksi paksa dan coba 1x lagi
                    if not exec_res.get("success") and ("Simbol" in str(exec_res.get("error", "")) or "koneksi" in str(exec_res.get("error", "")).lower()):
                        logger.warning("Order %s belum berhasil verifikasi simbol. Melakukan re-inisialisasi terminal dan mencoba ulang...", order_id)
                        mt5.shutdown()
                        time.sleep(1.0)
                        if mt5.initialize():
                            time.sleep(1.0)
                            mt5.symbol_select("EURUSD", True)
                            exec_res = execute_order(order_data)

                    order_data["execution_result"] = exec_res
                    order_data["executed_at"] = time.strftime("%Y-%m-%d %H:%M:%S")

                    if exec_res.get("success"):
                        ticket = exec_res.get("ticket")
                        if ticket:
                            active_positions[ticket] = order_data
                        dest = EXECUTED_DIR / order_file.name
                        with open(dest, "w", encoding="utf-8") as f:
                            json.dump(order_data, f, indent=2)
                        order_file.unlink(missing_ok=True)
                    else:
                        dest = FAILED_DIR / order_file.name
                        with open(dest, "w", encoding="utf-8") as f:
                            json.dump(order_data, f, indent=2)
                        order_file.unlink(missing_ok=True)

                except Exception as file_err:
                    logger.error("Error memproses file %s: %s", order_file.name, file_err)

            time.sleep(0.3)
        except KeyboardInterrupt:
            logger.info("Bridge dihentikan oleh pengguna.")
            break
        except Exception as loop_err:
            logger.error("Unexpected error di loop bridge: %s", loop_err)
            time.sleep(1.0)


def main():
    parser = argparse.ArgumentParser(description="MetaTrader 5 Windows Bridge for AI Trading Bot")
    parser.add_argument("--test", action="store_true", help="Tes koneksi ke MT5 Desktop tanpa order")
    parser.add_argument("--symbols", action="store_true", help="Tampilkan daftar simbol yang tersedia di broker MT5")
    parser.add_argument("--fix-stops", action="store_true", help="Pasang SL/TP darurat seketika ke seluruh posisi aktif yang tidak memiliki proteksi")
    parser.add_argument("--close-breached", action="store_true", help="Tutup darurat posisi jika harga pasar saat ini telah menembus level intended SL")
    args = parser.parse_args()

    if not init_mt5():
        sys.exit(1)

    if args.fix_stops or args.close_breached:
        action_desc = "Memeriksa dan menutup posisi breached / memasang SL/TP darurat" if args.close_breached else "Memeriksa dan memasang SL/TP darurat"
        logger.info("%s ke seluruh posisi terbuka di MT5...", action_desc)
        load_active_positions(close_if_breached=args.close_breached)
        mt5.shutdown()
        return

    if args.symbols:
        logger.info("Mencari daftar simbol di MT5...")
        all_syms = mt5.symbols_get() or ()
        vis_syms = [s.name for s in all_syms if getattr(s, "visible", False)]
        eur_syms = [s.name for s in all_syms if "EUR" in s.name.upper() or "USD" in s.name.upper()]
        print("=" * 60)
        print(f"Total simbol di broker : {len(all_syms)}")
        print(f"Simbol di Market Watch : {', '.join(vis_syms[:30]) if vis_syms else 'KOSONG'}")
        print(f"Simbol EUR / USD       : {', '.join(eur_syms[:30]) if eur_syms else 'Tidak ditemukan'}")
        print("=" * 60)
        mt5.shutdown()
        return

    if args.test:
        logger.info("Tes koneksi berhasil! MT5 Desktop siap menerima order.")
        mt5.shutdown()
        return

    try:
        process_queue()
    finally:
        mt5.shutdown()
        logger.info("Koneksi MT5 ditutup.")


if __name__ == "__main__":
    main()
