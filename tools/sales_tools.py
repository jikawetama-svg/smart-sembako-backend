from typing import Dict, Any
from tools.registry import BaseTool, ToolResult
from tools.inventory_tools import query_supabase

class GetDailyRevenueTool(BaseTool):
    name = "get_daily_revenue"
    description = "Dapatkan data pendapatan dan profit penjualan hari ini atau tanggal tertentu"

    async def execute(self, params: Dict[str, Any]) -> ToolResult:
        date_str = params.get("date", "").strip()
        
        queryParams = {"select": "date,total_revenue,total_profit,total_transactions", "order": "date.desc", "limit": 1}
        if date_str:
            queryParams = {"select": "date,total_revenue,total_profit,total_transactions", "date": f"eq.{date_str}"}

        summaries = await query_supabase("transactions_summary", queryParams)

        if summaries:
            summary = summaries[0]
            return ToolResult(success=True, data={
                "date": summary.get("date"),
                "total_revenue": summary.get("total_revenue", 0),
                "total_profit": summary.get("total_profit", 0),
                "total_transactions": summary.get("total_transactions", 0)
            })

        return ToolResult(success=True, data={
            "date": date_str or "Hari ini",
            "total_revenue": 0,
            "total_profit": 0,
            "total_transactions": 0,
            "message": f"Belum ada data transaksi yang tersinkronisasi untuk tanggal {date_str or 'ini'}."
        })

class GetTransactionSummaryTool(BaseTool):
    name = "get_transaction_summary"
    description = "Ringkasan data transaksi toko dalam rentang waktu beberapa hari atau bulan"

    async def execute(self, params: Dict[str, Any]) -> ToolResult:
        days = params.get("days", 7)
        start_date = params.get("start_date")
        end_date = params.get("end_date")
        period_label = params.get("period_label", f"{days} hari terakhir")

        queryParams = {
            "select": "date,total_revenue,total_profit,total_transactions",
            "order": "date.desc"
        }

        if start_date and end_date:
            queryParams["and"] = f"(date.gte.{start_date},date.lte.{end_date})"
        else:
            queryParams["limit"] = days

        summaries = await query_supabase("transactions_summary", queryParams)

        total_revenue = sum(float(s.get("total_revenue", 0) or 0) for s in summaries)
        total_profit = sum(float(s.get("total_profit", 0) or 0) for s in summaries)
        total_transactions = sum(int(s.get("total_transactions", 0) or 0) for s in summaries)

        return ToolResult(success=True, data={
            "period_label": period_label,
            "period_days": len(summaries),
            "total_revenue": total_revenue,
            "total_profit": total_profit,
            "total_transactions": total_transactions,
            "history": summaries
        })

class GetTopProductsTool(BaseTool):
    name = "get_top_products"
    description = "Produk terlaris berdasarkan ringkasan sinkronisasi cloud"

    async def execute(self, params: Dict[str, Any]) -> ToolResult:
        summaries = await query_supabase("transactions_summary", {
            "select": "top_products_json",
            "order": "date.desc",
            "limit": 1
        })

        top_products = []
        if summaries and summaries[0].get("top_products_json"):
            top_products = summaries[0].get("top_products_json")

        return ToolResult(success=True, data={"top_products": top_products})
