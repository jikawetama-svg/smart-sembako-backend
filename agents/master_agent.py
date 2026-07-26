from typing import Dict, Any, List, Optional
from tools.registry import ToolRegistry, ToolResult
from tools.inventory_tools import GetStockTool, FindProductTool, GetLowStockTool
from tools.sales_tools import GetDailyRevenueTool, GetTransactionSummaryTool, GetTopProductsTool
from model_manager.manager import ModelManager
from telegram.rbac import RBACManager

class MasterAgent:
    def __init__(self, registry: Optional[ToolRegistry] = None, model_manager: Optional[ModelManager] = None):
        self.registry = registry or ToolRegistry()
        self._register_default_tools()
        self.model_manager = model_manager or ModelManager()

    def _register_default_tools(self):
        self.registry.register(GetStockTool())
        self.registry.register(FindProductTool())
        self.registry.register(GetLowStockTool())
        self.registry.register(GetDailyRevenueTool())
        self.registry.register(GetTransactionSummaryTool())
        self.registry.register(GetTopProductsTool())

    def classify_intent(self, text: str) -> str:
        lower = text.lower()
        if any(w in lower for w in ["restock", "kritis", "stok rendah", "belanja lagi"]):
            return "restock"
        elif any(w in lower for w in ["omset", "pendapatan", "jual", "penjualan", "laporan", "profit", "untung"]):
            return "laporan_penjualan"
        elif any(w in lower for w in ["stok", "ada berapa", "sisa", "barang", "produk", "habis"]):
            return "cek_stok"
        return "sapaan_umum"

    async def handle_message(self, user_id: int, message_text: str) -> str:
        user_role = RBACManager.get_user_role(user_id)
        intent = self.classify_intent(message_text)

        if intent == "cek_stok":
            # Ekstrak nama produk dari pesan jika ada
            words = message_text.split()
            product_query = words[-1] if len(words) > 1 else ""
            
            tool = self.registry.get_tool("get_stock") if product_query else self.registry.get_tool("find_product")
            if tool and RBACManager.can_access_tool(user_role, tool.name):
                param_key = "product_name" if tool.name == "get_stock" else "keyword"
                result = await tool.execute({param_key: product_query})
                
                products = result.data.get("products", [])
                if products:
                    lines = [f"📦 *Hasil Pencarian Stok ({product_query or 'Catalog'}):*"]
                    for p in products:
                        status = "🔴 Stok Kritis" if p.get("is_low_stock") or (p.get("stock", 0) <= 10) else "🟢 Tersedia"
                        lines.append(f"• *{p.get('name')}*: {p.get('stock')} {p.get('unit')} ({status}) - Rp {p.get('selling_price'):,}")
                    return "\n".join(lines)
                else:
                    return f"ℹ️ Produk dengan kata kunci '{product_query}' tidak ditemukan di catalog sync."

        elif intent == "laporan_penjualan":
            tool = self.registry.get_tool("get_daily_revenue")
            if tool and RBACManager.can_access_tool(user_role, tool.name):
                result = await tool.execute({})
                if result.success and "total_revenue" in result.data:
                    data = result.data
                    return (
                        f"📊 *Laporan Penjualan Toko ({data.get('date', 'Hari ini')}):*\n"
                        f"• Total Omset: Rp {data.get('total_revenue', 0):,}\n"
                        f"• Estimasi Profit: Rp {data.get('total_profit', 0):,}\n"
                        f"• Jumlah Transaksi: {data.get('total_transactions', 0)} nota"
                    )
                return "ℹ️ Belum ada laporan data penjualan yang tersinkronisasi dari POS."

        elif intent == "restock":
            tool = self.registry.get_tool("get_low_stock")
            if tool and RBACManager.can_access_tool(user_role, tool.name):
                result = await tool.execute({})
                products = result.data.get("low_stock_products", [])
                if products:
                    lines = ["⚠️ *Daftar Produk Perlu Restock:*"]
                    for p in products:
                        lines.append(f"• *{p.get('name')}*: sisa {p.get('stock')} {p.get('unit')}")
                    return "\n".join(lines)
                return "✅ Semua stok produk dalam batas aman!"

        # Fallback ke LLM Model Manager jika intent sapaan umum atau query bebas
        messages = [
            {"role": "system", "content": "Anda adalah Smart Sembako Assistant, asisten AI toko kelontong/sembako yang ramah, cepat, dan akurat."},
            {"role": "user", "content": message_text}
        ]
        response_text, _ = await self.model_manager.chat(messages, model_tier="balanced")
        return response_text
