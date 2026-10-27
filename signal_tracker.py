"""Self-Optimizing Trade Outcome Tracker & AI Reflection Engine.

Tracks executed signals in SQLite, detects Take Profit / Stop Loss hits in real time,
computes quantitative win rates, and triggers autonomous AI reflections to dynamically
inject corrective trading guardrails into ChromaDB knowledge base.
"""

import sqlite3
import json
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, List, Optional, Tuple, Set
import re

from config import settings, logger

DB_PATH = Path(__file__).resolve().parent / "signals.db"


class SignalTracker:
    """Manages trading signal lifecycle, outcome tracking, and autonomous self-optimization."""

    def __init__(self, db_path: Path = DB_PATH) -> None:
        self.db_path = db_path
        self._init_db()

    def _get_connection(self) -> sqlite3.Connection:
        """Create a thread-safe connection to SQLite database."""
        conn = sqlite3.connect(str(self.db_path))
        conn.row_factory = sqlite3.Row
        return conn

    def _init_db(self) -> None:
        """Initialize database schema for signals and AI self-reflections."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            # 1. Tabel sinyal trading
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS trading_signals (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    created_at TEXT NOT NULL,
                    instrument TEXT NOT NULL,
                    timeframe TEXT NOT NULL,
                    action TEXT NOT NULL,
                    entry_price REAL NOT NULL,
                    stop_loss REAL NOT NULL,
                    take_profit REAL NOT NULL,
                    risk_reward_ratio TEXT,
                    confidence_score REAL,
                    pattern_name TEXT,
                    indicator_status TEXT,
                    notes_detail TEXT,
                    bar_timestamp TEXT,
                    status TEXT NOT NULL DEFAULT 'OPEN',
                    exit_price REAL,
                    exit_time TEXT,
                    pips_result REAL DEFAULT 0.0,
                    reflection_id INTEGER DEFAULT NULL
                )
            """)

            # 2. Tabel refleksi dan optimasi mandiri AI
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS ai_reflections (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    created_at TEXT NOT NULL,
                    analyzed_loss_ids TEXT NOT NULL,
                    reflection_summary TEXT NOT NULL,
                    injected_rules TEXT NOT NULL
                )
            """)
            conn.commit()

    def record_signal(self, decision: Any, setup: Dict[str, Any]) -> Optional[int]:
        """Record newly dispatched BUY or SELL trading signal into tracker database."""
        action = getattr(decision, "action", "")
        if action not in ("BUY", "SELL"):
            return None

        instrument = getattr(decision, "instrument", setup.get("symbol", "")).upper()
        timeframe = getattr(decision, "timeframe", setup.get("timeframe", "5m"))

        # Parse numeric prices safely
        def _parse_price(val: Any) -> float:
            if isinstance(val, (int, float)):
                return float(val)
            cleaned = re.sub(r"[^\d\.]", "", str(val or "0"))
            try:
                return float(cleaned) if cleaned else 0.0
            except ValueError:
                return 0.0

        entry_val = _parse_price(getattr(decision, "entry_zone", setup.get("price", 0.0)))
        if entry_val <= 0:
            entry_val = float(setup.get("price", 0.0))

        sl_val = _parse_price(getattr(decision, "stop_loss", setup.get("dynamic_sl", 0.0)))
        tp_val = _parse_price(getattr(decision, "take_profit", setup.get("dynamic_tp", 0.0)))

        created_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        bar_ts = getattr(decision, "bar_timestamp", setup.get("timestamp", ""))

        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO trading_signals (
                    created_at, instrument, timeframe, action, entry_price, stop_loss,
                    take_profit, risk_reward_ratio, confidence_score, pattern_name,
                    indicator_status, notes_detail, bar_timestamp, status
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'OPEN')
            """, (
                created_at,
                instrument,
                timeframe,
                action,
                entry_val,
                sl_val,
                tp_val,
                getattr(decision, "risk_reward_ratio", "1:1.7"),
                float(getattr(decision, "confidence_score", 0.8)),
                getattr(decision, "pattern_name", setup.get("reason", "")),
                getattr(decision, "indicator_status", setup.get("indicator_status", "")),
                getattr(decision, "notes_detail", setup.get("notes", "")),
                str(bar_ts),
            ))
            conn.commit()
            signal_id = cursor.lastrowid
            logger.info("📝 [TRACKER] Sinyal %s %s [%s] ID #%d tercatat di database (Entry: %.5f, SL: %.5f, TP: %.5f)",
                        action, instrument, timeframe, signal_id, entry_val, sl_val, tp_val)
            return signal_id

    def sync_executed_orders(self) -> None:
        """Synchronize open signals in DB with actual execution prices from MT5 bridge."""
        executed_dir = Path(__file__).resolve().parent / "orders_queue" / "executed"
        if not executed_dir.exists():
            return

        with self._get_connection() as conn:
            cursor = conn.cursor()
            for f in executed_dir.glob("*.json"):
                try:
                    with open(f, "r", encoding="utf-8") as jf:
                        data = json.load(jf)
                    exec_res = data.get("execution_result", {})
                    if not exec_res.get("success"):
                        continue

                    real_entry = float(exec_res.get("open_price", 0.0))
                    real_sl = float(exec_res.get("sl", 0.0))
                    real_tp = float(exec_res.get("tp", 0.0))
                    symbol = data.get("symbol", "").upper()
                    action = data.get("action", "").upper()
                    created_at = data.get("created_at", "")

                    ticket = exec_res.get("ticket")
                    if real_entry > 0 and real_sl > 0:
                        cursor.execute("""
                            UPDATE trading_signals
                            SET entry_price = ?, stop_loss = ?, take_profit = ?, ticket = ?
                            WHERE instrument = ? AND action = ?
                              AND (created_at = ? OR abs(julianday(?) - julianday(created_at)) * 86400 < 300)
                              AND (ticket IS NULL OR ticket = ?)
                        """, (real_entry, real_sl, real_tp, ticket, symbol, action, created_at, created_at, ticket))
                except Exception as e:
                    logger.debug("Sync executed order error on %s: %s", f.name, e)
            conn.commit()

    def process_external_outcomes(self) -> List[Dict[str, Any]]:
        """Read and process closed position outcomes reported directly by MT5 Windows Bridge."""
        outcomes_dir = Path(__file__).resolve().parent / "orders_queue" / "outcomes"
        if not outcomes_dir.exists():
            return []

        resolved_outcomes: List[Dict[str, Any]] = []
        now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        with self._get_connection() as conn:
            cursor = conn.cursor()
            for f in outcomes_dir.glob("*.json"):
                try:
                    with open(f, "r", encoding="utf-8") as jf:
                        data = json.load(jf)

                    sym = data.get("symbol", "EURUSD").upper()
                    action = data.get("action", "").upper()
                    status = data.get("status", "LOSS")
                    exit_price = float(data.get("exit_price") or 0.0)
                    profit = float(data.get("profit") or 0.0)
                    close_time = data.get("close_time") or now_str
                    ticket = data.get("ticket")

                    pip_scale = 0.0001
                    if "JPY" in sym:
                        pip_scale = 0.01
                    elif "XAU" in sym or "GOLD" in sym:
                        pip_scale = 0.10

                    # 1. Prioritaskan pencarian presisi berdasarkan nomor tiket unik MT5
                    row = None
                    if ticket:
                        cursor.execute("SELECT * FROM trading_signals WHERE ticket = ? LIMIT 1", (ticket,))
                        row = cursor.fetchone()

                    # 2. Fallback pencarian open order jika tiket belum terpetakan
                    if not row:
                        cursor.execute("""
                            SELECT * FROM trading_signals
                            WHERE instrument = ? AND action = ? AND status = 'OPEN'
                            ORDER BY id DESC LIMIT 1
                        """, (sym, action))
                        row = cursor.fetchone()

                    if row:
                        s_id = row["id"]
                        entry_p = row["entry_price"]
                        # Sanity check: pastikan exit_price sesuai dengan skala instrumen
                        is_price_insane = False
                        if "JPY" in sym and (exit_price < 50.0 or exit_price > 500.0):
                            is_price_insane = True
                        elif ("XAU" in sym or "GOLD" in sym) and (exit_price < 1000.0 or exit_price > 6000.0):
                            is_price_insane = True
                        elif not ("JPY" in sym or "XAU" in sym or "GOLD" in sym) and (exit_price > 10.0 or exit_price <= 0.0):
                            is_price_insane = True

                        if exit_price <= 0 or is_price_insane:
                            exit_price = row["take_profit"] if status == "WIN" else (entry_p if status == "BREAKEVEN" else row["stop_loss"])
                        pips = round((exit_price - entry_p) / pip_scale if action == "BUY" else (entry_p - exit_price) / pip_scale, 1)

                        cursor.execute("""
                            UPDATE trading_signals
                            SET status = ?, exit_price = ?, exit_time = ?, pips_result = ?, ticket = ?
                            WHERE id = ?
                        """, (status, exit_price, close_time, pips, ticket, s_id))

                        outcome_item = {
                            "id": s_id,
                            "ticket": ticket,
                            "instrument": sym,
                            "timeframe": row["timeframe"],
                            "action": action,
                            "status": status,
                            "entry_price": entry_p,
                            "exit_price": exit_price,
                            "pips": pips,
                            "profit": profit,
                            "pattern_name": row["pattern_name"],
                            "indicator_status": row["indicator_status"],
                            "notes_detail": row["notes_detail"],
                            "created_at": row["created_at"],
                            "bar_timestamp": row["bar_timestamp"],
                            "exit_time": close_time,
                        }
                        resolved_outcomes.append(outcome_item)
                        logger.info("📢 [MT5 OUTCOME SYNC] Sinyal #%d (Ticket #%s) ditutup di MT5 dengan status: %s (Exit: %.5f, Pips: %.1f, Profit: $%.2f)",
                                    s_id, str(ticket), status, exit_price, pips, profit)

                    # Hapus file outcome setelah diproses agar tidak duplikat
                    f.unlink(missing_ok=True)
                except Exception as err:
                    logger.error("Error memproses file outcome %s: %s", f.name, err)
            conn.commit()

        return resolved_outcomes

    def check_signals_outcome(
        self,
        symbol: str,
        current_high: float,
        current_low: float,
        current_close: float,
        bar_time: str = ""
    ) -> List[Dict[str, Any]]:
        """Evaluate open signals against live price bars to detect Take Profit or Stop Loss hits.
        
        NOTE: HANYA mengevaluasi sinyal offline (ticket IS NULL). Sinyal yang memiliki tiket MT5
        wajib dievaluasi secara eksklusif oleh MT5 bridge agar 100% presisi dan tidak desinkron.
        """
        sym = symbol.upper()
        now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        resolved_signals: List[Dict[str, Any]] = []

        is_jpy = "JPY" in sym
        is_gold = "XAU" in sym or "GOLD" in sym
        is_crypto = "BTC" in sym or "ETH" in sym

        if is_gold:
            pip_scale = 0.10
        elif is_crypto:
            pip_scale = 1.00
        elif is_jpy:
            pip_scale = 0.01
        else:
            pip_scale = 0.0001

        with self._get_connection() as conn:
            cursor = conn.cursor()
            # KUNCI INTEGRITAS: Hanya evaluasi sinyal yang TIDAK memiliki tiket MT5 (paper trading fallback)
            cursor.execute("""
                SELECT * FROM trading_signals
                WHERE instrument = ? AND status = 'OPEN' AND ticket IS NULL
                ORDER BY id ASC
            """, (sym,))
            open_rows = cursor.fetchall()

            for row in open_rows:
                s_id = row["id"]
                action = row["action"]
                entry_p = row["entry_price"]
                sl_p = row["stop_loss"]
                tp_p = row["take_profit"]

                status = None
                exit_price = None
                pips = 0.0

                if action == "BUY":
                    # Cek Take Profit
                    if current_high >= tp_p:
                        status = "WIN"
                        exit_price = tp_p
                        pips = round((tp_p - entry_p) / pip_scale, 1)
                    # Cek Stop Loss
                    elif current_low <= sl_p:
                        status = "LOSS"
                        exit_price = sl_p
                        pips = round((sl_p - entry_p) / pip_scale, 1)

                elif action == "SELL":
                    # Cek Take Profit
                    if current_low <= tp_p:
                        status = "WIN"
                        exit_price = tp_p
                        pips = round((entry_p - tp_p) / pip_scale, 1)
                    # Cek Stop Loss
                    elif current_high >= sl_p:
                        status = "LOSS"
                        exit_price = sl_p
                        pips = round((entry_p - sl_p) / pip_scale, 1)

                if status:
                    cursor.execute("""
                        UPDATE trading_signals
                        SET status = ?, exit_price = ?, exit_time = ?, pips_result = ?
                        WHERE id = ?
                    """, (status, exit_price, now_str, pips, s_id))

                    res_item = {
                        "id": s_id,
                        "instrument": sym,
                        "timeframe": row["timeframe"],
                        "action": action,
                        "status": status,
                        "entry_price": entry_p,
                        "exit_price": exit_price,
                        "pips": pips,
                        "pattern_name": row["pattern_name"],
                        "indicator_status": row["indicator_status"],
                        "notes_detail": row["notes_detail"],
                        "created_at": row["created_at"],
                        "bar_timestamp": row["bar_timestamp"],
                        "exit_time": now_str,
                    }
                    resolved_signals.append(res_item)

                    if status == "WIN":
                        logger.info("🎉 [OUTCOME TP] Sinyal #%d %s %s TERCAPAI TP! (+%.1f pips pada %.5f)",
                                    s_id, sym, action, pips, exit_price)
                    else:
                        logger.warning("🛑 [OUTCOME SL] Sinyal #%d %s %s TERSENTUH SL! (%.1f pips pada %.5f)",
                                       s_id, sym, action, pips, exit_price)

            if resolved_signals:
                conn.commit()

        return resolved_signals

    def get_performance_report(self) -> Dict[str, Any]:
        """Generate quantitative statistics of trading performance."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT COUNT(*) FROM trading_signals")
            total = cursor.fetchone()[0]

            cursor.execute("SELECT COUNT(*) FROM trading_signals WHERE status = 'WIN'")
            wins = cursor.fetchone()[0]

            cursor.execute("SELECT COUNT(*) FROM trading_signals WHERE status = 'BREAKEVEN'")
            breakevens = cursor.fetchone()[0]

            cursor.execute("SELECT COUNT(*) FROM trading_signals WHERE status = 'LOSS'")
            losses = cursor.fetchone()[0]

            cursor.execute("SELECT COUNT(*) FROM trading_signals WHERE status = 'OPEN'")
            open_count = cursor.fetchone()[0]

            cursor.execute("SELECT COALESCE(SUM(pips_result), 0.0) FROM trading_signals WHERE status IN ('WIN', 'BREAKEVEN', 'LOSS')")
            net_pips = round(cursor.fetchone()[0], 1)

            cursor.execute("SELECT COALESCE(SUM(pips_result), 0.0) FROM trading_signals WHERE status IN ('WIN', 'BREAKEVEN')")
            gross_win_pips = cursor.fetchone()[0]

            cursor.execute("SELECT COALESCE(ABS(SUM(pips_result)), 0.0) FROM trading_signals WHERE status = 'LOSS'")
            gross_loss_pips = cursor.fetchone()[0]

            completed = wins + breakevens + losses
            win_rate = round(((wins + breakevens) / completed) * 100.0, 1) if completed > 0 else 0.0
            profit_factor = round(gross_win_pips / gross_loss_pips, 2) if gross_loss_pips > 0 else (99.0 if gross_win_pips > 0 else 0.0)

            return {
                "total_signals": total,
                "wins": wins,
                "breakevens": breakevens,
                "losses": losses,
                "open": open_count,
                "completed": completed,
                "win_rate_pct": win_rate,
                "net_pips": net_pips,
                "profit_factor": profit_factor,
            }

    def diagnose_single_loss(self, rag_engine: Any, outcome: Dict[str, Any]) -> str:
        """Diagnose a single losing trade immediately using Gemini to provide root-cause insights."""
        gemini_client = getattr(rag_engine, "gemini_client", None)
        if not gemini_client:
            return "Evaluasi AI offline."

        sym = outcome.get("instrument", "EURUSD")
        action = outcome.get("action", "")
        pips = outcome.get("pips", 0.0)
        entry_p = outcome.get("entry_price", "-")
        exit_p = outcome.get("exit_price", "-")
        candle_bar = outcome.get("bar_timestamp") or outcome.get("created_at", "-")
        pattern = outcome.get("pattern_name", "-")
        notes = outcome.get("notes_detail", "-")
        indicator = outcome.get("indicator_status", "-")

        prompt = f"""Anda adalah Master Risk Auditor Algoritmik.
Sebuah posisi trading scalping baru saja tersentuh STOP LOSS:
- Instrumen & Aksi: {action} {sym}
- Waktu Candle Asal: {candle_bar}
- Harga Entry: {entry_p} | Harga Exit SL: {exit_p} (Rugi {pips} pips)
- Pola Awal: {pattern}
- Indikator saat Sinyal: {indicator}
- Catatan Teknis: {notes}

TUGAS ANDA:
Tuliskan analisis teknikal singkat dan padat (maksimal 2-3 kalimat lugas dalam Bahasa Indonesia) yang menjelaskan:
1. Mengapa Stop Loss tersentuh (misal: dorongan tren mayor, false breakout/rejection, volatilitas sesi, dll).
2. Peringatan mitigasi untuk posisi berikutnya.
Gunakan nada objektif, lugas, tanpa salam pembuka/penutup.
"""
        models_to_try = [
            settings.GEMINI_MODEL,
            "gemini-3.1-flash-lite",
            "gemini-2.5-flash-lite",
            "gemini-2.5-flash",
            "gemini-1.5-flash",
        ]
        for mod in models_to_try:
            try:
                from google.genai import types
                response = gemini_client.models.generate_content(
                    model=mod,
                    contents=prompt,
                    config=types.GenerateContentConfig(
                        temperature=0.2,
                        max_output_tokens=250,
                        automatic_function_calling=types.AutomaticFunctionCallingConfig(disable=True),
                    ),
                )
                if response and response.text:
                    return response.text.strip()
            except Exception as exc:
                logger.warning("Diagnosa loss model '%s' gagal: %s. Mencoba model alternatif...", mod, exc)
                continue

        return "Penyebab: Tekanan pasar berlawanan menembus level proteksi stop loss."

    def format_telegram_outcome_alert(self, outcome: Dict[str, Any], loss_diagnosis: Optional[str] = None) -> str:
        """Format an outcome alert (TP / SL hit) for Telegram with rich candle origin metadata."""
        status = outcome["status"]
        action = outcome["action"]
        sym = outcome["instrument"]
        tf = outcome["timeframe"]
        pips = outcome["pips"]
        candle_bar = outcome.get("bar_timestamp") or outcome.get("created_at", "-")
        created_at = outcome.get("created_at", "-")
        exit_time = outcome.get("exit_time", "-")

        if status == "WIN":
            header = "🎯 *TARGET TAKE PROFIT TERCAPAI!* 🎯"
            badge = "🟢 *HASIL: WIN (+PROFIT)*"
            pip_str = f"+{pips:.1f} pips"
        elif status == "BREAKEVEN":
            header = "🛡️ *STOP LOSS BREAKEVEN TERCAPAI!* 🛡️"
            badge = "🔵 *HASIL: BREAKEVEN (+PROFIT AMAN)*"
            pip_str = f"+{pips:.1f} pips"
        else:
            header = "🛑 *STOP LOSS TERSENTUH!* 🛑"
            badge = "🔴 *HASIL: LOSS (-DEFENSE)*"
            pip_str = f"{pips:.1f} pips"

        lines = [
            header,
            "═" * 32,
            f"📊 *Instrumen:* `{sym}` | ⏱️ *TF:* `{tf}`",
            f"🎯 *Tindakan Asal:* `{action}` | {badge}",
            "─" * 32,
            f"📍 *Harga Entry:* `{outcome['entry_price']}`",
            f"🏁 *Harga Exit:* `{outcome['exit_price']}`",
            f"💰 *Hasil Pips:* `{pip_str}`",
            f"🕯️ *Setup Asal:* `{outcome.get('pattern_name', '-')}`",
            "─" * 32,
            "🕒 *Detail Sumber & Waktu Transaksi:*",
            f"• *Sumber Candle Sinyal:* `Candle {tf} Bar {candle_bar}`",
            f"• *Waktu Sinyal Masuk:* `{created_at}`",
            f"• *Waktu Tercapai Exit:* `{exit_time}`",
            f"ℹ️ _Posisi ini berasal dari sinyal candle {tf} yang ditutup pada pukul {candle_bar}._",
        ]
        if status == "LOSS" and loss_diagnosis:
            lines.extend([
                "─" * 32,
                "🧠 *Analisis AI Penyebab Kena SL:*",
                f"_{loss_diagnosis}_",
            ])
        lines.append("═" * 32)
        return "\n".join(lines)

    def reflect_and_self_optimize(self, rag_engine: Any, min_losses: int = 2) -> Optional[str]:
        """Perform autonomous AI self-reflection on recent losing trades and inject guardrails into ChromaDB."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            # Ambil sinyal LOSS yang belum pernah direfleksikan
            cursor.execute("""
                SELECT * FROM trading_signals
                WHERE status = 'LOSS' AND reflection_id IS NULL
                ORDER BY id ASC
                LIMIT 10
            """)
            loss_rows = cursor.fetchall()

            if len(loss_rows) < min_losses:
                logger.info("ℹ️ [SELF-OPT] Jumlah trade LOSS yang belum dievaluasi (%d) belum mencapai ambang batas (%d). Belum perlu refleksi.",
                            len(loss_rows), min_losses)
                return None

            loss_ids = [str(r["id"]) for r in loss_rows]
            loss_summaries = []
            for r in loss_rows:
                loss_summaries.append(
                    f"- Sinyal #{r['id']} {r['instrument']} {r['timeframe']} {r['action']} pada {r['created_at']}: "
                    f"Pola: {r['pattern_name']}, Indikator: {r['indicator_status']}, Catatan: {r['notes_detail']}, Rugi: {r['pips_result']} pips."
                )

            cases_text = "\n".join(loss_summaries)

            # Minta Gemini melakukan Self-Reflection
            gemini_client = getattr(rag_engine, "gemini_client", None)
            if not gemini_client:
                logger.warning("Gemini Client tidak tersedia untuk Self-Reflection.")
                return None

            prompt = f"""Anda adalah Master Trading Risk Auditor dan Algorithmic Coach.
Berikut adalah {len(loss_rows)} riwayat sinyal trading yang mengalami KERUGIAN (HIT STOP LOSS):

{cases_text}

TUGAS ANDA:
1. Temukan benang merah atau pola kesalahan berulang (root cause) dari kegagalan setup di atas (misalnya: false breakout, counter-trend, indikator MACD bertentangan, atau volatilitas sesi).
2. Rumuskan MAKSIMAL 3 ATURAN PANTANGAN BARU (Self-Learned Guardrails) yang konkret, ketat, dan dapat diterapkan oleh AI scanner untuk mencegah kerugian serupa di masa depan.
3. Tuliskan dalam Bahasa Indonesia yang lugas dan berwibawa dengan format poin-poin jelas.
"""
            models_to_try = [
                settings.GEMINI_MODEL,
                "gemini-3.1-flash-lite",
                "gemini-2.5-flash-lite",
                "gemini-2.5-flash",
                "gemini-1.5-flash",
            ]
            reflection_text = ""
            for mod in models_to_try:
                try:
                    from google.genai import types
                    response = gemini_client.models.generate_content(
                        model=mod,
                        contents=prompt,
                        config=types.GenerateContentConfig(
                            temperature=0.2,
                            max_output_tokens=600,
                            automatic_function_calling=types.AutomaticFunctionCallingConfig(disable=True),
                        ),
                    )
                    if response and response.text:
                        reflection_text = response.text.strip()
                        break
                except Exception as exc:
                    logger.warning("Self-reflection model '%s' gagal: %s. Mencoba alternatif...", mod, exc)
                    continue

            if not reflection_text:
                return None

            try:
                # Simpan hasil refleksi ke database SQLite
                now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                cursor.execute("""
                    INSERT INTO ai_reflections (created_at, analyzed_loss_ids, reflection_summary, injected_rules)
                    VALUES (?, ?, ?, ?)
                """, (now_str, ",".join(loss_ids), reflection_text, reflection_text))
                reflection_id = cursor.lastrowid

                # Update sinyal-sinyal loss agar ditandai sudah direfleksikan
                cursor.execute(f"""
                    UPDATE trading_signals
                    SET reflection_id = ?
                    WHERE id IN ({','.join(loss_ids)})
                """, (reflection_id,))
                conn.commit()

                # Suntikkan aturan pantangan baru ini ke ChromaDB (Knowledge Base)
                if getattr(rag_engine, "collection", None) is not None:
                    chunk_id = f"self_learned_guardrail_{reflection_id}_{int(datetime.now().timestamp())}"
                    rag_engine.collection.add(
                        ids=[chunk_id],
                        documents=[f"# SOP HASIL EVALUASI DIRI MANDIRI (SELF-LEARNED GUARDRAIL #{reflection_id})\n\n{reflection_text}"],
                        metadatas=[{
                            "source": "AI_Self_Reflection_Guardrails.md",
                            "page": reflection_id,
                            "category": "self_learned_guardrail",
                        }],
                    )
                    logger.info("🧠 [SELF-OPT] Aturan pantangan baru berhasil disuntikkan ke ChromaDB ID '%s'!", chunk_id)

                return reflection_text

            except Exception as exc:
                logger.error("Gagal melakukan AI Self-Reflection: %s", exc)
                return None

    def reflect_and_self_optimize_breakeven(self, rag_engine: Any, min_breakevens: int = 3) -> Optional[str]:
        """Perform autonomous AI self-reflection when 3 Breakeven trades accumulate (even non-consecutively)."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            # Ambil sinyal BREAKEVEN yang belum pernah dievaluasi
            cursor.execute("""
                SELECT * FROM trading_signals
                WHERE status = 'BREAKEVEN' AND reflection_id IS NULL
                ORDER BY id ASC
                LIMIT 10
            """)
            be_rows = cursor.fetchall()

            if len(be_rows) < min_breakevens:
                logger.info(
                    "ℹ️ [BREAKEVEN-AUDIT] Jumlah trade BREAKEVEN belum dievaluasi (%d/%d). Belum mencapai ambang batas.",
                    len(be_rows), min_breakevens
                )
                return None

            be_ids = [str(r["id"]) for r in be_rows]
            be_summaries = []
            for r in be_rows:
                be_summaries.append(
                    f"- Sinyal #{r['id']} {r['instrument']} {r['timeframe']} {r['action']} pada {r['created_at']}: "
                    f"Entry: {r['entry_price']}, Target TP: {r['take_profit']}, Pola: {r['pattern_name']}, "
                    f"Indikator: {r['indicator_status']}, Catatan: {r['notes_detail']}, Hasil: +{r['pips_result']} pips (Kena SL BE)."
                )

            cases_text = "\n".join(be_summaries)

            gemini_client = getattr(rag_engine, "gemini_client", None)
            if not gemini_client:
                logger.warning("Gemini Client tidak tersedia untuk Breakeven Audit.")
                return None

            prompt = f"""Anda adalah Master Algorithmic Trading Coach & Exit Strategy Auditor.
Berikut adalah {len(be_rows)} riwayat posisi trading yang menyentuh STOP LOSS BREAKEVEN (posisi sempat floating profit >= 5.0 pips namun berbalik arah sebelum mencapai Take Profit penuh):

{cases_text}

TUGAS ANDA:
1. Analisis pola atau faktor teknikal mengapa harga berulang kali berbalik arah setelah bergerak 5 pips sebelum menyentuh target Take Profit (misal: target TP terlalu optimis, resistensi/support struktural menghadang di tengah jalan, divergensi momentum, atau pelemahan volume).
2. Rumuskan 2-3 ATURAN OPTIMASI EXIT & TARGET TP BARU (misalnya: kalibrasi TP adaptif lebih realistis di 1.25x - 1.4x SL pada kondisi tertentu, atau penguncian trailing step) agar profit tidak sering kembali ke titik impas.
3. Tuliskan dalam Bahasa Indonesia yang lugas dan berwibawa dengan format poin-poin jelas.
"""
            models_to_try = [
                settings.GEMINI_MODEL,
                "gemini-3.1-flash-lite",
                "gemini-2.5-flash-lite",
                "gemini-2.5-flash",
                "gemini-1.5-flash",
            ]
            reflection_text = ""
            for mod in models_to_try:
                try:
                    from google.genai import types
                    response = gemini_client.models.generate_content(
                        model=mod,
                        contents=prompt,
                        config=types.GenerateContentConfig(
                            temperature=0.2,
                            max_output_tokens=600,
                            automatic_function_calling=types.AutomaticFunctionCallingConfig(disable=True),
                        ),
                    )
                    if response and response.text:
                        reflection_text = response.text.strip()
                        break
                except Exception as exc:
                    logger.warning("Breakeven audit model '%s' gagal: %s. Mencoba alternatif...", mod, exc)
                    continue

            if not reflection_text:
                return None

            try:
                now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                cursor.execute("""
                    INSERT INTO ai_reflections (created_at, analyzed_loss_ids, reflection_summary, injected_rules)
                    VALUES (?, ?, ?, ?)
                """, (now_str, ",".join(be_ids), reflection_text, reflection_text))
                reflection_id = cursor.lastrowid

                # Update sinyal-sinyal breakeven agar ditandai sudah direfleksikan
                cursor.execute(f"""
                    UPDATE trading_signals
                    SET reflection_id = ?
                    WHERE id IN ({','.join(be_ids)})
                """, (reflection_id,))
                conn.commit()

                # Suntikkan aturan optimasi baru ini ke ChromaDB (Knowledge Base)
                if getattr(rag_engine, "collection", None) is not None:
                    chunk_id = f"self_learned_breakeven_guardrail_{reflection_id}_{int(datetime.now().timestamp())}"
                    rag_engine.collection.add(
                        ids=[chunk_id],
                        documents=[f"# SOP HASIL AUDIT STRATEGI BREAKEVEN (BREAKEVEN REFLECTION #{reflection_id})\n\n{reflection_text}"],
                        metadatas=[{
                            "source": "AI_Breakeven_Reflection.md",
                            "page": reflection_id,
                            "category": "self_learned_guardrail",
                        }],
                    )
                    logger.info("🧠 [BREAKEVEN-OPT] Aturan optimasi Breakeven berhasil disuntikkan ke ChromaDB ID '%s'!", chunk_id)

                return reflection_text

            except Exception as exc:
                logger.error("Gagal melakukan AI Breakeven Reflection: %s", exc)
                return None

    def get_all_active_symbols(self) -> List[str]:
        """Retrieve all currently active symbols across disk pending queue and database OPEN signals."""
        active_syms: Set[str] = set()

        # 1. Cek antrean pending di disk
        pending_dir = Path(__file__).resolve().parent / "orders_queue" / "pending"
        if pending_dir.exists():
            for f in pending_dir.glob("ORD_*.json"):
                # Ekstrak simbol dari nama file ORD_EURUSD_...
                parts = f.stem.split("_")
                if len(parts) >= 2:
                    active_syms.add(parts[1].upper())

        # 2. Cek database trading_signals untuk status OPEN
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT DISTINCT instrument FROM trading_signals WHERE status = 'OPEN'")
            for row in cursor.fetchall():
                active_syms.add(row["instrument"].upper())

        return list(active_syms)

    def has_cluster_conflict(self, symbol: str) -> Tuple[bool, Optional[str], Optional[str]]:
        """Check if symbol conflicts with any open position within the same currency cluster (Correlation Shield).
        
        Returns:
            (is_blocked, cluster_name, conflicting_active_symbol)
        """
        from currency_clusters import get_cluster_conflicts
        active_symbols = self.get_all_active_symbols()
        return get_cluster_conflicts(symbol, active_symbols)

    def has_open_position(self, symbol: str) -> bool:
        """Check if symbol currently has an active open position in MT5 or DB to prevent duplicate orders."""
        sym = symbol.upper()
        # 1. Cek antrean pending di disk (belum dieksekusi bridge)
        pending_dir = Path(__file__).resolve().parent / "orders_queue" / "pending"
        if pending_dir.exists():
            for _ in pending_dir.glob(f"ORD_{sym}_*.json"):
                return True

        # 2. Cek database trading_signals untuk status OPEN
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT id FROM trading_signals
                WHERE instrument = ? AND status = 'OPEN'
                LIMIT 1
            """, (sym,))
            if cursor.fetchone():
                return True

        return False

    def is_loss_cooldown(self, symbol: str, cooldown_minutes: int = 15) -> Tuple[bool, Optional[str]]:
        """Check if symbol is in post-loss cooldown to prevent revenge trading or consecutive stop-outs."""
        sym = symbol.upper()
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT status, exit_time, pips_result FROM trading_signals
                WHERE instrument = ? AND (status = 'LOSS' OR (status IN ('WIN', 'LOSS') AND pips_result < 0))
                ORDER BY id DESC LIMIT 1
            """, (sym,))
            row = cursor.fetchone()
            if row and row["exit_time"]:
                try:
                    exit_dt = datetime.strptime(str(row["exit_time"]), "%Y-%m-%d %H:%M:%S")
                    diff_seconds = (datetime.now() - exit_dt).total_seconds()
                    if 0 <= diff_seconds < (cooldown_minutes * 60):
                        remaining_min = int((cooldown_minutes * 60 - diff_seconds) / 60) + 1
                        loss_pips_str = f" ({row['pips_result']} pips)" if row.get("pips_result") else ""
                        return True, f"Trade sebelumnya rugi{loss_pips_str} pada {row['exit_time']} (Cooldown sisa: {remaining_min} menit untuk stabilisasi pasar)"
                except Exception as err:
                    logger.debug("Cooldown time parse error: %s", err)
        return False, None


# Global singleton tracker instance
signal_tracker = SignalTracker()

