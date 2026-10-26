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

PENDING_DIR.mkdir(parents=True, exist_ok=True)
EXECUTED_DIR.mkdir(parents=True, exist_ok=True)
FAILED_DIR.mkdir(parents=True, exist_ok=True)
OUTCOMES_DIR.mkdir(parents=True, exist_ok=True)

# Active position tracking dictionary {ticket: order_data}
active_positions: Dict[int, Dict[str, Any]] = {}

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

    symbol_info = mt5.symbol_info(symbol)
    if symbol_info is None:
        ensure_mt5_connected(max_wait_sec=3)
        symbol_info = mt5.symbol_info(symbol)
    if symbol_info is None:
        err = f"Gagal mendapatkan info simbol {symbol}."
        logger.error(err)
        return {"success": False, "error": err}

    if not symbol_info.visible:
        if not mt5.symbol_select(symbol, True):
            err = f"Simbol {symbol} tidak dapat diaktifkan di Market Watch."
            logger.error(err)
            return {"success": False, "error": err}

    tick = mt5.symbol_info_tick(symbol)
    if tick is None:
        for _ in range(3):
            time.sleep(0.5)
            tick = mt5.symbol_info_tick(symbol)
            if tick is not None:
                break
    if tick is None:
        err = f"Gagal mendapatkan tick harga terkini untuk {symbol}."
        logger.error(err)
        return {"success": False, "error": err}

    digits = symbol_info.digits
    point = symbol_info.point

    if action_str == "BUY":
        order_type = mt5.ORDER_TYPE_BUY
        price = tick.ask
    elif action_str == "SELL":
        order_type = mt5.ORDER_TYPE_SELL
        price = tick.bid
    else:
        err = f"Tindakan order tidak valid: {action_str} (Hanya BUY atau SELL)."
        logger.error(err)
        return {"success": False, "error": err}

    # Format SL & TP dinamis yang berjangkar pada harga riil eksekusi (Anti-Slippage Distortion)
    sl_val = 0.0
    tp_val = 0.0
    planned_price = float(order_data.get("price", price))

    if sl_raw and sl_raw != "N/A" and tp_raw and tp_raw != "N/A":
        try:
            raw_sl_f = float(sl_raw)
            raw_tp_f = float(tp_raw)
            # Hitung jarak absolut dari planned price
            sl_dist = abs(raw_sl_f - planned_price)
            tp_dist = abs(raw_tp_f - planned_price)

            # Batas minimal higienis SL (minimal 4.5 pips untuk mencegah premature hit akibat spread)
            min_floor = 0.00045 if digits >= 4 else (0.45 if digits == 2 and "XAU" in symbol else 0.045)
            if sl_dist < min_floor:
                sl_dist = min_floor

            # Dukungan TP Adaptif (Izinkan pergeseran ke Resistance/Support terdekat minimal 1.25x SL, fallback default 1.5x)
            min_adaptive_tp = round(sl_dist * 1.25, digits)
            if tp_dist < min_adaptive_tp:
                tp_dist = round(sl_dist * 1.5, digits)

            # Jangkar SL dan TP ke harga riil eksekusi saat ini
            if action_str == "BUY":
                sl_val = round(price - sl_dist, digits)
                tp_val = round(price + tp_dist, digits)
            elif action_str == "SELL":
                sl_val = round(price + sl_dist, digits)
                tp_val = round(price - tp_dist, digits)
        except (ValueError, TypeError):
            # Fallback ke nilai mentah jika parsing gagal
            try:
                sl_val = round(float(sl_raw), digits)
                tp_val = round(float(tp_raw), digits)
            except Exception:
                pass

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
            if tick:
                price = tick.ask if action_str == "BUY" else tick.bid
                request["price"] = price
                if 'sl_dist' in locals() and sl_dist > 0:
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
        if (sl_val > 0 or tp_val > 0) and result.retcode in (10016, 10015):
            logger.warning("Broker menolak SL/TP awal (Retcode %s). Mencoba open posisi terlebih dahulu lalu memasang SL/TP...", result.retcode)
            request_no_sltp = dict(request)
            request_no_sltp["sl"] = 0.0
            request_no_sltp["tp"] = 0.0
            result = mt5.order_send(request_no_sltp)
            if result and result.retcode == mt5.TRADE_RETCODE_DONE:
                ticket = result.order
                time.sleep(0.1)
                modify_req = {
                    "action": mt5.TRADE_ACTION_SLTP,
                    "position": ticket,
                    "symbol": symbol,
                    "sl": sl_val,
                    "tp": tp_val,
                }
                mod_res = mt5.order_send(modify_req)
                if mod_res and mod_res.retcode == mt5.TRADE_RETCODE_DONE:
                    logger.info("✅ SL/TP berhasil dipasang ke Ticket #%d!", ticket)
                else:
                    logger.warning("⚠️ Gagal menyusulkan SL/TP: %s", mod_res.comment if mod_res else mt5.last_error())
            else:
                err = f"Order ditolak oleh broker! Retcode: {result.retcode if result else 'N/A'} ({result.comment if result else mt5.last_error()})"
                logger.error(err)
                return {"success": False, "error": err, "retcode": result.retcode if result else -1}
        else:
            err = f"Order ditolak oleh broker! Retcode: {result.retcode} ({result.comment})"
            logger.error(err)
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


def load_active_positions() -> None:
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
            
            # Cari history deals 3 hari terakhir agar history selalu termuat
            now_dt = datetime.now()
            from_dt = now_dt - timedelta(days=3)
            deals = mt5.history_deals_get(from_dt, now_dt, position=ticket)
            if not deals or len(deals) == 0:
                deals = mt5.history_deals_get(position=ticket)

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

            # Fallback jika deal history MT5 belum sinkron
            if exit_price is None:
                info = mt5.symbol_info_tick(sym)
                cur_price = info.bid if action == "BUY" else info.ask if info else 0.0
                if action == "BUY":
                    if sl_val > 0 and cur_price <= sl_val:
                        exit_price = sl_val
                        reason_str = "🛑 STOP LOSS TERSENTUH"
                        profit = -abs(exit_price - float(order_data.get("price", exit_price))) * 100000 * float(order_data.get("lot", 0.01))
                    else:
                        exit_price = tp_val if tp_val > 0 else cur_price
                else:
                    if sl_val > 0 and cur_price >= sl_val:
                        exit_price = sl_val
                        reason_str = "🛑 STOP LOSS TERSENTUH"
                        profit = -abs(exit_price - float(order_data.get("price", exit_price))) * 100000 * float(order_data.get("lot", 0.01))
                    else:
                        exit_price = tp_val if tp_val > 0 else cur_price

            if profit >= 0 and "STOP LOSS" in reason_str:
                pip_scale = 0.01 if "JPY" in sym else (0.10 if "XAU" in sym or "GOLD" in sym else 0.0001)
                planned_price = float(order_data.get("price") or exit_price or 0.0)
                pips_gain = round(abs(exit_price - planned_price) / pip_scale, 1) if (exit_price and planned_price) else 0.5
                if pips_gain >= 2.0:
                    reason_str = f"💰 TRAILING PROFIT LOCK TERSENTUH (+{pips_gain:.1f} pips)"
                    status_word = "WIN"
                else:
                    reason_str = "🛡️ BREAKEVEN TERSENTUH (+PROFIT)"
                    status_word = "BREAKEVEN"
            else:
                is_sl_hit = (
                    reason_str == "🛑 STOP LOSS TERSENTUH" or
                    profit < 0 or
                    (exit_price and sl_val > 0 and (
                        (action == "BUY" and exit_price <= sl_val + 0.00005) or
                        (action == "SELL" and exit_price >= sl_val - 0.00005)
                    ))
                )
                status_word = "LOSS" if is_sl_hit else "WIN"

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
    args = parser.parse_args()

    if not init_mt5():
        sys.exit(1)

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
