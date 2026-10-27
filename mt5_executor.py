"""
MT5 Order Executor for AI Trading Bot.
Integrates live signals from live_market_scanner.py into MetaTrader 5.
Supports both Direct Mode (on Windows) and Bridge Queue Mode (from Linux/WSL).
"""

import os
import re
import time
import json
import logging
from pathlib import Path
from typing import Optional, Dict, Any

logger = logging.getLogger("MT5Executor")

BASE_DIR = Path(__file__).resolve().parent
PENDING_DIR = BASE_DIR / "orders_queue" / "pending"
EXECUTED_DIR = BASE_DIR / "orders_queue" / "executed"
FAILED_DIR = BASE_DIR / "orders_queue" / "failed"

PENDING_DIR.mkdir(parents=True, exist_ok=True)
EXECUTED_DIR.mkdir(parents=True, exist_ok=True)
FAILED_DIR.mkdir(parents=True, exist_ok=True)


def dispatch_signal_order(
    decision: Any,
    setup: Dict[str, Any],
    lot_size: float = 0.01,
    wait_receipt_sec: float = 2.0,
) -> Dict[str, Any]:
    """
    Dispatch confirmed BUY/SELL signal to MetaTrader 5.
    Writes order payload to orders_queue/pending/ for immediate execution by MT5 bridge.
    """
    action = getattr(decision, "action", "")
    if action not in ("BUY", "SELL"):
        return {"success": False, "message": "Bukan sinyal eksekusi (WAIT)"}

    symbol = getattr(decision, "instrument", setup.get("symbol", "EURUSD")).upper()
    timeframe = getattr(decision, "timeframe", setup.get("timeframe", "5m"))

    def _clean_price(val: Any) -> float:
        if isinstance(val, (int, float)):
            return float(val)
        cleaned = re.sub(r"[^\d\.]", "", str(val or "0"))
        try:
            return float(cleaned) if cleaned else 0.0
        except ValueError:
            return 0.0

    raw_price = _clean_price(getattr(decision, "current_price", setup.get("price", 0.0)))
    if raw_price <= 0:
        raw_price = float(setup.get("price", 0.0))

    sl_dec = _clean_price(getattr(decision, "stop_loss", 0.0))
    tp_dec = _clean_price(getattr(decision, "take_profit", 0.0))
    dyn_sl = float(setup.get("dynamic_sl", 0.0) or 0.0)
    dyn_tp = float(setup.get("dynamic_tp", 0.0) or 0.0)

    # Validasi Stop Loss & Take Profit: Pastikan berada di sisi yang benar dari harga entry
    is_sl_valid = False
    if action == "BUY" and 0 < sl_dec < raw_price and abs(raw_price - sl_dec) / raw_price < 0.15:
        is_sl_valid = True
    elif action == "SELL" and sl_dec > raw_price and abs(sl_dec - raw_price) / raw_price < 0.15:
        is_sl_valid = True

    final_sl = sl_dec if is_sl_valid else dyn_sl

    is_tp_valid = False
    if action == "BUY" and tp_dec > raw_price and abs(tp_dec - raw_price) / raw_price < 0.25:
        is_tp_valid = True
    elif action == "SELL" and 0 < tp_dec < raw_price and abs(raw_price - tp_dec) / raw_price < 0.25:
        is_tp_valid = True

    final_tp = tp_dec if is_tp_valid else dyn_tp

    price = str(raw_price)
    sl = str(final_sl)
    tp = str(final_tp)
    reason = getattr(decision, "pattern_name", "") or setup.get("reason", "AI Setup")

    order_id = f"ORD_{symbol}_{int(time.time() * 1000)}"
    order_file_name = f"{order_id}.json"
    pending_file = PENDING_DIR / order_file_name

    candle_time = getattr(decision, "bar_timestamp", "") or setup.get("timestamp", "-")

    payload = {
        "order_id": order_id,
        "symbol": symbol,
        "action": action,
        "lot": lot_size,
        "price": price,
        "sl": sl,
        "tp": tp,
        "reason": reason,
        "timeframe": timeframe,
        "candle_time": candle_time,
        "created_at": time.strftime("%Y-%m-%d %H:%M:%S"),
    }

    try:
        # Atomic write: write to temp file then rename to avoid partial read by bridge
        temp_file = PENDING_DIR / f"temp_{order_file_name}"
        with open(temp_file, "w", encoding="utf-8") as f:
            json.dump(payload, f, indent=2)
        temp_file.rename(pending_file)

        logger.info(
            "📤 [MT5 AUTO-ORDER DISPATCHED] Order %s dikirim ke antrean MT5: %s %s %.2f lot (SL: %s, TP: %s)",
            order_id, action, symbol, lot_size, sl, tp
        )

        # Cek apakah receipt eksekusi langsung tersedia dalam beberapa detik
        start_wait = time.time()
        while time.time() - start_wait < wait_receipt_sec:
            exec_file = EXECUTED_DIR / order_file_name
            if exec_file.exists():
                with open(exec_file, "r", encoding="utf-8") as f:
                    res = json.load(f)
                return res.get("execution_result", {"success": True, "order_id": order_id})

            failed_file = FAILED_DIR / order_file_name
            if failed_file.exists():
                with open(failed_file, "r", encoding="utf-8") as f:
                    res = json.load(f)
                return res.get("execution_result", {"success": False, "order_id": order_id})

            time.sleep(0.2)

        return {
            "success": True,
            "order_id": order_id,
            "status": "QUEUED",
            "message": "Order telah masuk antrean MT5 dan sedang diproses bridge."
        }

    except Exception as exc:
        logger.error("Gagal mendispatch order MT5: %s", exc)
        return {"success": False, "error": str(exc)}
