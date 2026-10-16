"""
MT5 Order Executor for AI Trading Bot.
Integrates live signals from live_market_scanner.py into MetaTrader 5.
Supports both Direct Mode (on Windows) and Bridge Queue Mode (from Linux/WSL).
"""

import os
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
    price = getattr(decision, "current_price", setup.get("price", 0.0))
    sl = getattr(decision, "stop_loss", setup.get("dynamic_sl", "N/A"))
    tp = getattr(decision, "take_profit", setup.get("dynamic_tp", "N/A"))
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
