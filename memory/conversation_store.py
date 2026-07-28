import json
import asyncio
import urllib.request
import urllib.parse
from datetime import datetime, timezone, timedelta
from typing import List, Dict, Any, Optional
from config import settings

MAX_HISTORY = 12  # jumlah pesan yang disimpan per user
MEMORY_TTL_HOURS = 24  # memory auto-expire setelah 24 jam

async def _supabase_request(method: str, table: str, body: Optional[dict | list] = None, params: Optional[dict] = None) -> Any:
    if not settings.SUPABASE_URL or not settings.SUPABASE_KEY:
        return None
    if settings.TENANT_ISOLATION_REQUIRED and not settings.MERCHANT_ID:
        print("[TenantIsolation] Conversation memory blocked: MERCHANT_ID is not configured.")
        return None

    params = dict(params or {})
    if settings.MERCHANT_ID:
        params["merchant_id"] = f"eq.{settings.MERCHANT_ID}"
        if method == "POST":
            if isinstance(body, dict):
                body = {**body, "merchant_id": settings.MERCHANT_ID}
            elif isinstance(body, list):
                body = [{**item, "merchant_id": settings.MERCHANT_ID} for item in body]

    url = f"{settings.SUPABASE_URL.rstrip('/')}/rest/v1/{table}"
    headers = {
        "apikey": settings.SUPABASE_KEY,
        "Authorization": f"Bearer {settings.SUPABASE_KEY}",
        "Content-Type": "application/json",
        "Prefer": "return=minimal"
    }

    try:
        import httpx
        async with httpx.AsyncClient() as client:
            if method == "GET":
                resp = await client.get(url, headers=headers, params=params, timeout=8.0)
            elif method == "POST":
                resp = await client.post(url, headers=headers, json=body, params=params, timeout=8.0)
            elif method == "DELETE":
                resp = await client.delete(url, headers=headers, params=params, timeout=8.0)
            else:
                return None
            if resp.status_code in (200, 201, 204):
                try:
                    return resp.json()
                except Exception:
                    return True
    except Exception as e:
        print(f"[MemoryStore] {method} {table} error: {e}")
    return None


async def get_history(user_id: int) -> List[Dict[str, str]]:
    """Ambil riwayat percakapan user dari Supabase, diurutkan dari terlama ke terbaru."""
    cutoff = (datetime.now(timezone.utc) - timedelta(hours=MEMORY_TTL_HOURS)).isoformat()
    rows = await _supabase_request("GET", "conversations_memory", params={
        "select": "role,content,created_at",
        "user_id": f"eq.{user_id}",
        "created_at": f"gte.{cutoff}",
        "order": "created_at.asc",
        "limit": MAX_HISTORY
    })
    if not rows or not isinstance(rows, list):
        return []
    return [{"role": r["role"], "content": r["content"]} for r in rows]


async def save_message(user_id: int, role: str, content: str) -> None:
    """Simpan satu pesan ke memory. Lalu prune jika melebihi MAX_HISTORY."""
    await _supabase_request("POST", "conversations_memory", body={
        "user_id": user_id,
        "role": role,
        "content": content[:2000],  # cap panjang pesan
        "created_at": datetime.now(timezone.utc).isoformat()
    })
    # Prune asinkron di background
    asyncio.create_task(_prune_old_messages(user_id))


async def _prune_old_messages(user_id: int) -> None:
    """Hapus pesan lama melampaui TTL atau melebihi MAX_HISTORY per user."""
    cutoff = (datetime.now(timezone.utc) - timedelta(hours=MEMORY_TTL_HOURS)).isoformat()
    await _supabase_request("DELETE", "conversations_memory", params={
        "user_id": f"eq.{user_id}",
        "created_at": f"lt.{cutoff}"
    })


async def clear_history(user_id: int) -> None:
    """Reset seluruh memory user (dipanggil saat /start atau /reset)."""
    await _supabase_request("DELETE", "conversations_memory", params={
        "user_id": f"eq.{user_id}"
    })
