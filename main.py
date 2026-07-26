import os
import httpx
from typing import Dict, Any
from fastapi import FastAPI, Request, Depends, HTTPException, Header
from config import settings
from telegram.webhook import verify_telegram_webhook, parse_telegram_update
from agents.master_agent import MasterAgent

app = FastAPI(
    title=settings.APP_NAME,
    version="5.2.0",
    description="Smart Sembako Cloud Bot Runtime (Decoupled Cloud Service)"
)

master_agent = MasterAgent()

@app.get("/")
async def root():
    return {
        "app": settings.APP_NAME,
        "version": "5.2.0",
        "status": "online",
        "environment": settings.ENVIRONMENT
    }

@app.get("/health")
async def health_check():
    return {
        "status": "healthy",
        "supabase_configured": bool(settings.SUPABASE_URL and settings.SUPABASE_KEY),
        "groq_configured": bool(settings.GROQ_API_KEY),
        "gemini_configured": bool(settings.GEMINI_API_KEY)
    }

@app.post("/webhook/telegram")
async def telegram_webhook(
    request: Request,
    x_telegram_bot_api_secret_token: str = Header(None, alias="X-Telegram-Bot-Api-Secret-Token")
):
    # Fix K-2: Verify webhook authentication header
    await verify_telegram_webhook(request, x_telegram_bot_api_secret_token)

    try:
        body = await request.json()
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid JSON body")

    update_info = parse_telegram_update(body)
    chat_id = update_info.get("chat_id")
    user_id = update_info.get("user_id")
    text = update_info.get("text", "")

    if not chat_id or not text:
        return {"status": "ignored", "reason": "empty message or missing chat_id"}

    # Process message via MasterAgent
    response_text = await master_agent.handle_message(user_id=user_id or 0, message_text=text)

    # Send response back to Telegram if BOT_TOKEN is configured
    if settings.TELEGRAM_BOT_TOKEN:
        tg_url = f"https://api.telegram.org/bot{settings.TELEGRAM_BOT_TOKEN}/sendMessage"
        async with httpx.AsyncClient() as client:
            await client.post(tg_url, json={
                "chat_id": chat_id,
                "text": response_text,
                "parse_mode": "Markdown"
            }, timeout=10.0)

    return {
        "status": "success",
        "chat_id": chat_id,
        "response_text": response_text
    }

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=settings.PORT)
