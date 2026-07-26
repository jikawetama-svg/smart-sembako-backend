from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Dict, Any, Optional, List

@dataclass
class ToolResult:
    success: bool
    data: Dict[str, Any]
    error: Optional[str] = None
    tokens_used: int = 0

class BaseTool(ABC):
    name: str
    description: str

    @abstractmethod
    async def execute(self, params: Dict[str, Any]) -> ToolResult:
        pass

class ToolRegistry:
    def __init__(self):
        self._tools: Dict[str, BaseTool] = {}

    def register(self, tool: BaseTool) -> None:
        self._tools[tool.name] = tool

    def get_tool(self, name: str) -> Optional[BaseTool]:
        return self._tools.get(name)

    def list_tools(self) -> List[Dict[str, str]]:
        return [
            {"name": tool.name, "description": tool.description}
            for tool in self._tools.values()
        ]

global_registry = ToolRegistry()
