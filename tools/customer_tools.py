import re
from typing import Dict, Any, List
from tools.registry import BaseTool, ToolResult
from tools.inventory_tools import query_supabase

class GetCustomerDebtTool(BaseTool):
    name = "get_customer_debt"
    description = "Dapatkan data piutang / hutang pelanggan dari sinkronisasi database cloud"

    async def execute(self, params: Dict[str, Any]) -> ToolResult:
        customer_name = params.get("customer_name", "").strip()
        # Strip noise words from customer query
        if customer_name:
            lower_name = customer_name.lower()
            if re.search(r"\b(semua|total|jumlah|seluruh|daftar)\b.*\b(piutang|hutang|utang|tagihan)\b", lower_name):
                customer_name = ""
            else:
                prefixes = [
                    "tampilkan detail transaksi piutang", "tampilkan detail transaksi hutang", "tampilkan detail transaksi utang",
                    "tampilkan detail piutang", "tampilkan detail hutang", "tampilkan detail utang",
                    "detail transaksi piutang", "detail transaksi hutang", "detail transaksi utang",
                    "tampilkan piutang", "tampilkan hutang", "tampilkan utang",
                    "cek detail piutang", "cek detail hutang", "cek detail utang",
                    "detail piutang", "detail hutang", "detail utang",
                    "cek piutang", "cek hutang", "cek utang",
                    "piutang", "hutang", "utang", "tagihan",
                    "pelanggan", "customer", "atas nama", "saudara"
                ]
                for prefix in sorted(prefixes, key=len, reverse=True):
                    customer_name = re.sub(rf"(?i)^{re.escape(prefix)}\s*", "", customer_name).strip()
                customer_name = re.sub(r"(?i)^(ibu|bapak|pak|bu)\s+", "", customer_name).strip()
        
        rows = []
        if customer_name:
            # Search debt by customer name using PostgREST ilike syntax with *
            rows = await query_supabase("customers_sync", {
                "select": "id,name,phone,total_debt,last_transaction_date",
                "name": f"ilike.*{customer_name}*",
                "limit": 15
            })
            # Fallback to word splitting if exact phrase search yields no rows
            if not rows and " " in customer_name:
                words = [w for w in customer_name.split() if len(w) > 1 and w.lower() not in ("ibu", "bapak", "pak", "bu")]
                if words:
                    or_clause = ",".join([f"name.ilike.*{w}*" for w in words])
                    rows = await query_supabase("customers_sync", {
                        "select": "id,name,phone,total_debt,last_transaction_date",
                        "or": f"({or_clause})",
                        "limit": 15
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
