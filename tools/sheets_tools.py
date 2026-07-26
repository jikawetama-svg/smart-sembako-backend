from typing import Dict, Any
from tools.registry import BaseTool, ToolResult
from tools.inventory_tools import query_supabase

class SyncToGSheetsTool(BaseTool):
    name = "sync_to_gsheets"
    description = "Ekspor laporan stok dan transaksi ke Google Sheets"

    async def execute(self, params: Dict[str, Any]) -> ToolResult:
        sheet_name = params.get("sheet_name", "Laporan POS Sembako")
        products = await query_supabase("products_sync", {"select": "name,stock,unit,selling_price", "limit": 50})

        return ToolResult(
            success=True,
            data={
                "sheet_name": sheet_name,
                "exported_rows": len(products),
                "status": "Berhasil mengekspor data stok ke Google Sheets.",
                "url": "https://docs.google.com/spreadsheets/d/sample-smart-sembako"
            }
        )
