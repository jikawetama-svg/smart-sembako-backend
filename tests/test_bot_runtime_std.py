import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import unittest
import asyncio
from config import settings
from agents.master_agent import MasterAgent
from tools.registry import ToolRegistry, ToolResult, BaseTool
from telegram.rbac import RBACManager
from model_manager.manager import ModelManager

from rag.vector_store import VectorStore
from rag.compressor import MapReduceCompressor

from agents.security_agent import SecurityAgent
from tools.encryption import SecurityEncryption
from tools.supplier_tools import GetSupplierCatalogTool, MultiBranchStockTool

from tools.hf_dataset_loader import HFDatasetLoader

class TestBotRuntime(unittest.TestCase):
    def test_config_defaults(self):
        self.assertEqual(settings.APP_NAME, "Smart Sembako Cloud Bot")
        self.assertIsInstance(settings.PORT, int)

    def test_intent_classification(self):
        agent = MasterAgent()
        self.assertEqual(agent.classify_intent("Berapa stok minyak goreng?"), "cek_stok")
        self.assertEqual(agent.classify_intent("Berapa omset hari ini?"), "laporan_penjualan")
        self.assertEqual(agent.classify_intent("Barang apa yang perlu restock?"), "restock")
        self.assertEqual(agent.classify_intent("Halo asisten toko!"), "sapaan_umum")

    def test_rbac_roles(self):
        role_owner = RBACManager.OWNER_ROLE
        role_public = RBACManager.PUBLIC_ROLE

        self.assertTrue(RBACManager.can_access_tool(role_owner, "get_daily_revenue"))
        self.assertFalse(RBACManager.can_access_tool(role_public, "get_daily_revenue"))

    def test_master_agent_handle_message(self):
        agent = MasterAgent()
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        response = loop.run_until_complete(agent.handle_message(user_id=1, message_text="halo asisten"))
        loop.close()
        
        self.assertIsInstance(response, str)
        self.assertTrue(len(response) > 0)

    def test_rag_vector_store(self):
        store = VectorStore()
        store.add_document({"name": "Minyak Goreng Bimoli 2L", "stock": 45, "unit": "btl"})
        store.add_document({"name": "Beras Premium 5kg", "stock": 20, "unit": "karung"})

        results = store.search("minyak bimoli", top_k=1)
        self.assertEqual(len(results), 1)
        doc, score = results[0]
        self.assertEqual(doc["name"], "Minyak Goreng Bimoli 2L")
        self.assertGreater(score, 0.0)

    def test_security_and_encryption(self):
        sec_agent = SecurityAgent()
        report = sec_agent.detect_anomalies("drop table products", user_id=123)
        self.assertTrue(report["is_suspicious"])
        self.assertEqual(report["action"], "block")

        phone = "081234567890"
        masked = SecurityEncryption.mask_phone_number(phone)
        self.assertEqual(masked, "0812****7890")
        hashed = SecurityEncryption.hash_phone_number(phone)
        self.assertEqual(len(hashed), 64)

    def test_hf_dataset_loader(self):
        rows = HFDatasetLoader.fetch_hf_dataset()
        self.assertIsInstance(rows, list)
        self.assertGreater(len(rows), 0)

if __name__ == "__main__":
    unittest.main()
