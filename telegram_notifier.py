"""Async Telegram notification dispatcher using python-telegram-bot v20+ with retry logic."""

import asyncio
from typing import Optional
from telegram import Bot
from telegram.constants import ParseMode
from telegram.error import TelegramError, RetryAfter, NetworkError, BadRequest

from config import settings, logger
from rag_engine import TradingSignalDecision


class TelegramNotifier:
    """Dispatches trading signal alerts to Telegram with exponential backoff retry."""

    def __init__(
        self,
        bot_token: Optional[str] = None,
        chat_id: Optional[str] = None,
        max_retries: int = 4,
    ) -> None:
        self.bot_token = bot_token or settings.TELEGRAM_BOT_TOKEN
        self.chat_id = chat_id or settings.TELEGRAM_CHAT_ID
        self.max_retries = max_retries
        self.bot: Optional[Bot] = None

        if self.bot_token:
            try:
                self.bot = Bot(token=self.bot_token)
                logger.info("Telegram Bot client initialized.")
            except Exception as exc:
                logger.error("Failed to initialize Telegram Bot: %s", exc)
                self.bot = None
        else:
            logger.warning("TELEGRAM_BOT_TOKEN not provided. Notifications will be logged to console only.")

    @property
    def is_configured(self) -> bool:
        """Check if Telegram credentials are valid and present."""
        return bool(self.bot and self.chat_id)

    async def _send_chunked_message(self, text: str, max_chunk_size: int = 3800) -> bool:
        """Split a long message into multiple chunks and send sequentially."""
        if not self.is_configured:
            return False

        chunks = []
        current = []
        current_len = 0
        for line in text.split("\n"):
            line_len = len(line) + 1
            if current_len + line_len > max_chunk_size and current:
                chunks.append("\n".join(current))
                current = [line]
                current_len = line_len
            else:
                current.append(line)
                current_len += line_len
        if current:
            chunks.append("\n".join(current))

        all_ok = True
        for idx, chunk in enumerate(chunks, 1):
            try:
                assert self.bot is not None
                await self.bot.send_message(
                    chat_id=self.chat_id,
                    text=chunk,
                    parse_mode=None,
                    disable_web_page_preview=True,
                )
                logger.info("Sent Telegram message chunk %d/%d.", idx, len(chunks))
            except Exception as exc:
                logger.error("Failed to send Telegram message chunk %d/%d: %s", idx, len(chunks), exc)
                all_ok = False
        return all_ok

    async def send_message(self, text: str, parse_mode: Optional[str] = ParseMode.MARKDOWN) -> bool:
        """Send message with exponential backoff retry and rate-limit handling."""
        if not self.is_configured:
            logger.info("[TELEGRAM NOTIFICATION (Dry-Run / Unconfigured)]:\n%s", text)
            return False

        if len(text) > 4000:
            logger.warning("Message length (%d chars) exceeds safety threshold. Splitting into chunks...", len(text))
            return await self._send_chunked_message(text)

        delay = 1.0
        for attempt in range(1, self.max_retries + 1):
            try:
                assert self.bot is not None
                await self.bot.send_message(
                    chat_id=self.chat_id,
                    text=text,
                    parse_mode=parse_mode,
                    disable_web_page_preview=True,
                )
                logger.info("Telegram alert dispatched successfully (attempt %d).", attempt)
                return True

            except RetryAfter as e:
                wait_sec = e.retry_after + 1.0
                logger.warning("Telegram flood limit reached. Waiting %.1fs...", wait_sec)
                await asyncio.sleep(wait_sec)

            except BadRequest as e:
                err_msg = str(e).lower()
                # 1. Fallback for Markdown entity parsing errors
                if ("can't parse entities" in err_msg or "can't find end of the entity" in err_msg) and parse_mode is not None:
                    logger.warning("Telegram parse error encountered (%s). Retrying immediately as plain text...", e)
                    try:
                        assert self.bot is not None
                        await self.bot.send_message(
                            chat_id=self.chat_id,
                            text=text,
                            parse_mode=None,
                            disable_web_page_preview=True,
                        )
                        logger.info("Telegram alert dispatched successfully via plain text fallback.")
                        return True
                    except Exception as fallback_exc:
                        logger.error("Plain text fallback failed: %s", fallback_exc)
                        return False

                # 2. Message length exceeded limit -> split into chunks
                if "message is too long" in err_msg:
                    logger.warning("Telegram message exceeded character limit. Retrying with chunking...")
                    return await self._send_chunked_message(text)

                # 3. Non-recoverable bad request (wrong chat ID, forbidden, etc.)
                logger.error("Telegram BadRequest error (non-retryable): %s", e)
                return False

            except NetworkError as e:
                logger.warning("Network error sending Telegram message (attempt %d/%d): %s", attempt, self.max_retries, e)
                if attempt == self.max_retries:
                    logger.error("Exceeded max retries for Telegram dispatch due to network error.")
                    return False
                await asyncio.sleep(delay)
                delay *= 2.0

            except TelegramError as e:
                logger.error("Telegram error on attempt %d: %s", attempt, e)
                if attempt == self.max_retries:
                    return False
                await asyncio.sleep(delay)
                delay *= 2.0

            except Exception as e:
                logger.error("Unexpected exception during Telegram send: %s", e)
                return False

        return False

    async def send_signal_decision(self, decision: TradingSignalDecision) -> bool:
        """Format structured decision and send to configured Telegram chat."""
        markdown_text = decision.to_telegram_markdown()
        return await self.send_message(markdown_text)


# Global instance
notifier = TelegramNotifier()
