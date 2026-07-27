from typing import Dict, Any, List
from tools.registry import BaseTool, ToolResult
from tools.inventory_tools import query_supabase

class GetCustomerDebtTool(BaseTool):
    name = "get_customer_debt"
    description = "Dapatkan data piutang / hutang pelanggan dari sinkronisasi database cloud"

    async def execute(self, params: Dict[str, Any]) -> ToolResult:
        customer_name = params.get("customer_name", "").strip()
        
        if customer_name:
            # Search debt by customer name
            rows = await query_supabase("customers_sync", {
                "select": "id,name,phone,total_debt,last_transaction_date",
                "name": f"ilike.%{customer_name}%",
                "limit": 10
            })
        else:
            # Query top customers with active debt
            rows = await query_supabase("customers_sync", {
                "select": "id,name,phone,total_debt,last_transaction_date",
                "total_debt": "gt.0",
                "order": "total_debt.desc",
                "limit": 15
            })

        if not rows:
            if customer_name:
                return ToolResult(success=True, data={
                    "customers": [],
                    "message": f"Tidak ditemukan catatan piutang/hutang untuk pelanggan '{customer_name}'."
                })
            return ToolResult(success=True, data={
                "customers": [],
                "message": "Tidak ada pelanggan yang memiliki piutang aktif saat ini (atau data piutang belum tersinkronisasi dari Desktop POS)."
            })

        customers = []
        total_all_debt = 0
        for r in rows:
            debt = float(r.get("total_debt", 0) or 0)
            total_all_debt += debt
            customers.append({
                "name": r.get("name"),
                "phone": r.get("phone") or "-",
                "total_debt": debt,
                "last_tx": r.get("last_transaction_date")
            })

        return ToolResult(success=True, data={
            "customers": customers,
            "total_debtors": len(customers),
            "total_all_debt": total_all_debt
        })
