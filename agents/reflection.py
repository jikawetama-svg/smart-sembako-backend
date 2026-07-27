from dataclasses import dataclass, field
from typing import Dict, Any, List, Optional

@dataclass
class ReflectionResult:
    is_valid: bool
    confidence_score: float  # 0.0 to 1.0
    summary_data: Dict[str, Any] = field(default_factory=dict)
    warnings: List[str] = field(default_factory=list)
    formatted_context: str = ""

class ReflectionAgent:
    """
    Reflection Agent: Evaluates gathered tool execution outputs, verifies data integrity,
    checks for gaps/anomalies, and prepares structured facts for final LLM synthesis.
    """

    def reflect(self, query: str, intent: str, agent_outputs: Dict[str, Any]) -> ReflectionResult:
        warnings = []
        is_valid = True
        total_items_found = 0
        summary_data = {}
        context_parts = []

        if not agent_outputs:
            return ReflectionResult(
                is_valid=False,
                confidence_score=0.0,
                warnings=["Tidak ada data hasil eksekusi tool yang dikumpulkan."],
                formatted_context="Data dari database tidak tersedia."
            )

        for task_id, res in agent_outputs.items():
            if not isinstance(res, dict):
                continue

            success = res.get("success", True)
            data = res.get("data", {})

            if not success:
                warnings.append(f"Tugas {task_id} gagal: {res.get('error', 'Unknown error')}")
                continue

            # Inventory / Stock checks
            if "products" in data or "low_stock_products" in data:
                prods = data.get("products", data.get("low_stock_products", []))
                total_items_found += len(prods)
                summary_data["products"] = prods
                if not prods:
                    context_parts.append("Hasil pencarian produk: Kosong / tidak ditemukan.")
                else:
                    context_parts.append(f"Ditemukan {len(prods)} produk relevan di katalog.")

            # Sales / Revenue checks
            elif "total_revenue" in data:
                rev = data.get("total_revenue", 0)
                prof = data.get("total_profit", 0)
                txs = data.get("total_transactions", 0)
                summary_data["sales"] = data
                context_parts.append(f"Ringkasan Penjualan: Omset Rp {rev:,.0f}, Profit Rp {prof:,.0f}, Transaksi: {txs} nota.")

            # Restock History
            elif "restock_history" in data:
                rows = data.get("restock_history", [])
                summary_data["restock_history"] = rows
                context_parts.append(f"Riwayat Restock: Ditemukan {len(rows)} catatan pembelian.")

            # Inventory History
            elif "inventory_history" in data:
                rows = data.get("inventory_history", [])
                summary_data["inventory_history"] = rows
                context_parts.append(f"Riwayat Koreksi Stok: Ditemukan {len(rows)} catatan koreksi.")

            # Expiring products
            elif "expiring_products" in data:
                rows = data.get("expiring_products", [])
                summary_data["expiring_products"] = rows
                context_parts.append(f"Produk Expired: Ditemukan {len(rows)} produk mendekati kadaluarsa.")

        confidence = 1.0 if not warnings else max(0.5, 1.0 - (len(warnings) * 0.2))
        formatted_context = "\n".join(context_parts) if context_parts else "Data diproses secara normal."

        return ReflectionResult(
            is_valid=is_valid,
            confidence_score=confidence,
            summary_data=summary_data,
            warnings=warnings,
            formatted_context=formatted_context
        )
