"""Real-time Economic Calendar and High-Impact News Filter module.

Protects trading operations from slippage, spread spikes, and whipsaw during
major macroeconomic news events (e.g., NFP, CPI, FOMC, Interest Rate decisions).
"""

from datetime import datetime, timezone, timedelta
from typing import Dict, Any, List, Optional, Tuple
import requests
from config import settings, logger

# Standard symbols to tracked fiat currencies
SYMBOL_CURRENCY_MAP = {
    "EURUSD": ["EUR", "USD"],
    "GBPUSD": ["GBP", "USD"],
    "USDJPY": ["USD", "JPY"],
    "AUDUSD": ["AUD", "USD"],
    "USDCAD": ["USD", "CAD"],
    "USDCHF": ["USD", "CHF"],
    "NZDUSD": ["NZD", "USD"],
    "EURGBP": ["EUR", "GBP"],
    "EURJPY": ["EUR", "JPY"],
    "GBPJPY": ["GBP", "JPY"],
    "XAUUSD": ["USD"],  # Gold is primarily affected by USD macro data
    "GOLD": ["USD"],
    "BTCUSD": ["USD"],
}


class EconomicNewsFilter:
    """Monitors global economic calendar events and implements News Blackout rules."""

    def __init__(
        self,
        cache_ttl_seconds: int = 1800,  # 30 minutes cache
        default_pre_blackout_min: int = 30,
        default_post_blackout_min: int = 15,
    ) -> None:
        self.cache_ttl = cache_ttl_seconds
        self.pre_blackout_min = default_pre_blackout_min
        self.post_blackout_min = default_post_blackout_min
        self.events_cache: List[Dict[str, Any]] = []
        self.last_fetch_time: Optional[datetime] = None

    def _fetch_calendar_events(self) -> List[Dict[str, Any]]:
        """Fetch high impact economic calendar events from free real-time sources."""
        now = datetime.now(timezone.utc)
        if self.last_fetch_time and (now - self.last_fetch_time).total_seconds() < self.cache_ttl:
            return self.events_cache

        events: List[Dict[str, Any]] = []

        # Source 1: Forex Factory JSON feed (free, fast, updated continuously)
        try:
            resp = requests.get(
                "https://nfs.faireconomy.media/ff_calendar_thisweek.json",
                headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/124.0.0.0"},
                timeout=10,
            )
            if resp.status_code == 200:
                data = resp.json()
                for item in data:
                    impact = str(item.get("impact", "")).strip().capitalize()
                    if impact in ("High", "Holiday"):
                        event_date_str = item.get("date", "")
                        try:
                            # Format: "2026-10-13T08:30:00-04:00"
                            event_dt = datetime.fromisoformat(event_date_str)
                            if event_dt.tzinfo is None:
                                event_dt = event_dt.replace(tzinfo=timezone.utc)
                            events.append({
                                "title": item.get("title", "High Impact News"),
                                "country": item.get("country", "").upper(),
                                "impact": impact,
                                "timestamp": event_dt,
                                "forecast": item.get("forecast", ""),
                                "previous": item.get("previous", ""),
                            })
                        except Exception:
                            continue

                self.events_cache = events
                self.last_fetch_time = now
                logger.info("📅 Economic Calendar loaded %d High-Impact events for this week.", len(events))
                return events
        except Exception as exc:
            logger.warning("Failed to fetch primary economic calendar feed: %s", exc)

        # Retain previous cache if temporary network failure occurs
        return self.events_cache

    def is_news_blackout(
        self,
        symbol: str,
        current_time: Optional[datetime] = None,
        pre_blackout_min: Optional[int] = None,
        post_blackout_min: Optional[int] = None,
    ) -> Tuple[bool, Optional[str]]:
        """Check if trading is currently in a blackout window for the given symbol.

        Returns:
            Tuple[bool, Optional[str]]: (is_blackout, blackout_reason)
        """
        now = current_time or datetime.now(timezone.utc)
        if now.tzinfo is None:
            now = now.replace(tzinfo=timezone.utc)

        pre_min = pre_blackout_min or self.pre_blackout_min
        post_min = post_blackout_min or self.post_blackout_min

        sym_upper = symbol.upper().replace("=X", "")
        currencies = SYMBOL_CURRENCY_MAP.get(sym_upper, [sym_upper[:3], sym_upper[3:6]])

        events = self._fetch_calendar_events()
        for event in events:
            event_curr = event["country"]
            if event_curr in currencies or event_curr in ("ALL", "USD"):
                event_dt = event["timestamp"]
                pre_window = event_dt - timedelta(minutes=pre_min)
                post_window = event_dt + timedelta(minutes=post_min)

                if pre_window <= now <= post_window:
                    minutes_diff = int((event_dt - now).total_seconds() / 60)
                    if minutes_diff > 0:
                        timing_desc = f"dimulai dalam {minutes_diff} menit"
                    else:
                        timing_desc = f"telah rilis {-minutes_diff} menit lalu (cooldown)"

                    reason = (
                        f"News Blackout [{event['impact']} Impact]: '{event['title']}' ({event_curr}) "
                        f"{timing_desc}. Dilarang membuka posisi baru."
                    )
                    return True, reason

        return False, None

    def get_post_news_context(
        self,
        symbol: str,
        current_time: Optional[datetime] = None,
        min_cooldown_min: Optional[int] = None,
        max_drift_min: int = 120,
    ) -> Dict[str, Any]:
        """Check if symbol is currently in the Post-News Continuation Window (15m to 120m after release).

        Returns:
            Dict containing post-news event details if active, otherwise {'is_post_news': False}.
        """
        now = current_time or datetime.now(timezone.utc)
        if now.tzinfo is None:
            now = now.replace(tzinfo=timezone.utc)

        post_min = min_cooldown_min or self.post_blackout_min  # default 15 min

        sym_upper = symbol.upper().replace("=X", "")
        currencies = SYMBOL_CURRENCY_MAP.get(sym_upper, [sym_upper[:3], sym_upper[3:6]])

        events = self._fetch_calendar_events()
        for event in events:
            event_curr = event["country"]
            if event.get("impact") == "High" and (event_curr in currencies or event_curr in ("ALL", "USD")):
                event_dt = event["timestamp"]
                seconds_diff = (now - event_dt).total_seconds()
                minutes_since = int(seconds_diff / 60)

                # Active in the post-blackout continuation window (15m to 120m)
                if post_min <= minutes_since <= max_drift_min:
                    return {
                        "is_post_news": True,
                        "event_title": event["title"],
                        "country": event_curr,
                        "impact": event["impact"],
                        "event_time": event_dt,
                        "minutes_since_event": minutes_since,
                        "forecast": event.get("forecast", ""),
                        "previous": event.get("previous", ""),
                    }

        return {"is_post_news": False}


# Global singleton instance for easy import across modules
news_filter = EconomicNewsFilter()

