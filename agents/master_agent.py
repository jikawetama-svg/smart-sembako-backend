import re
import asyncio
import traceback
from datetime import datetime, timezone, timedelta
from typing import Dict, Any, List, Optional
from tools.registry import ToolRegistry, ToolResult
from tools.inventory_tools import GetStockTool, FindProductTool, GetLowStockTool, query_supabase, insert_supabase
from tools.sales_tools import GetDailyRevenueTool, GetTransactionSummaryTool, GetTopProductsTool
from tools.restock_tools import (
    GetRestockHistoryTool, GetInventoryHistoryTool,
    GetExpiringProductsTool, GetLowStockAlertTool
)
from model_manager.manager import ModelManager
from telegram.rbac import RBACManager
import memory.conversation_store as mem_store
from memory.store_brain import StoreBrain
from agents.planner import PlannerAgent
from agents.supervisor import AgentSupervisor
from agents.reflection import ReflectionAgent
from rag.knowledge_manager import KnowledgeManager
from config import settings

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
    "input_restock": "📦 *Restock baru* perlu dicatat melalui Smart Sembako Desktop agar stok dan dokumen pembelian tetap konsisten.\n\nGunakan Desktop Bot atau menu Pembelian/Restock, lalu Cloud Bot akan membaca hasil sinkronisasi terbaru.",
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


def _is_missing_argument(text: str, prefixes: List[str]) -> bool:
    cleaned = text.strip().lower().lstrip("/")
    return cleaned in {p.lstrip("/").lower() for p in prefixes}


def _fmt_date(value: Any) -> str:
    if not value:
        return "-"
    raw = str(value)
    return raw[:10] if len(raw) >= 10 else raw


def _trim_name(value: Any, max_len: int = 28) -> str:
    name = str(value or "-").strip()
    return name if len(name) <= max_len else f"{name[:max_len - 1]}..."


from tools.customer_tools import GetCustomerDebtTool

# ─────────────────────────────────────────────
# MASTER AGENT
# ─────────────────────────────────────────────
class MasterAgent:
    def __init__(self):
        self.registry = ToolRegistry()
        self.model_manager = ModelManager()
        self.planner = PlannerAgent()
        self.supervisor = AgentSupervisor(self.registry)
        self.reflection = ReflectionAgent()
        self.store_brain = StoreBrain()
        self.knowledge_manager = KnowledgeManager()
        self.knowledge_manager.load_and_index_sops()
        self._register_default_tools()

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
        # Customer & Debt
        self.registry.register(GetCustomerDebtTool())

    def classify_intent(self, text: str) -> str:
        lower = text.lower()
        stripped = lower.strip()
        # Command spesifik
        if stripped in ("/start", "/menu", "menu", "mulai"):
            return "start"
        if stripped in ("/help", "help", "bantuan"):
            return "help"
        if stripped in ("/reset", "reset memory", "hapus ingatan", "clear chat"):
            return "reset_memory"
        if stripped.startswith((
            "/confirm", "/cancel", "/batal", "/simpan", "/simpan_jual",
            "/set_harga_jual", "/jual", "/detail_harga", "/lewati_harga",
            "/inventory_family", "/set_family", "/dual_stock_watcher",
            "/dual_stock_channel", "/dual_stock_sync"
        )):
            return "cloud_local_command"
        if re.search(r"\b(namamu siapa|siapa namamu|kamu siapa|nama bot|bot apa|apa yang bisa kamu bantu)\b", lower):
            return "bot_identity"
        if re.search(r"\b(total|jumlah|berapa)\s+(pelanggan|customer|supplier|produk|barang)\b", lower):
            return "record_count"
        # Desktop-only deteksi dini
        if any(w in lower for w in ["ocr", "foto struk", "scan struk", "gambar struk"]):
            return "desktop_ocr"
        if any(w in lower for w in ["bayar piutang", "lunas piutang"]):
            return "desktop_piutang_bayar"
        # Pertanyaan konfigurasi dan ingatan harus diproses sebelum intent umum.
        if re.search(r"\b(nama toko|nama tokoku|nama toko saya)\b.*\b(apa|ingat)\b", lower):
            return "store_name_query"
        if any(phrase in lower for phrase in ["barusan saya minta apa", "tadi saya minta apa", "pesan terakhir saya", "pertanyaan terakhir saya"]):
            return "recall_last_request"

        # Restock: bedakan riwayat, rekomendasi, dan permintaan input yang hanya aman via Desktop.
        if any(w in lower for w in ["riwayat beli", "riwayat restock", "/riwayat_restock", "history restock", "beli barang kapan"]):
            return "restock_history"
        if any(w in lower for w in ["stok kritis", "stok rendah", "rekomendasi restock", "perlu beli", "barang apa yang perlu restock"]):
            return "restock_rekomendasi"
        if stripped.startswith(("restock", "/restock", "beli ")):
            return "cloud_input_restock"
        # Inventory correction
        if stripped.startswith(("/inventory", "inventory ", "koreksi stok ")):
            return "cloud_input_inventory"
        if any(w in lower for w in ["koreksi stok", "riwayat inventory", "/riwayat_inventory", "history inventory", "inventory correction"]):
            return "inventory_history"
        # Expired
        if any(w in lower for w in ["expired", "kadaluarsa", "exp", "kadaluwarsa"]):
            return "cek_expired"
        # Saran bisnis bukan laporan angka. Ini harus sampai ke LLM dengan konteks toko.
        if any(w in lower for w in ["meningkatkan penjualan", "naikkan penjualan", "strategi jual", "agar laku", "cara jual lebih"]):
            return "strategi_penjualan"
        # Laporan & penjualan
        if any(w in lower for w in ["omset", "pendapatan", "jual", "penjualan", "laporan", "profit", "untung", "transaksi", "pemasukan"]):
            return "laporan_penjualan"
        if re.search(r"\b(pelanggan|customer)\b", lower):
            return "customer_query"
        if re.search(r"\b(supplier|pemasok)\b", lower):
            return "supplier_query"
        # Stok
        if any(w in lower for w in ["stok", "ada berapa", "sisa", "barang", "produk", "harga", "cek"]):
            return "cek_stok"
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

        if settings.TENANT_ISOLATION_REQUIRED and not settings.MERCHANT_ID:
            return "⚠️ Cloud Bot belum siap membaca data karena `MERCHANT_ID` belum dikonfigurasi. Hubungi owner untuk menyelesaikan setup tenant toko."

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

        if intent == "bot_identity":
            return (
                "Saya *Smart Sembako Assistant*, bot pendamping operasional toko sembako.\n\n"
                "Saya bisa bantu cek stok, laporan penjualan, stok kritis, riwayat restock, "
                "riwayat koreksi stok, dan piutang pelanggan. Untuk daftar command, ketik `/help`."
            )

        # ── Desktop-only features ─────────────────
        if intent == "desktop_ocr":
            return DESKTOP_ONLY_FEATURES["ocr"]
        if intent == "desktop_piutang_bayar":
            return DESKTOP_ONLY_FEATURES["piutang_bayar"]
        if intent == "cloud_input_restock":
            return await self._queue_local_command(
                text=text,
                user_id=user_id,
                command_kind="restock",
                expected_prefix="/restock",
                format_hint="Gunakan: `/restock <produk> <qty> [harga_modal]`\nContoh: `/restock kapal api mix 12 17500`"
            )

        if intent == "cloud_input_inventory":
            return await self._queue_local_command(
                text=text,
                user_id=user_id,
                command_kind="inventory",
                expected_prefix="/inventory",
                format_hint="Gunakan: `/inventory <produk> <stok_target>`\nContoh: `/inventory kapal api mix 130`"
            )

        if intent == "cloud_local_command":
            return await self._queue_local_command(
                text=text,
                user_id=user_id,
                command_kind="local_command",
                expected_prefix="",
                format_hint="Command lokal akan diproses saat aplikasi Smart Sembako Desktop aktif."
            )

        # Deterministic memory responses prevent the model from denying available history.
        if intent == "recall_last_request":
            prior_user_messages = [item.get("content", "") for item in history if item.get("role") == "user"]
            if prior_user_messages:
                return f"🧠 Permintaan Anda sebelumnya: *{prior_user_messages[-1]}*"
            return "🧠 Belum ada permintaan sebelumnya yang tersimpan pada sesi ini."

        if intent == "store_name_query":
            store_mem = await self.store_brain.get_store_memory(user_id=user_id)
            store_name = store_mem.get("store_name", "Smart Sembako")
            return f"🏪 Nama toko yang saya simpan: *{store_name}*."

        if intent == "record_count":
            return await self._handle_record_count(text)

        if intent == "customer_query":
            return await self._handle_customer_query(text)

        if intent == "supplier_query":
            return await self._handle_supplier_query(text)

        # ── Chat Configuration Commands ─────────
        lower_text = text.lower().strip()
        if lower_text.startswith("namaku "):
            name_val = text[7:].strip()
            await self.store_brain.save_store_memory("owner_name", name_val, user_id=user_id, user_role=role)
            return f"✅ Baik Bapak/Ibu {name_val}, nama Anda telah disimpan di Store Brain!"

        # Gunakan bentuk eksplisit agar pertanyaan seperti "nama toko ku apa?"
        # tidak pernah dianggap sebagai perintah pengubahan nama.
        store_match = re.match(r"(?i)^(?:set|ubah|ganti)\s+nama\s+toko\s*[:=]?\s*(.+)$", text.strip())
        if store_match:
            store_val = store_match.group(1).strip()
            if not store_val:
                return "Tulis nama lengkapnya, misalnya: `set nama toko: Toko Sembako Teh Asiah`."
            await self.store_brain.save_store_memory("store_name", store_val, user_id=user_id, user_role=role)
            return f"✅ Nama toko telah diperbarui menjadi: *{store_val}*!"

        if "jawaban singkat" in lower_text:
            await self.store_brain.save_store_memory("response_style", "compact", user_id=user_id, user_role=role)
            return "⚡ Gaya jawaban diubah menjadi: *Singkat & Padat*."

        if "jawaban detail" in lower_text or "jawaban lengkap" in lower_text:
            await self.store_brain.save_store_memory("response_style", "detail", user_id=user_id, user_role=role)
            return "📝 Gaya jawaban diubah menjadi: *Detail & Lengkap*."

        if intent == "restock_history" and _is_missing_argument(text, ["/riwayat_restock", "riwayat restock", "history restock"]):
            return (
                "❌ Format salah.\n"
                "Gunakan: `/riwayat_restock <nama produk>`\n"
                "Contoh: `/riwayat_restock kapal api mix`"
            )

        if intent == "inventory_history" and _is_missing_argument(text, ["/riwayat_inventory", "riwayat inventory", "history inventory", "koreksi stok"]):
            return (
                "❌ Format salah.\n"
                "Gunakan: `/riwayat_inventory <nama produk>`\n"
                "Contoh: `/riwayat_inventory kapal api mix`"
            )

        # ── Agent Runtime Pipeline Execution ────────
        # Step 1: Planner Agent decompose plan
        plan = self.planner.plan(intent, text, user_role=role)

        # Step 2: Agent Supervisor execute sub-tasks across specialist agents
        gathered_outputs = {}
        if plan.tasks:
            gathered_outputs = await self.supervisor.execute_plan(plan, user_role=role)

        # Step 3: Reflection Agent evaluate outputs and data integrity
        reflection_res = self.reflection.reflect(text, intent, gathered_outputs)

        # Step 4: RAG Knowledge Base search for SOPs & store guidelines
        rag_context = self.knowledge_manager.search_knowledge(text, top_k=2)

        # Direct response shortcuts for simple data formatting if confidence is high
        if intent == "piutang":
            cust_data = reflection_res.summary_data.get("customer_debt") or reflection_res.summary_data.get("customers")
            if cust_data is not None:
                msg = None
                if isinstance(cust_data, dict):
                    c_list = cust_data.get("customers", [])
                    tot_all = cust_data.get("total_all_debt", 0)
                    msg = cust_data.get("message")
                else:
                    c_list = cust_data
                    tot_all = sum(float(c.get("total_debt", 0)) for c in c_list)

                if not c_list:
                    if msg:
                        return f"💳 *Informasi Piutang Pelanggan*\n\n{msg}"
                    return "💳 *Informasi Piutang Pelanggan*\n\n✅ Tidak ada catatan hutang/piutang aktif saat ini."

                lines = [f"💳 *Laporan Piutang Pelanggan (Total: {fmt_rp(tot_all)}):*"]
                for c in c_list[:15]:
                    phone = c.get('phone')
                    phone_str = f" (HP: {phone})" if phone and phone != '-' else ""
                    lines.append(f"• *{c.get('name')}*: {fmt_rp(c.get('total_debt',0))}{phone_str}")
                return "\n".join(lines)

        if intent in ("cek_stok", "stok_kritis", "restock_rekomendasi"):
            products = reflection_res.summary_data.get("products") or reflection_res.summary_data.get("low_stock_products")
            if products is not None and isinstance(products, list):
                if not products:
                    return "🟢 *Semua Stok Aman!* Tidak ada produk kritis saat ini."
                prod_q = extract_product_query(text) or ("Stok Kritis" if intent in ("stok_kritis", "restock_rekomendasi") else "Stok Barang")
                lines = [f"📦 *Hasil Stok ({prod_q}):*"]
                for p in products[:20]:
                    stock_val = float(p.get("stock", 0) or 0)
                    status = "🔴 Kritis" if p.get("is_low_stock") or stock_val <= 10 else "🟢 Aman"
                    lines.append(
                        f"• *{p.get('name')}*: {stock_val:g} {p.get('unit','pcs')} "
                        f"({status}) — {fmt_rp(p.get('selling_price', 0))}"
                    )
                return "\n".join(lines)

        if intent == "laporan_penjualan" and "sales" in reflection_res.summary_data:
            d = reflection_res.summary_data["sales"]
            if "total_revenue" in d:
                period_label = d.get("period_label") or d.get("date") or "Hari Ini"
                top_p = reflection_res.summary_data.get("top_products", [])
                lines = [
                    f"📊 *Laporan Penjualan ({period_label}):*",
                    f"• Total Omset: {fmt_rp(d.get('total_revenue',0))}",
                    f"• Estimasi Profit: {fmt_rp(d.get('total_profit',0))}",
                    f"• Jumlah Transaksi: {d.get('total_transactions',0)} nota"
                ]
                if top_p:
                    lines.append("\n🏆 *Produk Terlaris:*")
                    for tp in top_p[:5]:
                        if isinstance(tp, dict):
                            lines.append(f"• *{tp.get('name')}*: {tp.get('qty',0)} {tp.get('unit','pcs')} ({fmt_rp(tp.get('total_sales',0))})")
                        else:
                            lines.append(f"• {tp}")
                return "\n".join(lines)

        if intent == "restock_history" and "restock_history" in reflection_res.summary_data:
            rows = reflection_res.summary_data.get("restock_history", [])
            query = self.planner._extract_product(text)
            if not rows:
                return f"📋 Riwayat restock untuk *{query}* belum ditemukan."

            lines = [f"📋 *RIWAYAT RESTOCK - {query.upper()}*"]
            lines.append("Tgl | Qty | Modal | Supplier")
            for row in rows[:10]:
                qty = f"{row.get('quantity', 0)} {row.get('unit', '')}".strip()
                lines.append(
                    f"{_fmt_date(row.get('restock_date') or row.get('synced_at'))} | "
                    f"{qty} | {fmt_rp(row.get('purchase_price', 0))} | "
                    f"{_trim_name(row.get('supplier_name'), 20)}"
                )
            lines.append(f"\nTotal entri: {len(rows)}")
            return "\n".join(lines)

        if intent == "inventory_history" and "inventory_history" in reflection_res.summary_data:
            rows = reflection_res.summary_data.get("inventory_history", [])
            query = self.planner._extract_product(text)
            if not rows:
                return f"📋 Riwayat inventory untuk *{query}* belum ditemukan."

            lines = [f"📋 *RIWAYAT INVENTORY - {query.upper()}*"]
            lines.append("Tgl | Sebelum | Sesudah | Selisih | Alasan")
            for row in rows[:10]:
                delta = float(row.get("delta", 0) or 0)
                arrow = "⬆️" if delta > 0 else "⬇️" if delta < 0 else "➡️"
                lines.append(
                    f"{_fmt_date(row.get('corrected_at') or row.get('synced_at'))} | "
                    f"{row.get('quantity_before', 0)} | {row.get('quantity_after', 0)} | "
                    f"{arrow} {delta:g} | {_trim_name(row.get('reason'), 18)}"
                )
            lines.append(f"\nTotal entri: {len(rows)}")
            return "\n".join(lines)

        # Step 5: LLM Synthesis with context, history, store brain, and RAG knowledge
        store_mem = await self.store_brain.get_store_memory(user_id=user_id)
        store_name = store_mem.get("store_name", "Smart Sembako")
        owner_name = store_mem.get("owner_name", "Pemilik Toko")
        style = store_mem.get("response_style", "normal")

        system_prompt = (
            f"Anda adalah Smart Sembako Assistant, AI Agent cerdas untuk toko {store_name}.\n"
            f"Anda sedang berbicara dengan {owner_name} (Role: {role.upper()}).\n"
            f"Gaya jawaban disukai: {style}.\n"
            "FAKTA TERVERIFIKASI DATABASE (WAJIB ACUAN UTAMA):\n"
            f"{reflection_res.formatted_context or 'Tidak ada data spesifik dari database.'}\n\n"
            "PENGETAHUAN SOP & ATURAN TOKO (RAG ENGINE):\n"
            f"{rag_context or 'Tidak ada SOP khusus.'}\n\n"
            "INSTRUKSI UTAMA:\n"
            "1. Jawab ramah, akurat, dan profesional dalam Bahasa Indonesia.\n"
            "2. Jangan mengarang angka stok atau penjualan — berpijaklah pada fakta terverifikasi.\n"
            "3. Snapshot cloud bisa tertunda; bila data sync tidak tersedia, sebutkan fakta itu tanpa menyimpulkan stok aman.\n"
            "4. Stok negatif wajib disebut MINUS, bukan nol.\n"
            "5. Hormati peran: data profit/modal/piutang hanya untuk owner/admin.\n"
            "6. Cloud Bot hanya membaca data; perubahan stok, restock, dan pembayaran harus melalui Desktop POS dengan persetujuan owner.\n"
            "7. Jika user menanyakan fitur OCR/input stok baru, arahkan ke Desktop App.\n"
            "8. Jika ditanya identitas, jawab bahwa Anda adalah Smart Sembako Assistant.\n"
            "9. Jangan memakai data dari percakapan sebelumnya untuk pertanyaan baru yang intent-nya berbeda.\n"
            "10. Jika intent tidak jelas atau data tidak tersedia, arahkan ke command relevan atau `/help`; jangan menebak."
        )

        messages = [{"role": "system", "content": system_prompt}]
        messages.extend(history[-8:])
        messages.append({"role": "user", "content": text})

        response_text, _ = await self.model_manager.chat(messages, model_tier="balanced")
        return response_text

    async def _handle_record_count(self, text: str) -> str:
        lower = text.lower()
        if "pelanggan" in lower or "customer" in lower:
            table, label = "customers_sync", "pelanggan"
        elif "supplier" in lower:
            table, label = "suppliers_sync", "supplier"
        else:
            table, label = "products_sync", "produk"

        rows = await query_supabase(table, {"select": "id", "limit": 10000})
        if rows:
            return f"Total {label} yang tersinkron di cloud: *{len(rows)}*."
        return (
            f"Total {label} belum tersedia dari cloud sync.\n"
            "Pastikan sinkronisasi Desktop POS ke Supabase sudah berjalan."
        )

    async def _handle_customer_query(self, text: str) -> str:
        query = re.sub(r"(?i)^/?(cek\s+)?(data\s+)?(pelanggan|customer)\s*", "", text).strip()
        params = {
            "select": "name,phone,total_debt,last_transaction_date",
            "order": "name.asc",
            "limit": 15
        }
        if query:
            params["name"] = f"ilike.*{query}*"
        rows = await query_supabase("customers_sync", params)
        if not rows:
            return "👥 Data pelanggan belum ditemukan di cloud sync."
        lines = [f"👥 *PELANGGAN ({len(rows)} ditampilkan)*"]
        for row in rows:
            phone = row.get("phone") or "-"
            debt = fmt_rp(row.get("total_debt", 0))
            lines.append(f"• *{_trim_name(row.get('name'))}* | HP: {phone} | Piutang: {debt}")
        return "\n".join(lines)

    async def _handle_supplier_query(self, text: str) -> str:
        query = re.sub(r"(?i)^/?(cek\s+)?(data\s+)?(supplier|pemasok)\s*", "", text).strip()
        params = {
            "select": "name,phone,address",
            "order": "name.asc",
            "limit": 15
        }
        if query:
            params["name"] = f"ilike.*{query}*"
        rows = await query_supabase("suppliers_sync", params)
        if not rows:
            return "🏭 Data supplier belum ditemukan di cloud sync."
        lines = [f"🏭 *SUPPLIER ({len(rows)} ditampilkan)*"]
        for row in rows:
            phone = row.get("phone") or "-"
            address = _trim_name(row.get("address"), 24)
            lines.append(f"• *{_trim_name(row.get('name'))}* | HP: {phone} | {address}")
        return "\n".join(lines)

    async def _queue_local_command(
        self,
        text: str,
        user_id: int,
        command_kind: str,
        expected_prefix: str,
        format_hint: str
    ) -> str:
        command_text = text.strip()
        if expected_prefix and not command_text.startswith("/"):
            command_text = f"{expected_prefix} {command_text.split(' ', 1)[1] if ' ' in command_text else ''}".strip()

        parts = command_text.split()
        if command_kind in ("restock", "inventory") and len(parts) < 3:
            return f"❌ Format belum lengkap.\n{format_hint}"

        row = await insert_supabase("agent_command_queue", {
            "source_channel": "telegram",
            "source_chat_id": str(user_id),
            "source_user_id": str(user_id),
            "command_text": command_text,
            "command_kind": command_kind,
            "status": "pending",
            "requires_local_app": True
        })

        if not row:
            return (
                "⚠️ Perintah belum bisa dimasukkan ke antrean cloud.\n"
                "Pastikan Supabase aktif, `MERCHANT_ID` sudah benar, dan tabel `agent_command_queue` sudah dibuat."
            )

        queue_id = str(row.get("id", ""))[:8]
        action_label = "restock" if command_kind == "restock" else "koreksi inventory"
        return (
            f"🕒 Perintah {action_label} sudah masuk antrean cloud `{queue_id}`.\n\n"
            "Status: menunggu aplikasi Smart Sembako lokal dibuka.\n"
            "Saat aplikasi lokal aktif, perintah akan diproses lewat POS lokal dan bot akan mengirim hasil/konfirmasi ke chat ini.\n\n"
            "Cloud Bot tidak mengubah stok langsung agar data pos.db tetap aman sebagai sumber utama."
        )
