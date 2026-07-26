from typing import Dict, Any
from tools.registry import BaseTool, ToolResult
from tools.inventory_tools import query_supabase

class GetDailyRevenueTool(BaseTool):
    name = "get_daily_revenue"
    description = "Dapatkan data pendapatan dan profit penjualan hari ini atau tanggal tertentu"

    async def execute(self, params: Dict[str, Any]) -> ToolResult:
        date_str = params.get("date", "")
        
        queryParams = {"select": "date,total_revenue,total_profit,total_transactions", "order": "date.desc", "limit": 1}
        if date_str:
            queryParams["date"] = f"eq.{date_str}"

        summaries = await query_supabase("transactions_summary", queryParams)

        if summaries:
            summary = summaries[0]
            return ToolResult(success=True, data={
                "date": summary.get("date"),
                "total_revenue": summary.get("total_revenue", 0),
                "total_profit": summary.get("total_profit", 0),
                "total_transactions": summary.get("total_transactions", 0)
            })

        return ToolResult(success=True, data={"message": "Belum ada data transaksi yang tersinkronisasi untuk tanggal ini."})

class GetTransactionSummaryTool(BaseTool):
    name = "get_transaction_summary"
    description = "Ringkasan data transaksi toko dalam rentang waktu beberapa hari terakhir"

    async def execute(self, params: Dict[str, Any]) -> ToolResult:
        days = params.get("days", 7)
        summaries = await query_supabase("transactions_summary", {
            "select": "date,total_revenue,total_profit,total_transactions",
            "order": "date.desc",
            "limit": days
        })

        total_revenue = sum(s.get("total_revenue", 0) or 0 for s in summaries)
        total_profit = sum(s.get("total_profit", 0) or 0 for s in summaries)

        return ToolResult(success=True, data={
            "period_days": len(summaries),
            "total_revenue": total_revenue,
            "total_profit": total_profit,
            "history": summaries
        })

class GetTopProductsTool(BaseTool):
    name = "get_top_products"
    description = "Produk terlaris berdasarkan ringkasan sinkronisasi cloud"

    async def execute(self, params: Dict[str, Any]) -> ToolResult:
        summaries = await query_supabase("transactions_summary", {
            "select": "top_products",
            "order": "date.desc",
            "limit": 1
        })

        top_products = summaries[0].get("top_products") if summaries and summaries[0].get("top_products") else []

        return ToolResult(success=True, data={"top_products": top_products})
