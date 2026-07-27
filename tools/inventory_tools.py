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
