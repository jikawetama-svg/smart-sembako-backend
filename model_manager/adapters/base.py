from abc import ABC, abstractmethod
from typing import List, Dict, Any, Tuple

class BaseModelAdapter(ABC):
    provider_name: str
    supports_vision: bool = False
    supports_streaming: bool = False

    @abstractmethod
    async def chat(
        self,
        messages: List[Dict[str, str]],
        max_tokens: int = 500,
        temperature: float = 0.7,
        **kwargs
    ) -> Tuple[str, int]:
        """
        Mengembalikan tuple (response_text, tokens_used)
        """
        pass

    @abstractmethod
    async def health_check(self) -> bool:
        """
        Memeriksa apakah API provider dapat diakses
        """
        pass
