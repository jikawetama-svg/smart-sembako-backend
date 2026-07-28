import pytest
from fastapi.testclient import TestClient
from main import app
from config import settings
from agents.master_agent import MasterAgent
from tools.registry import ToolRegistry, ToolResult, BaseTool
from telegram.rbac import RBACManager
from model_manager.manager import ModelManager

client = TestClient(app)

def test_root_endpoint():
    response = client.get("/")
    assert response.status_code == 200
    data = response.json()
    assert data["version"] == "7.1.0"
    assert data["status"] == "healthy"

def test_health_endpoint():
    response = client.get("/bot-health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "healthy"

def test_webhook_invalid_secret_token():
    settings.TELEGRAM_SECRET_TOKEN = "valid-secret-123"
    response = client.post(
        "/webhook/telegram",
        headers={"X-Telegram-Bot-Api-Secret-Token": "wrong-secret"},
        json={"update_id": 1, "message": {"chat": {"id": 123}, "text": "stok minyak"}}
    )
    assert response.status_code == 403

def test_webhook_valid_secret_token():
    settings.TELEGRAM_SECRET_TOKEN = "valid-secret-123"
    response = client.post(
        "/webhook/telegram",
        headers={"X-Telegram-Bot-Api-Secret-Token": "valid-secret-123"},
        json={"update_id": 1, "message": {"chat": {"id": 123}, "text": "halo"}}
    )
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "success"
    assert data["chat_id"] == 123

def test_intent_classification():
    agent = MasterAgent()
    assert agent.classify_intent("Berapa stok minyak goreng?") == "cek_stok"
    assert agent.classify_intent("Berapa omset hari ini?") == "laporan_penjualan"
    assert agent.classify_intent("Barang apa yang perlu restock?") == "restock_rekomendasi"
    assert agent.classify_intent("stok kritis") == "restock_rekomendasi"
    assert agent.classify_intent("restock kapal api mix") == "cloud_input_restock"
    assert agent.classify_intent("/inventory kapal api mix 130") == "cloud_input_inventory"
    assert agent.classify_intent("/confirm") == "cloud_local_command"
    assert agent.classify_intent("Gimana caranya meningkatkan penjualan?") == "strategi_penjualan"
    assert agent.classify_intent("Halo asisten toko!") == "sapaan_umum"

def test_rbac_access():
    role_owner = RBACManager.OWNER_ROLE
    role_public = RBACManager.PUBLIC_ROLE
    
    assert RBACManager.can_access_tool(role_owner, "get_daily_revenue") is True
    assert RBACManager.can_access_tool(role_public, "get_daily_revenue") is False

@pytest.mark.asyncio
async def test_master_agent_handle_message():
    agent = MasterAgent()
    response = await agent.handle_message(user_id=1, message_text="halo asisten")
    assert isinstance(response, str)
    assert len(response) > 0
