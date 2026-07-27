import asyncio
from typing import Dict, Any, List, Optional
from datetime import datetime, timezone
from config import settings

class StoreBrain:
    """
    Store Brain Engine: Manages persistent business memory & store preferences
    per store_id and user_id (supporting roles: owner, admin, kasir).
    """

    def __init__(self, default_store_id: str = "store_main"):
        self.default_store_id = default_store_id

    async def _supabase_request(self, method: str, table: str, body: Optional[dict | list] = None, params: Optional[dict] = None) -> Any:
        if not settings.SUPABASE_URL or not settings.SUPABASE_KEY:
            return None

        url = f"{settings.SUPABASE_URL.rstrip('/')}/rest/v1/{table}"
        headers = {
            "apikey": settings.SUPABASE_KEY,
            "Authorization": f"Bearer {settings.SUPABASE_KEY}",
            "Content-Type": "application/json",
            "Prefer": "resolution=merge-duplicates,return=representation"
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
            print(f"[StoreBrain] {method} {table} error: {e}")
        return None

    async def get_store_memory(self, store_id: Optional[str] = None, user_id: Optional[int] = None) -> Dict[str, Any]:
        target_store = store_id or self.default_store_id
        params = {"store_id": f"eq.{target_store}"}
        if user_id:
            params["user_id"] = f"eq.{user_id}"

        rows = await self._supabase_request("GET", "store_brain", params=params)
        if not rows or not isinstance(rows, list):
            return {}

        result = {}
        for r in rows:
            result[r.get("key")] = r.get("value")
        return result

    async def save_store_memory(
        self,
        key: str,
        value: Any,
        category: str = "preference",
        store_id: Optional[str] = None,
        user_id: Optional[int] = None,
        user_role: str = "owner"
    ) -> bool:
        target_store = store_id or self.default_store_id
        payload = {
            "store_id": target_store,
            "user_id": user_id or 0,
            "user_role": user_role,
            "category": category,
            "key": key,
            "value": value,
            "updated_at": datetime.now(timezone.utc).isoformat()
        }

        res = await self._supabase_request("POST", "store_brain", body=payload, params={"on_conflict": "store_id,key"})
        return bool(res)

    async def get_user_preference(self, user_id: int, key: str, default_val: Any = None) -> Any:
        mem = await self.get_store_memory(user_id=user_id)
        return mem.get(key, default_val)
