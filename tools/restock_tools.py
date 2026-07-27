from typing import Dict, Any
from tools.registry import BaseTool, ToolResult
from tools.inventory_tools import query_supabase


class GetRestockHistoryTool(BaseTool):
    name = "get_restock_history"
    description = "Ambil riwayat restock/pembelian barang dari cloud sync"

    async def execute(self, params: Dict[str, Any]) -> ToolResult:
        product_name = params.get("product_name", "").strip()
        limit = int(params.get("limit", 10))

        query_params = {
            "select": "product_name,quantity,unit,supplier_name,purchase_price,restock_date,synced_at",
            "order": "restock_date.desc",
            "limit": limit
        }
        if product_name:
            query_params["product_name"] = f"ilike.*{product_name}*"

        rows = await query_supabase("restock_sync", query_params)
        return ToolResult(success=True, data={"restock_history": rows, "count": len(rows), "query": product_name})


class GetInventoryHistoryTool(BaseTool):
    name = "get_inventory_history"
    description = "Ambil riwayat koreksi inventory/stok dari cloud sync"

    async def execute(self, params: Dict[str, Any]) -> ToolResult:
        product_name = params.get("product_name", "").strip()
        limit = int(params.get("limit", 10))

        query_params = {
            "select": "product_name,quantity_before,quantity_after,delta,reason,corrected_at,synced_at",
            "order": "corrected_at.desc",
            "limit": limit
        }
        if product_name:
            query_params["product_name"] = f"ilike.*{product_name}*"

        rows = await query_supabase("inventory_sync", query_params)
        return ToolResult(success=True, data={"inventory_history": rows, "count": len(rows), "query": product_name})


class GetExpiringProductsTool(BaseTool):
    name = "get_expiring_products"
    description = "Dapatkan daftar produk yang mendekati tanggal expired"

    async def execute(self, params: Dict[str, Any]) -> ToolResult:
        rows = await query_supabase("products_sync", {
            "select": "name,stock,unit,expiry_date",
            "expiry_date": "not.is.null",
            "order": "expiry_date.asc",
            "limit": 20
        })
        return ToolResult(success=True, data={"expiring_products": rows, "count": len(rows)})


class GetLowStockAlertTool(BaseTool):
    name = "get_low_stock_alert"
    description = "Daftar produk stok kritis disertai estimasi kebutuhan restock"

    async def execute(self, params: Dict[str, Any]) -> ToolResult:
        rows = await query_supabase("products_sync", {
            "select": "name,stock,unit,selling_price,category_name",
            "is_low_stock": "eq.true",
            "order": "stock.asc",
            "limit": 25
        })
        return ToolResult(success=True, data={"low_stock_alerts": rows, "count": len(rows)})
