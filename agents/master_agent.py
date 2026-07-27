import re
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional
from tools.registry import ToolRegistry, ToolResult
from tools.inventory_tools import GetStockTool, FindProductTool, GetLowStockTool
from tools.sales_tools import GetDailyRevenueTool, GetTransactionSummaryTool, GetTopProductsTool
from model_manager.manager import ModelManager
from telegram.rbac import RBACManager

INDONESIAN_MONTHS = {
    "januari": 1, "jan": 1,
    "februari": 2, "feb": 2, "pebruari": 2,
    "maret": 3, "mar": 3,
    "april": 4, "apr": 4,
    "mei": 5,
    "juni": 6, "jun": 6,
    "juli": 7, "jul": 7,
    "agustus": 8, "ags": 8, "agu": 8,
    "september": 9, "sep": 9,
    "oktober": 10, "okt": 10,
    "november": 11, "nov": 11,
    "desember": 12, "des": 12
}

def parse_date_or_period(text: str) -> Dict[str, Any]:
    lower = text.lower()
    today = datetime.now()

    if "kemarin" in lower:
        dt = today - timedelta(days=1)
        return {"type": "single_date", "date": dt.strftime("%Y-%m-%d"), "label": f"Kemarin ({dt.strftime('%d-%m-%Y')})"}
    
    if "hari ini" in lower:
        return {"type": "single_date", "date": today.strftime("%Y-%m-%d"), "label": f"Hari ini ({today.strftime('%d-%m-%Y')})"}

    if "bulan ini" in lower:
        start_date = today.replace(day=1).strftime("%Y-%m-%d")
        next_month = (today.replace(day=28) + timedelta(days=4)).replace(day=1)
        end_date = (next_month - timedelta(days=1)).strftime("%Y-%m-%d")
        month_name = list(INDONESIAN_MONTHS.keys())[list(INDONESIAN_MONTHS.values()).index(today.month)].capitalize()
        return {"type": "range", "start_date": start_date, "end_date": end_date, "label": f"Bulan Ini ({month_name} {today.year})"}

    # Match ISO format: YYYY-MM-DD
    iso_match = re.search(r'(\d{4})[-/.](\d{1,2})[-/.](\d{1,2})', lower)
    if iso_match:
        y, m, d = int(iso_match.group(1)), int(iso_match.group(2)), int(iso_match.group(3))
        dt = datetime(y, m, d)
        return {"type": "single_date", "date": dt.strftime("%Y-%m-%d"), "label": dt.strftime("%d-%m-%Y")}

    # Match DD-MM-YYYY or DD/MM/YYYY
    dmy_match = re.search(r'(\d{1,2})[-/.](\d{1,2})[-/.](?:20)?(\d{2})', lower)
    if dmy_match:
        d, m, y = int(dmy_match.group(1)), int(dmy_match.group(2)), int(dmy_match.group(3))
        if y < 100: y += 2000
        dt = datetime(y, m, d)
        return {"type": "single_date", "date": dt.strftime("%Y-%m-%d"), "label": dt.strftime("%d-%m-%Y")}

    # Match named month: e.g. "14 juli 2026", "14 juli"
    named_match = re.search(r'(\d{1,2})\s+([a-zA-Z]+)(?:\s+(\d{4}))?', lower)
    if named_match:
        day = int(named_match.group(1))
        month_str = named_match.group(2)
        year = int(named_match.group(3)) if named_match.group(3) else today.year
        if month_str in INDONESIAN_MONTHS:
            month = INDONESIAN_MONTHS[month_str]
            try:
                dt = datetime(year, month, day)
                return {"type": "single_date", "date": dt.strftime("%Y-%m-%d"), "label": f"{day} {month_str.capitalize()} {year}"}
            except ValueError:
                pass

    # Check for month query: e.g. "bulan juli", "penjualan juli 2026"
    for m_str, m_num in INDONESIAN_MONTHS.items():
        if m_str in lower and len(m_str) > 3:
            yr_match = re.search(r'\b(20\d{2})\b', lower)
            yr = int(yr_match.group(1)) if yr_match else today.year
            first_day = datetime(yr, m_num, 1)
            next_m = (first_day.replace(day=28) + timedelta(days=4)).replace(day=1)
            last_day = next_m - timedelta(days=1)
            return {
                "type": "range",
                "start_date": first_day.strftime("%Y-%m-%d"),
                "end_date": last_day.strftime("%Y-%m-%d"),
                "label": f"Bulan {m_str.capitalize()} {yr}"
            }

    return {"type": "default", "label": "Hari ini"}


def extract_product_query(text: str) -> str:
    cleaned = text
    prefixes = [
        "cek stok", "cek sisa", "cek barang", "stok barang", "stok produk",
        "sisa stok", "ada berapa", "cari produk", "cari barang", "cek produk",
        "stok", "sisa", "produk", "barang", "cari", "cek"
    ]
    for prefix in prefixes:
        pattern = re.compile(rf'^{re.escape(prefix)}\s*', re.IGNORECASE)
        if pattern.search(cleaned):
            cleaned = pattern.sub('', cleaned).strip()
            break
    return cleaned.strip()


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
        if any(w in lower for w in ["restock", "kritis", "stok rendah", "belanja lagi", "habis"]):
            return "restock"
        elif any(w in lower for w in ["omset", "pendapatan", "jual", "penjualan", "laporan", "profit", "untung", "transaksi"]):
            return "laporan_penjualan"
        elif any(w in lower for w in ["stok", "ada berapa", "sisa", "barang", "produk", "harga", "cek"]):
            return "cek_stok"
        return "sapaan_umum"

    async def handle_message(self, user_id: int, message_text: str) -> str:
        user_role = RBACManager.get_user_role(user_id)
        intent = self.classify_intent(message_text)

        if intent == "cek_stok":
            product_query = extract_product_query(message_text)
            
            tool = self.registry.get_tool("get_stock") if product_query else self.registry.get_tool("find_product")
            if tool and RBACManager.can_access_tool(user_role, tool.name):
                param_key = "product_name" if tool.name == "get_stock" else "keyword"
                result = await tool.execute({param_key: product_query})
                
                products = result.data.get("products", [])
                if products:
                    query_label = product_query if product_query else "Katalog Produk"
                    lines = [f"📦 *Hasil Pencarian Stok ({query_label}):*"]
                    for p in products:
                        status = "🔴 Stok Kritis" if p.get("is_low_stock") or (p.get("stock", 0) <= 10) else "🟢 Tersedia"
                        price_fmt = f"Rp {float(p.get('selling_price', 0)):,.0f}"
                        lines.append(f"• *{p.get('name')}*: {p.get('stock')} {p.get('unit', 'pcs')} ({status}) - {price_fmt}")
                    return "\n".join(lines)
                else:
                    return f"ℹ️ Produk dengan kata kunci '{product_query or message_text}' tidak ditemukan di catalog sync."

        elif intent == "laporan_penjualan":
            period_info = parse_date_or_period(message_text)
            
            if period_info["type"] == "range":
                tool = self.registry.get_tool("get_transaction_summary")
                if tool and RBACManager.can_access_tool(user_role, tool.name):
                    result = await tool.execute({
                        "start_date": period_info["start_date"],
                        "end_date": period_info["end_date"],
                        "period_label": period_info["label"]
                    })
                    if result.success:
                        data = result.data
                        return (
                            f"📊 *Laporan Penjualan Toko ({period_info['label']}):*\n"
                            f"• Total Omset: Rp {data.get('total_revenue', 0):,.0f}\n"
                            f"• Estimasi Profit: Rp {data.get('total_profit', 0):,.0f}\n"
                            f"• Jumlah Transaksi: {data.get('total_transactions', 0)} nota\n"
                            f"• Total Hari Ada Data: {data.get('period_days', 0)} hari"
                        )
            else:
                # Single date or default
                target_date = period_info.get("date", "")
                tool = self.registry.get_tool("get_daily_revenue")
                if tool and RBACManager.can_access_tool(user_role, tool.name):
                    result = await tool.execute({"date": target_date})
                    if result.success and "total_revenue" in result.data:
                        data = result.data
                        date_display = data.get("date") or period_info.get("label", "Hari ini")
                        return (
                            f"📊 *Laporan Penjualan Toko ({date_display}):*\n"
                            f"• Total Omset: Rp {float(data.get('total_revenue', 0)):,.0f}\n"
                            f"• Estimasi Profit: Rp {float(data.get('total_profit', 0)):,.0f}\n"
                            f"• Jumlah Transaksi: {data.get('total_transactions', 0)} nota"
                        )
            return "ℹ️ Belum ada data laporan penjualan yang tersinkronisasi dari POS."

        elif intent == "restock":
            tool = self.registry.get_tool("get_low_stock")
            if tool and RBACManager.can_access_tool(user_role, tool.name):
                result = await tool.execute({})
                products = result.data.get("low_stock_products", [])
                if products:
                    lines = ["⚠️ *Daftar Produk Perlu Restock:*"]
                    for p in products:
                        lines.append(f"• *{p.get('name')}*: sisa {p.get('stock')} {p.get('unit', 'pcs')}")
                    return "\n".join(lines)
                return "✅ Semua stok produk dalam batas aman!"

        # Fallback ke LLM Model Manager jika intent sapaan umum atau pertanyaan bebas
        messages = [
            {
                "role": "system", 
                "content": (
                    "Anda adalah Smart Sembako Assistant, asisten AI pintar khusus toko kelontong dan sembako. "
                    "Jawablah pertanyaan pemilik toko secara ramah, profesional, ringkas, dan sangat membantu."
                )
            },
            {"role": "user", "content": message_text}
        ]
        response_text, _ = await self.model_manager.chat(messages, model_tier="balanced")
        return response_text
