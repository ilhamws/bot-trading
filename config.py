"""Configuration module using Pydantic Settings."""

from pathlib import Path
import logging
import sys
from typing import Literal
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

BASE_DIR = Path(__file__).resolve().parent


class Settings(BaseSettings):
    """Application settings with environment variable support."""

    model_config = SettingsConfigDict(
        env_file=str(BASE_DIR / ".env"),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # API Keys
    GEMINI_API_KEY: str = Field(default="", description="Google Gemini API Key")
    VULTR_API_KEY: str = Field(default="", description="Vultr Serverless Inference API Key")
    VULTR_MODEL: str = Field(default="deepseek-v4.1-flash-1017", description="Vultr Model ID")
    VULTR_BASE_URL: str = Field(default="https://api.vultrinference.com/v1", description="Vultr Inference Base URL")
    AI_PROVIDER: str = Field(default="vultr", description="Primary AI provider: vultr or gemini")
    TELEGRAM_BOT_TOKEN: str = Field(default="", description="Telegram Bot Token from @BotFather")
    TELEGRAM_CHAT_ID: str = Field(default="", description="Target Telegram Chat or Channel ID")

    # Network / Webhook
    WEBHOOK_HOST: str = Field(default="0.0.0.0", description="Webhook listener bind host")
    WEBHOOK_PORT: int = Field(default=8001, description="Webhook listener port")
    WEBHOOK_SECRET: str = Field(default="", description="Optional secret token for webhook validation")

    # Data Source & MT5 Auto-Trading
    DATA_SOURCE: Literal["webhook", "mt5", "simulation"] = Field(
        default="webhook", description="Primary market data source"
    )
    MT5_AUTO_TRADE: bool = Field(default=True, description="Enable automatic order execution on MT5")
    MT5_LOT_SIZE: float = Field(default=0.01, description="Default lot size for MT5 auto-orders")

    # Storage Paths
    PDF_DIR: str = Field(default="./materi_pdf", description="Directory containing trading PDF modules")
    KNOWLEDGE_DIR: str = Field(default="./knowledge_db", description="ChromaDB persistent storage directory")
    COLLECTION_NAME: str = Field(default="trading_rules", description="ChromaDB collection name")

    # Model & Retrieval
    GEMINI_MODEL: str = Field(default="gemini-flash-lite-latest", description="Gemini model identifier")
    TOP_K_RULES: int = Field(default=4, description="Number of SOP rule chunks to retrieve for each signal")

    @property
    def resolved_pdf_dir(self) -> Path:
        """Resolve PDF directory path relative to project root if relative."""
        p = Path(self.PDF_DIR)
        return p if p.is_absolute() else (BASE_DIR / p).resolve()

    @property
    def resolved_knowledge_dir(self) -> Path:
        """Resolve knowledge DB directory path relative to project root if relative."""
        p = Path(self.KNOWLEDGE_DIR)
        return p if p.is_absolute() else (BASE_DIR / p).resolve()


def setup_logger(name: str = "trading_bot", level: int = logging.INFO) -> logging.Logger:
    """Configure and return a standardized structured logger."""
    logger = logging.getLogger(name)
    if not logger.handlers:
        logger.setLevel(level)
        handler = logging.StreamHandler(sys.stdout)
        formatter = logging.Formatter(
            fmt="%(asctime)s | %(levelname)-7s | %(name)s | %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S",
        )
        handler.setFormatter(formatter)
        logger.addHandler(handler)
    return logger


# Global settings instance
settings = Settings()
logger = setup_logger("trading_bot")
