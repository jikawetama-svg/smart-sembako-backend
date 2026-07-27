import re
import asyncio
import traceback
from datetime import datetime, timezone, timedelta
from typing import Dict, Any, List, Optional
from tools.registry import ToolRegistry, ToolResult
from tools.inventory_tools import GetStockTool, FindProductTool, GetLowStockTool
from tools.sales_tools import GetDailyRevenueTool, GetTransactionSummaryTool, GetTopProductsTool
from tools.restock_tools import (
    GetRestockHistoryTool, GetInventoryHistoryTool,
    GetExpiringProductsTool, GetLowStockAlertTool
)
from model_manager.manager import ModelManager
from telegram.rbac import RBACManager
import memory.conversation_store as mem_store

# ─────────────────────────────────────────────
# Kamus nama bulan Bahasa Indonesia
# ─────────────────────────────────────────────
INDONESIAN_MONTHS = {
    "januari": 1, "jan": 1, "februari": 2, "feb": 2, "pebruari": 2,
    "maret": 3, "mar": 3, "april": 4, "apr": 4, "mei": 5,
    "juni": 6, "jun": 6, "juli": 7, "jul": 7, "agustus": 8,
    "ags": 8, "agu": 8, "september": 9, "sep": 9, "oktober": 10,
    "okt": 10, "november": 11, "nov": 11, "desember": 12, "des": 12
}

# ─────────────────────────────────────────────
# Fitur yang memerlukan Desktop Bot aktif
# ─────────────────────────────────────────────
DESKTOP_ONLY_FEATURES = {
    "ocr": "📷 *Fitur OCR Struk Foto* membutuhkan aplikasi *Smart Sembako Assistant* (Desktop) aktif di PC toko.\n\nSilakan buka aplikasi dan aktifkan Telegram Bot dari sana.",
    "input_restock": "📦 *Input Restock/Pembelian Baru* dilakukan melalui aplikasi Desktop (scan/input langsung ke POS).\n\nKirim pesan ke bot Desktop Anda untuk mencatat pembelian baru.",
    "input_inventory": "🔧 *Koreksi Stok* dilakukan melalui aplikasi Desktop.\n\nBuka menu Inventory di aplikasi Smart Sembako Assistant.",
    "nota": "📄 *Detail Nota Transaksi* hanya tersedia via Desktop Bot (akses langsung database POS).",
    "piutang_bayar": "💳 *Pembayaran Piutang* dilakukan melalui aplikasi Desktop untuk menjaga integritas data.",
}

# ─────────────────────────────────────────────
# Helper: ekstrak nama produk dari teks perintah
# ─────────────────────────────────────────────
PREFIXES_STOK = [
    "cek stok", "cek sisa", "stok barang", "sisa stok",
    "ada berapa", "cari produk", "cari barang", "cek produk",
    "stok produk", "stok", "sisa", "cek", "cari",
]

def extract_product_query(text: str) -> str:
    cleaned = text.strip()
    for prefix in sorted(PREFIXES_STOK, key=len, reverse=True):
        pattern = re.compile(rf'(?i)^{re.escape(prefix)}\s*')
        if pattern.search(cleaned):
            cleaned = pattern.sub('', cleaned).strip()
            break
    return cleaned


# ─────────────────────────────────────────────
# Helper: parse tanggal/periode dari teks
# ─────────────────────────────────────────────
def parse_date_or_period(text: str) -> Dict[str, Any]:
    lower = text.lower()
    today = datetime.now()

    if "kemarin" in lower:
        dt = today - timedelta(days=1)
        return {"type": "single_date", "date": dt.strftime("%Y-%m-%d"), "label": f"Kemarin ({dt.strftime('%d-%m-%Y')})"}
    if "hari ini" in lower:
        return {"type": "single_date", "date": today.strftime("%Y-%m-%d"), "label": f"Hari ini ({today.strftime('%d-%m-%Y')})"}
    if "bulan ini" in lower:
        start = today.replace(day=1).strftime("%Y-%m-%d")
        next_m = (today.replace(day=28) + timedelta(days=4)).replace(day=1)
        end = (next_m - timedelta(days=1)).strftime("%Y-%m-%d")
        return {"type": "range", "start_date": start, "end_date": end,
                "label": f"Bulan Ini ({today.strftime('%B %Y')})"}

    # ISO: YYYY-MM-DD
    iso = re.search(r'(\d{4})[-/.](\d{1,2})[-/.](\d{1,2})', lower)
    if iso:
        dt = datetime(int(iso.group(1)), int(iso.group(2)), int(iso.group(3)))
        return {"type": "single_date", "date": dt.strftime("%Y-%m-%d"), "label": dt.strftime("%d-%m-%Y")}

    # DD/MM/YYYY atau DD-MM-YYYY
    dmy = re.search(r'(\d{1,2})[-/.](\d{1,2})[-/.](?:20)?(\d{2})', lower)
    if dmy:
        d, m, y = int(dmy.group(1)), int(dmy.group(2)), int(dmy.group(3))
        if y < 100: y += 2000
        dt = datetime(y, m, d)
        return {"type": "single_date", "date": dt.strftime("%Y-%m-%d"), "label": dt.strftime("%d-%m-%Y")}

    # "14 juli 2026" atau "14 juli"
    named = re.search(r'(\d{1,2})\s+([a-zA-Z]+)(?:\s+(\d{4}))?', lower)
    if named:
        day, month_str = int(named.group(1)), named.group(2)
        year = int(named.group(3)) if named.group(3) else today.year
        if month_str in INDONESIAN_MONTHS:
            try:
                dt = datetime(year, INDONESIAN_MONTHS[month_str], day)
                return {"type": "single_date", "date": dt.strftime("%Y-%m-%d"),
                        "label": f"{day} {month_str.capitalize()} {year}"}
            except ValueError:
                pass

    # "bulan juli 2026" atau "penjualan agustus"
    for m_str, m_num in INDONESIAN_MONTHS.items():
        if m_str in lower and len(m_str) > 2:
            yr_match = re.search(r'\b(20\d{2})\b', lower)
            yr = int(yr_match.group(1)) if yr_match else today.year
            first = datetime(yr, m_num, 1)
            last = ((first.replace(day=28) + timedelta(days=4)).replace(day=1) - timedelta(days=1))
            return {"type": "range", "start_date": first.strftime("%Y-%m-%d"),
                    "end_date": last.strftime("%Y-%m-%d"),
                    "label": f"Bulan {m_str.capitalize()} {yr}"}

    return {"type": "default", "label": "Hari ini"}


# ─────────────────────────────────────────────
# Helper: format harga Rupiah
# ─────────────────────────────────────────────
def fmt_rp(val) -> str:
    try:
        return f"Rp {float(val or 0):,.0f}"
    except Exception:
        return "Rp 0"


# ─────────────────────────────────────────────
# MASTER AGENT
# ─────────────────────────────────────────────
class MasterAgent:
    def __init__(self, registry: Optional[ToolRegistry] = None,
                 model_manager: Optional[ModelManager] = None):
        self.registry = registry or ToolRegistry()
        self._register_default_tools()
        self.model_manager = model_manager or ModelManager()

    def _register_default_tools(self):
        # Inventory
        self.registry.register(GetStockTool())
        self.registry.register(FindProductTool())
        self.registry.register(GetLowStockTool())
        self.registry.register(GetLowStockAlertTool())
        self.registry.register(GetExpiringProductsTool())
        # Sales
        self.registry.register(GetDailyRevenueTool())
        self.registry.register(GetTransactionSummaryTool())
        self.registry.register(GetTopProductsTool())
        # Restock & Inventory history
        self.registry.register(GetRestockHistoryTool())
        self.registry.register(GetInventoryHistoryTool())

    def classify_intent(self, text: str) -> str:
        lower = text.lower()
        # Command spesifik
        if lower.strip() in ("/start", "/menu", "menu", "mulai"):
            return "start"
        if lower.strip() in ("/help", "help", "bantuan"):
            return "help"
        if lower.strip() in ("/reset", "reset memory", "hapus ingatan", "clear chat"):
            return "reset_memory"
        # Desktop-only deteksi dini
        if any(w in lower for w in ["ocr", "foto struk", "scan struk", "gambar struk"]):
            return "desktop_ocr"
        if any(w in lower for w in ["bayar piutang", "lunas piutang"]):
            return "desktop_piutang_bayar"
        # Restock
        if any(w in lower for w in ["restock", "riwayat beli", "riwayat restock", "history restock", "beli barang kapan"]):
            return "restock_history"
        # Inventory correction
        if any(w in lower for w in ["koreksi stok", "riwayat inventory", "history inventory", "inventory correction"]):
            return "inventory_history"
        # Expired
        if any(w in lower for w in ["expired", "kadaluarsa", "exp", "kadaluwarsa"]):
            return "cek_expired"
        # Laporan & penjualan
        if any(w in lower for w in ["omset", "pendapatan", "jual", "penjualan", "laporan", "profit", "untung", "transaksi", "pemasukan"]):
            return "laporan_penjualan"
        # Stok
        if any(w in lower for w in ["stok", "ada berapa", "sisa", "barang", "produk", "harga", "cek"]):
            return "cek_stok"
        # Rekomendasi restock
        if any(w in lower for w in ["kritis", "stok rendah", "perlu beli", "rekomendasi"]):
            return "restock_rekomendasi"
        # Piutang
        if any(w in lower for w in ["piutang", "hutang pelanggan", "belum bayar"]):
            return "piutang"
        return "sapaan_umum"

    # ─────────────────────────────────────────
    # Handler utama
    # ─────────────────────────────────────────
    async def handle_message(self, user_id: int, message_text: str) -> str:
        user_role = RBACManager.get_user_role(user_id)
        intent = self.classify_intent(message_text)

        # Ambil history memory untuk semua intent (dipakai oleh LLM fallback)
        history = await mem_store.get_history(user_id)

        # Simpan pesan user ke memory
        await mem_store.save_message(user_id, "user", message_text)

        response = await self._dispatch(intent, message_text, user_id, user_role, history)

        # Simpan respons bot ke memory
        await mem_store.save_message(user_id, "assistant", response)
        return response

    async def _dispatch(self, intent: str, text: str, user_id: int, role: str,
                        history: List[Dict[str, str]]) -> str:
        # ── /start ──────────────────────────────
        if intent == "start":
            await mem_store.clear_history(user_id)
            return (
                "👋 Halo! Selamat datang di *Smart Sembako Cloud Bot*!\n\n"
                "Saya bisa membantu:\n"
                "• 📦 *Cek stok* — `cek stok [nama produk]`\n"
                "• 📊 *Laporan penjualan* — `laporan hari ini` / `penjualan bulan juli`\n"
                "• ⚠️ *Stok kritis* — `stok kritis` atau `rekomendasi restock`\n"
                "• 📋 *Riwayat restock* — `riwayat restock [produk]`\n"
                "• 🕐 *Produk expired* — `cek expired`\n"
                "• 🤖 *Tanya apa saja* tentang toko!\n\n"
                "_Memory percakapan aktif — saya mengingat konteks chat Anda!_ 🧠"
            )

        # ── /help ────────────────────────────────
        if intent == "help":
            return (
                "📖 *Panduan Smart Sembako Cloud Bot*\n\n"
                "*📦 Stok & Inventaris:*\n"
                "• `cek stok kapal api` — cari produk spesifik\n"
                "• `stok kritis` — daftar produk hampir habis\n"
                "• `cek expired` — produk mendekati kadaluarsa\n\n"
                "*📊 Laporan & Penjualan:*\n"
                "• `laporan hari ini`\n"
                "• `penjualan 14 juli 2026`\n"
                "• `omset bulan ini` / `omset bulan juli`\n\n"
                "*📋 Riwayat:*\n"
                "• `riwayat restock [produk]`\n"
                "• `riwayat inventory [produk]`\n\n"
                "*💬 Lainnya:*\n"
                "• `reset` — hapus ingatan percakapan\n"
                "• Tanya bebas dalam Bahasa Indonesia 🇮🇩\n\n"
                "⚠️ *Fitur OCR & input transaksi* memerlukan Desktop Bot aktif."
            )

        # ── Reset memory ─────────────────────────
        if intent == "reset_memory":
            await mem_store.clear_history(user_id)
            return "🧠 Ingatan percakapan telah dihapus. Mulai sesi baru!"

        # ── Desktop-only features ─────────────────
        if intent == "desktop_ocr":
            return DESKTOP_ONLY_FEATURES["ocr"]
        if intent == "desktop_piutang_bayar":
            return DESKTOP_ONLY_FEATURES["piutang_bayar"]

        # ── Cek stok produk ──────────────────────
        if intent == "cek_stok":
            product_query = extract_product_query(text)
            tool_name = "get_stock" if product_query else "get_low_stock"
            tool = self.registry.get_tool(tool_name)
            if tool and RBACManager.can_access_tool(role, tool.name):
                param_key = "product_name"
                result = await tool.execute({param_key: product_query})
                products = result.data.get("products", result.data.get("low_stock_products", []))
                if products:
                    label = product_query or "Semua Produk"
                    lines = [f"📦 *Hasil Stok ({label}):*"]
                    for p in products:
                        stock_val = float(p.get("stock", 0) or 0)
                        status = "🔴 Kritis" if p.get("is_low_stock") or stock_val <= 10 else "🟢 Aman"
                        lines.append(
                            f"• *{p.get('name')}*: {stock_val:g} {p.get('unit','pcs')} "
                            f"({status}) — {fmt_rp(p.get('selling_price', 0))}"
                        )
                    return "\n".join(lines)
                return f"ℹ️ Produk '{product_query or 'stok kritis'}' tidak ditemukan di catalog."

        # ── Restock kritis / rekomendasi ─────────
        if intent == "restock_rekomendasi":
            tool = self.registry.get_tool("get_low_stock_alert")
            if tool:
                result = await tool.execute({})
                products = result.data.get("low_stock_alerts", [])
                if products:
                    lines = ["⚠️ *Rekomendasi Restock — Produk Kritis:*"]
                    for p in products:
                        lines.append(f"• *{p.get('name')}*: sisa {p.get('stock')} {p.get('unit','pcs')}")
                    lines.append("\n_Segera lakukan pembelian untuk menghindari kehabisan stok._")
                    return "\n".join(lines)
                return "✅ Semua stok produk masih dalam batas aman!"

        # ── Cek expired ──────────────────────────
        if intent == "cek_expired":
            tool = self.registry.get_tool("get_expiring_products")
            if tool and RBACManager.can_access_tool(role, tool.name):
                result = await tool.execute({})
                products = result.data.get("expiring_products", [])
                if products:
                    lines = ["⏳ *Produk Mendekati Expired:*"]
                    for p in products:
                        exp = p.get("expiry_date", "—")
                        lines.append(f"• *{p.get('name')}*: {p.get('stock')} {p.get('unit','pcs')} | Exp: {exp}")
                    return "\n".join(lines)
                return "✅ Tidak ada produk yang mendekati tanggal expired."

        # ── Riwayat restock ──────────────────────
        if intent == "restock_history":
            product_query = extract_product_query(
                re.sub(r'riwayat\s+restock|history\s+restock|riwayat\s+beli', '', text, flags=re.I).strip()
            )
            tool = self.registry.get_tool("get_restock_history")
            if tool and RBACManager.can_access_tool(role, tool.name):
                result = await tool.execute({"product_name": product_query, "limit": 10})
                rows = result.data.get("restock_history", [])
                if rows:
                    label = product_query or "Semua Produk"
                    lines = [f"📋 *Riwayat Restock ({label}):*"]
                    for r in rows:
                        tanggal = r.get("restock_date", r.get("synced_at", "—"))[:10]
                        lines.append(
                            f"• *{r.get('product_name')}*: {r.get('quantity')} {r.get('unit','pcs')} "
                            f"| {fmt_rp(r.get('purchase_price',0))}/pcs | {tanggal}"
                        )
                    return "\n".join(lines)
                return f"ℹ️ Belum ada riwayat restock {f'untuk \"{product_query}\"' if product_query else ''}."

        # ── Riwayat inventory correction ─────────
        if intent == "inventory_history":
            product_query = extract_product_query(
                re.sub(r'riwayat\s+inventory|history\s+inventory|koreksi\s+stok', '', text, flags=re.I).strip()
            )
            tool = self.registry.get_tool("get_inventory_history")
            if tool and RBACManager.can_access_tool(role, tool.name):
                result = await tool.execute({"product_name": product_query, "limit": 10})
                rows = result.data.get("inventory_history", [])
                if rows:
                    label = product_query or "Semua Produk"
                    lines = [f"🔧 *Riwayat Koreksi Inventory ({label}):*"]
                    for r in rows:
                        tanggal = r.get("corrected_at", r.get("synced_at", "—"))[:10]
                        delta = r.get("delta", 0)
                        sign = "+" if float(delta or 0) >= 0 else ""
                        lines.append(
                            f"• *{r.get('product_name')}*: {sign}{delta} | "
                            f"Alasan: {r.get('reason','—')} | {tanggal}"
                        )
                    return "\n".join(lines)
                return f"ℹ️ Belum ada riwayat koreksi inventory {f'untuk \"{product_query}\"' if product_query else ''}."

        # ── Laporan penjualan ────────────────────
        if intent == "laporan_penjualan":
            period_info = parse_date_or_period(text)
            if period_info["type"] == "range":
                tool = self.registry.get_tool("get_transaction_summary")
                if tool and RBACManager.can_access_tool(role, tool.name):
                    result = await tool.execute({
                        "start_date": period_info["start_date"],
                        "end_date": period_info["end_date"],
                        "period_label": period_info["label"]
                    })
                    if result.success:
                        d = result.data
                        return (
                            f"📊 *Laporan Penjualan — {period_info['label']}:*\n"
                            f"• Omset: {fmt_rp(d.get('total_revenue',0))}\n"
                            f"• Profit: {fmt_rp(d.get('total_profit',0))}\n"
                            f"• Transaksi: {d.get('total_transactions',0)} nota\n"
                            f"• Hari Aktif: {d.get('period_days',0)} hari"
                        )
            else:
                target_date = period_info.get("date", "")
                tool = self.registry.get_tool("get_daily_revenue")
                if tool and RBACManager.can_access_tool(role, tool.name):
                    result = await tool.execute({"date": target_date})
                    if result.success and "total_revenue" in result.data:
                        d = result.data
                        date_display = d.get("date") or period_info.get("label", "Hari ini")
                        return (
                            f"📊 *Laporan Penjualan — {date_display}:*\n"
                            f"• Omset: {fmt_rp(d.get('total_revenue',0))}\n"
                            f"• Profit: {fmt_rp(d.get('total_profit',0))}\n"
                            f"• Transaksi: {d.get('total_transactions',0)} nota"
                        )
            return "ℹ️ Belum ada data laporan penjualan yang tersinkronisasi dari POS untuk periode tersebut."

        # ── Piutang (info saja) ──────────────────
        if intent == "piutang":
            return (
                "💳 *Informasi Piutang Pelanggan*\n\n"
                "Data piutang real-time hanya tersedia via Desktop Bot (akses langsung POS).\n\n"
                "Gunakan perintah `/piutang [nama]` di Desktop Bot, atau buka menu *Pelanggan & Piutang* di aplikasi."
            )

        # ── Fallback ke LLM dengan memory ────────
        system_prompt = (
            "Anda adalah Smart Sembako Assistant, asisten AI cerdas untuk toko kelontong/sembako.\n"
            "Jawab pertanyaan pemilik toko secara ramah, singkat, dan akurat dalam Bahasa Indonesia.\n"
            "Anda memiliki memori percakapan — gunakan konteks sebelumnya bila relevan.\n"
            "Jika ditanya soal fitur OCR atau input stok baru, arahkan ke Desktop App.\n"
            "JANGAN mengarang data stok atau penjualan — selalu akui jika data tidak tersedia."
        )
        messages = [{"role": "system", "content": system_prompt}]
        messages.extend(history[-8:])  # inject max 8 pesan terakhir sebagai konteks
        messages.append({"role": "user", "content": text})

        response_text, provider = await self.model_manager.chat(messages, model_tier="balanced")
        return response_text
