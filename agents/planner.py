import re
from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional
from datetime import datetime, timedelta

@dataclass
class AgentTask:
    task_id: str
    target_agent: str  # 'inventory' | 'sales' | 'analytics' | 'ocr' | 'restock'
    tool_name: str
    params: Dict[str, Any] = field(default_factory=dict)
    description: str = ""

@dataclass
class ExecutionPlan:
    user_query: str
    intent: str
    tasks: List[AgentTask] = field(default_factory=list)
    requires_llm_summary: bool = True
    context_needed: List[str] = field(default_factory=list)


class PlannerAgent:
    """
    Planner Agent: Decomposes complex user goals into structured sub-tasks
    for execution by the Agent Supervisor.
    """

    def plan(self, intent: str, query: str, user_role: str = "owner") -> ExecutionPlan:
        plan = ExecutionPlan(user_query=query, intent=intent)

        if intent == "cek_stok":
            prod = self._extract_product(query)
            if prod:
                plan.tasks.append(AgentTask(
                    task_id="task_stock_search",
                    target_agent="inventory",
                    tool_name="get_stock",
                    params={"product_name": prod},
                    description=f"Cari stok produk '{prod}'"
                ))
            else:
                plan.tasks.append(AgentTask(
                    task_id="task_low_stock",
                    target_agent="inventory",
                    tool_name="get_low_stock",
                    params={},
                    description="Ambil daftar produk stok kritis"
                ))

        elif intent == "restock_rekomendasi":
            plan.tasks.append(AgentTask(
                task_id="task_stock_alert",
                target_agent="inventory",
                tool_name="get_low_stock_alert",
                params={},
                description="Ambil rekomendasi produk stok rendah"
            ))
            plan.tasks.append(AgentTask(
                task_id="task_predict_restock",
                target_agent="analytics",
                tool_name="predict_restock",
                params={},
                description="Prediksi kuantitas restock"
            ))

        elif intent == "cek_expired":
            plan.tasks.append(AgentTask(
                task_id="task_expired",
                target_agent="inventory",
                tool_name="get_expiring_products",
                params={},
                description="Ambil daftar produk mendekati kedaluwarsa"
            ))

        elif intent == "restock_history":
            prod = self._extract_product(query)
            plan.tasks.append(AgentTask(
                task_id="task_restock_hist",
                target_agent="inventory",
                tool_name="get_restock_history",
                params={"product_name": prod, "limit": 10},
                description=f"Ambil riwayat restock {prod or 'semua produk'}"
            ))

        elif intent == "inventory_history":
            prod = self._extract_product(query)
            plan.tasks.append(AgentTask(
                task_id="task_inv_hist",
                target_agent="inventory",
                tool_name="get_inventory_history",
                params={"product_name": prod, "limit": 10},
                description=f"Ambil riwayat koreksi stok {prod or 'semua produk'}"
            ))

        elif intent == "laporan_penjualan":
            period = self._parse_period(query)
            if period.get("type") == "range":
                plan.tasks.append(AgentTask(
                    task_id="task_sales_range",
                    target_agent="sales",
                    tool_name="get_transaction_summary",
                    params={
                        "start_date": period["start_date"],
                        "end_date": period["end_date"],
                        "period_label": period["label"]
                    },
                    description=f"Ringkasan transaksi {period['label']}"
                ))
            else:
                plan.tasks.append(AgentTask(
                    task_id="task_sales_daily",
                    target_agent="sales",
                    tool_name="get_daily_revenue",
                    params={"date": period.get("date", "")},
                    description=f"Omset penjualan {period.get('label', 'hari ini')}"
                ))
            # Tambahkan top products untuk memperkaya laporan jika role owner/admin
            if user_role in ("owner", "admin"):
                plan.tasks.append(AgentTask(
                    task_id="task_top_products",
                    target_agent="sales",
                    tool_name="get_top_products",
                    params={"limit": 5},
                    description="Produk terlaris"
                ))

        elif intent == "profit_analisis":
            plan.tasks.append(AgentTask(
                task_id="task_profit_analysis",
                target_agent="analytics",
                tool_name="run_profit_analysis",
                params={},
                description="Analisis margin profit 7 hari terakhir"
            ))

        elif intent == "analisis_toko":
            plan.tasks.append(AgentTask(
                task_id="task_sales_daily",
                target_agent="sales",
                tool_name="get_daily_revenue",
                params={"date": ""},
                description="Penjualan hari ini"
            ))
            plan.tasks.append(AgentTask(
                task_id="task_low_stock",
                target_agent="inventory",
                tool_name="get_low_stock",
                params={},
                description="Stok kritis"
            ))
            plan.tasks.append(AgentTask(
                task_id="task_top_products",
                target_agent="sales",
                tool_name="get_top_products",
                params={"limit": 5},
                description="Produk terlaris"
            ))

        elif intent in ("piutang", "desktop_piutang_bayar"):
            cust_name = self._extract_customer(query)
            plan.tasks.append(AgentTask(
                task_id="task_customer_debt",
                target_agent="customer",
                tool_name="get_customer_debt",
                params={"customer_name": cust_name},
                description=f"Cari piutang pelanggan '{cust_name or 'semua'}'"
            ))

        return plan

    def _extract_customer(self, text: str) -> str:
        prefixes = ["/piutang", "piutang", "hutang", "tagihan", "cek piutang", "cek hutang"]
        cleaned = text.strip()
        for p in sorted(prefixes, key=len, reverse=True):
            pattern = re.compile(rf'(?i)^{re.escape(p)}\s*')
            if pattern.search(cleaned):
                cleaned = pattern.sub('', cleaned).strip()
                break
        return cleaned

    def _extract_product(self, text: str) -> str:
        prefixes = [
            "cek stok", "cek sisa", "stok barang", "sisa stok",
            "ada berapa", "cari produk", "cari barang", "cek produk",
            "riwayat restock", "history restock", "riwayat inventory",
            "history inventory", "koreksi stok", "stok", "sisa", "cek", "cari"
        ]
        cleaned = text.strip()
        for p in sorted(prefixes, key=len, reverse=True):
            pattern = re.compile(rf'(?i)^{re.escape(p)}\s*')
            if pattern.search(cleaned):
                cleaned = pattern.sub('', cleaned).strip()
                break
        return cleaned

    def _parse_period(self, text: str) -> Dict[str, Any]:
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
            return {"type": "range", "start_date": start, "end_date": end, "label": f"Bulan Ini ({today.strftime('%B %Y')})"}

        months_id = {
            "januari": 1, "jan": 1, "februari": 2, "feb": 2, "maret": 3, "mar": 3,
            "april": 4, "apr": 4, "mei": 5, "juni": 6, "jun": 6, "juli": 7, "jul": 7,
            "agustus": 8, "agu": 8, "september": 9, "sep": 9, "oktober": 10, "okt": 10,
            "november": 11, "nov": 11, "desember": 12, "des": 12
        }

        # 1. Custom single date parsing (e.g. 14 juli 2026 or 14 juli or 14-07-2026)
        match_full = re.search(r'(\d{1,2})\s+([a-zA-Z]+)(?:\s+(\d{4}))?', lower)
        if match_full:
            day, month_str = int(match_full.group(1)), match_full.group(2).lower()
            year = int(match_full.group(3)) if match_full.group(3) else today.year
            if month_str in months_id:
                m_num = months_id[month_str]
                dt_str = f"{year:04d}-{m_num:02d}-{day:02d}"
                return {"type": "single_date", "date": dt_str, "label": f"{day} {month_str.capitalize()} {year}"}

        match_numeric = re.search(r'(\d{4})[-/.](\d{1,2})[-/.](\d{1,2})', lower)
        if match_numeric:
            y, m, d = int(match_numeric.group(1)), int(match_numeric.group(2)), int(match_numeric.group(3))
            dt_str = f"{y:04d}-{m:02d}-{d:02d}"
            return {"type": "single_date", "date": dt_str, "label": f"{d}-{m:02d}-{y}"}

        match_dmy = re.search(r'(\d{1,2})[-/.](\d{1,2})[-/.](?:20)?(\d{2})', lower)
        if match_dmy:
            d, m, y = int(match_dmy.group(1)), int(match_dmy.group(2)), int(match_dmy.group(3))
            if y < 100: y += 2000
            dt_str = f"{y:04d}-{m:02d}-{d:02d}"
            return {"type": "single_date", "date": dt_str, "label": f"{d}-{m:02d}-{y}"}

        # 2. Month range parsing (e.g. omset bulan juli or juli 2026 or omset agustus)
        for m_str, m_num in months_id.items():
            if m_str in lower and len(m_str) > 2:
                yr_match = re.search(r'\b(20\d{2})\b', lower)
                yr = int(yr_match.group(1)) if yr_match else today.year
                start = f"{yr:04d}-{m_num:02d}-01"
                first_dt = datetime(yr, m_num, 1)
                last_dt = (first_dt.replace(day=28) + timedelta(days=4)).replace(day=1) - timedelta(days=1)
                end = last_dt.strftime("%Y-%m-%d")
                return {"type": "range", "start_date": start, "end_date": end, "label": f"Bulan {m_str.capitalize()} {yr}"}

        return {"type": "default", "label": "Hari ini"}
