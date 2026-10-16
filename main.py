"""Main entrypoint and orchestrator for AI Trading Signal Bot."""

import argparse
import asyncio
import sys
import uvicorn

from config import settings, logger
from ingest_pdf import PDFIngestor
from rag_engine import RAGEngine, TradingSignalDecision
from market_fetcher import MarketDataFetcher, create_app
from telegram_notifier import TelegramNotifier


class TradingBotOrchestrator:
    """Coordinates PDF Ingestion, RAG Evaluation, Market Webhook, and Telegram alerts."""

    def __init__(self) -> None:
        self.ingestor = PDFIngestor()
        self.rag_engine = RAGEngine(collection=self.ingestor.collection)
        self.notifier = TelegramNotifier()
        self.fetcher = MarketDataFetcher(signal_handler=self.process_market_signal)
        self.app = create_app(self.fetcher)

    def verify_and_prepare_knowledge_base(self, force_reindex: bool = False) -> None:
        """Ensure vector database contains indexed SOP rules; ingest if empty or requested."""
        count = self.ingestor.collection.count()
        logger.info("Knowledge Base Status: %d chunks found in collection '%s'.", count, settings.COLLECTION_NAME)

        if count == 0 or force_reindex:
            logger.info("Initializing vector indexing for trading PDF modules in '%s'...", settings.PDF_DIR)
            results = self.ingestor.ingest_all(force_reindex=force_reindex)
            # Reconnect RAG engine to updated collection
            self.rag_engine.collection = self.ingestor.collection
            logger.info(
                "Ingestion completed. Total chunks now available: %d",
                results["total_in_db"],
            )

    async def process_market_signal(self, payload: dict) -> TradingSignalDecision:
        """Route incoming market alert through RAG engine and dispatch to Telegram."""
        symbol = payload.get("symbol", "UNKNOWN")
        timeframe = payload.get("timeframe", "5m")
        price = payload.get("price", 0.0)
        indicator = payload.get("indicator_status", "")

        logger.info(">>> Processing market alert for %s (%s) @ %s | Indicators: %s", symbol, timeframe, price, indicator)

        # 1. AI RAG evaluation strictly against SOP
        decision = self.rag_engine.evaluate_market_setup(payload)

        # 2. Dispatch alert to Telegram
        await self.notifier.send_signal_decision(decision)

        return decision

    async def run_simulation(self, scenario: str = "EURUSD") -> None:
        """Execute a simulated market tick through the full AI RAG and alert pipeline."""
        logger.info("--- Starting Simulation Mode for Scenario '%s' ---", scenario)
        simulated_data = MarketDataFetcher.generate_simulated_tick(scenario=scenario)
        logger.info("Generated Simulated Market Data: %s", simulated_data)

        decision = await self.process_market_signal(simulated_data)
        logger.info("Simulation Completed. Decision: %s", decision.action)

    def start_server(self) -> None:
        """Start FastAPI uvicorn ASGI server."""
        logger.info(
            "Starting Trading AI Webhook Listener on %s:%d (Source: %s)",
            settings.WEBHOOK_HOST,
            settings.WEBHOOK_PORT,
            settings.DATA_SOURCE,
        )
        uvicorn.run(
            self.app,
            host=settings.WEBHOOK_HOST,
            port=settings.WEBHOOK_PORT,
            log_level="info",
        )


def main() -> None:
    """CLI orchestrator entrypoint."""
    parser = argparse.ArgumentParser(description="AI Trading Signal Bot Orchestrator")
    parser.add_argument("--ingest", action="store_true", help="Force re-indexing of PDFs into ChromaDB")
    parser.add_argument(
        "--simulate",
        nargs="?",
        const="EURUSD",
        default=None,
        help="Run a simulated market alert test (e.g., --simulate EURUSD or --simulate XAUUSD)",
    )
    parser.add_argument("--port", type=int, default=settings.WEBHOOK_PORT, help="Override webhook server port")
    parser.add_argument("--host", type=str, default=settings.WEBHOOK_HOST, help="Override webhook server host")

    args = parser.parse_args()

    orchestrator = TradingBotOrchestrator()

    # Step 1: Verify Knowledge Base
    orchestrator.verify_and_prepare_knowledge_base(force_reindex=args.ingest)

    # Step 2: Handle Simulation or Webhook Server
    if args.simulate:
        asyncio.run(orchestrator.run_simulation(scenario=args.simulate))
    else:
        if args.port:
            settings.WEBHOOK_PORT = args.port
        if args.host:
            settings.WEBHOOK_HOST = args.host
        orchestrator.start_server()


if __name__ == "__main__":
    main()
