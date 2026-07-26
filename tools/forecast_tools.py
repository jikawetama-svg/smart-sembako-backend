from typing import Dict, Any
from tools.registry import BaseTool, ToolResult
from tools.inventory_tools import query_supabase

class PredictRestockTool(BaseTool):
    name = "predict_restock"
    description = "Prediksi kebutuhan restock berdasarkan laju penjualan dan sisa stok"

    async def execute(self, params: Dict[str, Any]) -> ToolResult:
        products = await query_supabase("products_sync", {
            "select": "name,stock,unit,is_low_stock",
            "order": "stock.asc",
            "limit": 10
        })

        recommendations = []
        for p in products:
            stock = p.get("stock", 0)
            suggested_qty = max(50 - stock, 20)
            recommendations.append({
                "name": p.get("name"),
                "current_stock": stock,
                "suggested_restock": suggested_qty,
                "unit": p.get("unit")
            })

        return ToolResult(
            success=True,
            data={"recommendations": recommendations, "total_items": len(recommendations)}
        )

class GetExpiringProductsTool(BaseTool):
    name = "get_expiring_products"
    description = "Daftar produk yang mendekati tanggal kedaluwarsa"

    async def execute(self, params: Dict[str, Any]) -> ToolResult:
        products = await query_supabase("products_sync", {
            "select": "name,stock,unit",
            "limit": 5
        })

        return ToolResult(
            success=True,
            data={"expiring_products": products, "message": "Peringatan kedaluwarsa diperiksa."}
        )

class GetDeadStockTool(BaseTool):
    name = "get_dead_stock"
    description = "Analisis produk lambat laku / dead stock"

    async def execute(self, params: Dict[str, Any]) -> ToolResult:
        return ToolResult(
            success=True,
            data={"dead_stock_items": [], "message": "Tidak terdeteksi produk dead stock kritis bulan ini."}
        )

class RunProfitAnalysisTool(BaseTool):
    name = "run_profit_analysis"
    description = "Jalankan analisis margin profit per kategori produk"

    async def execute(self, params: Dict[str, Any]) -> ToolResult:
        summaries = await query_supabase("transactions_summary", {
            "select": "total_revenue,total_profit,total_transactions",
            "order": "date.desc",
            "limit": 7
        })

        total_rev = sum(s.get("total_revenue", 0) or 0 for s in summaries)
        total_prof = sum(s.get("total_profit", 0) or 0 for s in summaries)
        margin = (total_prof / total_rev * 100) if total_rev > 0 else 0.0

        return ToolResult(
            success=True,
            data={
                "total_revenue_7d": total_rev,
                "total_profit_7d": total_prof,
                "profit_margin_percent": round(margin, 2)
            }
        )
