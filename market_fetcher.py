"""Market data ingestion: TradingView Webhook, YFinance connector, and Simulator."""

from typing import Dict, Any, Optional, Callable, Awaitable
from datetime import datetime
import random
from fastapi import FastAPI, APIRouter, HTTPException, Header, Request
from pydantic import BaseModel, Field

from config import settings, logger

# Callback type for processing evaluated market alerts
SignalHandler = Callable[[Dict[str, Any]], Awaitable[None]]


class TradingViewPayload(BaseModel):
    """Pydantic schema for TradingView webhook alert payloads."""

    symbol: str = Field(..., description="Ticker or pair symbol (e.g., EURUSD, XAUUSD, AAPL)")
    timeframe: str = Field(default="5m", description="Timeframe of the alert (e.g., 5m, 15m, 1h, 4h, 1D)")
    price: float = Field(..., description="Current asset price at trigger")
    indicator_status: str = Field(
        ...,
        description="Summary of indicator state, e.g. 'MACD golden cross, BB lower band rejection, RSI oversold'"
    )
    strategy: Optional[str] = Field(default="TradingView Alert", description="Strategy or alert name")
    notes: Optional[str] = Field(default="", description="Additional context or chart pattern observations")
    timestamp: Optional[str] = Field(default_factory=lambda: datetime.utcnow().isoformat())


class MarketDataFetcher:
    """Handles Webhook listening, YFinance quotes, and market simulation."""

    def __init__(self, signal_handler: Optional[SignalHandler] = None) -> None:
        self.signal_handler = signal_handler
        self.router = APIRouter()
        self._setup_routes()

    def set_signal_handler(self, handler: SignalHandler) -> None:
        """Register the async signal evaluation handler."""
        self.signal_handler = handler

    def _setup_routes(self) -> None:
        """Define FastAPI endpoints."""

        @self.router.post("/webhook/tradingview")
        async def receive_tradingview_alert(
            payload: TradingViewPayload,
            request: Request,
            x_webhook_secret: Optional[str] = Header(None, alias="X-Webhook-Secret"),
        ) -> Dict[str, Any]:
            """Receive alert JSON from TradingView."""
            # Optional secret token validation
            if settings.WEBHOOK_SECRET and x_webhook_secret != settings.WEBHOOK_SECRET:
                logger.warning("Unauthorized webhook alert attempt from %s", request.client.host if request.client else "unknown")
                raise HTTPException(status_code=401, detail="Invalid webhook secret token")

            logger.info("Received TradingView alert: %s @ %.5f [%s]", payload.symbol, payload.price, payload.indicator_status)

            data = payload.model_dump()
            if self.signal_handler:
                # Dispatch alert asynchronously to the handler
                import asyncio
                asyncio.create_task(self.signal_handler(data))

            return {
                "status": "received",
                "symbol": payload.symbol,
                "timestamp": payload.timestamp,
                "queued_for_rag": self.signal_handler is not None,
            }

        @self.router.get("/health")
        async def health_check() -> Dict[str, str]:
            """Service health probe."""
            return {"status": "ok", "service": "trading-ai-bot"}

    def fetch_yfinance_snapshot(self, symbol: str) -> Optional[Dict[str, Any]]:
        """Fetch latest price and basic technical indicators using yfinance."""
        try:
            import yfinance as yf
            ticker = yf.Ticker(symbol)
            history = ticker.history(period="5d", interval="5m")
            if history.empty:
                logger.warning("No yfinance history returned for %s", symbol)
                return None

            latest = history.iloc[-1]
            close_prices = history["Close"]

            # Calculate simple technical indicators
            sma20 = close_prices.rolling(window=20).mean().iloc[-1] if len(close_prices) >= 20 else latest["Close"]
            sma50 = close_prices.rolling(window=50).mean().iloc[-1] if len(close_prices) >= 50 else latest["Close"]

            # Delta & RSI approximation
            delta = close_prices.diff()
            gain = (delta.where(delta > 0, 0)).rolling(14).mean().iloc[-1]
            loss = (-delta.where(delta < 0, 0)).rolling(14).mean().iloc[-1]
            rs = gain / (loss + 1e-9)
            rsi = 100 - (100 / (1 + rs))

            status_notes = []
            if latest["Close"] > sma20 > sma50:
                status_notes.append("Price above SMA20 & SMA50 (Uptrend)")
            elif latest["Close"] < sma20 < sma50:
                status_notes.append("Price below SMA20 & SMA50 (Downtrend)")

            if rsi < 30:
                status_notes.append(f"RSI oversold ({rsi:.1f})")
            elif rsi > 70:
                status_notes.append(f"RSI overbought ({rsi:.1f})")
            else:
                status_notes.append(f"RSI neutral ({rsi:.1f})")

            indicator_summary = ", ".join(status_notes)

            return {
                "symbol": symbol,
                "timeframe": "5m",
                "price": round(float(latest["Close"]), 5),
                "indicator_status": indicator_summary,
                "strategy": "YFinance Technical Feed",
                "notes": f"High: {latest['High']:.5f}, Low: {latest['Low']:.5f}, Volume: {int(latest['Volume'])}",
                "timestamp": datetime.utcnow().isoformat(),
            }
        except Exception as exc:
            logger.error("Failed fetching yfinance snapshot for '%s': %s", symbol, exc)
            return None

    @staticmethod
    def generate_simulated_tick(symbol: str = "EURUSD", scenario: Optional[str] = None) -> Dict[str, Any]:
        """Generate a realistic simulated market tick with technical pattern description."""
        # Attempt to get real current market price if available
        live_price = None
        try:
            import yfinance as yf
            ticker = yf.Ticker("EURUSD=X" if symbol.upper() == "EURUSD" else symbol)
            h = ticker.history(period="1d", interval="5m")
            if not h.empty:
                live_price = round(float(h["Close"].iloc[-1]), 5)
        except Exception:
            pass

        eurusd_price = live_price if (live_price and symbol.upper() == "EURUSD") else 1.13207

        scenarios = [
            {
                "symbol": "EURUSD",
                "price": eurusd_price,
                "timeframe": "5m",
                "indicator_status": (
                    f"Bullish Engulfing pattern formed at key support ({eurusd_price - 0.00030:.5f}), "
                    "MACD Golden Cross, Lower Bollinger Band rejection"
                ),
                "notes": f"Rejection from lower Bollinger Band on 5m timeframe with strong volume at {eurusd_price:.5f}.",
            },
            {
                "symbol": "EURUSD",
                "price": eurusd_price,
                "timeframe": "5m",
                "indicator_status": (
                    f"Three Black Crows formed near resistance ({eurusd_price + 0.00030:.5f}), "
                    "MACD Death Cross, Upper Bollinger Band rejection"
                ),
                "notes": f"Rejection from upper Bollinger Band on 5m timeframe at {eurusd_price:.5f}.",
            },
            {
                "symbol": "XAUUSD",
                "price": 2685.50,
                "timeframe": "5m",
                "indicator_status": "Bearish Evening Star at major resistance, Bollinger Band upper touch, RSI 74 overbought",
                "notes": "Strong exhaustion pin bar followed by high-volume bearish confirmation candle on 5m.",
            },
            {
                "symbol": "BBCA.JK",
                "price": 10250.0,
                "timeframe": "5m",
                "indicator_status": "Breakout above consolidation base with volume spike, MACD Golden Cross",
                "notes": "5m momentum continuation breakout.",
            },
            {
                "symbol": "GBPUSD",
                "price": 1.3340,
                "timeframe": "5m",
                "indicator_status": "Inside bar inside indecision doji, low volatility, MACD flat around zero line",
                "notes": "Pre-news consolidation, no trend direction established.",
            },
        ]

        if scenario:
            for s in scenarios:
                if s["symbol"].lower() == scenario.lower():
                    return s

        chosen = random.choice(scenarios)
        if symbol and symbol != "EURUSD":
            chosen["symbol"] = symbol
        return chosen


def create_app(fetcher: MarketDataFetcher) -> FastAPI:
    """Build and configure the FastAPI application."""
    app = FastAPI(
        title="AI Trading Signal Bot Webhook Service",
        description="FastAPI service for ingesting TradingView and broker alerts for RAG evaluation",
        version="1.0.0",
    )
    app.include_router(fetcher.router)
    return app
