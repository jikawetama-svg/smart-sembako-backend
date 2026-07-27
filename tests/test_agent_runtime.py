import sys
import os
import asyncio

# Set UTF-8 encoding for stdout on Windows
if sys.platform == "win32":
    sys.stdout.reconfigure(encoding='utf-8')

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from agents.master_agent import MasterAgent

async def run_tests():
    print("[INIT] Initializing MasterAgent (Agent Runtime Engine)...")
    agent = MasterAgent()

    test_queries = [
        (1001, "cek stok minyak"),
        (1001, "laporan penjualan hari ini"),
        (1001, "rekomendasi restock"),
        (1001, "analisis profit minggu ini"),
        (1001, "reset memory")
    ]

    print("\n--- Running Agent Runtime Pipeline Tests ---")
    for user_id, q in test_queries:
        print(f"\nUser [{user_id}]: {q}")
        res = await agent.handle_message(user_id, q)
        print(f"Bot Response:\n{res}")

    print("\n[SUCCESS] All Agent Runtime tests executed successfully!")

if __name__ == "__main__":
    asyncio.run(run_tests())
