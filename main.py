import os
import sys
import json
import socket
import asyncio
import httpx
import traceback
from typing import Dict, Any
from fastapi import FastAPI, Request, Response, Depends, HTTPException, Header

# Force IPv4 socket resolution on HF Spaces to bypass IPv6 egress handshake timeout
old_getaddrinfo = socket.getaddrinfo
def ipv4_only_getaddrinfo(host, port, family=0, type=0, proto=0, flags=0):
    return old_getaddrinfo(host, port, socket.AF_INET, type, proto, flags)

socket.getaddrinfo = ipv4_only_getaddrinfo

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from config import settings
from telegram.webhook import verify_telegram_webhook, parse_telegram_update
from agents.master_agent import MasterAgent

app = FastAPI(
    title=settings.APP_NAME,
    version="6.2.0",
    description="Smart Sembako Cloud Bot Router (Embedded Dual-Runtime Service)"
)

master_agent = MasterAgent()

async def send_telegram_response(bot_token: str, chat_id: int, response_text: str):
    tg_url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
    payload = {"chat_id": chat_id, "text": str(response_text)}

    # Attempt 1: Async httpx with trust_env=True and forced IPv4
    try:
        async with httpx.AsyncClient(trust_env=True, timeout=10.0) as client:
            res = await client.post(tg_url, json=payload)
            print(f"[Telegram Send httpx SUCCESS] chat_id={chat_id}, status={res.status_code}, response={res.text}")
            return
    except Exception as e:
        print(f"[Telegram Send httpx Warning]: {e}. Retrying via urllib IPv4...")

    # Attempt 2: Standard library urllib fallback over IPv4
    try:
        def _urllib_send():
            import urllib.request
            data_bytes = json.dumps(payload).encode('utf-8')
            req = urllib.request.Request(
                tg_url,
                data=data_bytes,
                headers={"Content-Type": "application/json"}
            )
            with urllib.request.urlopen(req, timeout=10) as resp:
                return resp.read().decode('utf-8')

        res_text = await asyncio.to_thread(_urllib_send)
        print(f"[Telegram Send urllib SUCCESS]: {res_text}")
    except Exception as e2:
        print(f"[Telegram Send urllib Exception]: {e2}\n{traceback.format_exc()}")

@app.get("/")
@app.head("/")
@app.get("/bot-health")
async def health_check():
    return {
        "status": "healthy",
        "bot_app": settings.APP_NAME,
        "supabase_configured": bool(settings.SUPABASE_URL and settings.SUPABASE_KEY),
        "telegram_configured": bool(settings.TELEGRAM_BOT_TOKEN or os.getenv("TELEGRAM_BOT_TOKEN"))
    }


@app.post("/webhook/telegram")
async def telegram_webhook(
    request: Request,
    x_telegram_bot_api_secret_token: str = Header(None, alias="X-Telegram-Bot-Api-Secret-Token")
):
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

    try:
        response_text = await master_agent.handle_message(user_id=user_id or 0, message_text=text)
    except Exception as e:
        print(f"[MasterAgent Error]: {e}\n{traceback.format_exc()}")
        response_text = f"🤖 Halo! Asisten Smart Sembako siap membantu toko Anda. (Pesan: {text})"

    bot_token = settings.TELEGRAM_BOT_TOKEN or os.getenv("TELEGRAM_BOT_TOKEN", "")
    if bot_token:
        # Fire-and-forget background task so webhook responds 200 instantly
        asyncio.create_task(send_telegram_response(bot_token, chat_id, response_text))
    else:
        print(f"[Telegram Webhook Warning] TELEGRAM_BOT_TOKEN is missing! (chat_id={chat_id})")

    return {
        "status": "success",
        "chat_id": chat_id,
        "response_text": str(response_text)
    }

# Proxy root '/' and all other routes to original 9router running on internal port 3000
@app.api_route("/", methods=["GET", "POST", "PUT", "DELETE", "PATCH", "OPTIONS", "HEAD"])
@app.api_route("/{path:path}", methods=["GET", "POST", "PUT", "DELETE", "PATCH", "OPTIONS", "HEAD"])
async def proxy_to_9router(request: Request, path: str = ""):
    target_url = f"http://127.0.0.1:3000/{path}"
    async with httpx.AsyncClient() as client:
        try:
            req_headers = {k: v for k, v in request.headers.items() if k.lower() != 'host'}
            req_body = await request.body()
            resp = await client.request(
                method=request.method,
                url=target_url,
                headers=req_headers,
                content=req_body,
                params=request.query_params,
                timeout=60.0
            )
            resp_headers = {k: v for k, v in resp.headers.items() if k.lower() not in ['content-length', 'content-encoding', 'transfer-encoding']}
            return Response(
                content=resp.content,
                status_code=resp.status_code,
                headers=resp_headers
            )
        except Exception as e:
            return Response(content=f"9router internal proxy: {e}", status_code=502)

if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("PORT", "7860"))
    uvicorn.run(app, host="0.0.0.0", port=port)
