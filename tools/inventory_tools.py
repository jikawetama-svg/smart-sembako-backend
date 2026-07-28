import json
import urllib.request
import urllib.parse
from typing import Dict, Any
from config import settings
from tools.registry import BaseTool, ToolResult

async def query_supabase(table: str, params: dict) -> list:
    """Helper to query Supabase REST API directly via httpx or urllib."""
    if not settings.SUPABASE_URL or not settings.SUPABASE_KEY:
        return []
    # Never read a shared table without an explicit tenant scope. This is a
    # defense-in-depth layer; Supabase RLS remains the authoritative boundary.
    if settings.TENANT_ISOLATION_REQUIRED and not settings.MERCHANT_ID:
        print("[TenantIsolation] Query blocked: MERCHANT_ID is not configured.")
        return []

    params = dict(params or {})
    if settings.MERCHANT_ID:
        supplied_scope = params.get("merchant_id")
        expected_scope = f"eq.{settings.MERCHANT_ID}"
        if supplied_scope and supplied_scope != expected_scope:
            print(f"[TenantIsolation] Query blocked: invalid merchant scope for {table}.")
            return []
        params["merchant_id"] = expected_scope

    url = f"{settings.SUPABASE_URL.rstrip('/')}/rest/v1/{table}"
    headers = {
        "apikey": settings.SUPABASE_KEY,
        "Authorization": f"Bearer {settings.SUPABASE_KEY}",
        "Content-Type": "application/json"
    }

    try:
        import httpx
        async with httpx.AsyncClient() as client:
            response = await client.get(url, headers=headers, params=params, timeout=10.0)
            if response.status_code == 200:
                return response.json()
    except Exception:
        # Fallback to urllib.request if httpx is missing or errors
        try:
            query_str = urllib.parse.urlencode(params)
            full_url = f"{url}?{query_str}" if query_str else url
            req = urllib.request.Request(full_url, headers=headers)
            with urllib.request.urlopen(req, timeout=10.0) as resp:
                if resp.status == 200:
                    return json.loads(resp.read().decode('utf-8'))
        except Exception:
            pass

    return []


async def insert_supabase(table: str, payload: dict) -> dict:
    """Insert one row into Supabase REST API and return the inserted row when available."""
    if not settings.SUPABASE_URL or not settings.SUPABASE_KEY:
        return {}
    if settings.TENANT_ISOLATION_REQUIRED and not settings.MERCHANT_ID:
        print("[TenantIsolation] Insert blocked: MERCHANT_ID is not configured.")
        return {}

    body = dict(payload or {})
    if settings.MERCHANT_ID:
        supplied_scope = body.get("merchant_id")
        if supplied_scope and supplied_scope != settings.MERCHANT_ID:
            print(f"[TenantIsolation] Insert blocked: invalid merchant scope for {table}.")
            return {}
        body["merchant_id"] = settings.MERCHANT_ID

    url = f"{settings.SUPABASE_URL.rstrip('/')}/rest/v1/{table}"
    headers = {
        "apikey": settings.SUPABASE_KEY,
        "Authorization": f"Bearer {settings.SUPABASE_KEY}",
        "Content-Type": "application/json",
        "Prefer": "return=representation"
    }

    try:
        import httpx
        async with httpx.AsyncClient() as client:
            response = await client.post(url, headers=headers, json=body, timeout=10.0)
            if response.status_code in (200, 201):
                rows = response.json()
                return rows[0] if isinstance(rows, list) and rows else {}
            print(f"[SupabaseInsert] {table} HTTP {response.status_code}: {response.text[:200]}")
    except Exception as exc:
        print(f"[SupabaseInsert] {table} failed: {exc}")

    return {}

class GetStockTool(BaseTool):
    name = "get_stock"
    description = "Ambil data stok produk spesifik berdasarkan nama produk"

    async def execute(self, params: Dict[str, Any]) -> ToolResult:
        query = params.get("product_name", "").strip()
        if not query:
            return ToolResult(success=False, data={}, error="Nama produk tidak boleh kosong")

        products = await query_supabase("products_sync", {
            "select": "name,stock,unit,selling_price,is_low_stock",
            "name": f"ilike.*{query}*",
            "limit": 15
        })

        if not products and " " in query:
            words = [w for w in query.split() if len(w) > 1]
            if words:
                or_clause = ",".join([f"name.ilike.*{w}*" for w in words])
                products = await query_supabase("products_sync", {
                    "select": "name,stock,unit,selling_price,is_low_stock",
                    "or": f"({or_clause})",
                    "limit": 15
                })

        return ToolResult(success=True, data={"products": products, "query": query})

class FindProductTool(BaseTool):
    name = "find_product"
    description = "Cari produk di catalog berdasarkan kata kunci (pencarian fuzzy)"

    async def execute(self, params: Dict[str, Any]) -> ToolResult:
        keyword = params.get("keyword", "").strip()
        products = await query_supabase("products_sync", {
            "select": "name,stock,unit,selling_price",
            "name": f"ilike.*{keyword}*",
            "limit": 20
        })

        return ToolResult(success=True, data={"products": products, "count": len(products)})

class GetLowStockTool(BaseTool):
    name = "get_low_stock"
    description = "Dapatkan daftar produk yang memiliki stok rendah / kritis"

    async def execute(self, params: Dict[str, Any]) -> ToolResult:
        products = await query_supabase("products_sync", {
            "select": "name,stock,unit,selling_price,is_low_stock",
            "or": "(is_low_stock.eq.true,stock.lte.10)",
            "order": "stock.asc",
            "limit": 25
        })

        return ToolResult(success=True, data={"low_stock_products": products, "count": len(products)})
