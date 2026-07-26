from typing import Dict, Any, List
from tools.registry import BaseTool, ToolRegistry
from tools.inventory_tools import GetStockTool, FindProductTool, GetLowStockTool
from tools.sales_tools import GetDailyRevenueTool, GetTransactionSummaryTool, GetTopProductsTool
from tools.ocr_tools import ParseReceiptImageTool
from tools.forecast_tools import PredictRestockTool, RunProfitAnalysisTool

class InventoryAgent:
    """Specialist Agent for Inventory Management"""
    def __init__(self, registry: ToolRegistry):
        self.registry = registry

    async def run(self, action: str, params: dict) -> dict:
        tool = self.registry.get_tool(action)
        if tool:
            res = await tool.execute(params)
            return res.data
        return {"error": f"Unknown inventory action: {action}"}

class SalesAgent:
    """Specialist Agent for Sales and Revenue Analysis"""
    def __init__(self, registry: ToolRegistry):
        self.registry = registry

    async def run(self, action: str, params: dict) -> dict:
        tool = self.registry.get_tool(action)
        if tool:
            res = await tool.execute(params)
            return res.data
        return {"error": f"Unknown sales action: {action}"}

class OCRAgent:
    """Specialist Agent for Struk/Receipt OCR Parsing"""
    def __init__(self, registry: ToolRegistry):
        self.registry = registry

    async def run(self, params: dict) -> dict:
        tool = self.registry.get_tool("parse_receipt_image")
        if tool:
            res = await tool.execute(params)
            return res.data
        return {"error": "OCR tool not available"}

class AnalyticsAgent:
    """Specialist Agent for Financial & Predictive Analytics"""
    def __init__(self, registry: ToolRegistry):
        self.registry = registry

    async def run(self, action: str, params: dict) -> dict:
        tool = self.registry.get_tool(action)
        if tool:
            res = await tool.execute(params)
            return res.data
        return {"error": f"Unknown analytics action: {action}"}
