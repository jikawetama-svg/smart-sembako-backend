import asyncio
from typing import Dict, Any, List
from tools.registry import ToolRegistry
from agents.planner import ExecutionPlan, AgentTask
from agents.specialized_agents import InventoryAgent, SalesAgent, OCRAgent, AnalyticsAgent, CustomerAgent
from telegram.rbac import RBACManager

class AgentSupervisor:
    """
    Agent Supervisor: Orchestrates execution of sub-tasks across specialized agents
    in parallel, ensuring RBAC security enforcement.
    """

    def __init__(self, registry: ToolRegistry):
        self.registry = registry
        self.inventory_agent = InventoryAgent(registry)
        self.sales_agent = SalesAgent(registry)
        self.ocr_agent = OCRAgent(registry)
        self.analytics_agent = AnalyticsAgent(registry)
        self.customer_agent = CustomerAgent(registry)

        self._agent_map = {
            "inventory": self.inventory_agent,
            "sales": self.sales_agent,
            "ocr": self.ocr_agent,
            "analytics": self.analytics_agent,
            "customer": self.customer_agent
        }

    async def execute_plan(self, plan: ExecutionPlan, user_role: str = "owner") -> Dict[str, Any]:
        results: Dict[str, Any] = {}
        async_tasks = []
        task_ids = []

        for task in plan.tasks:
            # Security RBAC check per tool
            if not RBACManager.can_access_tool(user_role, task.tool_name):
                results[task.task_id] = {
                    "success": False,
                    "error": f"Akses ditolak: Peran '{user_role}' tidak memiliki izin untuk tool '{task.tool_name}'"
                }
                continue

            agent = self._agent_map.get(task.target_agent)
            if not agent:
                results[task.task_id] = {
                    "success": False,
                    "error": f"Specialist Agent '{task.target_agent}' tidak dikenal"
                }
                continue

            async_tasks.append(agent.execute_task(task.tool_name, task.params))
            task_ids.append(task.task_id)

        if async_tasks:
            task_outputs = await asyncio.gather(*async_tasks, return_exceptions=True)
            for tid, out in zip(task_ids, task_outputs):
                if isinstance(out, Exception):
                    results[tid] = {"success": False, "error": str(out)}
                else:
                    results[tid] = out

        return results
