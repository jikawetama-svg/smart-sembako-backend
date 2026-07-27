import asyncio
import traceback
from datetime import datetime, timezone, timedelta
from typing import List, Optional, Dict, Any
from config import settings
from tools.inventory_tools import query_supabase
from memory.store_brain import StoreBrain

class SchedulerAgent:
    """
    Proactive notification agent running scheduled jobs for Smart Sembako Assistant.
    Ensures ZERO duplicate notifications between Cloud Bot and Desktop Bot via
    StoreBrain locking ('last_notif_sent_by').
    """

    def __init__(self, bot_id: str = "cloud_bot"):
        self.bot_id = bot_id
        self.store_brain = StoreBrain()
        self._is_running = False

    async def start_scheduler(self):
        if self._is_running:
            return
        self._is_running = True
        print(f"[SchedulerAgent] ⏰ Proactive Scheduler Started ({self.bot_id})")

        while self._is_running:
            try:
                now_utc = datetime.now(timezone.utc)
                # Convert to WIB (UTC+7)
                wib_time = now_utc + timedelta(hours=7)
                hour = wib_time.hour
                minute = wib_time.minute

                morning_hr = settings.SCHEDULER_MORNING_HR
                evening_hr = settings.SCHEDULER_EVENING_HR

                # Morning Briefing (e.g. 07:00 - 07:15)
                if hour == morning_hr and minute < 15:
                    await self._trigger_job_if_not_claimed("morning_briefing", self._send_morning_briefing)

                # Evening Summary (e.g. 20:00 - 20:15)
                if hour == evening_hr and minute < 15:
                    await self._trigger_job_if_not_claimed("evening_summary", self._send_evening_summary)

                # Low Stock Check every 6 hours (at minute < 10)
                if hour in (6, 12, 18) and minute < 10:
                    await self._trigger_job_if_not_claimed(f"low_stock_check_{hour}", self._send_low_stock_alert)

            except Exception as e:
                print(f"[SchedulerAgent Error]: {e}\n{traceback.format_exc()}")

            # Sleep 5 minutes between checks
            await asyncio.sleep(300)

    async def _trigger_job_if_not_claimed(self, job_name: str, job_func):
        today_str = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        lock_key = f"lock_notif_{job_name}_{today_str}"

        # Check if already sent today
        mem = await self.store_brain.get_store_memory()
        already_sent = mem.get(lock_key)

        if already_sent:
            return  # Job already executed by Desktop Bot or Cloud Bot today

        # Claim lock
        await self.store_brain.save_store_memory(
            key=lock_key,
            value={"sent_by": self.bot_id, "timestamp": datetime.now(timezone.utc).isoformat()},
            category="scheduler_lock"
        )

        print(f"[SchedulerAgent] 🚀 Executing scheduled job '{job_name}' by {self.bot_id}")
        await job_func()

    async def _send_morning_briefing(self):
        owner_ids = settings.get_owner_ids()
        if not owner_ids or not settings.TELEGRAM_BOT_TOKEN:
            return

        # Fetch low stock & yesterday sales
        low_stock = await query_supabase("products_sync", {
            "select": "name,stock,unit",
            "is_low_stock": "eq.true",
            "limit": 10
        })

        lines = [
            "🌅 *Smart Sembako Morning Briefing*",
            f"📅 Tanggal: {datetime.now().strftime('%d-%m-%Y')}\n",
            f"⚠️ *Stok Kritis ({len(low_stock)} produk):*" if low_stock else "✅ *Stok produk dalam kondisi aman.*"
        ]

        for p in low_stock:
            lines.append(f"• *{p.get('name')}*: {p.get('stock')} {p.get('unit', 'pcs')}")

        lines.append("\n*Semangat untuk penjualan hari ini!* 💪")
        msg = "\n".join(lines)

        for oid in owner_ids:
            await self._send_telegram(oid, msg)

    async def _send_evening_summary(self):
        owner_ids = settings.get_owner_ids()
        if not owner_ids or not settings.TELEGRAM_BOT_TOKEN:
            return

        today_str = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        summaries = await query_supabase("transactions_summary", {
            "select": "total_revenue,total_profit,total_transactions",
            "date": f"eq.{today_str}"
        })

        rev, profit, txs = 0, 0, 0
        if summaries:
            s = summaries[0]
            rev = s.get("total_revenue", 0)
            profit = s.get("total_profit", 0)
            txs = s.get("total_transactions", 0)

        lines = [
            "🌙 *Smart Sembako Evening Summary*",
            f"📅 Tanggal: {today_str}\n",
            f"💰 Omset Hari Ini: Rp {float(rev):,.0f}",
            f"📈 Profit Estimasi: Rp {float(profit):,.0f}",
            f"🧾 Total Transaksi: {txs} nota\n",
            " Terima kasih atas kerja keras hari ini!"
        ]
        msg = "\n".join(lines)

        for oid in owner_ids:
            await self._send_telegram(oid, msg)

    async def _send_low_stock_alert(self):
        owner_ids = settings.get_owner_ids()
        if not owner_ids or not settings.TELEGRAM_BOT_TOKEN:
            return

        low_stock = await query_supabase("products_sync", {
            "select": "name,stock,unit",
            "is_low_stock": "eq.true",
            "limit": 10
        })
        if not low_stock:
            return

        lines = [
            "⚠️ *Peringatan Stok Kritis (Auto-Monitor)*\n"
        ]
        for p in low_stock:
            lines.append(f"• *{p.get('name')}*: sisa {p.get('stock')} {p.get('unit','pcs')}")

        lines.append("\n_Segera lakukan restock untuk menjaga ketersediaan barang._")
        msg = "\n".join(lines)

        for oid in owner_ids:
            await self._send_telegram(oid, msg)

    async def _send_telegram(self, chat_id: int, text: str):
        import httpx
        url = f"https://api.telegram.org/bot{settings.TELEGRAM_BOT_TOKEN}/sendMessage"
        payload = {"chat_id": chat_id, "text": text, "parse_mode": "Markdown"}
        try:
            async with httpx.AsyncClient(timeout=8.0) as client:
                await client.post(url, json=payload)
        except Exception as e:
            print(f"[SchedulerAgent Send Error]: {e}")
