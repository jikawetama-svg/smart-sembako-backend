import os
import asyncio
import traceback
from typing import Optional
from config import settings

TELEGRAM_API = "https://api.telegram.org"

async def set_webhook(bot_token: str, webhook_url: str, secret_token: str) -> bool:
    """Register webhook Telegram. Dipanggil saat Desktop Bot offline."""
    try:
        import httpx
        url = f"{TELEGRAM_API}/bot{bot_token}/setWebhook"
        payload = {
            "url": webhook_url,
            "secret_token": secret_token,
            "drop_pending_updates": False,
            "max_connections": 40
        }
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.post(url, json=payload)
            result = resp.json()
            if result.get("ok"):
                print(f"[WebhookManager] ✅ Webhook terdaftar: {webhook_url}")
                return True
            else:
                print(f"[WebhookManager] ❌ Gagal daftar webhook: {result}")
                return False
    except Exception as e:
        print(f"[WebhookManager] Exception set_webhook: {e}\n{traceback.format_exc()}")
        return False


async def delete_webhook(bot_token: str) -> bool:
    """Hapus webhook Telegram. Dipanggil saat Desktop Bot kembali online."""
    try:
        import httpx
        url = f"{TELEGRAM_API}/bot{bot_token}/deleteWebhook"
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.post(url, json={"drop_pending_updates": False})
            result = resp.json()
            if result.get("ok"):
                print(f"[WebhookManager] ✅ Webhook dihapus, Desktop Bot sekarang aktif polling")
                return True
            else:
                print(f"[WebhookManager] ❌ Gagal hapus webhook: {result}")
                return False
    except Exception as e:
        print(f"[WebhookManager] Exception delete_webhook: {e}\n{traceback.format_exc()}")
        return False


async def get_webhook_info(bot_token: str) -> dict:
    """Cek status webhook saat ini."""
    try:
        import httpx
        url = f"{TELEGRAM_API}/bot{bot_token}/getWebhookInfo"
        async with httpx.AsyncClient(timeout=8.0) as client:
            resp = await client.get(url)
            data = resp.json()
            return data.get("result", {})
    except Exception:
        return {}


def get_cloud_bot_url() -> str:
    """Ambil URL public cloud bot dari env."""
    return os.getenv("CLOUD_BOT_URL", "https://smart-sembako-backend.onrender.com")


def build_webhook_url() -> str:
    return f"{get_cloud_bot_url()}/webhook/telegram"
