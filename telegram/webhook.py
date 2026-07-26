import hmac
import hashlib
from typing import Dict, Any, Optional
from fastapi import Request, HTTPException, Header
from config import settings

async def verify_telegram_webhook(
    request: Request, 
    x_telegram_bot_api_secret_token: Optional[str] = Header(None)
) -> bool:
    """
    Validasi secret token dari header HTTP Telegram webhook.
    Fix K-2 (Cloud Side Verification).
    """
    expected_token = settings.TELEGRAM_SECRET_TOKEN
    if not expected_token:
        # Jika tidak dikonfigurasi, lewati validasi (development mode)
        return True

    if x_telegram_bot_api_secret_token != expected_token:
        raise HTTPException(status_code=403, detail="Invalid Telegram secret token header")

    return True

def parse_telegram_update(body: Dict[str, Any]) -> Dict[str, Any]:
    """
    Ekstrak data penting dari payload update Telegram.
    """
    message = body.get("message") or body.get("edited_message") or {}
    chat = message.get("chat", {})
    user = message.get("from", {})

    return {
        "update_id": body.get("update_id"),
        "message_id": message.get("message_id"),
        "chat_id": chat.get("id"),
        "user_id": user.get("id"),
        "username": user.get("username", ""),
        "first_name": user.get("first_name", ""),
        "text": message.get("text", "").strip(),
        "photo": message.get("photo"),
        "date": message.get("date")
    }
