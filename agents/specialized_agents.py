from typing import Dict, Any, List, Optional
from tools.registry import BaseTool, ToolRegistry

class BaseSpecialistAgent:
    def __init__(self, registry: ToolRegistry):
        self.registry = registry

    async def execute_task(self, tool_name: str, params: dict) -> dict:
        tool = self.registry.get_tool(tool_name)
        if tool:
            res = await tool.execute(params)
            return {"success": res.success, "data": res.data, "error": res.error}
        return {"success": False, "error": f"Tool '{tool_name}' not found in registry"}


class InventoryAgent(BaseSpecialistAgent):
    """Specialist Agent for Inventory, Stock Search, and Low Stock Alerts."""
    pass

class SalesAgent(BaseSpecialistAgent):
    """Specialist Agent for Sales, Revenue, and Transaction Analytics."""
    pass

class OCRAgent(BaseSpecialistAgent):
    """Specialist Agent for Struk/Receipt Image OCR Processing."""
    pass

class AnalyticsAgent(BaseSpecialistAgent):
    """Specialist Agent for Financial, Restock Prediction, and Profit Analysis."""
    pass

class CustomerAgent(BaseSpecialistAgent):
    """Specialist Agent for Customer Debt and Receivable Analytics."""
    pass
