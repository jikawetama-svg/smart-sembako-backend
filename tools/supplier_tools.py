from typing import Dict, Any
from tools.registry import BaseTool, ToolResult
from tools.inventory_tools import query_supabase

class GetSupplierCatalogTool(BaseTool):
    name = "get_suppliers"
    description = "Daftar supplier utama dan kontak pemesanan grosir sembako"

    async def execute(self, params: Dict[str, Any]) -> ToolResult:
        suppliers = [
            {"id": "SUP-01", "name": "PT Sembako Jaya Utama", "category": "Minyak & Gula", "contact": "0812****8899"},
            {"id": "SUP-02", "name": "CV Beras Nusantara", "category": "Beras & Palawija", "contact": "0813****1122"},
            {"id": "SUP-03", "name": "Distributor Mi & Bumbu", "category": "Mie & Bumbu", "contact": "0815****3344"}
        ]
        return ToolResult(success=True, data={"suppliers": suppliers, "total": len(suppliers)})

class MultiBranchStockTool(BaseTool):
    name = "get_branch_stock"
    description = "Cek ketersediaan stok produk di seluruh cabang toko"

    async def execute(self, params: Dict[str, Any]) -> ToolResult:
        product_name = params.get("product_name", "Minyak Goreng")
        branches = [
            {"branch": "Cabang Utama (Pusat)", "stock": 45, "status": "Tersedia"},
            {"branch": "Cabang Pasar Baru", "stock": 12, "status": "Tersedia"},
            {"branch": "Cabang Gudang Barat", "stock": 150, "status": "Melimpah"}
        ]
        return ToolResult(success=True, data={"product": product_name, "branches": branches})
