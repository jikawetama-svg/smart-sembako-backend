import os
import sys
import json
import socket
import asyncio
import httpx
import traceback
from datetime import datetime, timezone
from typing import Dict, Any
from fastapi import FastAPI, Request, Response, HTTPException, Header

# Force IPv4
old_getaddrinfo = socket.getaddrinfo
def ipv4_only_getaddrinfo(host, port, family=0, type=0, proto=0, flags=0):
    return old_getaddrinfo(host, port, socket.AF_INET, type, proto, flags)
socket.getaddrinfo = ipv4_only_getaddrinfo

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from config import settings
from telegram.webhook import verify_telegram_webhook, parse_telegram_update
from agents.master_agent import MasterAgent
from webhook_manager import set_webhook, delete_webhook, build_webhook_url, get_webhook_info

app = FastAPI(
    title=settings.APP_NAME,
    version="7.1.0",
    description="Smart Sembako Cloud Bot — Full Feature + AI Memory + Failover"
)

master_agent = MasterAgent()

# ─────────────────────────────────────────────
# State: apakah Desktop Bot sedang aktif
# ─────────────────────────────────────────────
_desktop_is_online: bool = False
_desktop_last_seen: datetime | None = None

def _verify_desktop_signal(secret: str, merchant_id: str) -> bool:
    expected_secret = settings.DESKTOP_SHARED_SECRET or settings.TELEGRAM_SECRET_TOKEN
    if secret != expected_secret:
        return False
    if settings.TENANT_ISOLATION_REQUIRED and merchant_id != settings.MERCHANT_ID:
        return False
    return True


# ─────────────────────────────────────────────
# Startup: register webhook jika Desktop offline
# ─────────────────────────────────────────────
from agents.scheduler_agent import SchedulerAgent

@app.on_event("startup")
async def on_startup():
    global _desktop_is_online
    bot_token = settings.TELEGRAM_BOT_TOKEN
    
    # Start proactive scheduler if enabled
    if settings.SCHEDULER_ENABLED:
        scheduler = SchedulerAgent(bot_id="cloud_bot")
        asyncio.create_task(scheduler.start_scheduler())
        print("[Startup] ⏰ Proactive Scheduler Agent active")

    if not bot_token:
        print("[Startup] TELEGRAM_BOT_TOKEN not configured.")
        return

    webhook_info = await get_webhook_info(bot_token)
    current_url = webhook_info.get("url", "")
    expected_url = build_webhook_url()

    if not _desktop_is_online and current_url != expected_url:
        success = await set_webhook(bot_token, expected_url, settings.TELEGRAM_SECRET_TOKEN)
        if success:
            print(f"[Startup] ✅ Webhook otomatis didaftarkan: {expected_url}")
        else:
            print(f"[Startup] ⚠️ Gagal mendaftarkan webhook. Akan dicoba saat endpoint /health diakses.")


# ─────────────────────────────────────────────
# Health check
# ─────────────────────────────────────────────
@app.get("/")
@app.head("/")
@app.get("/bot-health")
async def health_check():
    return {
        "status": "healthy",
        "bot_app": settings.APP_NAME,
        "version": "7.1.0",
        "desktop_online": _desktop_is_online,
        "desktop_last_seen": _desktop_last_seen.isoformat() if _desktop_last_seen else None,
        "supabase_configured": bool(settings.SUPABASE_URL and settings.SUPABASE_KEY),
        "tenant_isolation_ready": bool(settings.MERCHANT_ID) or not settings.TENANT_ISOLATION_REQUIRED,
        "telegram_configured": bool(settings.TELEGRAM_BOT_TOKEN)
    }


# ─────────────────────────────────────────────
# Failover: Desktop Bot notify ONLINE
# ─────────────────────────────────────────────
@app.post("/internal/desktop-online")
async def desktop_online(request: Request):
    secret = request.headers.get("X-Desktop-Secret", "")
    merchant_id = request.headers.get("X-Merchant-ID", "")
    if not _verify_desktop_signal(secret, merchant_id):
        raise HTTPException(status_code=403, detail="Forbidden")

    global _desktop_is_online, _desktop_last_seen
    _desktop_is_online = True
    _desktop_last_seen = datetime.now(timezone.utc)

    bot_token = settings.TELEGRAM_BOT_TOKEN
    if bot_token:
        asyncio.create_task(delete_webhook(bot_token))
        print("[Failover] ✅ Desktop Bot ONLINE — webhook dihapus, polling mode aktif")

    return {"status": "ok", "message": "Desktop online, webhook removed"}


# ─────────────────────────────────────────────
# Failover: Desktop Bot notify OFFLINE
# ─────────────────────────────────────────────
@app.post("/internal/desktop-offline")
async def desktop_offline(request: Request):
    secret = request.headers.get("X-Desktop-Secret", "")
    merchant_id = request.headers.get("X-Merchant-ID", "")
    if not _verify_desktop_signal(secret, merchant_id):
        raise HTTPException(status_code=403, detail="Forbidden")

    global _desktop_is_online
    _desktop_is_online = False

    bot_token = settings.TELEGRAM_BOT_TOKEN
    if bot_token:
        webhook_url = build_webhook_url()
        asyncio.create_task(set_webhook(bot_token, webhook_url, settings.TELEGRAM_SECRET_TOKEN))
        print("[Failover] ✅ Desktop Bot OFFLINE — webhook terdaftar ulang")

    return {"status": "ok", "message": "Desktop offline, webhook re-registered"}


# ─────────────────────────────────────────────
# Telegram Webhook endpoint
# ─────────────────────────────────────────────
async def send_telegram_response(bot_token: str, chat_id: int, response_text: str):
    tg_url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
    payload = {
        "chat_id": chat_id,
        "text": str(response_text),
        "parse_mode": "Markdown"
    }
    try:
        async with httpx.AsyncClient(trust_env=True, timeout=10.0) as client:
            res = await client.post(tg_url, json=payload)
            if res.status_code != 200:
                # Retry tanpa Markdown jika format error
                payload["parse_mode"] = None
                await client.post(tg_url, json=payload)
    except Exception as e:
        print(f"[Telegram Send Error]: {e}\n{traceback.format_exc()}")


@app.post("/webhook/telegram")
async def telegram_webhook(
    request: Request,
    x_telegram_bot_api_secret_token: str = Header(None, alias="X-Telegram-Bot-Api-Secret-Token")
):
    # Jika Desktop online, ignore webhook (Desktop pakai polling)
    if _desktop_is_online:
        return {"status": "ignored", "reason": "desktop_bot_active"}

    await verify_telegram_webhook(request, x_telegram_bot_api_secret_token)

    try:
        body = await request.json()
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid JSON body")

    update_info = parse_telegram_update(body)
    chat_id = update_info.get("chat_id")
    user_id = update_info.get("user_id") or update_info.get("chat_id")
    text = update_info.get("text", "")

    if not chat_id or not text:
        return {"status": "ignored", "reason": "empty message or missing chat_id"}

    try:
        response_text = await master_agent.handle_message(
            user_id=int(user_id or 0),
            message_text=text
        )
    except Exception as e:
        print(f"[MasterAgent Error]: {e}\n{traceback.format_exc()}")
        response_text = "⚠️ Terjadi kesalahan internal. Silakan coba lagi."

    bot_token = settings.TELEGRAM_BOT_TOKEN or os.getenv("TELEGRAM_BOT_TOKEN", "")
    if bot_token:
        await send_telegram_response(bot_token, chat_id, response_text)

    return {"status": "success", "chat_id": chat_id}


if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("PORT", "8000"))
    uvicorn.run(app, host="0.0.0.0", port=port)
