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

        return plan

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

        return {"type": "default", "label": "Hari ini"}
