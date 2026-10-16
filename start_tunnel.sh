#!/usr/bin/env bash
# Quick tunnel launcher for AI Trading Bot Webhook (Port 8001)

export PATH="$HOME/.local/bin:$PATH"

if [ "$1" == "ngrok" ]; then
    echo ">>> Menjalankan ngrok pada port 8001..."
    ngrok http 8001
else
    echo ">>> Menjalankan Cloudflare Tunnel otomatis (Gratis, Tanpa Token/Akun)..."
    echo ">>> Salin URL HTTPS yang muncul (akhiran .trycloudflare.com) untuk TradingView Webhook."
    cloudflared tunnel --url http://127.0.0.1:8001
fi
